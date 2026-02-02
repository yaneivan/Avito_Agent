import pytest
from unittest.mock import Mock, patch, MagicMock
from models.research_models import MarketResearch, State, ChatMessage
from services.research_service import MarketResearchService


@pytest.fixture
def mock_service():
    """Фикстура для создания сервиса с замоканными зависимостями"""
    with patch('services.research_service.SessionLocal') as mock_session, \
         patch('services.research_service.MarketResearchRepository') as mock_mr_repo, \
         patch('services.research_service.SearchTaskRepository') as mock_task_repo, \
         patch('services.research_service.SchemaRepository') as mock_schema_repo, \
         patch('services.research_service.RawLotRepository') as mock_raw_lot_repo, \
         patch('services.research_service.AnalyzedLotRepository') as mock_analyzed_lot_repo:

        service = MarketResearchService()

        # Устанавливаем моки
        service.mr_repo = mock_mr_repo.return_value
        service.task_repo = mock_task_repo.return_value
        service.schema_repo = mock_schema_repo.return_value
        service.raw_lot_repo = mock_raw_lot_repo.return_value
        service.analyzed_lot_repo = mock_analyzed_lot_repo.return_value

        yield service, mock_session


def test_create_market_research_initializes_correctly(mock_service):
    """Тест создания нового исследования рынка"""
    service, _ = mock_service

    # Мокаем возвращаемое значение метода create
    mock_mr = MarketResearch(id=1, state=State.CHAT, chat_history=[])
    service.mr_repo.create.return_value = mock_mr

    initial_query = "тестовый запрос"
    result = service.create_market_research(initial_query)

    # Проверяем, что методы репозитория были вызваны
    service.mr_repo.create.assert_called_once()

    # Проверяем, что состояние установлено правильно
    assert result.state == State.CHAT


def test_process_user_message_updates_chat_history(mock_service):
    """Тест обработки сообщения пользователя"""
    service, _ = mock_service

    # Создаем тестовое исследование
    test_mr = MarketResearch(
        id=1,
        state=State.CHAT,
        chat_history=[ChatMessage(role="user", content="тестовый запрос")]
    )

    # Мокаем возвращаемое значение для репозитория
    service.mr_repo.get_by_id.return_value = test_mr

    # Мокаем методы в соответствующих сервисах
    with patch.object(service.chat_service, 'process_user_message', return_value=(test_mr, False)):

        message = "тестовое сообщение пользователя"
        result = service.process_user_message(1, message)

        # Проверяем, что сообщение добавлено в историю
        assert len(result.chat_history) >= 1  # как минимум 1 сообщение: исходное
        assert result.chat_history[0].content == "тестовый запрос"


def test_analyze_visual_features():
    """Тест визуального анализа изображения"""
    from unittest.mock import mock_open
    from services.visual_analysis_service import VisualAnalysisService

    service = VisualAnalysisService()

    # Мокаем вызов LLM и чтение файла
    with patch('services.visual_analysis_service.get_completion') as mock_llm, \
         patch('builtins.open', mock_open(read_data=b"fake image data")), \
         patch('base64.b64encode') as mock_b64:

        mock_b64.return_value.decode.return_value = "fake_base64_data"
        mock_response = Mock()
        mock_response.content = "Изображение содержит красный диван"
        mock_llm.return_value = mock_response

        image_path = "/fake/path/image.jpg"
        visual_notes, image_desc = service.analyze_visual_features(image_path)

        # Проверяем, что LLM был вызван
        mock_llm.assert_called_once()

        # Проверяем результаты
        assert visual_notes == "Изображение содержит красный диван"
        assert "Изображение товара:" in image_desc


def test_apply_tournament_ranking():
    """Тест турнирного реранкинга"""
    from models.research_models import AnalyzedLot, Schema
    from services.deep_search_service import DeepSearchService
    from unittest.mock import Mock

    # Создаем тестовые лоты
    analyzed_lots = [
        AnalyzedLot(
            id=1,
            raw_lot_id=1,
            schema_id=1,
            structured_data={"title": "Товар 1", "price": "1000"},
            visual_notes="Примечание 1",
            image_description="Описание 1"
        ),
        AnalyzedLot(
            id=2,
            raw_lot_id=2,
            schema_id=1,
            structured_data={"title": "Товар 2", "price": "2000"},
            visual_notes="Примечание 2",
            image_description="Описание 2"
        )
    ]

    schema = Schema(
        id=1,
        name="Тестовая схема",
        description="Описание",
        json_schema={"properties": {"title": {"type": "string"}}}
    )

    # Создаем моки для репозиториев
    mock_mr_repo = Mock()
    mock_task_repo = Mock()
    mock_schema_repo = Mock()
    mock_raw_lot_repo = Mock()
    mock_analyzed_lot_repo = Mock()
    mock_visual_service = Mock()

    service = DeepSearchService(
        mock_mr_repo,
        mock_task_repo,
        mock_schema_repo,
        mock_raw_lot_repo,
        mock_analyzed_lot_repo,
        mock_visual_service
    )

    # Мокаем турнирный реранкинг
    with patch('services.deep_search_service.tournament_ranking') as mock_tournament:
        mock_tournament.return_value = [
            {"id": 2, "score": 10, "original_data": {}},
            {"id": 1, "score": 5, "original_data": {}}
        ]

        ranked_lots = service._apply_tournament_ranking(analyzed_lots, schema)

        # Проверяем, что турнирный реранкинг был вызван
        mock_tournament.assert_called_once()

        # Проверяем, что результаты отсортированы правильно
        assert len(ranked_lots) == 2
        assert ranked_lots[0].id == 2
        assert ranked_lots[1].id == 1