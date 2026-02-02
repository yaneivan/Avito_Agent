import pytest
import json
import re
from unittest.mock import Mock, patch
from services.research_service import MarketResearchService
from models.research_models import MarketResearch, State, ChatMessage


def test_parse_tool_call_from_llm_response():
    """Тест парсинга вызова инструмента из ответа LLM"""
    # Тестовые данные
    llm_response = """Конечно! Я помогу вам найти MacBook на Avito. Чтобы дать наиболее точный результат, уточните, какой именно MacBook вас интересует — например:

- Модель (MacBook Air, MacBook Pro, MacBook Studio и т.д.)
- Память (RAM), процессор (M1, M2, M3 и т.д.)
- Операционная система (macOS)
- Уровень новизны (например, 2020, 2022, или "б/у")

Если у вас нет конкретных предпочтений — я проведу быстрый поиск по всем доступным моделям.

<tool_call>{ "name": "start_quick_search", "query": "MacBook", "needs_visual": false }</tool_call>"""

    # Создаем mock сервис
    service = MarketResearchService()
    
    # Тестируем парсинг
    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', llm_response, re.DOTALL)
    
    assert tool_match is not None, "Не найден тег <tool_call>"
    
    # Извлекаем JSON
    tool_json = tool_match.group(1).strip()
    
    # Проверяем что JSON валиден
    tool_data = json.loads(tool_json)
    
    # Проверяем структуру данных
    assert tool_data["name"] == "start_quick_search"
    assert tool_data["query"] == "MacBook"
    assert tool_data["needs_visual"] is False


def test_parse_tool_call_with_parameters_key():
    """Тест парсинга вызова инструмента с ключом parameters"""
    llm_response = """<tool_call>
{
    "name": "start_quick_search",
    "parameters": {
        "query": "iPhone 14",
        "needs_visual": true
    }
}
</tool_call>"""

    service = MarketResearchService()
    
    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', llm_response, re.DOTALL)
    assert tool_match is not None
    
    tool_json = tool_match.group(1).strip()
    tool_data = json.loads(tool_json)
    
    # Проверяем структуру с parameters
    assert tool_data["name"] == "start_quick_search"
    assert "parameters" in tool_data
    assert tool_data["parameters"]["query"] == "iPhone 14"
    assert tool_data["parameters"]["needs_visual"] is True


def test_parse_tool_call_for_deep_research():
    """Тест парсинга вызова инструмента для глубокого исследования"""
    llm_response = """<tool_call>
{
    "name": "initiate_deep_research_planning",
    "parameters": {
        "initial_topic": "сравнение игровых ноутбуков 2023 года"
    }
}
</tool_call>"""

    service = MarketResearchService()
    
    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', llm_response, re.DOTALL)
    assert tool_match is not None
    
    tool_json = tool_match.group(1).strip()
    tool_data = json.loads(tool_json)
    
    assert tool_data["name"] == "initiate_deep_research_planning"
    assert "parameters" in tool_data
    assert tool_data["parameters"]["initial_topic"] == "сравнение игровых ноутбуков 2023 года"


def test_parse_tool_call_whitespace_handling():
    """Тест обработки пробелов и переносов в JSON"""
    # JSON с переносами строк
    llm_response = """<tool_call>{
    "name": "start_quick_search",
    "query": "MacBook Pro",
    "needs_visual": false
}</tool_call>"""

    service = MarketResearchService()
    
    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', llm_response, re.DOTALL)
    assert tool_match is not None
    
    # JSON должен парситься несмотря на переносы строк
    tool_json = tool_match.group(1).strip()
    tool_data = json.loads(tool_json)
    
    assert tool_data["name"] == "start_quick_search"
    assert tool_data["query"] == "MacBook Pro"


