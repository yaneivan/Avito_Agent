import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.processing import ProcessingService, ChatProcessingService
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
    
    with patch('services.processing.Session') as mock_session_class, \
         patch('services.processing.engine') as mock_engine, \
         patch('services.processing.select') as mock_select, \
         patch('services.processing.extract_product_features') as mock_extract:
        
        # Создаем мок-сессию
        mock_session_instance = MagicMock(spec=Session)
        mock_session_class.return_value.__enter__.return_value = mock_session_instance
        
        # Мокаем возвращаемое значение для поиска сессии
        mock_search_session = MagicMock(spec=SearchSession)
        mock_search_session.query_text = "test query"
        mock_search_session.schema_id = None
        mock_session_instance.get.return_value = mock_search_session
        
        # Мокаем результат извлечения признаков
        mock_extract.return_value = {
            "relevance_score": 85,
            "visual_notes": "Хороший товар",
            "specs": {"color": "red", "size": "large"}
        }
        
        # Мокаем результаты запросов
        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = None  # Нет дубликатов
        mock_session_instance.exec.return_value = mock_exec_result
        
        # Вызываем метод
        await service.process_incoming_data(task_id, raw_items)
        
        # Проверяем, что были сделаны правильные вызовы
        assert mock_session_instance.add.called
        assert mock_session_instance.commit.called
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
    
    with patch('services.processing.Session') as mock_session_class, \
         patch('services.processing.engine') as mock_engine:
        
        # Создаем мок-сессию
        mock_session_instance = MagicMock(spec=Session)
        mock_session_class.return_value.__enter__.return_value = mock_session_instance
        
        # Мокаем возвращаемое значение для поиска сессии (None для теста)
        mock_session_instance.get.return_value = None
        
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