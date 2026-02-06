from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from database import SessionLocal
from models.api_models import (
    CreateMarketResearchRequest,
    CreateSearchTaskRequest,
    SubmitResultsRequest,
    GetTaskResponse,
    ChatUpdateRequest
)
from services.research_service import MarketResearchService
from models.research_models import MarketResearch, State
from repositories.research_repository import (
    MarketResearchRepository,
    SearchTaskRepository,
    SchemaRepository,
    RawLotRepository,
    AnalyzedLotRepository
)
from utils.logger import logger, extension_logger
from typing import List
import json

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_service_with_session(db: Session) -> MarketResearchService:
    """Создание экземпляра сервиса с переданной сессией"""
    service = MarketResearchService()
    # Заменяем сессию в сервисе на переданную
    service.db = db
    service.mr_repo = MarketResearchRepository(db)
    service.task_repo = SearchTaskRepository(db)
    service.schema_repo = SchemaRepository(db)
    service.raw_lot_repo = RawLotRepository(db)
    service.analyzed_lot_repo = AnalyzedLotRepository(db)
    # Обновляем репозиторий в чат-сервисе
    service.chat_service.mr_repo = service.mr_repo
    return service

@router.post("/market_research", response_model=MarketResearch)
async def create_market_research(request: CreateMarketResearchRequest, db: Session = Depends(get_db)):
    """Создание нового исследования рынка"""
    try:
        service = create_service_with_session(db)
        created_mr = service.create_market_research(request.initial_query)
        created_mr = service.process_user_message(created_mr.id, request.initial_query)
        return created_mr
    except Exception as e:
        logger.error(f"Ошибка при создании исследования: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/market_research/{mr_id}", response_model=MarketResearch)
async def get_market_research(mr_id: int, db: Session = Depends(get_db)):
    """Получение исследования по ID"""
    try:
        # Создаем репозиторий с переданной сессией
        mr_repo = MarketResearchRepository(db)
        market_research = mr_repo.get_by_id(mr_id)
        if not market_research:
            raise HTTPException(status_code=404, detail="Market research not found")
        return market_research
    except Exception as e:
        logger.error(f"Ошибка при получении исследования: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat/{mr_id}")
async def update_chat(mr_id: int, request: ChatUpdateRequest, db: Session = Depends(get_db)):
    """Обновление чата (добавление сообщения пользователя)"""
    try:
        service = create_service_with_session(db)
        market_research = service.process_user_message(mr_id, request.message)
        return market_research
    except Exception as e:
        logger.error(f"Ошибка при обновлении чата: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_task", response_model=GetTaskResponse)
async def get_task(db: Session = Depends(get_db)):
    """Получение задачи от сервера (для браузерного расширения)"""
    extension_logger.info("Запрос задачи от браузерного расширения")

    # Получаем первую доступную задачу из базы данных
    task_repo = SearchTaskRepository(db)

    # Импортируем нужные модели
    from database import DBSearchTask

    # Ищем задачу, которая в состоянии "pending" и нуждается в обработке
    # Сортируем по времени создания (сначала самые старые)
    pending_tasks = db.query(DBSearchTask).filter(
        DBSearchTask.status == "pending"
    ).order_by(DBSearchTask.created_at.asc()).all()

    if not pending_tasks:
        extension_logger.info("Нет доступных задач для расширения")
        # Возвращаем 204 No Content, если нет задач
        raise HTTPException(status_code=204, detail="No tasks available")

    # Берем первую доступную задачу
    task = pending_tasks[0]

    # Обновляем статус задачи на "in_progress"
    updated_task = task_repo.update_status(task.id, "in_progress")

    extension_logger.info(f"Отправляем задачу {task.id} расширению")

    # Используем лимит из задачи поиска, если он задан, иначе 10 по умолчанию
    task_limit = task.limit if hasattr(task, 'limit') and task.limit is not None else 10

    return GetTaskResponse(
        task_id=task.id,
        query=task.query,
        active_tab=True,
        limit=task_limit
    )

@router.post("/submit_results")
async def submit_results(request: SubmitResultsRequest, db: Session = Depends(get_db)):
    """Отправка результатов на сервер (от браузерного расширения)"""
    extension_logger.info(f"Получены результаты для задачи {request.task_id}")

    service = create_service_with_session(db)

    try:
        # Получаем информацию о задаче
        task = service.task_repo.get_by_id(request.task_id)
        if not task:
            extension_logger.error(f"Задача с ID {request.task_id} не найдена")
            raise HTTPException(status_code=404, detail="Task not found")

        # В зависимости от типа задачи, обрабатываем результаты
        if task.mode == "quick":
            # Обработка результатов быстрого поиска
            market_research = service.handle_quick_search_results(request.task_id, request.items)
        elif task.mode == "deep":
            # Обработка результатов глубокого поиска
            market_research = service.handle_deep_search_results(request.task_id, request.items)
        else:
            extension_logger.error(f"Неизвестный режим задачи: {task.mode}")
            raise HTTPException(status_code=400, detail="Unknown task mode")

        extension_logger.info(f"Результаты задачи {request.task_id} успешно обработаны")

        # Возвращаем обновленное состояние исследования, чтобы клиент мог обновить чат
        return market_research
    except Exception as e:
        extension_logger.error(f"Ошибка при обработке результатов задачи {request.task_id}: {e}")

        # Ставим failed, чтобы разорвать цикл переповторов
        service.task_repo.update_status(request.task_id, "failed")

        logger.exception(f"Full traceback for task {request.task_id}:")
        raise HTTPException(status_code=500, detail=str(e))
    


@router.get("/search_task/{task_id}/results")
async def get_task_results(task_id: int, db: Session = Depends(get_db)):
    task_repo = SearchTaskRepository(db)
    analyzed_repo = AnalyzedLotRepository(db)
    schema_repo = SchemaRepository(db)
    raw_repo = RawLotRepository(db)

    task = task_repo.get_by_id(task_id)
    if not task: raise HTTPException(status_code=404)

    schema = schema_repo.get_by_id(task.schema_id)
    analyzed_lots = analyzed_repo.get_by_task_id(task_id)

    # Собираем данные: объединяем проанализированные данные с заголовком и ценой из RawLot
    results = []
    for al in analyzed_lots:
        raw = raw_repo.get_by_id(al.raw_lot_id)
        results.append({
            "id": al.id,
            "title": raw.title,
            "price": raw.price,
            "url": raw.url,
            "image_path": raw.image_path,
            "structured_data": al.structured_data, 
            "relevance_note": al.relevance_note,
            "image_description": al.image_description_and_notes,
            "score": al.tournament_score
        })

    return {
        "topic": task.topic,
        "schema": schema.json_schema,
        "rows": results
    }