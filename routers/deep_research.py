import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from dependencies import get_session
from schemas import InterviewRequest, SchemaAgreementRequest
from database import DeepResearchSession, SearchSession, ChatSession, ChatMessage, ExtractionSchema, Item, SearchItemLink
from llm_engine import deep_research_agent, generate_schema_proposal
from services import ProcessingService
from services.orchestrator import confirm_search_schema

# Важно: prefix="/api/deep_research"
router = APIRouter(prefix="/api/deep_research", tags=["deep_research"])
processing_service = ProcessingService()


def _get_or_create_search_session(db_session: Session, query: str) -> DeepResearchSession:
    """Получить или создать сессию глубокого исследования"""
    s = db_session.exec(
        select(DeepResearchSession).where(
            DeepResearchSession.status == "created"
        ).order_by(desc(DeepResearchSession.created_at))
    ).first()
    if not s:
        print("[DEBUG ORCH] Creating new Deep Research Session")
        s = DeepResearchSession(query_text=query, stage="interview", status="created", limit_count=10)
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
    return s


def _get_or_create_chat_session(db_session: Session, research_session: DeepResearchSession) -> ChatSession:
    """Получить или создать сессию чата, связанную с сессией глубокого исследования"""
    # Проверяем, есть ли уже связанная чат-сессия
    if research_session.chat_session_id:
        c = db_session.get(ChatSession, research_session.chat_session_id)
        if c:
            return c

    # Создаем новую чат-сессию
    title = f"Глубокое исследование: {research_session.query_text[:30]}..."
    c = ChatSession(title=title)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    # Связываем сессии
    research_session.chat_session_id = c.id
    db_session.add(research_session)
    db_session.commit()

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

    # Получаем или создаем сессию глубокого исследования
    research_session = _get_or_create_search_session(session, user_content)
    print(f"[INFO] Deep research session created/retrieved: ID {research_session.id}, stage: {research_session.stage}")

    # Получаем или создаем связанную чат-сессию
    chat_session = _get_or_create_chat_session(session, research_session)
    print(f"[INFO] Chat session created/retrieved: ID {chat_session.id}")

    _save_message(session, chat_session.id, "user", user_content, {"stage": research_session.stage})
    print("[INFO] User message saved to chat session")

    # Подготовка состояния для агента
    current_state = {
        "stage": research_session.stage,
        "query_text": research_session.query_text,
        "interview_data": research_session.interview_data,
        "schema_agreed": research_session.schema_agreed
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
                # Выводим только краткую информацию о схеме, без подробных описаний
                schema_info = {
                    "fields_count": len(schema_result.get("schema", {})),
                    "search_query": schema_result.get("search_query", "")
                }
                print(f"[INFO] Schema proposal generated: {schema_info}")

                # Сохраняем предложенную схему
                research_session.schema_agreed = json.dumps(schema_result["schema"], ensure_ascii=False)
                research_session.stage = "schema_proposed"
                session.add(research_session)
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
                    "research_id": research_session.id
                }

            elif function_name == "proceed_to_search":
                print("[INFO] Executing proceed_to_search tool call")
                # Подтверждение схемы и переход к поиску
                success = await confirm_search_schema(research_session.id, arguments["schema"], session)
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
                        "research_id": research_session.id,
                        "stage": "parsing"
                    }
                else:
                    print("[WARNING] Failed to confirm schema")
                    return {
                        "type": "error",
                        "message": "Не удалось подтвердить схему",
                        "research_id": research_session.id,
                        "stage": research_session.stage
                    }
            else:
                print(f"[WARNING] Unknown tool function called: {function_name}")
                # Обработка неизвестного инструмента - возвращаем ошибку
                return {
                    "type": "error",
                    "message": f"Неизвестный инструмент: {function_name}",
                    "research_id": research_session.id,
                    "stage": research_session.stage
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
            {"stage": research_session.stage, "type": "chat_response"}
        )
        print("[INFO] Assistant chat message saved")

        return {
            "type": "chat",
            "message": response["message"],
            "stage": research_session.stage,
            "research_id": research_session.id
        }


# Удаляем endpoint для отдельного согласования схемы,
# так как теперь это часть основного потока
# @router.post("/schema_agreement")
# async def schema_agreement(...)

@router.post("/start_parsing")
async def start_parsing(research_id: int, session: Session = Depends(get_session)):
    """Ручной запуск парсинга (если нужно)"""
    # Получаем сессию глубокого исследования
    from fastapi import HTTPException
    research_session = session.get(DeepResearchSession, research_id)
    if not research_session:
        raise HTTPException(status_code=404, detail="Research session not found")

    # Запускаем процесс парсинга
    research_session.status = "processing"
    research_session.stage = "parsing"
    session.add(research_session)
    session.commit()

    # Запускаем обработку данных
    processing_service = ProcessingService()
    await processing_service.process_incoming_data(research_id, [], is_deep_analysis=True)

    return {"status": "started", "research_id": research_id}

@router.get("/status/{research_id}")
def get_research_status(research_id: int, session: Session = Depends(get_session)):
    research_session = session.get(DeepResearchSession, research_id)
    if not research_session:
        raise HTTPException(status_code=404)

    return {
        "status": research_session.status,
        "stage": research_session.stage,
        "summary": research_session.summary
    }

@router.get("/items/{research_id}")
def get_research_items(research_id: int, session: Session = Depends(get_session)):
    # Получаем элементы, связанные с сессией глубокого исследования
    # В текущей архитектуре элементы связаны с SearchSession через SearchItemLink
    # Сначала находим все связанные SearchSession
    search_sessions = session.exec(
        select(SearchSession.id).where(SearchSession.deep_research_session_id == research_id)
    ).all()

    items = []
    if search_sessions:
        # search_sessions содержит список ID (int), а не объекты
        search_ids = [s for s in search_sessions]
        if search_ids:  # Проверяем, что список не пустой
            items = session.exec(
                select(Item)
                .join(SearchItemLink)
                .where(SearchItemLink.search_id.in_(search_ids))
            ).all()

    # В альтернативной реализации, если элементы могут быть связаны напрямую с DeepResearchSession,
    # нужно добавить дополнительную логику. Но в текущей модели такой связи нет.
    # Поэтому возвращаем только те элементы, которые связаны через SearchSession

    res = []
    for i in items:
        d = i.model_dump()
        if i.image_path:
            p = i.image_path.replace('\\', '/')
            d["image_url"] = f"/images/{p.split('images/')[-1]}"
        res.append(d)
    return res

@router.post("/execute_analysis")
async def execute_analysis(research_id: int, session: Session = Depends(get_session)):
    research_session = session.get(DeepResearchSession, research_id)
    if not research_session:
        raise HTTPException(status_code=404)

    research_session.stage = "analysis"
    research_session.status = "processing"
    session.add(research_session)
    session.commit()

    # Запускаем анализ
    await processing_service.process_incoming_data(research_id, [], is_deep_analysis=True)

    return {"status": "completed", "stage": "completed"}