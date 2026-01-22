import os, json
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, desc
from pydantic import BaseModel
from contextlib import asynccontextmanager
from datetime import datetime

from database import create_db_and_tables, engine, SearchSession, ExtractionSchema, Item, SearchItemLink, ChatSession, ChatMessage
from services import ProcessingService, ChatProcessingService
from image_utils import save_base64_image
from llm_engine import decide_action, generate_schema_structure, conduct_interview, conduct_interview_basic, generate_schema_proposal, generate_sql_query

class ItemSchema(BaseModel):
    title: str; price: str; url: str; description: Optional[str] = None; image_base64: Optional[str] = None; local_path: Optional[str] = None 

class SubmitData(BaseModel):
    task_id: int; items: List[ItemSchema]

class ChatRequest(BaseModel):
    history: List[Dict[str, Any]]; open_browser: bool = True; use_cache: bool = True

class LogMessage(BaseModel):
    source: str; message: str; level: str = "info"

class InterviewRequest(BaseModel):
    history: List[Dict[str, Any]]

class SchemaAgreementRequest(BaseModel):
    search_id: int
    agreed_schema: str

class ChatSchemaAgreementRequest(BaseModel):
    search_id: int
    agreed_schema: str
    history: list

class SqlGenerationRequest(BaseModel):
    search_id: int
    criteria: str

class DeepResearchRequest(BaseModel):
    history: List[Dict[str, Any]]
    agreed_schema: Optional[str] = None  # Used when confirming schema agreement

service = ProcessingService()
templates = Jinja2Templates(directory="templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- SERVER STARTUP ---")
    create_db_and_tables()
    os.makedirs("images", exist_ok=True)
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/images", StaticFiles(directory="images"), name="images")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    with Session(engine) as session:
        schemas = session.exec(select(ExtractionSchema)).all()
    return templates.TemplateResponse("index.html", {"request": request, "schemas": schemas})

@app.get("/deep_research", response_class=HTMLResponse)
async def deep_research(request: Request):
    return templates.TemplateResponse("deep_research.html", {"request": request})

@app.get("/chat_history", response_class=HTMLResponse)
async def chat_history(request: Request):
    return templates.TemplateResponse("chat_history.html", {"request": request})

