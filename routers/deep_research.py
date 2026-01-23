import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from dependencies import get_session
from schemas import InterviewRequest, SchemaAgreementRequest
from database import SearchSession, ChatSession, ChatMessage, ExtractionSchema
from llm_engine import deep_research_agent, generate_schema_proposal
from services import ProcessingService
from services.orchestrator import confirm_search_schema

# Важно: prefix="/api/deep_research"
router = APIRouter(prefix="/api/deep_research", tags=["deep_research"])
processing_service = ProcessingService()


def _get_or_create_search_session(db_session: Session, query: str) -> SearchSession:
    """Получить или создать сессию поиска"""
    s = db_session.exec(
        select(SearchSession).where(
            SearchSession.mode == "deep",
            SearchSession.status == "created"
        ).order_by(desc(SearchSession.created_at))
    ).first()
    if not s:
        print("[DEBUG ORCH] Creating new Deep Session")
        s = SearchSession(query_text=query, mode="deep", stage="interview", status="created", limit_count=10)
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
    return s


def _get_or_create_chat_session(db_session: Session, search_id: int) -> ChatSession:
    """Получить или создать сессию чата"""
    title = f"Deep Research Chat - {search_id}"
    c = db_session.exec(
        select(ChatSession).where(ChatSession.title.contains(str(search_id)))
    ).first()
    if not c:
        c = ChatSession(title=title)
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
    return c


def _save_message(db_session: Session, chat_id: int, role: str, content: str, meta: dict):
    """Сохранить сообщение"""
    from datetime import datetime
    msg = ChatMessage(
        role=role,
        content=content,
        chat_session_id=chat_id,
        timestamp=datetime.now(),
        extra_metadata=json.dumps(meta, ensure_ascii=False)
    )
    db_session.add(msg)
    db_session.commit()




@router.post("/chat")
async def deep_research_chat_endpoint(
    req: InterviewRequest,
    session: Session = Depends(get_session)
):
    print(f"\n[API] Deep Research Chat received: {req.history[-1]['content'] if req.history else 'No content'}")

    user_content = req.history[-1]['content'] if req.history else ""
    if not user_content:
        print("[WARNING] Received empty message")
        raise HTTPException(status_code=400, detail="Empty message")

    # Получаем или создаем сессию
    search_session = _get_or_create_search_session(session, user_content)
    print(f"[INFO] Search session created/retrieved: ID {search_session.id}, stage: {search_session.stage}")

    chat_session = _get_or_create_chat_session(session, search_session.id)
    print(f"[INFO] Chat session created/retrieved: ID {chat_session.id}")

    _save_message(session, chat_session.id, "user", user_content, {"stage": search_session.stage})
    print("[INFO] User message saved to chat session")

    # Подготовка состояния для агента
    current_state = {
        "stage": search_session.stage,
        "query_text": search_session.query_text,
        "interview_data": search_session.interview_data,
        "schema_agreed": search_session.schema_agreed
    }
    print(f"[INFO] Current state prepared: {current_state}")

    # Вызов универсального агента
    print("[INFO] Calling deep_research_agent...")
    response = await deep_research_agent(req.history, current_state)
    print(f"[INFO] Agent response received: type={response['type']}, has_tool_calls={bool(response.get('tool_calls'))}")

    # Обработка результата
    if response["type"] == "tool_call":
        print(f"[INFO] Processing tool calls: {len(response['tool_calls'])} calls")
        # Обработка вызова инструментов
        for tool_call in response["tool_calls"]:
            function_name = tool_call["name"]
            arguments = tool_call["arguments"]
            print(f"[INFO] Processing tool call: {function_name}")

            if function_name == "propose_schema":
                print("[INFO] Executing propose_schema tool call")
                schema_result = await generate_schema_proposal(arguments["criteria"])
                print(f"[INFO] Schema proposal generated: {schema_result}")

                # Сохраняем предложенную схему
                search_session.schema_agreed = json.dumps(schema_result["schema"], ensure_ascii=False)
                search_session.stage = "schema_proposed"
                session.add(search_session)
                session.commit()
                print("[INFO] Schema saved and session updated")

                # Сохраняем сообщение с предложенной схемой
                _save_message(
                    session,
                    chat_session.id,
                    "assistant",
                    f"Я предлагаю следующую схему извлечения данных: {json.dumps(schema_result['schema'], ensure_ascii=False, indent=2)}",
                    {"stage": "schema_proposed", "schema_proposal": schema_result["schema"]}
                )
                print("[INFO] Assistant message with schema proposal saved")

                return {
                    "type": "schema_proposal",
                    "message": f"Я предлагаю следующую схему извлечения данных: {json.dumps(schema_result['schema'], ensure_ascii=False, indent=2)}",
                    "schema_proposal": schema_result["schema"],
                    "stage": "schema_proposed",
                    "search_id": search_session.id
                }

            elif function_name == "proceed_to_search":
                print("[INFO] Executing proceed_to_search tool call")
                # Подтверждение схемы и переход к поиску
                success = await confirm_search_schema(search_session.id, arguments["schema"], session)
                print(f"[INFO] Schema confirmation result: {success}")

                if success:
                    # Сохраняем сообщение о начале поиска
                    _save_message(
                        session,
                        chat_session.id,
                        "assistant",
                        "Схема подтверждена! Начинаю сбор данных...",
                        {"stage": "parsing", "action": "search_started"}
                    )
                    print("[INFO] Assistant message with search start saved")

                    return {
                        "type": "search_started",
                        "message": "Схема подтверждена! Начинаю сбор данных...",
                        "search_id": search_session.id,
                        "stage": "parsing"
                    }
                else:
                    print("[WARNING] Failed to confirm schema")
                    return {
                        "type": "error",
                        "message": "Не удалось подтвердить схему",
                        "search_id": search_session.id,
                        "stage": search_session.stage
                    }
            else:
                print(f"[WARNING] Unknown tool function called: {function_name}")
                # Обработка неизвестного инструмента - возвращаем ошибку
                return {
                    "type": "error",
                    "message": f"Неизвестный инструмент: {function_name}",
                    "search_id": search_session.id,
                    "stage": search_session.stage
                }
    else:
        print("[INFO] Processing simple chat response")
        # Простой текстовый ответ
        # Сохраняем сообщение от ассистента
        _save_message(
            session,
            chat_session.id,
            "assistant",
            response["message"],
            {"stage": search_session.stage, "type": "chat_response"}
        )
        print("[INFO] Assistant chat message saved")

        return {
            "type": "chat",
            "message": response["message"],
            "stage": search_session.stage,
            "search_id": search_session.id
        }


# Удаляем endpoint для отдельного согласования схемы,
# так как теперь это часть основного потока
# @router.post("/schema_agreement")
# async def schema_agreement(...)

@router.post("/start_parsing")
async def start_parsing(search_id: int, session: Session = Depends(get_session)):
    """Ручной запуск парсинга (если нужно)"""
    return {"status": "started"}

@router.post("/execute_analysis")
async def execute_analysis(search_id: int, session: Session = Depends(get_session)):
    search_session = session.get(SearchSession, search_id)
    if not search_session:
        raise HTTPException(status_code=404)

    search_session.stage = "analysis"
    search_session.status = "processing"
    session.add(search_session)
    session.commit()

    # Запускаем анализ
    await processing_service.process_incoming_data(search_id, [], is_deep_analysis=True)

    return {"status": "completed", "stage": "completed"}