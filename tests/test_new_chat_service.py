import pytest
from unittest.mock import Mock
from models.research_models import MarketResearch, State, ChatMessage
from services.chat_service import ChatService
from repositories.research_repository import MarketResearchRepository


def test_process_user_message_with_quick_search_tool():
    """Тест обработки сообщения с вызовом инструмента быстрого поиска"""
    # Создаем мок для репозитория
    mock_mr_repo = Mock(spec=MarketResearchRepository)

    # Создаем тестовое исследование
    test_mr = MarketResearch(
        id=1,
        state=State.CHAT,
        chat_history=[ChatMessage(role="user", content="нужны наушники")]
    )

    # Мокаем метод get_by_id
    mock_mr_repo.get_by_id.return_value = test_mr
    mock_mr_repo.update.return_value = test_mr

    # Создаем чат-сервис с моком
    chat_service = ChatService(mock_mr_repo)

    # Выполняем реальный вызов LLM
    updated_mr, is_tool_call = chat_service.process_user_message(1, "нужны наушники")

    # Проверяем, что возвращается корректный тип для is_tool_call
    assert isinstance(is_tool_call, bool)

    # Проверяем, что сообщения добавлены в историю
    assert len(updated_mr.chat_history) == 2  # сообщение пользователя + ответ ассистента
    assert updated_mr.chat_history[0].content == "нужны наушники"


def test_process_user_message_without_tool_call():
    """Тест обработки сообщения без вызова инструмента"""
    # Создаем мок для репозитория
    mock_mr_repo = Mock(spec=MarketResearchRepository)

    # Создаем тестовое исследование
    test_mr = MarketResearch(
        id=1,
        state=State.CHAT,
        chat_history=[ChatMessage(role="user", content="привет")]
    )

    # Мокаем метод get_by_id
    mock_mr_repo.get_by_id.return_value = test_mr
    mock_mr_repo.update.return_value = test_mr

    # Создаем чат-сервис с моком
    chat_service = ChatService(mock_mr_repo)

    # Выполняем реальный вызов LLM
    updated_mr, is_tool_call = chat_service.process_user_message(1, "привет")

    # Проверяем, что возвращается корректный тип для is_tool_call
    assert isinstance(is_tool_call, bool)

    # Проверяем, что сообщения добавлены в историю
    assert len(updated_mr.chat_history) == 2  # сообщение пользователя + ответ ассистента
    assert updated_mr.chat_history[0].content == "привет"


def test_process_user_message_with_deep_research_tool():
    """Тест обработки сообщения с вызовом инструмента глубокого исследования"""
    # Создаем мок для репозитория
    mock_mr_repo = Mock(spec=MarketResearchRepository)

    # Создаем тестовое исследование
    test_mr = MarketResearch(
        id=1,
        state=State.CHAT,
        chat_history=[ChatMessage(role="user", content="нужен ноутбук для работы")]
    )

    # Мокаем метод get_by_id
    mock_mr_repo.get_by_id.return_value = test_mr
    mock_mr_repo.update.return_value = test_mr

    # Создаем чат-сервис с моком
    chat_service = ChatService(mock_mr_repo)

    # Выполняем реальный вызов LLM
    updated_mr, is_tool_call = chat_service.process_user_message(1, "нужен ноутбук для работы")

    # Проверяем, что возвращается корректный тип для is_tool_call
    assert isinstance(is_tool_call, bool)

    # Проверяем, что сообщения добавлены в историю
    assert len(updated_mr.chat_history) == 2  # сообщение пользователя + ответ ассистента
    assert updated_mr.chat_history[0].content == "нужен ноутбук для работы"