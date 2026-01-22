from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from dependencies import get_session
from schemas import SubmitData, LogMessage
from database import SearchSession
from services import ProcessingService
from image_utils import save_base64_image

router = APIRouter(prefix="/api", tags=["tasks"])
service = ProcessingService()

@router.get("/get_task")
def get_task(session: Session = Depends(get_session)):
    task = session.exec(select(SearchSession).where(SearchSession.status == "confirmed").limit(1)).first()
    if task:
        task.status = "processing"
        session.add(task); session.commit()
        return {"task_id": task.id, "query": task.query_text, "active_tab": task.open_in_browser, "limit": task.limit_count}
    return {"task_id": None}

@router.post("/submit_results")
async def submit_results(data: SubmitData):
    processed = []
    for idx, item in enumerate(data.items):
        path = save_base64_image(item.image_base64, data.task_id, idx, item.url)
        item.local_path = path; item.image_base64 = None
        processed.append(item)
    await service.process_incoming_data(data.task_id, processed)
    return {"status": "ok"}

@router.post("/log")
def remote_log(log: LogMessage):
    # Молча принимаем логи, чтобы не спамить в консоль
    return {"status": "ok"}