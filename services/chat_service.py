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

**Инструменты:**
Тебе доступно два инструмента 
1. Quick search - быстрый поисковый запрос. То что ты напишешь, будет вставлено в поисковик на маркетплейсе БУ товаров Авито (аналог ebay). Тебе будут возвращены результаты поиска. 
2. Deep Research - глубокий поиск. Ты задаешь поисковый запрос, но дополнительно объясняешь тему и контекст исследования. Ты должен также задать JSON схему для описания структуры данных. 
Схема будет использована для извлечения характеристик товаров. Схема описывает структуру данных, которая будет заполняться для Каждого найденного лота товара. 
Например, для автомобиля в схеме может быть поле "пробег" или "марка". Для мобильного телефона "процессор", "объем памяти", "диагональ". 
Схема это **НЕ** фильтр. Это то, на что пользователь обращает внимание при выборе. 
В дальнейшем будет выполняться сортировка и фильтрация на основании заполненных схем заданного типа. 

**Правила Deep Research:**
1. Будь креативен, сам предлагай пользователю критерии сравнения. Предположи на что пользователь обратит внимание при выборе. 
2. plan_deep_research нужен для того чтобы предложить пользователю ЧЕРНОВИК исследования. Вместе с ним напиши пользователю что-то типа "подойдет ли такой запрос на исследование?"
2.1. Если пользователь согласился на предложенный черновик, тогда вызови инструмент execute_deep_research (полностью повторив те параметры, с которыми согласился пользователь), это запустит реальный поиск. 
2.2. Если пользователь предложил что-то изменить, предложи черновик с изменениями. 
2.3. Если пользователь не хочет запускать глубокое исследование, продолжай общение. plan_deep_research не нужно отменять. 

**Стиль ответа:**
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
        "description": "Использовать, когда запрос пользователя сложный и требует сравнения характеристик. Переводит диалог в режим планирования. В этой фазе ты предлагаешь параметры поиска и структуру данных (схему), чтобы пользователь их одобрил.",
        "parameters": {
            "topic": "тема исследования",
            "context_summary": "краткий пересказ чата (зачем ищем)", 
            "schema": "JSON-схема (какие поля извлекать из объявления, формат см. ниже в правилах)", 
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

**ПРАВИЛА ФОРМАТИРОВАНИЯ ДЛЯ ПАРАМЕТРА 'schema':**
Параметр `schema` должен быть плоским JSON-объектом, где ключи — это названия полей (на английском, snake_case), а значения — описание типа данных.
Допустимые типы: "string", "integer", "boolean".
Поле "optional": true/false указывает, можно ли оставить поле пустым.
Поле "enum": ["val1", "val2"] (список строк) можно добавить к типу "string", чтобы ограничить возможные значения.

Пример заполнения параметра `schema` (для поиска iPhone):
{
  "battery_health": {
    "type": "integer",
    "description": "Процент износа аккумулятора",
    "optional": false
  },
  "storage_capacity": {
    "type": "string",
    "description": "Объем памяти",
    "enum": ["64GB", "128GB", "256GB", "512GB", "1TB"],
    "optional": false
  },
  "has_scratches": {
    "type": "boolean",
    "description": "Есть ли царапины на экране или корпусе",
    "optional": true
  }
}

Если ты вызываешь инструмент, оберни JSON вызова в тег <tool_call>.
Ты можешь совмещать обычный текст ответа и вызов инструмента.
Пример:
"Хорошо, я поищу варианты. <tool_call>{"name": "start_quick_search", "query": "название", "needs_visual": false}</tool_call>"
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