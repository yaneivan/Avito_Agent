import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from dependencies import get_session
from schemas import ChatRequest, ChatMessageSchema
from database import ChatSession, ChatMessage, SearchSession, ExtractionSchema, Item, SearchItemLink, DeepResearchSession
from core.services import ChatProcessingService
from llm_engine import generate_schema_structure

router = APIRouter(prefix="/api", tags=["chat"])

@router.get("/chats")
def get_all_chats(session: Session = Depends(get_session)):
    # Возвращаем только чаты, которые не связаны с DeepResearchSession
    # Это позволяет отделить обычные чаты от чатов глубокого исследования
    # Используем left join и фильтруем по NULL в связанной сессии
    chats = session.exec(
        select(ChatSession)
        .where(~ChatSession.deep_research_session.has())
        .order_by(desc(ChatSession.updated_at))
    ).all()
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in chats]

@router.get("/deep_research_chats")
def get_deep_research_chats(session: Session = Depends(get_session)):
    # Возвращаем только чаты, которые связаны с DeepResearchSession
    chats = session.exec(
        select(ChatSession)
        .where(ChatSession.deep_research_session.has())
        .order_by(desc(ChatSession.updated_at))
    ).all()
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in chats]

@router.get("/chats/{chat_id}/deep_research_session")
def get_deep_research_session_by_chat_id(chat_id: int, session: Session = Depends(get_session)):
    # Получаем DeepResearchSession по chat_id
    research_session = session.exec(
        select(DeepResearchSession)
        .where(DeepResearchSession.chat_session_id == chat_id)
    ).first()

    if research_session:
        return {
            "id": research_session.id,
            "query_text": research_session.query_text,
            "stage": research_session.stage,
            "status": research_session.status
        }
    return None

@router.post("/chats")
def create_new_chat(session: Session = Depends(get_session)):
    new_chat = ChatSession(title="Новый чат")
    session.add(new_chat); session.commit(); session.refresh(new_chat)
    return {"id": new_chat.id, "title": new_chat.title}

@router.get("/chats/{chat_id}")
def get_chat_details(chat_id: int, session: Session = Depends(get_session)):
    chat = session.get(ChatSession, chat_id)
    if not chat: raise HTTPException(404)
    messages = session.exec(select(ChatMessage).where(ChatMessage.chat_session_id == chat_id).order_by(ChatMessage.timestamp)).all()
    return {"chat": chat, "messages": messages}

@router.post("/chats/{chat_id}/messages")
def add_message(chat_id: int, msg: ChatMessageSchema, session: Session = Depends(get_session)):
    chat = session.get(ChatSession, chat_id)
    if not chat: raise HTTPException(404)
    chat.updated_at = datetime.now()
    if chat.title == "Новый чат" and msg.role == "user":
        chat.title = msg.content[:40]
    db_msg = ChatMessage(**msg.model_dump(), chat_session_id=chat_id)
    session.add(chat); session.add(db_msg); session.commit()
    return {"status": "ok"}

@router.get("/searches/{search_id}/status")
def get_search_status(search_id: int, session: Session = Depends(get_session)):
    s = session.get(SearchSession, search_id)
    if not s: return {"status": "not_found"}
    return {"status": s.status, "summary": s.summary}

@router.get("/searches/{search_id}/items")
def get_search_items(search_id: int, session: Session = Depends(get_session)):
    items = session.exec(select(Item).join(SearchItemLink).where(SearchItemLink.search_id == search_id)).all()
    res = []
    for i in items:
        d = i.model_dump()
        if i.image_path:
            p = i.image_path.replace('\\', '/')
            d["image_url"] = f"/images/{p.split('images/')[-1]}"
        res.append(d)
    return res

@router.post("/agent/chat")
async def agent_chat(req: ChatRequest, session: Session = Depends(get_session)):
    user_content = req.history[-1]['content']
    chat_service = ChatProcessingService()
    result = await chat_service.process_user_message(user_content, req.history)
    decision = result["decision"]
    
    if decision.get("action") == "search":
        schema_name = decision.get("schema_name") or "General"
        target_schema = session.exec(select(ExtractionSchema).where(ExtractionSchema.name == schema_name)).first()
        if not target_schema:
            ns = await generate_schema_structure(schema_name)
            target_schema = ExtractionSchema(name=schema_name, description="Auto", structure_json=json.dumps(ns["schema"], ensure_ascii=False))
            session.add(target_schema); session.commit(); session.refresh(target_schema)

        task = SearchSession(
            query_text=decision.get("search_query") or user_content,
            schema_id=target_schema.id if target_schema else None,
            status="confirmed",
            limit_count=decision.get("limit", 5),
            open_in_browser=req.open_browser,
            reasoning=decision.get("reasoning")
        )
        session.add(task); session.commit(); session.refresh(task)
        return {"type": "search", "message": f"Ищу {task.query_text}", "task_id": task.id, "plan": decision}
    
    return {"type": "chat", "message": decision.get("reply", ""), "plan": decision}