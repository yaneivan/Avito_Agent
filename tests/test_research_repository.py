import pytest
from unittest.mock import Mock, patch
from models.research_models import MarketResearch, State, ChatMessage
from repositories.research_repository import MarketResearchRepository
from database import DBMarketResearch


@pytest.fixture
def mock_db():
    """Фикстура для создания замоканной базы данных"""
    return Mock()


def test_create_market_research(mock_db):
    """Тест создания исследования рынка"""
    repo = MarketResearchRepository(mock_db)
    
    # Создаем тестовое исследование
    test_mr = MarketResearch(state=State.CHAT)
    
    # Мокаем возвращаемое значение для добавления в БД
    db_mr = DBMarketResearch(id=1, state=State.CHAT.value)
    mock_db.add.return_value = None
    mock_db.commit.return_value = None
    mock_db.refresh.return_value = None
    
    # Так как мы не можем напрямую установить id через DBMarketResearch,
    # мы мокаем поведение, чтобы после refresh id был установлен
    with patch('repositories.research_repository.DBMarketResearch', return_value=db_mr):
        result = repo.create(test_mr)
        
        # Проверяем, что методы базы данных были вызваны
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Проверяем, что ID было установлено
        assert result.id == 1


def test_get_market_research_by_id_found(mock_db):
    """Тест получения исследования по ID (когда найдено)"""
    from datetime import datetime

    repo = MarketResearchRepository(mock_db)

    # Мокаем результат запроса к базе данных
    db_mr = DBMarketResearch(
        id=1,
        state=State.CHAT.value,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    mock_query_mr = Mock()
    mock_query_mr.filter.return_value.first.return_value = db_mr

    # Мокаем результат запроса для поисковых задач
    mock_query_tasks = Mock()
    mock_query_tasks.filter.return_value.all.return_value = []

    # Мокаем вызов query для разных моделей
    mock_db.query.side_effect = lambda model: mock_query_mr if model == DBMarketResearch else mock_query_tasks

    result = repo.get_by_id(1)

    # Проверяем, что запрос к базе данных был сделан
    assert mock_db.query.called
    mock_query_mr.filter.assert_called_once()

    # Проверяем, что результат не None
    assert result is not None
    assert result.id == 1
    assert result.state == State.CHAT


def test_get_market_research_by_id_not_found(mock_db):
    """Тест получения исследования по ID (когда не найдено)"""
    repo = MarketResearchRepository(mock_db)
    
    # Мокаем результат запроса к базе данных (None)
    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = mock_query
    
    result = repo.get_by_id(999)
    
    # Проверяем, что результат None
    assert result is None


def test_update_market_research_state(mock_db):
    """Тест обновления состояния исследования"""
    repo = MarketResearchRepository(mock_db)
    
    # Мокаем существующее исследование
    db_mr = DBMarketResearch(id=1, state=State.CHAT.value)
    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = db_mr
    mock_db.query.return_value = mock_query
    
    # Мокаем возвращаемое значение для get_by_id
    with patch.object(repo, 'get_by_id', return_value=MarketResearch(id=1, state=State.SEARCHING_QUICK)):
        result = repo.update_state(1, State.SEARCHING_QUICK)
        
        # Проверяем, что состояние было обновлено
        assert db_mr.state == State.SEARCHING_QUICK.value
        mock_db.commit.assert_called_once()
        
        # Проверяем, что результат не None
        assert result is not None