@app.post("/api/agent/chat")
async def agent_chat(req: ChatRequest):
    print(f"\n[API] Chat Request: {req.history[-1]['content']}")

    with Session(engine) as session:
        # Create a new chat session for this interaction
        chat_session = ChatSession(title=req.history[-1]['content'][:50] + "..." if len(req.history[-1]['content']) > 50 else req.history[-1]['content'])
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)

        # Add user message to the chat session
        user_message = ChatMessage(
            role="user",
            content=req.history[-1]['content'],
            message_type="user_request",
            extra_metadata=json.dumps({"chat_type": "search"}),
            chat_session_id=chat_session.id
        )
        session.add(user_message)
        session.commit()

        # Используем новый сервисный слой для обработки сообщения
        chat_service = ChatProcessingService()
        result = await chat_service.process_user_message(
            user_message=req.history[-1]['content'],
            chat_history=req.history,
            use_cache=req.use_cache,
            open_browser=req.open_browser
        )

        decision = result["decision"]

        if decision.get("action") == "chat":
            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content=decision.get("reply", ""),
                message_type="chat_response",
                extra_metadata=json.dumps({
                    "reasoning": decision.get("reasoning", ""),
                    "internal_thoughts": decision.get("internal_thoughts", ""),
                    "plan": decision
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            return {
                "type": "chat",
                "message": decision.get("reply"),
                "plan": decision,
                "reasoning": decision.get("reasoning", ""),
                "internal_thoughts": decision.get("internal_thoughts", "")
            }

        elif decision.get("action") == "search":
            query = decision.get("search_query") or "Товар"
            if req.use_cache:
                existing = session.exec(select(SearchSession).where(SearchSession.query_text == query, SearchSession.status == "done", SearchSession.summary != None).order_by(desc(SearchSession.created_at))).first()
                if existing:
                    new_req = SearchSession(
                        query_text=query,
                        schema_id=existing.schema_id,
                        status="done",
                        open_in_browser=False,
                        use_cache=True,
                        summary=existing.summary,
                        reasoning=existing.reasoning,
                        internal_thoughts=existing.internal_thoughts
                    )
                    session.add(new_req); session.commit(); session.refresh(new_req)
                    for item in existing.items: session.add(SearchItemLink(search_id=new_req.id, item_id=item.id))
                    session.commit()

                    # Add assistant response to the chat session
                    assistant_message = ChatMessage(
                        role="assistant",
                        content="Найдено в кэше",
                        message_type="search_response",
                        extra_metadata=json.dumps({
                            "reasoning": existing.reasoning,
                            "internal_thoughts": existing.internal_thoughts,
                            "task_id": new_req.id,
                            "plan": decision
                        }),
                        chat_session_id=chat_session.id
                    )
                    session.add(assistant_message)
                    session.commit()

                    return {
                        "type": "search",
                        "message": "Найдено в кэше",
                        "task_id": new_req.id,
                        "plan": decision,
                        "reasoning": existing.reasoning,
                        "internal_thoughts": existing.internal_thoughts
                    }

            schema_name = decision.get("schema_name") or "General"
            target_schema = next((s for s in session.exec(select(ExtractionSchema)).all() if s.name.lower() == schema_name.lower()), None)
            if not target_schema:
                new_struct_result = await generate_schema_structure(schema_name)
                new_struct = new_struct_result["schema"]
                target_schema = ExtractionSchema(name=schema_name, description="Auto", structure_json=new_struct)
                session.add(target_schema); session.commit(); session.refresh(target_schema)

            # Создаем задачу поиска только после подтверждения, что это действительно запрос поиска
            task_info = await chat_service.create_search_task_if_confirmed(
                decision=decision,
                schema_id=target_schema.id,
                chat_session_id=chat_session.id,
                limit=decision.get("limit", 5),
                open_in_browser=req.open_browser
            )

            if task_info:
                # Add assistant response to the chat session
                assistant_message = ChatMessage(
                    role="assistant",
                    content=f"Запускаю поиск",
                    message_type="search_initiated",
                    extra_metadata=json.dumps({
                        "reasoning": decision.get("reasoning", ""),
                        "internal_thoughts": decision.get("internal_thoughts", ""),
                        "task_id": task_info["task_id"],
                        "plan": decision
                    }),
                    chat_session_id=chat_session.id
                )
                session.add(assistant_message)
                session.commit()

                return {
                    "type": "search",
                    "message": f"Запускаю поиск",
                    "task_id": task_info["task_id"],
                    "plan": decision,
                    "reasoning": decision.get("reasoning", ""),
                    "internal_thoughts": decision.get("internal_thoughts", "")
                }
            else:
                # Если задача не создана, возвращаем обычный ответ
                assistant_message = ChatMessage(
                    role="assistant",
                    content=decision.get("reply", ""),
                    message_type="chat_response",
                    extra_metadata=json.dumps({
                        "reasoning": decision.get("reasoning", ""),
                        "internal_thoughts": decision.get("internal_thoughts", ""),
                        "plan": decision
                    }),
                    chat_session_id=chat_session.id
                )
                session.add(assistant_message)
                session.commit()

                return {
                    "type": "chat",
                    "message": decision.get("reply"),
                    "plan": decision,
                    "reasoning": decision.get("reasoning", ""),
                    "internal_thoughts": decision.get("internal_thoughts", "")
                }
    return {"type": "error", "message": "Ошибка"}

# Обновим эндпоинт для глубокого исследования, чтобы он использовал ту же логику
@app.post("/api/deep_research/chat")
async def deep_research_chat(req: DeepResearchRequest):
    print(f"\n[API] Deep Research Request: {req.history[-1]['content']}")

    with Session(engine) as session:
        # Find or create a deep research session
        existing_session = session.exec(
            select(SearchSession).where(
                SearchSession.mode == "deep",
                SearchSession.stage == "interview",
                SearchSession.status == "created"
            ).order_by(desc(SearchSession.created_at))
        ).first()

        if not existing_session:
            # Create a new deep research session
            new_session = SearchSession(
                query_text=req.history[-1]['content'] if req.history else "Deep Research Query",
                mode="deep",
                stage="interview",
                status="created",
                limit_count=200  # Default for deep research
            )
            session.add(new_session)
            session.commit()
            session.refresh(new_session)
            search_session = new_session
        else:
            search_session = existing_session

        # Add user message to the associated chat session
        chat_sessions = session.exec(
            select(ChatSession).where(ChatSession.title.contains(str(search_session.id)))
        ).all()
        if chat_sessions:
            chat_session = chat_sessions[0]
        else:
            chat_session = ChatSession(title=f"Deep Research Chat - {search_session.id}")
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)

        user_message = ChatMessage(
            role="user",
            content=req.history[-1]['content'],
            message_type="user_request",
            extra_metadata=json.dumps({"research_stage": search_session.stage}),
            chat_session_id=chat_session.id
        )
        session.add(user_message)
        session.commit()

        # Process the message based on the current stage
        if search_session.stage == "interview":
            # Conduct interview to gather requirements
            interview_result = await conduct_interview(req.history)

            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content=interview_result.get("reply", ""),
                message_type="interview_question",
                extra_metadata=json.dumps({
                    "stage": "interview",
                    "interview_data": interview_result.get("interview_data", {}),
                    "needs_schema": interview_result.get("needs_schema", False)
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            # If interview is complete, move to schema agreement stage
            if interview_result.get("complete"):
                search_session.stage = "schema_agreement"
                search_session.interview_data = json.dumps(interview_result.get("interview_data", {}))
                session.add(search_session)
                session.commit()

            return {
                "type": "interview",
                "message": interview_result.get("reply", ""),
                "stage": "interview",
                "interview_data": interview_result.get("interview_data", {}),
                "needs_schema": interview_result.get("needs_schema", False),
                "complete": interview_result.get("complete", False)
            }
        elif search_session.stage == "schema_agreement":
            # Handle schema agreement
            schema_proposal = await generate_schema_proposal(
                json.loads(search_session.interview_data) if search_session.interview_data else {}
            )

            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content=schema_proposal.get("reply", ""),
                message_type="schema_proposal",
                extra_metadata=json.dumps({
                    "stage": "schema_agreement",
                    "proposed_schema": schema_proposal.get("schema", {}),
                    "sql_query": schema_proposal.get("sql_query", "")
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            return {
                "type": "schema_proposal",
                "message": schema_proposal.get("reply", ""),
                "stage": "schema_agreement",
                "proposed_schema": schema_proposal.get("schema", {}),
                "sql_query": schema_proposal.get("sql_query", "")
            }
        elif search_session.stage == "parsing":
            # This stage means the schema has been agreed upon and we're ready to parse
            # Create the agreed schema in the database
            schema_name = f"DeepResearch_{search_session.id}"
            existing_schema = session.exec(
                select(ExtractionSchema).where(ExtractionSchema.name == schema_name)
            ).first()

            if existing_schema:
                existing_schema.structure_json = req.agreed_schema
            else:
                new_schema = ExtractionSchema(
                    name=schema_name,
                    description=f"Auto-generated schema for deep research session {search_session.id}",
                    structure_json=req.agreed_schema
                )
                session.add(new_schema)

            # Update session status to confirmed so extension can pick it up
            search_session.schema_agreed = json.dumps(req.agreed_schema, ensure_ascii=False)
            search_session.stage = "parsing"
            search_session.status = "confirmed"  # Changed to "confirmed" so extension can pick it up

            session.commit()

            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content="Начинаю парсинг данных",
                message_type="parsing_started",
                extra_metadata=json.dumps({
                    "stage": "parsing",
                    "task_id": search_session.id
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            return {
                "type": "parsing",
                "message": "Начинаю парсинг данных",
                "stage": "parsing",
                "task_id": search_session.id
            }
        else:
            return {"type": "error", "message": "Invalid research stage"}

@app.get("/api/searches/{search_id}/status")
def get_search_status(search_id: int):
    with Session(engine) as session:
        req = session.get(SearchSession, search_id)
        # УБРАЛ ЛИШНИЕ ПРИНТЫ
        if req:
            return {
                "status": req.status,
                "summary": req.summary,
                "reasoning": req.reasoning,
                "internal_thoughts": req.internal_thoughts
            }
        else:
            return {"status": "not_found", "summary": None, "reasoning": None, "internal_thoughts": None}

@app.get("/api/get_task")
def get_task():
    with Session(engine) as session:
        # Теперь ищем задачи со статусом "confirmed", а не "pending" или "created"
        # чтобы избежать преждевременной обработки задач, которые еще не подтверждены ИИ
        task = session.exec(select(SearchSession).where(SearchSession.status == "confirmed").limit(1)).first()
        if task:
            task.status = "processing"
            session.add(task); session.commit()
            print(f"[API] Task #{task.id} picked up")
            return {
                "task_id": task.id,
                "query": task.query_text,
                "active_tab": task.open_in_browser,
                "limit": task.limit_count,
                "reasoning": task.reasoning,
                "internal_thoughts": task.internal_thoughts
            }
    return {"task_id": None}

@app.post("/api/submit_results")
async def submit_results(data: SubmitData):
    print(f"[API] Results received for Task #{data.task_id}")
    processed = []
    for idx, item in enumerate(data.items):
        path = save_base64_image(item.image_base64, data.task_id, idx, item.url)
        item.local_path = path; item.image_base64 = None; processed.append(item)

    # Получаем сессию поиска для получения рассуждений
    with Session(engine) as session:
        search_session = session.get(SearchSession, data.task_id)
        reasoning = search_session.reasoning if search_session else None
        internal_thoughts = search_session.internal_thoughts if search_session else None

    await service.process_incoming_data(data.task_id, processed)

    return {
        "status": "ok",
        "reasoning": reasoning,
        "internal_thoughts": internal_thoughts
    }

@app.get("/api/schemas")
def get_schemas():
    with Session(engine) as session:
        schemas = session.exec(select(ExtractionSchema)).all()
        # Возвращаем схемы с дополнительной информацией о последних сессиях
        result = []
        for schema in schemas:
            # Получаем последнюю сессию, связанную с этой схемой
            last_session = session.exec(
                select(SearchSession)
                .where(SearchSession.schema_id == schema.id)
                .order_by(desc(SearchSession.created_at))
                .limit(1)
            ).first()

            schema_dict = schema.model_dump()
            if last_session:
                schema_dict["last_reasoning"] = last_session.reasoning
                schema_dict["last_internal_thoughts"] = last_session.internal_thoughts
            else:
                schema_dict["last_reasoning"] = None
                schema_dict["last_internal_thoughts"] = None

            result.append(schema_dict)
        return result

@app.get("/api/searches/{search_id}/items")
def get_search_items(search_id: int):
    with Session(engine) as session:
        # Получаем товары, связанные с сессией поиска
        items = session.exec(select(Item).join(SearchItemLink).where(SearchItemLink.search_id == search_id)).all()

        # Получаем сессию поиска для получения рассуждений
        search_session = session.get(SearchSession, search_id)

        res = []
        for i in items:
            d = i.model_dump()
            if i.image_path:
                p = i.image_path.replace('\\', '/')
                rel = p.split('images/')[-1] if 'images/' in p else p
                d["image_url"] = f"/images/{rel}"

            # Добавляем рассуждения и внутренние мысли из сессии поиска (если доступны)
            # В реальной реализации, каждому товару могут быть присвоены свои рассуждения
            # Но в текущей структуре данных они хранятся на уровне сессии
            if search_session:
                d["reasoning"] = search_session.reasoning
                d["internal_thoughts"] = search_session.internal_thoughts

            res.append(d)
        return res

@app.post("/api/log")
def remote_log(log: LogMessage):
    # В зависимости от типа лога, можем возвращать различные данные
    if log.level == "debug_detailed":
        # Возвращаем информацию о рассуждениях и внутренних мыслях
        return {
            "status": "ok",
            "reasoning": "Лог получен и обработан",
            "internal_thoughts": f"Обработка лога от {log.source} уровня {log.level}: {log.message}"
        }
    else:
        return {"status": "ok"}

def detect_schema_confirmation(user_input: str) -> dict:
    """Detect if user is confirming the schema in natural language"""
    user_input_lower = user_input.lower().strip()

    confirmation_keywords = [
        'подтверждаю', 'подтвердить', 'да', 'верно', 'согласен', 'ok', 'okay',
        'принято', 'угу', 'давай', 'согласен', 'подходит', 'хорошо'
    ]

    # Check if input contains confirmation keywords but not modification keywords
    confirmation_found = any(keyword in user_input_lower for keyword in confirmation_keywords)

    modification_keywords = [
        'изменить', 'поменять', 'редактировать', 'не подходит', 'нужно изменить',
        'другое', 'не согласен', 'передумал', 'назад', 'отмена'
    ]

    modification_found = any(keyword in user_input_lower for keyword in modification_keywords)

    result = confirmation_found and not modification_found

    # Возвращаем результат с объяснением
    return {
        "result": result,
        "reasoning": f"Подтверждение найдено: {confirmation_found}, Изменение найдено: {modification_found}",
        "internal_thoughts": f"Анализирую ввод пользователя '{user_input}' на предмет подтверждения схемы. Подходящие ключевые слова: {confirmation_found}, Ключевые слова на изменение: {modification_found}"
    }

@app.post("/api/deep_research/interview")
async def deep_research_interview(req: InterviewRequest):
    """Endpoint for conducting the interview phase of deep research"""
    print(f"\n[API] Deep Research Interview Request: {req.history[-1]['content'] if req.history else 'No history'}")

    # Create a new search session in deep mode
    with Session(engine) as session:
        # Find existing session in interview stage or create new one
        existing_session = session.exec(
            select(SearchSession).where(
                SearchSession.mode == "deep",
                SearchSession.stage == "interview",
                SearchSession.status == "created"
            ).order_by(desc(SearchSession.created_at))
        ).first()

        if not existing_session:
            # Create a new deep research session
            new_session = SearchSession(
                query_text=req.history[-1]['content'] if req.history else "Deep Research Query",
                mode="deep",
                stage="interview",
                status="created",
                limit_count=200  # Default for deep research
            )
            session.add(new_session)
            session.commit()
            session.refresh(new_session)
            search_session = new_session
        else:
            search_session = existing_session

        # Conduct the interview using LLM
        try:
            interview_response = await conduct_interview(req.history)
        except ConnectionError:
            # LLM is unavailable, return error message and stop the process
            return {
                "type": "interview",
                "message": "Нейросеть временно недоступна. Пожалуйста, повторите попытку позже.",
                "needs_more_info": False,
                "search_id": search_session.id,
                "stage": search_session.stage,
                "error": "llm_unavailable"
            }

        # Update session with interview data if needed
        if search_session.interview_data:
            try:
                interview_data = json.loads(search_session.interview_data)
            except json.JSONDecodeError:
                interview_data = {}
        else:
            interview_data = {}

        # Add the latest response to interview data
        interview_data[len(interview_data)] = {
            "question": req.history[-1]['content'] if req.history else "",
            "response": interview_response.get("response", ""),
            "needs_more_info": interview_response.get("needs_more_info", True),
            "reasoning": interview_response.get("reasoning", ""),
            "internal_thoughts": interview_response.get("internal_thoughts", "")
        }

        search_session.interview_data = json.dumps(interview_data, ensure_ascii=False)

        # Check if user is confirming schema in natural language
        if req.history and len(req.history) > 0:
            last_user_message = req.history[-1]
            if last_user_message.get("role") == "user":
                user_input = last_user_message.get("content", "")

                # Detect if user is confirming schema
                schema_confirmation_result = detect_schema_confirmation(user_input)
                if schema_confirmation_result["result"]:
                    # If we're in schema agreement stage, finalize it
                    if search_session.stage == "schema_agreement":
                        # Use the schema proposal from the last interview response if available
                        schema_proposal = interview_response.get("schema_proposal")

                        if not schema_proposal:
                            # Generate schema based on interview data if not in response
                            criteria_summary = ""
                            if search_session.interview_data:
                                try:
                                    interview_data = json.loads(search_session.interview_data)
                                    # Extract criteria from interview data
                                    for entry in interview_data.values():
                                        if "criteria_summary" in entry:
                                            criteria_summary = entry["criteria_summary"]
                                            break
                                        elif "response" in entry:
                                            criteria_summary += entry["response"] + " "
                                except:
                                    criteria_summary = "Пользователь хочет купить товар"

                            # Generate schema proposal
                            schema_proposal_result = await generate_schema_proposal(criteria_summary)
                            schema_proposal = schema_proposal_result["schema"]

                        # Update session stage to parsing
                        search_session.stage = "parsing"
                        search_session.schema_agreed = schema_proposal

                        session.add(search_session)
                        session.commit()

                        return {
                            "type": "schema_confirmed",
                            "message": "Схема подтверждена! Начинаю сбор данных...",
                            "search_id": search_session.id,
                            "stage": search_session.stage,
                            "reasoning": schema_confirmation_result["reasoning"],
                            "internal_thoughts": schema_confirmation_result["internal_thoughts"]
                        }

        # Move to next stage if enough info gathered
        if not interview_response.get("needs_more_info", True) and search_session.stage == "interview":
            search_session.stage = "schema_agreement"

        session.add(search_session)
        session.commit()

        # Prepare response based on whether schema was proposed
        response_data = {
            "type": "interview",
            "message": interview_response.get("response", ""),
            "reasoning": interview_response.get("reasoning", ""),
            "internal_thoughts": interview_response.get("internal_thoughts", ""),
            "needs_more_info": interview_response.get("needs_more_info", True),
            "search_id": search_session.id,
            "stage": search_session.stage
        }

        # Include schema proposal if provided in the response
        if interview_response.get("schema_proposal"):
            response_data["schema_proposal"] = interview_response["schema_proposal"]

        return response_data

@app.post("/api/deep_research/generate_schema_proposal")
async def deep_research_generate_schema_proposal(search_id: int):
    """Endpoint to generate schema proposal based on interview data"""
    with Session(engine) as session:
        search_session = session.get(SearchSession, search_id)
        if not search_session:
            raise HTTPException(status_code=404, detail="Search session not found")

        if search_session.mode != "deep":
            raise HTTPException(status_code=400, detail="Not a deep research session")

        # Generate schema based on interview data
        criteria_summary = ""
        if search_session.interview_data:
            try:
                interview_data = json.loads(search_session.interview_data)
                # Extract criteria from interview data
                for entry in interview_data.values():
                    if "criteria_summary" in entry:
                        criteria_summary = entry["criteria_summary"]
                        break
                    elif "response" in entry:
                        criteria_summary += entry["response"] + " "
            except:
                criteria_summary = "Пользователь хочет купить товар"

        schema_proposal_result = await generate_schema_proposal(criteria_summary)
        schema_proposal = schema_proposal_result["schema"]

        # Update session with reasoning and internal thoughts
        search_session.reasoning = schema_proposal_result["reasoning"]
        search_session.internal_thoughts = schema_proposal_result["internal_thoughts"]
        session.add(search_session)
        session.commit()

        return {
            "schema_proposal": schema_proposal,
            "reasoning": schema_proposal_result["reasoning"],
            "internal_thoughts": schema_proposal_result["internal_thoughts"],
            "search_id": search_session.id
        }

@app.post("/api/deep_research/schema_agreement")
async def deep_research_schema_agreement(req: SchemaAgreementRequest):
    """Endpoint for schema agreement phase of deep research"""
    with Session(engine) as session:
        search_session = session.get(SearchSession, req.search_id)
        if not search_session:
            raise HTTPException(status_code=404, detail="Search session not found")

        if search_session.mode != "deep":
            raise HTTPException(status_code=400, detail="Not a deep research session")

        # Update the agreed schema
        # Ensure req.agreed_schema is a string
        if isinstance(req.agreed_schema, dict):
            search_session.schema_agreed = json.dumps(req.agreed_schema, ensure_ascii=False)
        else:
            search_session.schema_agreed = req.agreed_schema
        search_session.stage = "parsing"
        search_session.status = "confirmed"  # Changed to "confirmed" so extension can pick it up

        # Create or update the extraction schema
        schema_name = f"DeepResearch_{search_session.id}"
        existing_schema = session.exec(
            select(ExtractionSchema).where(ExtractionSchema.name == schema_name)
        ).first()

        if existing_schema:
            existing_schema.structure_json = req.agreed_schema
            session.add(existing_schema)
        else:
            new_schema = ExtractionSchema(
                name=schema_name,
                description=f"Schema for deep research session {req.search_id}",
                structure_json=req.agreed_schema
            )
            session.add(new_schema)
            session.commit()
            session.refresh(new_schema)
            search_session.schema_id = new_schema.id

        session.add(search_session)
        session.commit()

        return {
            "status": "success",
            "message": "Schema agreed and saved",
            "next_stage": "parsing",
            "search_id": search_session.id
        }

@app.post("/api/deep_research/start_parsing")
async def deep_research_start_parsing(search_id: int):
    """Endpoint to start the parsing phase of deep research"""
    with Session(engine) as session:
        search_session = session.get(SearchSession, search_id)
        if not search_session:
            raise HTTPException(status_code=404, detail="Search session not found")

        if search_session.mode != "deep":
            raise HTTPException(status_code=400, detail="Not a deep research session")

        if search_session.stage != "parsing":
            raise HTTPException(status_code=400, detail="Invalid stage for parsing")

        # Update session to processing state
        search_session.status = "processing"
        session.add(search_session)
        session.commit()

        return {
            "status": "started",
            "message": "Parsing started",
            "search_id": search_session.id
        }

@app.post("/api/deep_research/generate_sql")
async def deep_research_generate_sql(req: SqlGenerationRequest):
    """Endpoint to generate SQL query for analysis phase"""
    with Session(engine) as session:
        search_session = session.get(SearchSession, req.search_id)
        if not search_session:
            raise HTTPException(status_code=404, detail="Search session not found")

        if search_session.mode != "deep":
            raise HTTPException(status_code=400, detail="Not a deep research session")

        # Generate SQL query based on criteria and agreed schema
        sql_query_result = await generate_sql_query(req.criteria, search_session.schema_agreed)
        sql_query = sql_query_result["sql_query"]

        # Update session with reasoning and internal thoughts
        search_session.reasoning = sql_query_result["reasoning"]
        search_session.internal_thoughts = sql_query_result["internal_thoughts"]
        session.add(search_session)
        session.commit()

        return {
            "sql_query": sql_query,
            "reasoning": sql_query_result["reasoning"],
            "internal_thoughts": sql_query_result["internal_thoughts"],
            "search_id": search_session.id
        }

@app.post("/api/deep_research/execute_analysis")
async def deep_research_execute_analysis(search_id: int):
    """Endpoint to execute the analysis phase"""
    with Session(engine) as session:
        search_session = session.get(SearchSession, search_id)
        if not search_session:
            raise HTTPException(status_code=404, detail="Search session not found")

        if search_session.mode != "deep":
            raise HTTPException(status_code=400, detail="Not a deep research session")

        # Move to analysis stage
        search_session.stage = "analysis"
        search_session.status = "processing"
        session.add(search_session)
        session.commit()

        # Process the items using the agreed schema
        await service.process_incoming_data(search_id, [], is_deep_analysis=True)

        # Update to completed stage
        search_session.stage = "completed"
        search_session.status = "done"
        session.add(search_session)
        session.commit()

        return {
            "status": "completed",
            "message": "Analysis completed",
            "search_id": search_session.id
        }

@app.post("/api/deep_research/chat")
async def deep_research_chat(req: InterviewRequest):
    """Universal endpoint for deep research chat that manages the entire process"""
    with Session(engine) as session:
        # Find existing session in any stage or create new one
        existing_session = session.exec(
            select(SearchSession).where(
                SearchSession.mode == "deep",
                SearchSession.status.in_(["created", "processing"])
            ).order_by(desc(SearchSession.created_at))
        ).first()

        if not existing_session:
            # Create a new deep research session
            new_session = SearchSession(
                query_text=req.history[-1]['content'] if req.history else "Deep Research Query",
                mode="deep",
                stage="interview",
                status="created",
                limit_count=200  # Default for deep research
            )
            session.add(new_session)
            session.commit()
            session.refresh(new_session)
            search_session = new_session
        else:
            search_session = existing_session

        # Create a new chat session for this interaction if it doesn't exist
        # Check if there's already a chat session associated with this search
        chat_session = session.exec(
            select(ChatSession).where(ChatSession.title.contains(str(search_session.id)))
        ).first()

        if not chat_session:
            chat_session = ChatSession(title=f"Deep Research Chat - {search_session.id}")
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)

        # Add user message to the chat session
        if req.history and len(req.history) > 0:
            last_user_message = req.history[-1]
            if last_user_message.get("role") == "user":
                user_message = ChatMessage(
                    role="user",
                    content=last_user_message.get("content", ""),
                    message_type="user_request",
                    extra_metadata=json.dumps({
                        "search_session_id": search_session.id,
                        "stage": search_session.stage,
                        "chat_type": "deep_research"
                    }),
                    chat_session_id=chat_session.id
                )
                session.add(user_message)
                session.commit()

        # Process based on current stage
        if search_session.stage == "interview":
            # Conduct the interview using LLM
            try:
                interview_response = await conduct_interview(req.history)
            except ConnectionError:
                # LLM is unavailable, return error message and stop the process
                # Add assistant response to the chat session
                assistant_message = ChatMessage(
                    role="assistant",
                    content="Нейросеть временно недоступна. Пожалуйста, повторите попытку позже.",
                    message_type="error_response",
                    extra_metadata=json.dumps({
                        "error": "llm_unavailable",
                        "search_id": search_session.id,
                        "stage": search_session.stage
                    }),
                    chat_session_id=chat_session.id
                )
                session.add(assistant_message)
                session.commit()

                return {
                    "type": "interview",
                    "message": "Нейросеть временно недоступна. Пожалуйста, повторите попытку позже.",
                    "needs_more_info": False,
                    "search_id": search_session.id,
                    "stage": search_session.stage,
                    "error": "llm_unavailable"
                }

            # Update session with interview data if needed
            if search_session.interview_data:
                try:
                    interview_data = json.loads(search_session.interview_data)
                except json.JSONDecodeError:
                    interview_data = {}
            else:
                interview_data = {}

            # Add the latest response to interview data
            interview_data[len(interview_data)] = {
                "question": req.history[-1]['content'] if req.history else "",
                "response": interview_response.get("response", ""),
                "needs_more_info": interview_response.get("needs_more_info", True),
                "reasoning": interview_response.get("reasoning", ""),
                "internal_thoughts": interview_response.get("internal_thoughts", "")
            }

            search_session.interview_data = json.dumps(interview_data, ensure_ascii=False)

            # Check if user is confirming schema in natural language
            if req.history and len(req.history) > 0:
                last_user_message = req.history[-1]
                if last_user_message.get("role") == "user":
                    user_input = last_user_message.get("content", "")

                    # Detect if user is confirming schema
                    schema_confirmation_result = detect_schema_confirmation(user_input)
                    if schema_confirmation_result["result"]:
                        # If we're in schema agreement stage, finalize it
                        if search_session.stage == "schema_agreement":
                            # Use the schema proposal from the last interview response if available
                            schema_proposal = interview_response.get("schema_proposal")

                            if not schema_proposal:
                                # Generate schema based on interview data if not in response
                                criteria_summary = ""
                                if search_session.interview_data:
                                    try:
                                        interview_data = json.loads(search_session.interview_data)
                                        # Extract criteria from interview data
                                        for entry in interview_data.values():
                                            if "criteria_summary" in entry:
                                                criteria_summary = entry["criteria_summary"]
                                                break
                                            elif "response" in entry:
                                                criteria_summary += entry["response"] + " "
                                    except:
                                        criteria_summary = "Пользователь хочет купить товар"

                                # Generate schema proposal
                                schema_proposal_result = await generate_schema_proposal(criteria_summary)
                                schema_proposal = schema_proposal_result["schema"]

                            # Update session stage to parsing
                            search_session.stage = "parsing"
                            # Ensure schema_proposal is a string
                            if isinstance(schema_proposal, dict):
                                search_session.schema_agreed = json.dumps(schema_proposal, ensure_ascii=False)
                            else:
                                search_session.schema_agreed = schema_proposal

                            session.add(search_session)
                            session.commit()

                            # Add assistant response to the chat session
                            assistant_message = ChatMessage(
                                role="assistant",
                                content="Схема подтверждена! Начинаю сбор данных...",
                                message_type="schema_confirmed",
                                extra_metadata=json.dumps({
                                    "search_id": search_session.id,
                                    "stage": search_session.stage,
                                    "reasoning": schema_confirmation_result["reasoning"],
                                    "internal_thoughts": schema_confirmation_result["internal_thoughts"]
                                }),
                                chat_session_id=chat_session.id
                            )
                            session.add(assistant_message)
                            session.commit()

                            return {
                                "type": "schema_confirmed",
                                "message": "Схема подтверждена! Начинаю сбор данных...",
                                "search_id": search_session.id,
                                "stage": search_session.stage,
                                "reasoning": schema_confirmation_result["reasoning"],
                                "internal_thoughts": schema_confirmation_result["internal_thoughts"]
                            }

            # Move to next stage if enough info gathered
            if not interview_response.get("needs_more_info", True) and search_session.stage == "interview":
                search_session.stage = "schema_agreement"

            session.add(search_session)
            session.commit()

            # Prepare response based on whether schema was proposed
            response_data = {
                "type": "interview",
                "message": interview_response.get("response", ""),
                "reasoning": interview_response.get("reasoning", ""),
                "internal_thoughts": interview_response.get("internal_thoughts", ""),
                "needs_more_info": interview_response.get("needs_more_info", True),
                "search_id": search_session.id,
                "stage": search_session.stage
            }

            # Include schema proposal if provided in the response
            if interview_response.get("schema_proposal"):
                response_data["schema_proposal"] = interview_response["schema_proposal"]
                # Also save it to the session for later use in schema agreement
                # Ensure schema_proposal is a string
                schema_proposal_value = interview_response["schema_proposal"]
                if isinstance(schema_proposal_value, dict):
                    search_session.schema_agreed = json.dumps(schema_proposal_value, ensure_ascii=False)
                else:
                    search_session.schema_agreed = schema_proposal_value
                session.add(search_session)
                session.commit()

            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content=response_data["message"],
                message_type="interview_response",
                extra_metadata=json.dumps({
                    "search_id": search_session.id,
                    "stage": search_session.stage,
                    "reasoning": response_data["reasoning"],
                    "internal_thoughts": response_data["internal_thoughts"],
                    "needs_more_info": response_data["needs_more_info"],
                    "schema_proposal": response_data.get("schema_proposal")
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            return response_data

        elif search_session.stage == "schema_agreement":
            # Handle schema agreement
            result = await deep_research_schema_agreement(SchemaAgreementRequest(
                search_id=search_session.id,
                agreed_schema=search_session.schema_agreed or "{}"
            ))

            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content=result.get("message", "Schema agreement processed"),
                message_type="schema_agreement_response",
                extra_metadata=json.dumps({
                    "search_id": search_session.id,
                    "result": result
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            return result

        elif search_session.stage == "parsing":
            # Handle parsing
            result = await deep_research_start_parsing(search_session.id)

            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content=result.get("message", "Parsing started"),
                message_type="parsing_response",
                extra_metadata=json.dumps({
                    "search_id": search_session.id,
                    "result": result
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            return result

        elif search_session.stage == "analysis":
            # Handle analysis
            result = await deep_research_execute_analysis(search_session.id)

            # Add assistant response to the chat session
            assistant_message = ChatMessage(
                role="assistant",
                content=result.get("message", "Analysis completed"),
                message_type="analysis_response",
                extra_metadata=json.dumps({
                    "search_id": search_session.id,
                    "result": result
                }),
                chat_session_id=chat_session.id
            )
            session.add(assistant_message)
            session.commit()

            return result

        else:
            # Unknown stage
            raise HTTPException(status_code=400, detail=f"Unknown stage: {search_session.stage}")


@app.get("/api/chats")
def get_all_chats():
    """Get all chat sessions"""
    with Session(engine) as session:
        chats = session.exec(select(ChatSession).order_by(desc(ChatSession.updated_at))).all()

        result = []
        for chat in chats:
            # Получаем первые несколько сообщений для определения типа чата
            messages = session.exec(
                select(ChatMessage).where(ChatMessage.chat_session_id == chat.id).order_by(ChatMessage.timestamp).limit(5)
            ).all()

            result.append({
                "id": chat.id,
                "title": chat.title,
                "created_at": chat.created_at,
                "updated_at": chat.updated_at,
                "messages": [{"id": msg.id, "role": msg.role, "content": msg.content, "timestamp": msg.timestamp, "message_type": msg.message_type, "extra_metadata": msg.extra_metadata} for msg in messages]
            })
        return result

@app.get("/api/chats/{chat_id}")
def get_chat_messages(chat_id: int):
    """Get all messages for a specific chat session"""
    with Session(engine) as session:
        chat = session.get(ChatSession, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")

        messages = session.exec(
            select(ChatMessage).where(ChatMessage.chat_session_id == chat_id).order_by(ChatMessage.timestamp)
        ).all()

        return {
            "chat": {"id": chat.id, "title": chat.title, "created_at": chat.created_at, "updated_at": chat.updated_at},
            "messages": [{"id": msg.id, "role": msg.role, "content": msg.content, "timestamp": msg.timestamp, "message_type": msg.message_type, "extra_metadata": msg.extra_metadata} for msg in messages]
        }

@app.post("/api/chats")
def create_new_chat():
    """Create a new chat session"""
    with Session(engine) as session:
        new_chat = ChatSession(title="Новый чат")
        session.add(new_chat)
        session.commit()
        session.refresh(new_chat)
        return {"id": new_chat.id, "title": new_chat.title, "created_at": new_chat.created_at, "updated_at": new_chat.updated_at}

@app.post("/api/chats/{chat_id}/messages")
def add_message_to_chat(chat_id: int, message: ChatMessage):
    """Add a message to a specific chat session"""
    with Session(engine) as session:
        chat = session.get(ChatSession, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Update the chat session's updated_at timestamp
        chat.updated_at = datetime.now()
        session.add(chat)

        # Add the new message
        message.chat_session_id = chat_id
        session.add(message)
        session.commit()
        session.refresh(message)

        return {"id": message.id, "role": message.role, "content": message.content, "timestamp": message.timestamp, "message_type": message.message_type}

@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: int):
    """Delete a chat session and all its messages"""
    with Session(engine) as session:
        chat = session.get(ChatSession, chat_id)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")

        session.delete(chat)
        session.commit()
        return {"message": "Chat session deleted successfully"}

# Запуск сервера
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)