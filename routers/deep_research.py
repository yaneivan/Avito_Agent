import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from dependencies import get_session
from schemas import DeepResearchRequest, InterviewRequest, SchemaAgreementRequest
from services.orchestrator import DeepResearchOrchestrator
from services import ProcessingService
from database import SearchSession

# Важно: prefix="/api/deep_research"
router = APIRouter(prefix="/api/deep_research", tags=["deep_research"])
processing_service = ProcessingService()

@router.post("/chat")
async def deep_research_chat_endpoint(
    req: InterviewRequest, 
    session: Session = Depends(get_session)
):
    print(f"\n[API] Deep Research Chat: {req.history[-1]['content']}")
    orchestrator = DeepResearchOrchestrator(session)
    
    user_content = req.history[-1]['content'] if req.history else ""
    if not user_content:
         raise HTTPException(status_code=400, detail="Empty message")

    response = await orchestrator.handle_message(req.history, user_content)
    return response

@router.post("/schema_agreement")
async def schema_agreement(
    req: SchemaAgreementRequest, 
    session: Session = Depends(get_session)
):
    orchestrator = DeepResearchOrchestrator(session)
    # Приводим схему к строке
    schema_str = req.agreed_schema if isinstance(req.agreed_schema, str) else json.dumps(req.agreed_schema, ensure_ascii=False)
    
    result = await orchestrator.confirm_schema(req.search_id, schema_str)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "status": "success",
        "message": "Schema saved, parsing started",
        "next_stage": "parsing",
        "search_id": req.search_id
    }

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