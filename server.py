import os, json
from typing import List, Optional, Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlmodel import Session, select, desc
from pydantic import BaseModel
from contextlib import asynccontextmanager

from database import create_db_and_tables, engine, SearchSession, ExtractionSchema, Item, SearchItemLink
from services import ProcessingService
from image_utils import save_base64_image
from llm_engine import decide_action, generate_schema_structure

class ItemSchema(BaseModel):
    title: str; price: str; url: str; description: Optional[str] = None; image_base64: Optional[str] = None; local_path: Optional[str] = None 

class SubmitData(BaseModel):
    task_id: int; items: List[ItemSchema]

class ChatRequest(BaseModel):
    history: List[Dict[str, Any]]; open_browser: bool = True; use_cache: bool = True

class LogMessage(BaseModel):
    source: str; message: str; level: str = "info"

service = ProcessingService()

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
async def index(): return FileResponse("templates/index.html")

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