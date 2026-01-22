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

from database import create_db_and_tables, engine, SearchSession, ExtractionSchema, Item, SearchItemLink
from services import ProcessingService
from image_utils import save_base64_image
from llm_engine import decide_action, generate_schema_structure, conduct_interview, generate_schema_proposal, generate_sql_query

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
    schema_json: str

class SqlGenerationRequest(BaseModel):
    search_id: int
    criteria: str

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

@app.post("/api/agent/chat")
async def agent_chat(req: ChatRequest):
    print(f"\n[API] Chat Request: {req.history[-1]['content']}")
    with Session(engine) as session:
        schemas = session.exec(select(ExtractionSchema)).all()
        decision = await decide_action(req.history, [s.name for s in schemas])
        
        if decision.get("action") == "chat":
            return {"type": "chat", "message": decision.get("reply"), "plan": decision}
            
        elif decision.get("action") == "search":
            query = decision.get("search_query") or "Товар"
            if req.use_cache:
                existing = session.exec(select(SearchSession).where(SearchSession.query_text == query, SearchSession.status == "done", SearchSession.summary != None).order_by(desc(SearchSession.created_at))).first()
                if existing:
                    new_req = SearchSession(query_text=query, schema_id=existing.schema_id, status="done", open_in_browser=False, use_cache=True, summary=existing.summary)
                    session.add(new_req); session.commit(); session.refresh(new_req)
                    for item in existing.items: session.add(SearchItemLink(search_id=new_req.id, item_id=item.id))
                    session.commit()
                    return {"type": "search", "message": "Найдено в кэше", "task_id": new_req.id, "plan": decision}

            schema_name = decision.get("schema_name") or "General"
            target_schema = next((s for s in schemas if s.name.lower() == schema_name.lower()), None)
            if not target_schema:
                new_struct = await generate_schema_structure(schema_name)
                target_schema = ExtractionSchema(name=schema_name, description="Auto", structure_json=new_struct)
                session.add(target_schema); session.commit(); session.refresh(target_schema)
            
            task = SearchSession(query_text=query, schema_id=target_schema.id, limit_count=decision.get("limit", 5), status="pending", open_in_browser=req.open_browser)
            session.add(task); session.commit(); session.refresh(task)
            print(f"[API] Created Task #{task.id}")
            return {"type": "search", "message": f"Запускаю поиск", "task_id": task.id, "plan": decision}
    return {"type": "error", "message": "Ошибка"}

@app.get("/api/searches/{search_id}/status")
def get_search_status(search_id: int):
    with Session(engine) as session:
        req = session.get(SearchSession, search_id)
        # УБРАЛ ЛИШНИЕ ПРИНТЫ
        return {"status": req.status if req else "not_found", "summary": req.summary if req else None}

@app.get("/api/get_task")
def get_task():
    with Session(engine) as session:
        task = session.exec(select(SearchSession).where(SearchSession.status == "pending").limit(1)).first()
        if task:
            task.status = "processing"
            session.add(task); session.commit()
            print(f"[API] Task #{task.id} picked up")
            return {"task_id": task.id, "query": task.query_text, "active_tab": task.open_in_browser, "limit": task.limit_count}
    return {"task_id": None}

@app.post("/api/submit_results")
async def submit_results(data: SubmitData):
    print(f"[API] Results received for Task #{data.task_id}")
    processed = []
    for idx, item in enumerate(data.items):
        path = save_base64_image(item.image_base64, data.task_id, idx, item.url)
        item.local_path = path; item.image_base64 = None; processed.append(item)
    await service.process_incoming_data(data.task_id, processed)
    return {"status": "ok"}

@app.get("/api/schemas")
def get_schemas():
    with Session(engine) as session: return session.exec(select(ExtractionSchema)).all()

@app.get("/api/searches/{search_id}/items")
def get_search_items(search_id: int):
    with Session(engine) as session:
        items = session.exec(select(Item).join(SearchItemLink).where(SearchItemLink.search_id == search_id)).all()
        res = []
        for i in items:
            d = i.model_dump()
            if i.image_path:
                p = i.image_path.replace('\\', '/')
                rel = p.split('images/')[-1] if 'images/' in p else p
                d["image_url"] = f"/images/{rel}"
            res.append(d)
        return res

@app.post("/api/log")
def remote_log(log: LogMessage): return {"status": "ok"}

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
                SearchSession.status == "pending"
            ).order_by(desc(SearchSession.created_at))
        ).first()

        if not existing_session:
            # Create a new deep research session
            new_session = SearchSession(
                query_text=req.history[-1]['content'] if req.history else "Deep Research Query",
                mode="deep",
                stage="interview",
                status="pending",
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
            "needs_more_info": interview_response.get("needs_more_info", True)
        }

        search_session.interview_data = json.dumps(interview_data, ensure_ascii=False)

        # Move to next stage if enough info gathered
        if not interview_response.get("needs_more_info", True):
            search_session.stage = "schema_agreement"

        session.add(search_session)
        session.commit()

        return {
            "type": "interview",
            "message": interview_response.get("response", ""),
            "needs_more_info": interview_response.get("needs_more_info", True),
            "search_id": search_session.id,
            "stage": search_session.stage
        }

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

        schema_proposal = await generate_schema_proposal(criteria_summary)

        return {
            "schema_proposal": schema_proposal,
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
        search_session.schema_agreed = req.schema_json
        search_session.stage = "parsing"
        search_session.status = "pending"

        # Create or update the extraction schema
        schema_name = f"DeepResearch_{search_session.id}"
        existing_schema = session.exec(
            select(ExtractionSchema).where(ExtractionSchema.name == schema_name)
        ).first()

        if existing_schema:
            existing_schema.structure_json = req.schema_json
            session.add(existing_schema)
        else:
            new_schema = ExtractionSchema(
                name=schema_name,
                description=f"Schema for deep research session {req.search_id}",
                structure_json=req.schema_json
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
        sql_query = await generate_sql_query(req.criteria, search_session.schema_agreed)

        return {
            "sql_query": sql_query,
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