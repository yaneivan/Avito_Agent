import re
import json
import uuid
from typing import List, Tuple
from models.research_models import MarketResearch, ChatMessage, State
from repositories.research_repository import MarketResearchRepository
from utils.llm_client import get_completion
from utils.logger import logger
from config import MAX_CHAT_HISTORY_TOKENS


class ChatService:
    def __init__(self, mr_repo: MarketResearchRepository):
        self.mr_repo = mr_repo

    def process_user_message(self, mr_id: int, message: str, images: List[str] = []) -> Tuple[MarketResearch, bool]:
        """Обработка сообщения от пользователя с использованием единого вызова LLM с инструментами"""
        logger.info(f"Начало обработки сообщения пользователя. MR ID: {mr_id}, Сообщение: '{message}'")

        # Логируем длину истории перед обработкой
        market_research = self.mr_repo.get_by_id(mr_id)
        if not market_research:
            raise ValueError(f"Исследование с ID {mr_id} не найдено")

        logger.info(f"Длина истории чата перед обработкой: {len(market_research.chat_history)}")
        logger.info(f"Содержимое истории перед обработкой: {[msg.content for msg in market_research.chat_history]}")

        user_msg = ChatMessage(id=str(uuid.uuid4()), role="user", content=message)
        market_research.chat_history.append(user_msg)
        logger.info(f"Добавлено сообщение пользователя к истории. ID: {user_msg.id}, Новая длина: {len(market_research.chat_history)}")
        logger.info(f"Содержимое истории после добавления сообщения пользователя: {[msg.content for msg in market_research.chat_history]}")

        # Подготовим историю чата для LLM
        llm_messages = []
        for msg in market_research.chat_history:
            llm_messages.append({"role": msg.role, "content": msg.content})

        # Добавим системный промпт с описанием инструментов
        system_prompt = """Ты — интеллектуальный агент по исследованию рынка на Avito.
Твоя задача — помогать пользователю искать товары, анализировать цены и характеристики.

**ВАЖНЫЕ ПРАВИЛА:**
1. Твои внутренни знания о ценах и видах товарах утсарели. **Ты НЕ знаешь, сколько стоят товары сейчас и какие модели и характеристики сейчас актуальны.** Актуальные данные ты можешь получить через поиск только. Запрещено отвечать по памяти. 


**Стиль ответа:**
* Запрещено использовать смайлики.  
* Будь краток и профессионален. 

У тебя есть доступ к следующим инструментам. Если ты решил выполнить поиск, ты ОБЯЗАН использовать формат XML:

<tools>
[
    {
        "name": "start_quick_search",
        "description": "Использовать для быстрого поиска конкретных товаров, когда запрос пользователя прост и понятен.",
        "parameters": {
            "query": "строка, поисковый запрос для Avito",
            "needs_visual": "bool, нужно ли анализировать изображения (одежда, дизайн) или достаточно текста (техника)"
        }
    },
    {
        "name": "plan_deep_research",
        "description": "Использовать, когда запрос пользователя сложный, и требует сравнения множества характеристик из нескольких объявлений. Переводит диалог в режим планирования схемы поиска. Это подготовительная фаза поиска. В этой фазе нужно вбить параметры поиска, для того чтобы пользователь их одобрил или внес правки. ",
        "parameters": {
            "topic": "тема исследования",
            "context_summary": "краткий пересказ чата (зачем ищем)", 
            "schema": "JSON-схема (какие поля извлекать из объявления)", 
            "limit": "сколько объявлений просмотреть (по умолчанию 50)", 
            "needs_visual": bool (нужно ли изучать изображение или достаточно прочитать только текст объявления)
        }
    }, 
    {
    "name": "execute_deep_research",
    "description": "Запускает глубокое исследование после того, как пользователь согласился с параметрами из plan_deep_research. Разрешено выполнять строго после согласования в plan_deep_research. Параметры аналогичные планированию. ",
    "parameters": {
        "topic": "...",
        "context_summary": "...", 
        "schema": "JSON-схема", 
        "limit": "...", 
        "needs_visual": bool 
        }
    }
]
</tools>

Если ты вызываешь инструмент, оберни JSON вызова в тег <tool_call>.
Ты можешь совмещать обычный текст ответа и вызов инструмента.
Пример:
"Хорошо, я поищу для вас варианты. <tool_call>{ "name": "start_quick_search", ... }</tool_call>"
"""

        llm_messages.insert(0, {"role": "system", "content": system_prompt})

        # Выполняем единый вызов LLM
        response = get_completion(llm_messages)
        response_content = response.content
        logger.info(f"Ответ LLM: {response_content}")

        # Сохраняем ответ в историю чата
        assistant_msg = ChatMessage(id=str(uuid.uuid4()), role="assistant", content=response_content)
        market_research.chat_history.append(assistant_msg)
        logger.info(f"Добавлен ответ LLM к истории. ID: {assistant_msg.id}, Новая длина: {len(market_research.chat_history)}")
        logger.info(f"Содержимое истории после добавления ответа LLM: {[msg.content for msg in market_research.chat_history]}")

        # Проверяем наличие тега вызова инструмента
        tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response_content, re.DOTALL)
        is_tool_call = False

        if tool_match:
            is_tool_call = True

        # Сохраняем обновленное исследование
        logger.info(f"Сохранение обновленного исследования с {len(market_research.chat_history)} сообщениями после обработки инструмента")
        self.mr_repo.update(market_research)
        logger.info(f"Состояние исследования {mr_id}: {market_research.state}")
        logger.info(f"Финальное содержимое истории: {[msg.content for msg in market_research.chat_history]}")

        return market_research, is_tool_call