import pytest
from datetime import datetime
from models.research_models import (
    MarketResearch, 
    State, 
    ChatMessage, 
    Schema, 
    RawLot, 
    AnalyzedLot, 
    SearchTask
)


def test_market_research_creation():
    """Тест создания исследования рынка"""
    mr = MarketResearch()
    
    # Проверяем начальное состояние
    assert mr.state == State.CHAT
    assert mr.chat_history == []
    assert mr.search_tasks == []
    assert mr.created_at is not None
    assert mr.updated_at is not None


def test_chat_message_creation():
    """Тест создания сообщения чата"""
    content = "Тестовое сообщение"
    message = ChatMessage(role="user", content=content)
    
    assert message.role == "user"
    assert message.content == content
    assert message.timestamp is not None
    assert message.images == []


def test_schema_creation():
    """Тест создания схемы"""
    schema_data = {
        "type": "object",
        "properties": {
            "title": {"type": "string"}
        }
    }
    schema = Schema(name="Тестовая схема", description="Описание", json_schema=schema_data)
    
    assert schema.name == "Тестовая схема"
    assert schema.description == "Описание"
    assert schema.json_schema == schema_data


def test_raw_lot_creation():
    """Тест создания сырого лота"""
    raw_lot = RawLot(
        url="https://example.com",
        title="Тестовый товар",
        price="10000",
        description="Описание товара"
    )
    
    assert raw_lot.url == "https://example.com"
    assert raw_lot.title == "Тестовый товар"
    assert raw_lot.price == "10000"
    assert raw_lot.description == "Описание товара"
    assert raw_lot.created_at is not None


def test_analyzed_lot_creation():
    """Тест создания проанализированного лота"""
    analyzed_lot = AnalyzedLot(
        raw_lot_id=1,
        schema_id=1,
        structured_data={"color": "red"},
        visual_notes="Красный цвет",
        image_description="Красный товар"
    )
    
    assert analyzed_lot.raw_lot_id == 1
    assert analyzed_lot.schema_id == 1
    assert analyzed_lot.structured_data == {"color": "red"}
    assert analyzed_lot.visual_notes == "Красный цвет"
    assert analyzed_lot.image_description == "Красный товар"
    assert analyzed_lot.created_at is not None


def test_search_task_creation():
    """Тест создания задачи поиска"""
    search_task = SearchTask(
        market_research_id=1,
        mode="quick",
        query="поиск товара",
        needs_visual=True
    )
    
    assert search_task.market_research_id == 1
    assert search_task.mode == "quick"
    assert search_task.query == "поиск товара"
    assert search_task.needs_visual is True
    assert search_task.status == "pending"
    assert search_task.results == []
    assert search_task.created_at is not None


def test_market_research_state_transitions():
    """Тест переходов между состояниями исследования"""
    mr = MarketResearch()
    
    # Проверяем начальное состояние
    assert mr.state == State.CHAT
    
    # Меняем состояние
    mr.state = State.SEARCHING_QUICK
    assert mr.state == State.SEARCHING_QUICK
    
    # Еще одно изменение состояния
    mr.state = State.PLANNING_DEEP_RESEARCH
    assert mr.state == State.PLANNING_DEEP_RESEARCH
    
    # И еще одно
    mr.state = State.DEEP_RESEARCH
    assert mr.state == State.DEEP_RESEARCH