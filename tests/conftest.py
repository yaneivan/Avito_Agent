# conftest.py
import pytest
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Фикстура для настройки тестовой среды"""
    # Здесь можно выполнить настройку перед запуском всех тестов
    print("Настройка тестовой среды...")
    
    # Мокаем конфигурацию для тестов
    with patch.dict('os.environ', {
        'DATABASE_URL': 'sqlite:///./test_avito_agent.db',
        'LOCAL_LLM_URL': 'http://localhost:8080/v1',
        'LOCAL_LLM_API_KEY': 'not-needed',
        'LOCAL_LLM_MODEL': 'Qwen3-Vl-4B-Instruct'
    }):
        yield
        print("Очистка после тестов...")


# Можно добавить другие общие фикстуры здесь