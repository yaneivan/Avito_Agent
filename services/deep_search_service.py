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
                for i, raw_lot in enumerate(raw_lots):
                    logger.info(f"LLM обрабатывает лот номер {i} из {len(raw_lots)}")
                    analyzed_lot = self._analyze_lot_with_schema(raw_lot, schema, task_id)
                    analyzed_lot.search_task_id = task_id 
                    saved_analyzed_lot = self.analyzed_lot_repo.create(analyzed_lot)
                    analyzed_lots.append(saved_analyzed_lot)

                # Если результатов много, применяем турнирный реранкинг
                if len(analyzed_lots) > 5:
                    ranked_lots = self._apply_tournament_ranking(analyzed_lots, schema)
                else:
                    ranked_lots = analyzed_lots

                result_message = self._generate_analytical_summary(ranked_lots[:10], schema, task.topic)
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

        items_for_tiles = []
        for lot in ranked_lots[:5]:
            raw = self.raw_lot_repo.get_by_id(lot.raw_lot_id)
            items_for_tiles.append({
                "title": raw.title,
                "price": raw.price,
                "url": raw.url,
                "image_path": raw.image_path.replace("\\", "/").replace("./", "") if raw.image_path else None,
                "is_deep": True,
                "structured_data": lot.structured_data # Чтобы потом показать по клику
            })

        market_research.chat_history.append(
            ChatMessage(
                id=str(uuid.uuid4()), 
                role="assistant", 
                content=result_message,
                items=items_for_tiles, 
                task_id=task_id  
                )
        )

        # Возвращаемся к состоянию CHAT и сохраняем обновленную историю чата
        market_research.state = State.CHAT
        self.mr_repo.update(market_research)

        logger.info(f"Результаты глубокого поиска обработаны и сохранены для исследования {task.market_research_id}")
        return market_research

    def _analyze_lot_with_schema(self, raw_lot: RawLot, schema: Schema, task_id: int) -> AnalyzedLot:
        """Анализ лота с использованием схемы и LLM"""
        logger.info(f"Анализируем лот {raw_lot.id} с использованием схемы {schema.id}")

        from utils.llm_client import get_completion


        # Формируем читаемые инструкции безопасно
        fields_list = []
        for k, v in schema.json_schema.items():
            if isinstance(v, dict):
                # Если это словарь, берем значения через .get() с дефолтами
                desc = v.get('description', 'Нет описания')
                field_type = v.get('type', 'string')
                fields_list.append(f"- {k}: {desc} (тип: {field_type})")
            else:
                # На случай, если LLM прислала просто "field": "string"
                fields_list.append(f"- {k}: (тип: {v})")

        fields_desc = "\n".join(fields_list)

        messages = [
            {
                "role": "system",
                "content": f"""Извлеки характеристики товара в формате JSON.

### **ВАЖНЫЕ ПРАВИЛА**
1. Если в объявлении предлагается несколько разных моделей (или товаров) в одном тексте, обязательно запиши это в relevance_note. Укажи, что в таком случае, цена указанная в объявлении может не являться реальной ценой.  

Поля для извлечения:
{fields_desc}
- relevance_note: почему этот лот подходит пользователю.
- image_description_and_notes: что изображено, видно на фото (объект, цвета, детали, состояние).


Возвращай СТРОГО чистый JSON."""
                    },]
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
            search_task_id=task_id,  
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
                    raw_lot = self.raw_lot_repo.get_by_id(lot.raw_lot_id)
                    group_data.append({
                        'id': lot.id,  # Обязательно передаем реальный ID
                        'title': raw_lot.title if raw_lot else 'N/A',
                        'price': raw_lot.price if raw_lot else 'N/A',
                        'structured_data': lot.structured_data,
                        'relevance': lot.relevance_note,  # Переименовано для TournamentService
                        'image_description_and_notes': lot.image_description_and_notes
                    })
                lot_groups_data.append(group_data)

            # 3. Определяем критерии на основе ключей плоской схемы
            criteria = "Цена (сравнение стоимости), " + ", ".join(schema.json_schema.keys())
            criteria += ". Также учитывай соотношение цены и характеристик (выгодность)."

            # 4. Выполняем турнирный реранкинг
            # Теперь ranked_result — это список словарей в правильном порядке
            ranked_result_data = tournament_ranking(lot_groups_data, criteria)

            # 5. Мапим ID обратно в объекты AnalyzedLot (эффективно через словарь)
            id_to_lot_map = {lot.id: lot for lot in analyzed_lots}
            ranked_lots = []
            
            for item in ranked_result_data:
                lot_id = int(item['id'])
                if lot_id in id_to_lot_map:
                    lot = id_to_lot_map[lot_id]
                    score = float(item.get('tournament_score', 0))
                    lot.tournament_score = score
                    self.analyzed_lot_repo.update_score(lot.id, score)
                    ranked_lots.append(lot)

            # 6. Добавляем лоты, которые могли не попасть в турнир (safety first)
            ranked_lot_ids = {lot.id for lot in ranked_lots}
            for lot in analyzed_lots:
                if lot.id not in ranked_lot_ids:
                    ranked_lots.append(lot)

            if ranked_lots:
                top_raw = self.raw_lot_repo.get_by_id(ranked_lots[0].raw_lot_id)
                top_title = top_raw.title if top_raw else "N/A"
                logger.info(f"Турнирный реранкинг завершен. Топ-1: {top_title} (ID: {ranked_lots[0].id})")
            
            return ranked_lots
    

    def _format_deep_search_results(self, analyzed_lots: List[AnalyzedLot], schema: Schema) -> str:
            """Форматирование результатов глубокого поиска для отправки пользователю"""
            logger.info(f"Форматируем {len(analyzed_lots)} результатов глубокого поиска")

            formatted_results = "### 📊 Результаты глубокого анализа\n\n"

            # Ограничиваем количество отображаемых карточек (например, топ-5)
            max_results = 5
            lots_to_show = analyzed_lots[:max_results]

            for i, lot in enumerate(lots_to_show):
                raw_lot = self.raw_lot_repo.get_by_id(lot.raw_lot_id)
                title = raw_lot.title if raw_lot else 'Без названия'
                price = raw_lot.price if raw_lot else 'Цена не указана'
                
                score_str = f" (Рейтинг: {lot.tournament_score})" if (hasattr(lot, 'tournament_score') and lot.tournament_score) else ""
                formatted_results += f"{i+1}. **{title}** — {price}{score_str}\n"

                # 1. Выводим поля из плоской схемы
                for prop_name in schema.json_schema.keys():
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
    

    def _generate_analytical_summary(self, top_lots: List[AnalyzedLot], schema: Schema, topic: str) -> str:
        """Генерация экспертного резюме на основе топ-результатов турнира"""
        logger.info(f"Генерируем аналитическое резюме для темы: {topic}")
        
        if not top_lots:
            return ""

        # Подготавливаем данные о лидерах для LLM
        lots_context = []
        for i, lot in enumerate(top_lots[:5]): # Берем топ-5 для глубокого анализа
            raw = self.raw_lot_repo.get_by_id(lot.raw_lot_id)
            lots_context.append(
                f"Лот #{i+1}: {raw.title}\n"
                f"Цена: {raw.price}\n"
                f"Параметры: {lot.structured_data}\n"
                f"Заметки: {lot.relevance_note}\n"
                f"Визуал: {lot.image_description_and_notes}"
            )

        context_str = "\n\n".join(lots_context)
        
        from utils.llm_client import get_completion
        
        system_prompt = f"""Ты — ведущий эксперт по закупкам и аналитик рынка. 
    Твоя задача: изучить результаты поиска по теме "{topic}" и написать краткое, живое аналитическое резюме.
    У тебя есть список товаров, которые уже отранжированы по качеству/цене в ходе турнира.

    ПРАВИЛА:
    1. Будь краток и профессионален.
    2. Выдели лучшую сделку (Best Buy) и объясни почему.
    3. Дай практический совет: на что нажать, что проверить (например, "цена подозрительно низкая, просите доп. фото" или "это редкая ревизия, надо брать").
    4. Будь критичен. Если все варианты плохие — так и скажи.
    5. Объем: 2-3 компактных абзаца."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Вот топ-5 товаров из моего исследования:\n\n{context_str}\n\nСделай вывод эксперта."}
        ]

        try:
            response = get_completion(messages)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Ошибка при генерации резюме: {e}")
            return "Не удалось сгенерировать аналитический отчет, но результаты поиска ниже."