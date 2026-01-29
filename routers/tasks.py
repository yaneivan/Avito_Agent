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
        print(f"[API] Extension picked up Task #{task.id}: {task.query_text}")
        print(f"[DEBUG TASK ROUTER] Task #{task.id} status changed from '{task.status}' to 'processing'")
        task.status = "processing"
        session.add(task); session.commit()
        print(f"[DEBUG TASK ROUTER] Task #{task.id} committed to DB")

        # Определяем, является ли задача задачей глубокого исследования
        is_deep_research = task.mode == "deep_research" or task.deep_research_session_id is not None

        return {
            "task_id": task.id,
            "query": task.query_text,
            "active_tab": task.open_in_browser,
            "limit": task.limit_count,
            "is_deep_research": is_deep_research,
            "deep_research_session_id": task.deep_research_session_id if is_deep_research else None
        }
    return {"task_id": None}

@router.post("/submit_results")
async def submit_results(data: SubmitData):
    print(f"\n[DEBUG TASK ROUTER] Received submit_results request")
    print(f"[API] Received {len(data.items)} items for Task #{data.task_id}")
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
            print(f"[DEBUG] Image saved for item {idx} at {path}")
        except Exception as e:
            print(f"[ERROR] Image save failed for item {idx}: {e}")

    print(f"[DEBUG TASK ROUTER] Successfully processed {len(processed)} items, about to call process_incoming_data")

    # Проверяем, является ли задача задачей глубокого исследования
    # Для этого нужно получить информацию о сессии
    from sqlmodel import select
    from database import SearchSession, engine
    from dependencies import get_session
    from sqlmodel import Session

    # Создаем сессию для получения информации о задаче
    with Session(engine) as db_session:
        search_session = db_session.get(SearchSession, data.task_id)

        if search_session and search_session.deep_research_session_id:
            # Это задача глубокого исследования - направляем в соответствующий обработчик
            print(f"[DEBUG] Task {data.task_id} is part of deep research session {search_session.deep_research_session_id}")
            await service.process_incoming_data(search_session.deep_research_session_id, processed, is_deep_analysis=True)
        else:
            # Это обычная задача - обрабатываем как обычно
            print(f"[DEBUG] Task {data.task_id} is a regular search task")
            await service.process_incoming_data(data.task_id, processed)

    print(f"[DEBUG TASK ROUTER] process_incoming_data completed for Task #{data.task_id}")
    return {"status": "ok"}

@router.post("/log")
def remote_log(log: LogMessage):
    # Логи от расширения
    if log.level == "error":
        print(f"[EXT ERROR] {log.source}: {log.message}")
    return {"status": "ok"}