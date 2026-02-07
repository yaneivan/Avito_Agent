import uuid
from typing import List, Dict, Any
from models.research_models import MarketResearch, State, ChatMessage, RawLot
from repositories.research_repository import (
    MarketResearchRepository,
    SearchTaskRepository,
    RawLotRepository
)
from utils.image_handler import save_image_from_base64
from utils.logger import logger
from utils.llm_client import get_completion


class QuickSearchService:
    def __init__(
        self,
        mr_repo: MarketResearchRepository,
        task_repo: SearchTaskRepository,
        raw_lot_repo: RawLotRepository
    ):
        self.mr_repo = mr_repo
        self.task_repo = task_repo
        self.raw_lot_repo = raw_lot_repo

    def handle_quick_search_results(self, task_id: int, results: List[Dict]) -> MarketResearch:
        """Обработка результатов быстрого поиска"""
        logger.info(f"Обрабатываем результаты быстрого поиска для задачи {task_id}")

        # Обновляем статус задачи
        task = self.task_repo.update_status(task_id, "completed")
        if not task:
            raise ValueError(f"Задача с ID {task_id} не найдена")

        # Сохраняем "сырые" лоты
        processed_results = []
        for item in results:
            # Если есть изображение в base64, сохраняем его
            image_path = None
            if item.get('image_base64'):
                image_path = save_image_from_base64(item['image_base64'], f"quick_{task_id}")

            # Создаем или обновляем лот
            raw_lot = RawLot(
                url=item.get('url', ''),
                title=item.get('title', ''),
                price=item.get('price', ''),
                description=item.get('description', ''),
                image_path=image_path
            )
            saved_raw_lot = self.raw_lot_repo.create_or_update(raw_lot)

            processed_item = {
                "title": saved_raw_lot.title,
                "price": saved_raw_lot.price,
                "url": saved_raw_lot.url,
                # Нормализуем путь: убираем ./ и меняем \ на /
                "image_path": saved_raw_lot.image_path.replace("\\", "/").replace("./", "") if saved_raw_lot.image_path else None,
                "saved_lot_id": saved_raw_lot.id
                # image_base64 сюда НЕ пишем, чтобы не раздувать историю чата
            }
            processed_results.append(processed_item)

        # Обновляем результаты задачи
        task = self.task_repo.update_results(task_id, processed_results)

        # Получаем исследование
        market_research = self.mr_repo.get_by_id(task.market_research_id)
        if not market_research:
            raise ValueError(f"Исследование с ID {task.market_research_id} не найдено")

        # Формируем сообщение для пользователя с результатами и инструкцией пересказать
        result_message = self._format_quick_search_results(processed_results)

        # Создаем специальное сообщение от пользователя с результатами и инструкцией пересказать
        user_message_with_results = f"{result_message}\n\nПожалуйста, перескажи эти результаты в виде краткого отчета, выделив ключевые моменты."

        # Подготовим историю чата для LLM (без добавления результатов в постоянную историю)
        llm_messages = []
        for msg in market_research.chat_history:
            llm_messages.append({"role": msg.role, "content": msg.content})

        # Добавляем сообщение с результатами как сообщение от пользователя
        llm_messages.append({"role": "user", "content": user_message_with_results})

        # Добавим системный промпт для генерации отчета
        system_prompt = """Ты — интеллектуальный агент по исследованию рынка на Avito. 
Твоя задача — **кратко и по существу** предоставить пользователю сводку по результатам поиска, обобщив найденные товары и выделив ключевые особенности.
Тебе представленно несколько конкретных результатов поиска.  
**Ответь не более чем в 3-5 абзацев.** Сформируй **концентрированный** отчет, основываясь на предоставленных результатах поиска. 
Укажи **основные** модели, **средний** ценовой диапазон и **самые важные** рекомендации. 
Избегай избыточных деталей для каждого товара, фокусируйся на общих трендах и самых интересных вариантах."""

        llm_messages.insert(0, {"role": "system", "content": system_prompt})

        # Выполняем вызов LLM для генерации отчета
        response = get_completion(llm_messages)
        report_content = response.content

        logger.info(f"Сгенерирован отчет на основе результатов поиска: {report_content}")

        # Возвращаемся к состоянию CHAT
        market_research.state = State.CHAT

        # Добавляем только отчет в историю чата, не добавляя результаты поиска
        report_message = ChatMessage(
            id=str(uuid.uuid4()), 
            role="assistant", 
            content=report_content,
            items=processed_results[:5]
            )
        logger.info(f"items в report_message: {processed_results[:5]}")
        market_research.chat_history.append(report_message)

        # Обновляем всю запись в базе данных, чтобы сохранить изменения в истории чата и состоянии
        self.mr_repo.update(market_research)

        logger.info(f"Результаты быстрого поиска обработаны для исследования {task.market_research_id}")
        return market_research

    def _format_quick_search_results(self, results: List[Dict]) -> str:
        """Форматирование результатов быстрого поиска для отправки пользователю"""
        logger.info(f"Форматируем {len(results)} результатов быстрого поиска")

        if not results:
            return "К сожалению, не удалось найти подходящие товары по вашему запросу."

        formatted_results = "Результаты поиска:\n\n"

        # Ограничиваем количество отображаемых результатов
        max_results = 5
        results_to_show = results[:max_results]

        for i, item in enumerate(results_to_show):
            title = item.get('title', 'Без названия')
            price = item.get('price', 'Цена не указана')
            url = item.get('url', '')

            formatted_results += f"{i+1}. {title} - {price}\n"

            # Добавляем URL, если доступен
            if url:
                formatted_results += f"   Ссылка: {url}\n"

            # Добавляем описание, если доступно
            description = item.get('description', '')
            if description:
                # Обрезаем описание до 100 символов, если оно слишком длинное
                desc_preview = description if len(description) <= 100 else description[:97] + "..."
                formatted_results += f"   Описание: {desc_preview}\n"

            formatted_results += "\n"

        # Если есть больше результатов, чем показываем, уведомляем пользователя
        if len(results) > max_results:
            formatted_results += f"... и еще {len(results) - max_results} товаров.\n"

        return formatted_results