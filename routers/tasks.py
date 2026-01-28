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
    # Ищем подтвержденные задачи
    task = session.exec(select(SearchSession).where(SearchSession.status == "confirmed").limit(1)).first()
    if task:
        print(f"\n[API] Extension picked up Task #{task.id}: {task.query_text}")
        task.status = "processing"
        session.add(task); session.commit()
        return {
            "task_id": task.id, 
            "query": task.query_text, 
            "active_tab": task.open_in_browser, 
            "limit": task.limit_count
        }
    return {"task_id": None}

@router.post("/submit_results")
async def submit_results(data: SubmitData):
    print(f"\n[API] Received {len(data.items)} items for Task #{data.task_id}")
    print(f"[DEBUG] First item structured_data: {data.items[0].structured_data if data.items else 'No items'}")
    processed = []

    # Сначала сохраняем картинки, чтобы не держать base64 в памяти
    for idx, item in enumerate(data.items):
        print(f"[DEBUG] Processing item {idx}, structured_data: {item.structured_data}")
        try:
            path = save_base64_image(item.image_base64, data.task_id, idx, item.url)
            item.local_path = path
            item.image_base64 = None # Освобождаем память
            processed.append(item)
        except Exception as e:
            print(f"[ERROR] Image save failed: {e}")

    # Запускаем тяжелую обработку
    print(f"[DEBUG] About to process incoming data with {len(processed)} items")
    await service.process_incoming_data(data.task_id, processed)
    return {"status": "ok"}

@router.post("/log")
def remote_log(log: LogMessage):
    # Логи от расширения
    if log.level == "error":
        print(f"[EXT ERROR] {log.source}: {log.message}")
    return {"status": "ok"}