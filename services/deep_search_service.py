import uuid
from typing import List
from models.research_models import MarketResearch, State, ChatMessage, RawLot, AnalyzedLot, Schema
from repositories.research_repository import (
    MarketResearchRepository,
    SearchTaskRepository,
    SchemaRepository,
    RawLotRepository,
    AnalyzedLotRepository
)
from services.tournament_service import tournament_ranking
from utils.image_handler import save_image_from_base64
from utils.logger import logger
import json
import copy
import base64


class DeepSearchService:
    def __init__(
        self,
        mr_repo: MarketResearchRepository,
        task_repo: SearchTaskRepository,
        schema_repo: SchemaRepository,
        raw_lot_repo: RawLotRepository,
        analyzed_lot_repo: AnalyzedLotRepository,
    ):
        self.mr_repo = mr_repo
        self.task_repo = task_repo
        self.schema_repo = schema_repo
        self.raw_lot_repo = raw_lot_repo
        self.analyzed_lot_repo = analyzed_lot_repo

    def handle_deep_search_results(self, task_id: int, raw_results: List[dict]) -> MarketResearch:
        """Обработка результатов глубокого поиска"""
        logger.info(f"Обрабатываем результаты глубокого поиска для задачи {task_id}")

        # Обновляем статус задачи
        task = self.task_repo.update_status(task_id, "completed")
        if not task:
            raise ValueError(f"Задача с ID {task_id} не найдена")

        # Сохраняем "сырые" лоты
        raw_lots = []
        for item in raw_results:
            # Если есть изображение в base64, сохраняем его
            image_path = None
            if item.get('image_base64'):
                image_path = save_image_from_base64(item['image_base64'], f"deep_{task_id}")

            raw_lot = RawLot(
                url=item.get('url', ''),
                title=item.get('title', ''),
                price=item.get('price', ''),
                description=item.get('description', ''),
                image_path=image_path
            )
            saved_raw_lot = self.raw_lot_repo.create_or_update(raw_lot)
            raw_lots.append(saved_raw_lot)

        # Если у задачи есть схема, применяем её для структурирования данных
        if task.schema_id:
            schema = self.schema_repo.get_by_id(task.schema_id)
            if schema:
                analyzed_lots = []

                # Анализируем каждый лот с помощью LLM и схемы
                for raw_lot in raw_lots:
                    analyzed_lot = self._analyze_lot_with_schema(raw_lot, schema)
                    saved_analyzed_lot = self.analyzed_lot_repo.create(analyzed_lot)
                    analyzed_lots.append(saved_analyzed_lot)

                # Если результатов много, применяем турнирный реранкинг
                if len(analyzed_lots) > 5:
                    ranked_lots = self._apply_tournament_ranking(analyzed_lots, schema)
                else:
                    ranked_lots = analyzed_lots

                # Формируем сообщение для пользователя с результатами
                result_message = self._format_deep_search_results(ranked_lots, schema)
            else:
                # Если схема не найдена, просто форматируем сырые результаты
                from .quick_search_service import QuickSearchService
                quick_service = QuickSearchService(self.mr_repo, self.task_repo, self.raw_lot_repo)
                result_message = quick_service._format_quick_search_results(raw_results)
        else:
            # Если нет схемы, просто форматируем сырые результаты
            from .quick_search_service import QuickSearchService
            quick_service = QuickSearchService(self.mr_repo, self.task_repo, self.raw_lot_repo)
            result_message = quick_service._format_quick_search_results(raw_results)

        # Добавляем результаты в историю чата
        market_research = self.mr_repo.get_by_id(task.market_research_id)
        if not market_research:
            raise ValueError(f"Исследование с ID {task.market_research_id} не найдено")

        market_research.chat_history.append(
            ChatMessage(id=str(uuid.uuid4()), role="assistant", content=result_message)
        )

        # Возвращаемся к состоянию CHAT
        market_research.state = State.CHAT
        self.mr_repo.update_state(task.market_research_id, State.CHAT)

        logger.info(f"Результаты глубокого поиска обработаны для исследования {task.market_research_id}")
        return market_research

    def _analyze_lot_with_schema(self, raw_lot: RawLot, schema: Schema) -> AnalyzedLot:
        """Анализ лота с использованием схемы и LLM"""
        logger.info(f"Анализируем лот {raw_lot.id} с использованием схемы {schema.id}")

        from utils.llm_client import get_completion


        full_schema = copy.deepcopy(schema.json_schema)
        full_schema.update({"relevance_note":"Why this lot is good/bad for user.", 
                            "image_description_and_notes": "Relevant information from the image - colors, details, condition"})


        # Формируем сообщение для LLM
        messages = [
            {
                "role": "system",
                "content": f"""Извлеки информацию из описания товара в соответствии со следующей JSON-схемой: {json.dumps(full_schema)}
                Возвращай только JSON в соответствии со схемой."""
            },
        ]

        user_content = [{"type": "text", "text": f"Title: {raw_lot.title}\nDesc: {raw_lot.description}\nPrice: {raw_lot.price}"}]
        
        
        # 3. Фото-логика (подключаемая)
        if raw_lot.image_path:
            try:
                with open(raw_lot.image_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
                user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})
            except Exception as e:
                logger.error(f"Image error: {e}")
        else:
            user_content.append({"type": "text", "text": "(NO PHOTO provided for this lot. Put 'N/A' in image_description_and_notes)"})

        messages.append({"role": "user", "content": user_content})

        response = get_completion(messages)

        # Парсим ответ от LLM
        try:
            structured_data = json.loads(response.content)
            
        except json.JSONDecodeError:
            # Если LLM вернул неправильный JSON, используем хотя бы частичные данные
            # В реальной реализации нужно будет обработать ошибку и, возможно, повторить запрос
            logger.error(f"LLM вернул некорректный JSON для лота {raw_lot.id}")
            structured_data = {}

        relevance_note = structured_data.pop("relevance_note", "No note")
        image_description_and_notes = structured_data.pop("image_description_and_notes", "No visual info")

        analyzed_lot = AnalyzedLot(
            raw_lot_id=raw_lot.id,
            schema_id=schema.id,
            structured_data=structured_data,
            relevance_note=relevance_note,
            image_description_and_notes=image_description_and_notes
        )

        return analyzed_lot

    def _apply_tournament_ranking(self, analyzed_lots: List[AnalyzedLot], schema: Schema) -> List[AnalyzedLot]:
            """Применение турнирного реранкинга к результатам"""
            logger.info(f"Применяем турнирный реранкинг к {len(analyzed_lots)} лотам")

            # 1. Разбиваем лоты на группы по 5 штук с перекрытием в 1 элемент
            groups = []
            group_size = 5
            overlap = 1

            for i in range(0, len(analyzed_lots), group_size - overlap):
                group = analyzed_lots[i:i + group_size]
                if len(group) >= 2:
                    groups.append(group)

            # 2. Подготовим данные для турнирного реранкинга (словари для LLM)
            lot_groups_data = []
            for group in groups:
                group_data = []
                for lot in group:
                    group_data.append({
                        'id': lot.id,  # Обязательно передаем реальный ID
                        'title': lot.structured_data.get('title', 'N/A'),
                        'price': lot.structured_data.get('price', 'N/A'),
                        'structured_data': lot.structured_data,
                        'relevance': lot.relevance_note,  # Переименовано для TournamentService
                        'image_description_and_notes': lot.image_description_and_notes
                    })
                lot_groups_data.append(group_data)

            # 3. Определяем критерии на основе ключей схемы
            criteria = ", ".join(schema.json_schema.get("properties", {}).keys())

            # 4. Выполняем турнирный реранкинг
            # Теперь ranked_result — это список словарей в правильном порядке
            ranked_result_data = tournament_ranking(lot_groups_data, criteria)

            # 5. Мапим ID обратно в объекты AnalyzedLot (эффективно через словарь)
            id_to_lot_map = {lot.id: lot for lot in analyzed_lots}
            ranked_lots = []
            
            for item in ranked_result_data:
                lot_id = item['id']
                if lot_id in id_to_lot_map:
                    ranked_lots.append(id_to_lot_map[lot_id])

            # 6. Добавляем лоты, которые могли не попасть в турнир (safety first)
            ranked_lot_ids = {lot.id for lot in ranked_lots}
            for lot in analyzed_lots:
                if lot.id not in ranked_lot_ids:
                    ranked_lots.append(lot)

            logger.info(f"Турнирный реранкинг завершен. Топ-1: {ranked_lots[0].structured_data.get('title') if ranked_lots else 'N/A'}")
            return ranked_lots
    

    def _format_deep_search_results(self, analyzed_lots: List[AnalyzedLot], schema: Schema) -> str:
            """Форматирование результатов глубокого поиска для отправки пользователю"""
            logger.info(f"Форматируем {len(analyzed_lots)} результатов глубокого поиска")

            if not analyzed_lots:
                return "К сожалению, не удалось найти подходящие товары по вашему запросу."

            formatted_results = "### 📊 Результаты глубокого анализа\n\n"

            # Ограничиваем количество отображаемых карточек (например, топ-5)
            max_results = 5
            lots_to_show = analyzed_lots[:max_results]

            for i, lot in enumerate(lots_to_show):
                title = lot.structured_data.get('title', 'Без названия')
                price = lot.structured_data.get('price', 'Цена не указана')
                
                # Заголовок лота с его турнирным баллом (если он был рассчитан)
                score_str = f" (Рейтинг: {lot.tournament_score})" if hasattr(lot, 'tournament_score') else ""
                formatted_results += f"{i+1}. **{title}** — {price}{score_str}\n"

                # 1. Выводим поля из JSON схемы (кроме заголовка и цены)
                schema_properties = schema.json_schema.get("properties", {})
                for prop_name in schema_properties.keys():
                    if prop_name in lot.structured_data and prop_name.lower() not in ['title', 'price']:
                        val = lot.structured_data[prop_name]
                        formatted_results += f"   - *{prop_name}*: {val}\n"

                # 2. Выводим релевантность (почему он в топе)
                if lot.relevance_note and lot.relevance_note != "N/A":
                    formatted_results += f"   - **Почему подходит**: {lot.relevance_note}\n"

                # 3. Выводим визуальные заметки
                if lot.image_description_and_notes and lot.image_description_and_notes != "N/A":
                    formatted_results += f"   - **Визуально**: {lot.image_description_and_notes}\n"

                formatted_results += "\n"

            if len(analyzed_lots) > max_results:
                formatted_results += f"*И еще {len(analyzed_lots) - max_results} товаров были проанализированы и отсортированы ниже по списку.*"

            return formatted_results