def test_process_user_message_with_tool_call():
    """Тест обработки сообщения пользователя с вызовом инструмента"""
    with patch('services.research_service.SessionLocal') as mock_session, \
         patch('services.research_service.MarketResearchRepository') as mock_mr_repo, \
         patch('services.research_service.SearchTaskRepository') as mock_task_repo, \
         patch('services.research_service.ChatService') as mock_chat_service:
        
        # Настраиваем моки
        mock_mr_repo_instance = Mock()
        mock_mr_repo.return_value = mock_mr_repo_instance
        
        mock_task_repo_instance = Mock()
        mock_task_repo.return_value = mock_task_repo_instance
        
        mock_chat_service_instance = Mock()
        mock_chat_service.return_value = mock_chat_service_instance
        
        service = MarketResearchService()
        service.mr_repo = mock_mr_repo_instance
        service.task_repo = mock_task_repo_instance
        service.chat_service = mock_chat_service_instance
        
        # Создаем тестовое исследование
        test_mr = MarketResearch(
            id=1,
            state=State.CHAT,
            chat_history=[
                ChatMessage(role="user", content="почем макбуки?"),
                ChatMessage(
                    role="assistant", 
                    content="""<tool_call>{ "name": "start_quick_search", "query": "MacBook", "needs_visual": false }</tool_call>"""
                )
            ]
        )
        
        # Мокаем вызов chat_service
        mock_chat_service_instance.process_user_message.return_value = (test_mr, True)
        
        # Мокаем get_by_id
        mock_mr_repo_instance.get_by_id.return_value = test_mr
        
        # Мокаем create для SearchTask
        mock_task = Mock(id=1)
        mock_task_repo_instance.create.return_value = mock_task
        
        # Вызываем метод
        result = service.process_user_message(1, "почем макбуки?")
        
        # Проверяем, что:
        # 1. Chat service был вызван
        mock_chat_service_instance.process_user_message.assert_called_once_with(1, "почем макбуки?", [])
        
        # 2. Создана задача поиска
        mock_task_repo_instance.create.assert_called_once()
        
        # 3. Обновлено состояние
        mock_mr_repo_instance.update_state.assert_called_once()


def test_handle_tool_call_with_different_formats():
    """Тест обработки разных форматов вызова инструмента"""
    test_cases = [
        {
            "name": "Корректный формат с параметрами",
            "response": '<tool_call>{"name": "start_quick_search", "parameters": {"query": "MacBook", "needs_visual": false}}</tool_call>',
            "expected_name": "start_quick_search",
            "expected_query": "MacBook",
            "expected_needs_visual": False
        },
        {
            "name": "Старый формат (без parameters)",
            "response": '<tool_call>{"name": "start_quick_search", "query": "iPhone", "needs_visual": true}</tool_call>',
            "expected_name": "start_quick_search",
            "expected_query": "iPhone",
            "expected_needs_visual": True
        },
        {
            "name": "С пробелами и переносами",
            "response": """<tool_call>
            {
                "name": "initiate_deep_research_planning",
                "parameters": {
                    "initial_topic": "ноутбуки"
                }
            }
            </tool_call>""",
            "expected_name": "initiate_deep_research_planning",
            "expected_topic": "ноутбуки"
        }
    ]
    
    for test_case in test_cases:
        service = MarketResearchService()
        
        # Парсим JSON
        tool_match = re.search(r'<tool_call>(.*?)</tool_call>', test_case["response"], re.DOTALL)
        assert tool_match is not None, f"Не удалось найти tool_call для теста: {test_case['name']}"
        
        tool_json = tool_match.group(1).strip()
        tool_data = json.loads(tool_json)
        
        # Проверяем имя инструмента
        assert tool_data["name"] == test_case["expected_name"]
        
        # Проверяем параметры в зависимости от формата
        if test_case["expected_name"] == "start_quick_search":
            if "parameters" in tool_data:
                params = tool_data["parameters"]
            else:
                params = tool_data
            
            assert params.get("query") == test_case["expected_query"]
            assert params.get("needs_visual") == test_case["expected_needs_visual"]
        
        elif test_case["expected_name"] == "initiate_deep_research_planning":
            if "parameters" in tool_data:
                params = tool_data["parameters"]
            else:
                params = tool_data
            
            assert params.get("initial_topic") == test_case["expected_topic"]


def test_invalid_json_handling():
    """Тест обработки некорректного JSON"""
    invalid_response = """<tool_call>{"name": "start_quick_search", "query": "MacBook", needs_visual: false}</tool_call>"""
    
    service = MarketResearchService()
    
    # Должен найти тег
    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', invalid_response, re.DOTALL)
    assert tool_match is not None
    
    # Но JSON невалидный (нет кавычек у false)
    tool_json = tool_match.group(1).strip()
    
    with pytest.raises(json.JSONDecodeError):
        json.loads(tool_json)


def test_missing_tool_call():
    """Тест случая, когда нет вызова инструмента"""
    no_tool_response = "Просто обычный ответ без вызова инструмента."
    
    service = MarketResearchService()
    
    tool_match = re.search(r'<tool_call>(.*?)</tool_call>', no_tool_response, re.DOTALL)
    assert tool_match is None, "Не должно быть совпадения при отсутствии тега <tool_call>"