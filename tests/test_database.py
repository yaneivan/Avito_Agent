import pytest
from sqlmodel import Session, select
from database import ChatSession, ChatMessage, DeepResearchSession, SearchSession, Item, ExtractionSchema
from datetime import datetime


def test_create_chat_session(session: Session):
    """Тест создания сессии чата"""
    chat_session = ChatSession(title="Тестовый чат")
    session.add(chat_session)
    session.commit()
    
    assert chat_session.id is not None
    assert chat_session.title == "Тестовый чат"
    assert isinstance(chat_session.created_at, datetime)


def test_create_chat_message(session: Session):
    """Тест создания сообщения в чате"""
    # Сначала создаем сессию
    chat_session = ChatSession(title="Тестовый чат")
    session.add(chat_session)
    session.commit()
    
    # Создаем сообщение
    message = ChatMessage(
        role="user",
        content="Тестовое сообщение",
        chat_session_id=chat_session.id
    )
    session.add(message)
    session.commit()
    
    assert message.id is not None
    assert message.role == "user"
    assert message.content == "Тестовое сообщение"
    assert message.chat_session_id == chat_session.id


def test_create_deep_research_session(session: Session):
    """Тест создания сессии глубокого исследования"""
    research_session = DeepResearchSession(
        query_text="Тестовый запрос",
        status="created",
        stage="interview"
    )
    session.add(research_session)
    session.commit()
    
    assert research_session.id is not None
    assert research_session.query_text == "Тестовый запрос"
    assert research_session.status == "created"
    assert research_session.stage == "interview"


def test_create_extraction_schema(session: Session):
    """Тест создания схемы извлечения данных"""
    schema = ExtractionSchema(
        name="Тестовая схема",
        description="Описание тестовой схемы",
        structure_json='{"field1": {"type": "str", "desc": "Описание"}}'
    )
    session.add(schema)
    session.commit()
    
    assert schema.id is not None
    assert schema.name == "Тестовая схема"
    assert schema.description == "Описание тестовой схемы"
    assert schema.structure_json == '{"field1": {"type": "str", "desc": "Описание"}}'


def test_relationships(session: Session):
    """Тест отношений между сущностями"""
    # Создаем чат-сессию
    chat_session = ChatSession(title="Тестовый чат")
    session.add(chat_session)
    session.commit()
    
    # Создаем сессию глубокого исследования
    research_session = DeepResearchSession(
        query_text="Тестовый запрос",
        status="created",
        stage="interview",
        chat_session_id=chat_session.id
    )
    session.add(research_session)
    session.commit()
    
    # Проверяем, что связь установлена
    retrieved_chat = session.get(ChatSession, chat_session.id)
    assert retrieved_chat.deep_research_session.id == research_session.id
    
    retrieved_research = session.get(DeepResearchSession, research_session.id)
    assert retrieved_research.chat_session.id == chat_session.id