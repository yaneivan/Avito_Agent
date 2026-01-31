import pytest
from fastapi.testclient import TestClient
from main import app
from sqlmodel import Session
from database import ChatSession, DeepResearchSession
from dependencies import get_session
import json


def test_create_deep_research_session(client: TestClient, session: Session):
    """Тест создания сессии глубокого исследования"""
    def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    # Сначала создаем чат-сессию
    chat_response = client.post("/api/chats")
    assert chat_response.status_code == 200
    chat_data = chat_response.json()
    chat_id = chat_data["id"]
    
    # Отправляем сообщение для запуска глубокого исследования
    history = [
        {"role": "user", "content": "Хочу купить ноутбук"},
        {"role": "assistant", "content": "Какой бюджет вы рассматриваете?"},
        {"role": "user", "content": "Бюджет 50000 рублей"}
    ]
    
    research_request = {
        "history": history,
        "chat_id": chat_id
    }
    
    response = client.post("/api/deep_research/chat", json=research_request)
    assert response.status_code == 200
    
    data = response.json()
    assert "type" in data
    assert "research_id" in data
    
    # Проверяем, что сессия глубокого исследования создана
    research_session = session.get(DeepResearchSession, data["research_id"])
    assert research_session is not None
    assert research_session.chat_session_id == chat_id
    
    # Убираем подмену
    app.dependency_overrides.clear()


def test_get_research_status(client: TestClient, session: Session):
    """Тест получения статуса сессии глубокого исследования"""
    # Создаем сессию глубокого исследования вручную
    research_session = DeepResearchSession(
        query_text="Тестовый запрос",
        status="created",
        stage="interview"
    )
    session.add(research_session)
    session.commit()
    
    def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    response = client.get(f"/api/deep_research/status/{research_session.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "created"
    assert data["stage"] == "interview"
    
    # Убираем подмену
    app.dependency_overrides.clear()


def test_get_chat_by_research_id(client: TestClient, session: Session):
    """Тест получения чата по ID сессии глубокого исследования"""
    # Создаем чат-сессию
    chat_session = ChatSession(title="Тестовый чат")
    session.add(chat_session)
    session.commit()
    
    # Создаем сессию глубокого исследования, связанную с чатом
    research_session = DeepResearchSession(
        query_text="Тестовый запрос",
        status="created",
        stage="interview",
        chat_session_id=chat_session.id
    )
    session.add(research_session)
    session.commit()
    
    def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    response = client.get(f"/api/deep_research/get_chat_by_research/{research_session.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["chat_id"] == chat_session.id
    
    # Убираем подмену
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_deep_research_agent_integration():
    """Интеграционный тест агента глубокого исследования"""
    from llm_engine import deep_research_agent
    
    history = [
        {"role": "user", "content": "Хочу купить ноутбук"},
        {"role": "assistant", "content": "Какой бюджет вы рассматриваете?"},
        {"role": "user", "content": "Бюджет 50000 рублей"}
    ]
    
    current_state = {
        "stage": "interview",
        "query_text": "ноутбук",
        "interview_data": None,
        "schema_agreed": None
    }
    
    # Тестируем, что функция не падает
    try:
        result = await deep_research_agent(history, current_state)
        # Проверяем, что результат имеет ожидаемую структуру
        assert "type" in result
        assert result["type"] in ["chat", "tool_call"]
    except Exception as e:
        # Если происходит ошибка из-за отсутствия LLM, это нормально для теста
        assert "No LLM" in str(e) or "Connection refused" in str(e) or "API" in str(e)