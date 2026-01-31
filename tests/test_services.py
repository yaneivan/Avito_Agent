import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.services import ProcessingService, ItemProcessingService
from core.services import ChatProcessingService
from database import Item, SearchSession, DeepResearchSession
from schemas import ItemSchema
from sqlmodel import Session
import json


@pytest.mark.asyncio
async def test_processing_service_process_incoming_data():
    """Тест обработки входящих данных сервисом"""
    service = ProcessingService()

    # Создаем фейковый объект ItemDTO
    item_dto = ItemSchema(
        title="Тестовый товар",
        price="10000",
        url="https://example.com/item1",
        description="Описание тестового товара",
        local_path="images/test.jpg",
        structured_data={"color": "red", "size": "large"}
    )

    raw_items = [item_dto]
    task_id = 1

    # Мокаем репозитории, которые используются в новом ProcessingService
    with patch('core.services.SearchSessionRepository') as mock_session_repo, \
         patch('core.services.ExtractionSchemaRepository') as mock_schema_repo, \
         patch('core.services.ItemRepository') as mock_item_repo, \
         patch('core.services.SearchItemLinkRepository') as mock_link_repo, \
         patch('core.services.extract_product_features') as mock_extract:

        # Мокаем возвращаемое значение для поиска сессии
        mock_search_session = MagicMock(spec=SearchSession)
        mock_search_session.query_text = "test query"
        mock_search_session.schema_id = None
        mock_search_session.deep_research_session_id = None
        mock_session_repo.get_session_by_id.return_value = mock_search_session

        # Мокаем результат извлечения признаков
        mock_extract.return_value = {
            "relevance_score": 85,
            "visual_notes": "Хороший товар",
            "specs": {"color": "red", "size": "large"}
        }

        # Мокаем создание товара
        mock_item = MagicMock(spec=Item)
        mock_item.id = 1
        mock_item.title = "Тестовый товар"
        mock_item.relevance_score = 85
        mock_item.url = "https://example.com/item1"
        mock_item_repo.create_item.return_value = mock_item
        mock_item_repo.get_item_by_url.return_value = None  # Нет дубликата

        # Вызываем метод
        await service.process_incoming_data(task_id, raw_items)

        # Проверяем, что были сделаны правильные вызовы
        mock_item_repo.create_item.assert_called()
        mock_extract.assert_called_once()


@pytest.mark.asyncio
async def test_chat_processing_service():
    """Тест сервиса обработки чата"""
    service = ChatProcessingService()

    user_message = "Хочу купить ноутбук"
    chat_history = [
        {"role": "user", "content": "Привет"},
        {"role": "assistant", "content": "Здравствуйте! Чем могу помочь?"},
        {"role": "user", "content": user_message}
    ]

    # Функция decide_action импортируется внутри метода как from llm_engine import decide_action
    # Поэтому нужно замокать в модуле llm_engine
    with patch('llm_engine.decide_action') as mock_decide:
        expected_decision = {
            "reasoning": "Пользователь хочет купить ноутбук",
            "action": "search",
            "search_query": "ноутбук",
            "limit": 5,
            "schema_name": "laptop",
            "reply": "Ищу ноутбук"
        }
        mock_decide.return_value = expected_decision

        result = await service.process_user_message(user_message, chat_history)

        assert result["decision"] == expected_decision


@pytest.mark.asyncio
async def test_processing_service_with_empty_items():
    """Тест обработки пустого списка товаров"""
    service = ProcessingService()

    raw_items = []
    task_id = 1

    # Мокаем репозитории, которые используются в новом ProcessingService
    with patch('core.services.SearchSessionRepository') as mock_session_repo:

        # Мокаем возвращаемое значение для поиска сессии (None для теста)
        mock_session_repo.get_session_by_id.return_value = None

        # Вызываем метод
        await service.process_incoming_data(task_id, raw_items)

        # В этом случае должна быть ошибка, потому что сессия не найдена
        # Но сам метод не должен падать


def test_item_serialization():
    """Тест сериализации элемента"""
    item = Item(
        url="https://example.com/item1",
        title="Тестовый товар",
        price="10000",
        description="Описание тестового товара",
        raw_json=json.dumps({"original_field": "value"})
    )
    
    serialized = item.model_dump()
    
    assert serialized["url"] == "https://example.com/item1"
    assert serialized["title"] == "Тестовый товар"
    assert serialized["price"] == "10000"
    assert serialized["description"] == "Описание тестового товара"