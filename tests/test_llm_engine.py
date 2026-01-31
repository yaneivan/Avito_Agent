import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from llm_engine import decide_action, deep_research_agent, extract_product_features, rank_items_group, summarize_search_results


@pytest.mark.asyncio
async def test_decide_action_basic():
    """Тест базовой функции решения действия"""
    history = [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуйте! Чем могу помочь?"},
        {"role": "user", "content": "Хочу купить MacBook"}
    ]

    # Создаем мок для клиента
    with patch('llm_engine.client') as mock_client:
        # Создаем мок-ответ
        mock_choice = AsyncMock()
        mock_choice.message.content = '''
        {
          "reasoning": "Пользователь хочет купить MacBook",
          "action": "search",
          "search_query": "MacBook",
          "limit": 5,
          "schema_name": "laptop",
          "reply": "Ищу MacBook"
        }
        '''

        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]

        # Устанавливаем возвращаемое значение для асинхронного вызова
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await decide_action(history)

        assert result["action"] == "search"
        assert result["search_query"] == "MacBook"


@pytest.mark.asyncio
async def test_deep_research_agent():
    """Тест агента глубокого исследования"""
    history = [
        {"role": "user", "content": "Хочу купить ноутбук"},
        {"role": "assistant", "content": "Какой бюджет вы рассматриваете?"}
    ]

    current_state = {
        "stage": "interview",
        "query_text": "ноутбук",
        "interview_data": None,
        "schema_agreed": None
    }

    # Создаем мок для клиента
    with patch('llm_engine.client') as mock_client:
        # Создаем мок-ответ
        mock_choice = AsyncMock()
        mock_choice.message.content = "Расскажите больше о ваших требованиях к ноутбуку"
        mock_choice.finish_reason = "stop"

        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]

        # Устанавливаем возвращаемое значение для асинхронного вызова
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await deep_research_agent(history, current_state)

        assert result["type"] == "chat"
        assert "message" in result


@pytest.mark.asyncio
async def test_extract_product_features():
    """Тест извлечения характеристик продукта"""
    title = "MacBook Air M1 2020"
    description = "Отличное состояние, работает без нареканий"
    price = "75000 руб."
    img_path = None
    criteria = "ноутбук для работы"
    extraction_schema = {
        "cpu": {"type": "str", "desc": "Процессор"},
        "ram_gb": {"type": "int", "desc": "Оперативная память в ГБ"}
    }

    # Создаем мок для клиента
    with patch('llm_engine.client') as mock_client:
        # Создаем мок-ответы для двух вызовов (извлечение и релевантность)
        mock_choice1 = AsyncMock()
        mock_choice1.message.content = '''
        {
          "cpu": "Apple M1",
          "ram_gb": 8
        }
        '''

        mock_response1 = AsyncMock()
        mock_response1.choices = [mock_choice1]

        mock_choice2 = AsyncMock()
        mock_choice2.message.content = '''
        {
          "relevance_score": 90,
          "visual_notes": "Хорошее внешнее состояние"
        }
        '''

        mock_response2 = AsyncMock()
        mock_response2.choices = [mock_choice2]

        # Мокаем два разных вызова
        mock_client.chat.completions.create = AsyncMock(side_effect=[mock_response1, mock_response2])

        result = await extract_product_features(title, description, price, img_path, criteria, extraction_schema)

        assert result["relevance_score"] == 90
        assert "visual_notes" in result
        assert "specs" in result
        if "specs" in result and result["specs"]:
            assert result["specs"].get("cpu") == "Apple M1"
            assert result["specs"].get("ram_gb") == 8


@pytest.mark.asyncio
async def test_rank_items_group():
    """Тест ранжирования группы товаров"""
    items_data = [
        {"id": 1, "title": "Товар 1", "price": "1000"},
        {"id": 2, "title": "Товар 2", "price": "2000"}
    ]
    criteria = "лучшее соотношение цена-качество"

    # Создаем мок для клиента
    with patch('llm_engine.client') as mock_client:
        mock_choice = AsyncMock()
        mock_choice.message.content = '''
        {
          "ranks": [
            {"item_id": 1, "score": 5},
            {"item_id": 2, "score": 4}
          ]
        }
        '''

        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]

        # Устанавливаем возвращаемое значение для асинхронного вызова
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await rank_items_group(items_data, criteria)

        assert "ranks" in result
        assert len(result["ranks"]) == 2
        assert result["ranks"][0]["item_id"] == 1


@pytest.mark.asyncio
async def test_summarize_search_results():
    """Тест генерации сводки результатов поиска"""
    query = "ноутбук для работы"

    # Создаем фейковые объекты Item с необходимыми атрибутами
    class MockItem:
        def __init__(self, title, price, visual_notes):
            self.title = title
            self.price = price
            self.visual_notes = visual_notes

    items = [
        MockItem("MacBook Air", "75000", "Отличное состояние"),
        MockItem("Lenovo ThinkPad", "50000", "Работает хорошо")
    ]

    # Создаем мок для клиента
    with patch('llm_engine.client') as mock_client:
        mock_choice = AsyncMock()
        mock_choice.message.content = '''
        {
          "summary": "Найдено 2 подходящих ноутбука",
          "reasoning": "Оба варианта подходят под критерии"
        }
        '''

        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]

        # Устанавливаем возвращаемое значение для асинхронного вызова
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await summarize_search_results(query, items)

        assert result["summary"] == "Найдено 2 подходящих ноутбука"
        assert "reasoning" in result