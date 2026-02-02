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
        logger.info(f"Обрабатываем сообщение для исследования {mr_id}: {message}")

        market_research = self.mr_repo.get_by_id(mr_id)
        if not market_research:
            raise ValueError(f"Исследование с ID {mr_id} не найдено")

        # Добавляем сообщение в историю
        market_research.chat_history.append(ChatMessage(id=str(uuid.uuid4()), role="user", content=message))

        # Подготовим историю чата для LLM
        llm_messages = []
        for msg in market_research.chat_history:
            llm_messages.append({"role": msg.role, "content": msg.content})

        # Добавим системный промпт с описанием инструментов
        system_prompt = """Ты — интеллектуальный агент по исследованию рынка на Avito.
Твоя задача — помогать пользователю искать товары, анализировать цены и характеристики.

**Стиль ответа**
* Запрещено использовать смайлики.  

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
        "name": "initiate_deep_research_planning",
        "description": "Использовать, когда запрос пользователя сложный, размытый или требует сравнения множества характеристик. Переводит диалог в режим планирования схемы поиска.",
        "parameters": {
            "initial_topic": "тема исследования"
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
        market_research.chat_history.append(ChatMessage(id=str(uuid.uuid4()), role="assistant", content=response_content))

        # Проверяем наличие тега вызова инструмента
        tool_match = re.search(r'<tool_call>(.*?)</tool_call>', response_content, re.DOTALL)
        is_tool_call = False

        if tool_match:
            is_tool_call = True
            try:
                # Извлекаем JSON из тега
                tool_json = tool_match.group(1).strip()
                tool_data = json.loads(tool_json)
                
                
                logger.info(f"Вызван инструмент: {tool_data.get('name')}")
                
                # В зависимости от инструмента обновляем состояние
                tool_name = tool_data.get('name')
                if tool_name == "start_quick_search":
                    market_research.state = State.SEARCHING_QUICK
                    # Здесь будет логика запуска быстрого поиска
                elif tool_name == "initiate_deep_research_planning":
                    market_research.state = State.PLANNING_DEEP_RESEARCH
                    # Здесь будет логика планирования глубокого исследования
                    
                # Обновляем исследование в БД
                self.mr_repo.update(market_research)
                
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON инструмента: {e}")
            except Exception as e:
                logger.error(f"Ошибка обработки вызова инструмента: {e}")

            # Сохраняем обновленное исследование
            self.mr_repo.update(market_research)
            logger.info(f"Состояние исследования {mr_id}: {market_research.state}")

        return market_research, is_tool_call