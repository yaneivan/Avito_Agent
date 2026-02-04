from sqlalchemy.orm import Session
from database import (
    DBMarketResearch, 
    DBSchema, 
    DBRawLot, 
    DBAnalyzedLot, 
    DBSearchTask
)
from models.research_models import (
    MarketResearch,
    Schema,
    RawLot,
    AnalyzedLot,
    SearchTask,
    State,
    ChatMessage
)
from typing import List, Optional
import json
from datetime import datetime
from utils.logger import logger


class MarketResearchRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, market_research: MarketResearch) -> MarketResearch:
        # Функция для сериализации объектов datetime
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        db_mr = DBMarketResearch(
            state=market_research.state.value,
            chat_history=json.dumps([msg.dict() for msg in market_research.chat_history], default=serialize_datetime)
        )
        self.db.add(db_mr)
        self.db.commit()
        self.db.refresh(db_mr)

        # Обновляем ID в объекте
        market_research.id = db_mr.id
        return market_research

    def get_by_id(self, mr_id: int) -> Optional[MarketResearch]:
        db_mr = self.db.query(DBMarketResearch).filter(DBMarketResearch.id == mr_id).first()
        if not db_mr:
            logger.warning(f"Исследование с ID {mr_id} не найдено")
            return None


        # Загружаем историю чата
        chat_history = []
        if db_mr.chat_history:
            chat_history_data = json.loads(db_mr.chat_history)
            for msg_data in chat_history_data:
                chat_history.append(ChatMessage(**msg_data))

        # Получаем связанные задачи поиска
        search_tasks = self.db.query(DBSearchTask).filter(
            DBSearchTask.market_research_id == db_mr.id
        ).all()

        # Преобразуем в модели Pydantic
        tasks = []
        for task in search_tasks:
            tasks.append(SearchTask(
                id=task.id,
                market_research_id=task.market_research_id,
                mode=task.mode,
                topic=task.topic, 
                query=task.query,
                schema_id=task.schema_id,
                needs_visual=task.needs_visual,
                status=task.status,
                results=json.loads(task.results) if task.results else [],
                created_at=task.created_at
            ))

        result = MarketResearch(
            id=db_mr.id,
            state=State(db_mr.state),
            chat_history=chat_history,
            search_tasks=tasks,
            created_at=db_mr.created_at,
            updated_at=db_mr.updated_at
        )

        return result

    def update_state(self, mr_id: int, new_state: State) -> Optional[MarketResearch]:
        db_mr = self.db.query(DBMarketResearch).filter(DBMarketResearch.id == mr_id).first()
        if not db_mr:
            return None

        db_mr.state = new_state.value
        db_mr.updated_at = db_mr.updated_at  # Обновляем время
        self.db.commit()
        self.db.refresh(db_mr)

        return self.get_by_id(mr_id)

    def update(self, market_research: MarketResearch) -> Optional[MarketResearch]:
        logger.info(f"Начало обновления исследования {market_research.id} с {len(market_research.chat_history)} сообщениями")

        db_mr = self.db.query(DBMarketResearch).filter(DBMarketResearch.id == market_research.id).first()
        if not db_mr:
            logger.warning(f"Исследование с ID {market_research.id} не найдено для обновления")
            return None

        # Функция для сериализации объектов datetime
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        # Обновляем состояние и историю чата
        db_mr.state = market_research.state.value
        serialized_history = [msg.dict() for msg in market_research.chat_history]
        logger.info(f"Сериализованная история содержит {len(serialized_history)} записей")
        db_mr.chat_history = json.dumps(serialized_history, default=serialize_datetime)
        logger.info(f"JSON истории сохранен в базу данных")

        # Обновляем время
        db_mr.updated_at = db_mr.updated_at

        self.db.commit()
        logger.info(f"Транзакция сохранена в базе данных")

        self.db.refresh(db_mr)
        logger.info(f"Объект в сессии обновлен")

        result = self.get_by_id(market_research.id)
        logger.info(f"Возвращаемое исследование содержит {len(result.chat_history if result else [])} сообщений")
        if result:
            logger.info(f"Содержимое возвращаемой истории: {[msg.content for msg in result.chat_history]}")

        return result


class SchemaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, schema: Schema) -> Schema:
        db_schema = DBSchema(
            name=schema.name,
            description=schema.description,
            json_schema=json.dumps(schema.json_schema)
        )
        self.db.add(db_schema)
        self.db.commit()
        self.db.refresh(db_schema)
        
        schema.id = db_schema.id
        return schema

    def get_by_id(self, schema_id: int) -> Optional[Schema]:
        db_schema = self.db.query(DBSchema).filter(DBSchema.id == schema_id).first()
        if not db_schema:
            return None
            
        return Schema(
            id=db_schema.id,
            name=db_schema.name,
            description=db_schema.description,
            json_schema=json.loads(db_schema.json_schema)
        )


class RawLotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_or_update(self, raw_lot: RawLot) -> RawLot:
        # Проверяем, существует ли уже лот с таким URL
        existing_lot = self.db.query(DBRawLot).filter(DBRawLot.url == raw_lot.url).first()
        
        if existing_lot:
            # Обновляем существующий лот
            existing_lot.title = raw_lot.title
            existing_lot.price = raw_lot.price
            existing_lot.description = raw_lot.description
            existing_lot.image_path = raw_lot.image_path
            self.db.commit()
            self.db.refresh(existing_lot)
            
            raw_lot.id = existing_lot.id
            return raw_lot
        else:
            # Создаем новый лот
            db_raw_lot = DBRawLot(
                url=raw_lot.url,
                title=raw_lot.title,
                price=raw_lot.price,
                description=raw_lot.description,
                image_path=raw_lot.image_path
            )
            self.db.add(db_raw_lot)
            self.db.commit()
            self.db.refresh(db_raw_lot)
            
            raw_lot.id = db_raw_lot.id
            return raw_lot

    def get_by_id(self, lot_id: int) -> Optional[RawLot]:
        db_lot = self.db.query(DBRawLot).filter(DBRawLot.id == lot_id).first()
        if not db_lot:
            return None
            
        return RawLot(
            id=db_lot.id,
            url=db_lot.url,
            title=db_lot.title,
            price=db_lot.price,
            description=db_lot.description,
            image_path=db_lot.image_path,
            created_at=db_lot.created_at
        )


class AnalyzedLotRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, analyzed_lot: AnalyzedLot) -> AnalyzedLot:
        db_analyzed_lot = DBAnalyzedLot(
            raw_lot_id=analyzed_lot.raw_lot_id,
            schema_id=analyzed_lot.schema_id,
            structured_data=json.dumps(analyzed_lot.structured_data),
            relevance_note=analyzed_lot.relevance_note,
            image_description_and_notes=analyzed_lot.image_description_and_notes,
            tournament_score=getattr(analyzed_lot, 'tournament_score', 0.0)
        )
        self.db.add(db_analyzed_lot)
        self.db.commit()
        self.db.refresh(db_analyzed_lot)
        analyzed_lot.id = db_analyzed_lot.id
        return analyzed_lot

    def get_by_id(self, lot_id: int) -> Optional[AnalyzedLot]:
        db_lot = self.db.query(DBAnalyzedLot).filter(DBAnalyzedLot.id == lot_id).first()
        if not db_lot:
            return None
            
        return AnalyzedLot(
            id=db_lot.id,
            raw_lot_id=db_lot.raw_lot_id,
            schema_id=db_lot.schema_id,
            structured_data=json.loads(db_lot.structured_data),
            relevance_note=db_lot.relevance_note,
            image_description_and_notes=db_lot.image_description_and_notes,
            tournament_score=db_lot.tournament_score or 0.0,
            created_at=db_lot.created_at
        )


class SearchTaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, search_task: SearchTask) -> SearchTask:
        db_task = DBSearchTask(
            market_research_id=search_task.market_research_id,
            mode=search_task.mode,
            topic=search_task.topic,
            query=search_task.query,
            schema_id=search_task.schema_id,
            needs_visual=search_task.needs_visual,
            limit=search_task.limit,
            status=search_task.status,
            results=json.dumps(search_task.results) if search_task.results else None
        )
        self.db.add(db_task)
        self.db.commit()
        self.db.refresh(db_task)

        search_task.id = db_task.id
        return search_task

    def get_by_id(self, task_id: int) -> Optional[SearchTask]:
        db_task = self.db.query(DBSearchTask).filter(DBSearchTask.id == task_id).first()
        if not db_task:
            return None

        return SearchTask(
            id=db_task.id,
            market_research_id=db_task.market_research_id,
            mode=db_task.mode,
            topic=db_task.topic, 
            query=db_task.query,
            schema_id=db_task.schema_id,
            needs_visual=db_task.needs_visual,
            limit=db_task.limit,
            status=db_task.status,
            results=json.loads(db_task.results) if db_task.results else [],
            created_at=db_task.created_at
        )

    def update_status(self, task_id: int, status: str) -> Optional[SearchTask]:
        db_task = self.db.query(DBSearchTask).filter(DBSearchTask.id == task_id).first()
        if not db_task:
            return None

        db_task.status = status
        self.db.commit()
        self.db.refresh(db_task)

        return self.get_by_id(task_id)

    def update_results(self, task_id: int, results: List[dict]) -> Optional[SearchTask]:
        db_task = self.db.query(DBSearchTask).filter(DBSearchTask.id == task_id).first()
        if not db_task:
            return None
            
        db_task.results = json.dumps(results)
        self.db.commit()
        self.db.refresh(db_task)
        
        return self.get_by_id(task_id)