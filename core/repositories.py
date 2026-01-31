"""
Слой доступа к данным (Data Access Layer) для проекта Avito Agent
"""
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, func
from database import Item, SearchSession, DeepResearchSession, SearchItemLink, engine, ExtractionSchema
import json


class ItemRepository:
    """Репозиторий для работы с товарами"""

    @staticmethod
    def create_item(item_data: Dict[str, Any]) -> Item:
        """Создание нового товара в базе данных"""
        with Session(engine) as session:
            db_item = Item(**item_data)
            session.add(db_item)
            session.commit()
            session.refresh(db_item)
            return db_item

    @staticmethod
    def get_item_by_id(item_id: int) -> Optional[Item]:
        """Получение товара по ID"""
        with Session(engine) as session:
            return session.get(Item, item_id)

    @staticmethod
    def update_item(item_id: int, **updates) -> Optional[Item]:
        """Обновление товара"""
        with Session(engine) as session:
            db_item = session.get(Item, item_id)
            if db_item:
                for key, value in updates.items():
                    setattr(db_item, key, value)
                session.add(db_item)
                session.commit()
                session.refresh(db_item)
            return db_item

    @staticmethod
    def get_items_by_session(session_id: int, session_type: str = "search") -> List[Item]:
        """Получение товаров по сессии"""
        with Session(engine) as session:
            # Определяем тип сессии
            if session_type == "deep_research":
                # Для DeepResearchSession используем связи через SearchSession
                search_sessions = session.exec(
                    select(SearchSession).where(SearchSession.deep_research_session_id == session_id)
                ).all()

                item_ids = []
                for s in search_sessions:
                    links = session.exec(
                        select(SearchItemLink).where(SearchItemLink.search_session_id == s.id)
                    ).all()
                    item_ids.extend([link.item_id for link in links])
            else:
                # Для SearchSession используем прямые связи
                links = session.exec(
                    select(SearchItemLink).where(SearchItemLink.search_session_id == session_id)
                ).all()
                item_ids = [link.item_id for link in links]

            # Получаем товары по ID
            items = []
            for item_id in item_ids:
                item = session.get(Item, item_id)
                if item:
                    items.append(item)

            return items

    @staticmethod
    def get_item_by_url(url: str) -> Optional[Item]:
        """Получение товара по URL"""
        with Session(engine) as session:
            return session.exec(select(Item).where(Item.url == url)).first()


class SearchSessionRepository:
    """Репозиторий для работы с сессиями поиска"""

    @staticmethod
    def get_session_by_id(session_id: int, session_type: str = "search") -> Optional[Any]:
        """Получение сессии по ID"""
        with Session(engine) as session:
            if session_type == "deep_research":
                return session.get(DeepResearchSession, session_id)
            else:
                return session.get(SearchSession, session_id)

    @staticmethod
    def update_session_status(session_id: int, status: str, session_type: str = "search"):
        """Обновление статуса сессии"""
        with Session(engine) as session:
            if session_type == "deep_research":
                db_session = session.get(DeepResearchSession, session_id)
                if db_session:
                    db_session.status = status
            else:
                db_session = session.get(SearchSession, session_id)
                if db_session:
                    db_session.status = status

            session.commit()

    @staticmethod
    def get_related_search_sessions(deep_research_session_id: int) -> List[SearchSession]:
        """Получение связанных SearchSession для DeepResearchSession"""
        with Session(engine) as session:
            return session.exec(
                select(SearchSession).where(
                    SearchSession.deep_research_session_id == deep_research_session_id
                )
            ).all()

    @staticmethod
    def create_search_session_for_deep_research(query_text: str, deep_research_session_id: int) -> SearchSession:
        """Создание SearchSession, связанной с DeepResearchSession"""
        with Session(engine) as session:
            search_session = SearchSession(
                query_text=query_text,
                deep_research_session_id=deep_research_session_id,
                status="completed",
                stage="completed"
            )
            session.add(search_session)
            session.commit()
            session.refresh(search_session)
            return search_session

    @staticmethod
    def get_existing_search_session(deep_research_session_id: int) -> Optional[SearchSession]:
        """Получение существующей SearchSession, связанной с DeepResearchSession"""
        with Session(engine) as session:
            return session.exec(
                select(SearchSession)
                .where(SearchSession.deep_research_session_id == deep_research_session_id)
            ).first()


class SearchItemLinkRepository:
    """Репозиторий для работы со связями между сессиями и товарами"""

    @staticmethod
    def create_link(search_session_id: int, item_id: int):
        """Создание связи между сессией и товаром"""
        with Session(engine) as session:
            link = SearchItemLink(search_session_id=search_session_id, item_id=item_id)
            session.add(link)
            session.commit()

    @staticmethod
    def get_items_for_session(search_session_id: int) -> List[int]:
        """Получение ID товаров для сессии"""
        with Session(engine) as session:
            links = session.exec(
                select(SearchItemLink).where(SearchItemLink.search_session_id == search_session_id)
            ).all()
            return [link.item_id for link in links]

    @staticmethod
    def link_exists(search_session_id: int, item_id: int) -> bool:
        """Проверка существования связи между сессией и товаром"""
        with Session(engine) as session:
            link = session.exec(
                select(SearchItemLink).where(
                    SearchItemLink.search_session_id == search_session_id,
                    SearchItemLink.item_id == item_id
                )
            ).first()
            return link is not None


class ExtractionSchemaRepository:
    """Репозиторий для работы со схемами извлечения данных"""

    @staticmethod
    def get_schema_by_id(schema_id: int) -> Optional[ExtractionSchema]:
        """Получение схемы по ID"""
        with Session(engine) as session:
            return session.get(ExtractionSchema, schema_id)