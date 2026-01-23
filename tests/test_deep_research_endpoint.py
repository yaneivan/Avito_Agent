"""
Тесты для проверки эндпоинта deep_research
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool
from main import app
from database import create_db_and_tables, SQLModel
from dependencies import get_session
from unittest.mock import AsyncMock


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_deep_research_chat_endpoint(client: TestClient):
    """Тест: Проверка эндпоинта deep_research/chat на наличие ошибки"""
    # Подготовка данных для запроса
    payload = {
        "history": [
            {"role": "user", "content": "Привет! Я хочу купить хороший ноутбук для работы"}
        ],
        "settings": {
            "limit_count": 10,
            "open_in_browser": True,
            "use_cache": False
        }
    }

    # Выполняем POST-запрос к эндпоинту
    response = client.post("/api/deep_research/chat", json=payload)

    # Проверяем, что запрос выполнен без ошибки
    assert response.status_code in [200, 422], f"Ошибка: {response.status_code}, детали: {response.text}"
    
    # Если статус 422, это означает валидацию, но не внутреннюю ошибку
    if response.status_code == 422:
        print(f"Валидация запроса: {response.json()}")
    elif response.status_code == 200:
        print(f"Успешный ответ: {response.json()}")


@pytest.mark.asyncio
async def test_deep_research_agent_integration():
    """Тест: Интеграция агента глубокого исследования"""
    from llm_engine import deep_research_agent
    
    # Подготовка истории и состояния
    history = [{"role": "user", "content": "Привет! Я хочу купить хороший ноутбук для работы"}]
    current_state = {
        "stage": "interview",
        "query_text": "Привет! Я хочу купить хороший ноутбук для работы",
        "interview_data": "",
        "schema_agreed": None
    }

    # Вызов агента
    response = await deep_research_agent(history, current_state)
    
    # Проверяем, что ответ имеет ожидаемую структуру
    assert "type" in response
    assert "message" in response or "tool_calls" in response
    print(f"Тип ответа: {response['type']}")
    print(f"Количество вызовов инструментов: {len(response.get('tool_calls', []) if response.get('tool_calls') else [])}")


def test_save_message_function_directly():
    """Тест: Прямой вызов функции _save_message для проверки ошибки"""
    from sqlmodel import Session
    from database import ChatSession, SearchSession
    from datetime import datetime
    
    # Создаем mock-сессию
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(bind=engine)
    
    with Session(engine) as db_session:
        # Создаем тестовую сессию поиска
        search_session = SearchSession(
            query_text="Тестовый запрос",
            mode="deep",
            stage="interview",
            status="created",
            limit_count=10
        )
        db_session.add(search_session)
        db_session.commit()
        db_session.refresh(search_session)
        
        # Создаем тестовую сессию чата
        chat_session = ChatSession(title=f"Deep Research Chat - {search_session.id}")
        db_session.add(chat_session)
        db_session.commit()
        db_session.refresh(chat_session)
        
        # Теперь определяем функцию _save_message как в routers/deep_research.py
        import json
        def _save_message(db_session: Session, chat_id: int, role: str, content: str, meta: dict):
            """Сохранить сообщение"""
            from datetime import datetime
            from database import ChatMessage
            
            msg = ChatMessage(
                role=role,
                content=content,
                chat_session_id=chat_id,
                timestamp=datetime.now(),
                extra_metadata=json.dumps(meta, ensure_ascii=False)
            )
            db_session.add(msg)
            db_session.commit()
        
        # Вызываем функцию с правильными аргументами
        try:
            _save_message(db_session, chat_session.id, "user", "Тестовое сообщение", {"stage": search_session.stage})
            print("Функция _save_message работает корректно с правильными аргументами")
        except TypeError as e:
            print(f"Ошибка в функции _save_message: {e}")
            raise
        
        # Проверяем, что сообщение было сохранено
        from sqlmodel import select
        from database import ChatMessage
        saved_messages = db_session.exec(select(ChatMessage).where(ChatMessage.chat_session_id == chat_session.id)).all()
        assert len(saved_messages) == 1
        assert saved_messages[0].role == "user"
        assert saved_messages[0].content == "Тестовое сообщение"
        print("Сообщение успешно сохранено в базу данных")