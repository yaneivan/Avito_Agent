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
    return service

@router.post("/market_research", response_model=MarketResearch)
async def create_market_research(request: CreateMarketResearchRequest, db: Session = Depends(get_db)):
    """Создание нового исследования рынка"""
    try:
        service = create_service_with_session(db)
        market_research = service.create_market_research(request.initial_query)
        return market_research
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

        # В случае ошибки, возвращаем задачу в состояние "pending"
        service.task_repo.update_status(request.task_id, "pending")

        raise HTTPException(status_code=500, detail=str(e))


class UnifiedChatRequest(ChatUpdateRequest):
    """Запрос для унифицированного чат-эндпоинта"""
    mr_id: Optional[int] = None  # ID существующего исследования (опционально)


@router.post("/chat", response_model=MarketResearch)
async def unified_chat_endpoint(request: UnifiedChatRequest, db: Session = Depends(get_db)):
    """
    Единый эндпоинт для чата.
    Если mr_id не передан или исследования не существует, создает новое и обрабатывает сообщение.
    Если mr_id передан и исследование существует, обрабатывает сообщение в существующем исследовании.
    Это фасад, который скрывает логику создания сессии от фронтенда.
    """
    try:
        service = create_service_with_session(db)

        # Если передан mr_id и такое исследование существует, обрабатываем сообщение в нем
        if request.mr_id:
            market_research = service.mr_repo.get_by_id(request.mr_id)
            if market_research:
                # Обрабатываем сообщение в существующем исследовании
                market_research = service.process_user_message(request.mr_id, request.message)
                return market_research

        # Если mr_id не передан или исследования не существует, создаем новое
        # и сразу обрабатываем сообщение (как если бы это было первое сообщение в чате)
        market_research = service.create_market_research(request.message)

        # После создания исследования, обрабатываем сообщение, чтобы вызвать LLM
        market_research = service.process_user_message(market_research.id, request.message)

        return market_research
    except Exception as e:
        logger.error(f"Ошибка при обработке чата: {e}")
        raise HTTPException(status_code=500, detail=str(e))