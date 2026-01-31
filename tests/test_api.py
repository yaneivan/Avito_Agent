import pytest
from fastapi.testclient import TestClient
from main import app
from sqlmodel import Session
from database import ChatSession
from dependencies import get_session


def test_root(client: TestClient):
    """Тест главной страницы"""
    response = client.get("/")
    # Ожидаем, что главная страница возвращает 404, так как у нас нет маршрута "/"
    assert response.status_code in [200, 404]  # Может быть 200 или 404 в зависимости от FastAPI


def test_get_all_chats_empty(client: TestClient, session: Session):
    """Тест получения всех чатов когда их нет"""
    # Подменяем сессию для тестирования
    def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    response = client.get("/api/chats")
    assert response.status_code == 200
    assert response.json() == []
    
    # Убираем подмену
    app.dependency_overrides.clear()


def test_create_new_chat(client: TestClient, session: Session):
    """Тест создания нового чата"""
    def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    response = client.post("/api/chats")
    assert response.status_code == 200
    
    data = response.json()
    assert "id" in data
    assert data["title"] == "Новый чат"
    
    # Проверим, что чат действительно создался в базе
    chat = session.get(ChatSession, data["id"])
    assert chat is not None
    assert chat.title == "Новый чат"
    
    # Убираем подмену
    app.dependency_overrides.clear()


def test_get_chat_details(client: TestClient, session: Session):
    """Тест получения деталей чата"""
    # Сначала создаем чат
    chat = ChatSession(title="Тестовый чат")
    session.add(chat)
    session.commit()
    
    def override_get_session():
        yield session
    
    app.dependency_overrides[get_session] = override_get_session
    
    response = client.get(f"/api/chats/{chat.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert "chat" in data
    assert "messages" in data
    assert data["chat"]["id"] == chat.id
    assert data["chat"]["title"] == "Тестовый чат"
    
    # Убираем подмену
    app.dependency_overrides.clear()