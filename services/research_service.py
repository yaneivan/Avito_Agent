from typing import List, Dict, Any, Optional
from models.research_models import (
    MarketResearch,
    SearchTask,
    State,
    ChatMessage
)
from repositories.research_repository import (
    MarketResearchRepository,
    SearchTaskRepository,
    SchemaRepository,
    RawLotRepository,
    AnalyzedLotRepository
)
from database import SessionLocal
from utils.logger import logger
from .chat_service import ChatService
from .quick_search_service import QuickSearchService
from .deep_search_service import DeepSearchService


class MarketResearchService:
    def __init__(self):
        self.db = SessionLocal()
        self.mr_repo = MarketResearchRepository(self.db)
        self.task_repo = SearchTaskRepository(self.db)
        self.schema_repo = SchemaRepository(self.db)
        self.raw_lot_repo = RawLotRepository(self.db)
        self.analyzed_lot_repo = AnalyzedLotRepository(self.db)

        # Инициализируем специализированные сервисы
        self.chat_service = ChatService(self.mr_repo)
        self.quick_search_service = QuickSearchService(
            self.mr_repo,
            self.task_repo,
            self.raw_lot_repo
        )
        self.deep_search_service = DeepSearchService(
            self.mr_repo,
            self.task_repo,
            self.schema_repo,
            self.raw_lot_repo,
            self.analyzed_lot_repo,
        )

    def create_market_research(self, initial_query: str) -> MarketResearch:
        """Создание нового исследования рынка"""
        logger.info(f"Создаем новое исследование рынка с запросом: {initial_query}")

        market_research = MarketResearch(
            state=State.CHAT,
            chat_history=[]
        )

        created_mr = self.mr_repo.create(market_research)

        logger.info(f"Исследование создано с ID: {created_mr.id}, состояние: {created_mr.state}")
        return created_mr


    def process_user_message(self, mr_id: int, message: str, images: List[str] = []) -> MarketResearch:
        """Обработка сообщения от пользователя"""
        logger.info(f"Обрабатываем сообщение для исследования {mr_id}: {message}")

        # 1. Делегируем обработку сообщения чат-сервису
        market_research, is_tool_call = self.chat_service.process_user_message(mr_id, message, images)

        # 2. Если был вызов инструмента, обрабатываем его
        if is_tool_call:
            # Найти последнее сообщение ассистента в истории чата
            last_assistant_msg = None
            for msg in reversed(market_research.chat_history):
                if msg.role == "assistant":
                    last_assistant_msg = msg
                    break
            
            if last_assistant_msg:
                # Использовать регулярное выражение для поиска вызова инструмента в формате <tool_call>
                import re
                import json
                
                tool_match = re.search(r'<tool_call>(.*?)</tool_call>', last_assistant_msg.content, re.DOTALL)
                
                if tool_match:
                    try:
                        # Извлечь JSON с информацией о вызове инструмента
                        tool_json = tool_match.group(1).strip()
                        tool_data = json.loads(tool_json)
                        
                        # Получить имя инструмента и параметры
                        tool_name = tool_data.get('name')

                        # Извлекаем параметры - они находятся на верхнем уровне вместе с 'name'
                        params = {k: v for k, v in tool_data.items() if k != 'name'}

                        logger.info(f"Обрабатываем вызов инструмента: {tool_name} с параметрами: {params}")

                        # 3. Выполнить соответствующую логику в зависимости от имени инструмента

                        # 3.1. Если это быстрый поиск
                        if tool_name == "start_quick_search":
                            # Извлечь параметры из вызова инструмента
                            query = params.get('query', message)
                            needs_visual = params.get('needs_visual', False)

                            # Создать задачу быстрого поиска
                            search_task = SearchTask(
                                market_research_id=mr_id,
                                mode="quick",
                                query=query,
                                needs_visual=needs_visual
                            )
                            created_task = self.task_repo.create(search_task)

                            # Обновить состояние исследования
                            new_state = State.SEARCHING_QUICK
                            market_research.state = new_state
                            self.mr_repo.update_state(mr_id, new_state)

                            # Сообщение пользователю уже добавлено в chat_service, не нужно дублировать
                            # Только обновляем состояние

                        # 3.2. Планирование (только меняем стейт)
                        elif tool_name == "plan_deep_research":
                            new_state = State.PLANNING_DEEP_RESEARCH
                            market_research.state = new_state
                            self.mr_repo.update_state(mr_id, new_state)

                        # 3.3. Запуск (создаем схему и задачу)
                        elif tool_name == "execute_deep_research":
                            # 1. Сохраняем схему
                            from models.research_models import Schema as SchemaModel
                            schema_obj = SchemaModel(
                                name=f"Schema: {params.get('topic')}",
                                description=params.get('context_summary', ''),
                                json_schema=params.get('schema', {})
                            )
                            new_schema = self.schema_repo.create(schema_obj)

                            # 2. Создаем задачу поиска
                            search_task = SearchTask(
                                market_research_id=mr_id,
                                mode="deep",
                                query=params.get('topic'),
                                limit=int(params.get('limit', 10)),
                                needs_visual=bool(params.get('needs_visual', False)),
                                schema_id=new_schema.id,
                                status="pending"
                            )
                            self.task_repo.create(search_task)

                            # 3. Переходим в режим поиска
                            new_state = State.DEEP_RESEARCH
                            market_research.state = new_state
                            self.mr_repo.update_state(mr_id, new_state)
                        
                        # Сохранить обновленное исследование
                        self.mr_repo.update(market_research)
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка парсинга JSON вызова инструмента: {e}")
                    except Exception as e:
                        logger.error(f"Ошибка обработки вызова инструмента: {e}")

        # 4. Вернуть обновленное исследование
        logger.info(f"Состояние исследования {mr_id} обновлено до: {market_research.state}")
        return market_research

    def handle_quick_search_results(self, task_id: int, results: List[Dict]) -> MarketResearch:
        """Обработка результатов быстрого поиска"""
        return self.quick_search_service.handle_quick_search_results(task_id, results)

    def handle_deep_search_results(self, task_id: int, results: List[Dict]) -> MarketResearch:
        """Обработка результатов глубокого поиска"""
        return self.deep_search_service.handle_deep_search_results(task_id, results)

    def get_market_research(self, mr_id: int) -> MarketResearch:
        """Получение исследования по ID"""
        return self.mr_repo.get_by_id(mr_id)