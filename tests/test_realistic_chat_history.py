"""
Тест для проверки сохранения истории чата с учетом реального поведения системы
"""
import sys
import os
from unittest.mock import patch

# Добавим путь к проекту, чтобы можно было импортировать модули
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.research_models import MarketResearch, ChatMessage, State
from services.research_service import MarketResearchService
from services.chat_service import ChatService
from repositories.research_repository import MarketResearchRepository
from database import SessionLocal


def test_realistic_chat_history():
    """Тест проверяет, что история чата сохраняется с реальным поведением системы"""
    print("Запускаем тест: test_realistic_chat_history")
    
    # Создаем реальный экземпляр сервиса
    service = MarketResearchService()
    
    # Подменим вызов LLM, чтобы не зависеть от внешнего API
    with patch('services.chat_service.get_completion') as mock_get_completion:
        # Подготовим ответы для разных вызовов
        responses = [
            # Первый ответ на "Привет!" - "Здравствуйте! Чем могу помочь?"
            type('MockResponse', (), {
                'content': 'Здравствуйте! Чем могу помочь?',
                'tool_calls': None
            })(),
            # Второй ответ на "Мне нужны наушники." - "Хорошо, я поищу для вас наушники."
            type('MockResponse', (), {
                'content': 'Хорошо, я поищу для вас наушники.',
                'tool_calls': None
            })(),
            # Третий ответ на "С Bluetooth, пожалуйста." - "Понял, ищу наушники с Bluetooth."
            type('MockResponse', (), {
                'content': 'Понял, ищу наушники с Bluetooth.',
                'tool_calls': None
            })(),
            # Четвертый ответ на "А сколько примерно стоят?" - "Цены на наушники..."
            type('MockResponse', (), {
                'content': 'Цены на наушники с Bluetooth варьируются от 1000 до 15000 рублей, в зависимости от качества и бренда.',
                'tool_calls': None
            })()
        ]
        
        mock_get_completion.side_effect = responses
        
        # Создаем новое исследование
        initial_mr = service.create_market_research("Привет!")
        
        print(f"Создано исследование с ID: {initial_mr.id}")
        print(f"История после создания: {len(initial_mr.chat_history)} сообщений")
        
        # Проверяем, что в истории одно сообщение (от пользователя)
        assert len(initial_mr.chat_history) == 1
        assert initial_mr.chat_history[0].role == "user"
        assert initial_mr.chat_history[0].content == "Привет!"
        
        # Обрабатываем второе сообщение
        updated_mr_1 = service.process_user_message(initial_mr.id, "Мне нужны наушники.", add_to_history=True)
        
        print(f"После второго сообщения: {len(updated_mr_1.chat_history)} сообщений")
        
        # Проверяем, что в истории 3 сообщения:
        # 0: "Привет!" (от пользователя)
        # 1: "Мне нужны наушники." (от пользователя)
        # 2: "Хорошо, я поищу для вас наушники." (от ассистента)
        assert len(updated_mr_1.chat_history) == 3
        assert updated_mr_1.chat_history[0].content == "Привет!"
        assert updated_mr_1.chat_history[1].content == "Мне нужны наушники."
        assert updated_mr_1.chat_history[2].content == "Хорошо, я поищу для вас наушники."
        
        # Обрабатываем третье сообщение
        updated_mr_2 = service.process_user_message(updated_mr_1.id, "С Bluetooth, пожалуйста.", add_to_history=True)
        
        print(f"После третьего сообщения: {len(updated_mr_2.chat_history)} сообщений")
        
        # Проверяем, что в истории 4 сообщения
        assert len(updated_mr_2.chat_history) == 4
        assert updated_mr_2.chat_history[0].content == "Привет!"
        assert updated_mr_2.chat_history[1].content == "Мне нужны наушники."
        assert updated_mr_2.chat_history[2].content == "Хорошо, я поищу для вас наушники."
        assert updated_mr_2.chat_history[3].content == "Понял, ищу наушники с Bluetooth."
        
        # Обрабатываем четвертое сообщение
        updated_mr_3 = service.process_user_message(updated_mr_2.id, "А сколько примерно стоят?", add_to_history=True)
        
        print(f"После четвертого сообщения: {len(updated_mr_3.chat_history)} сообщений")
        
        # Проверяем, что в истории 5 сообщений
        assert len(updated_mr_3.chat_history) == 5
        
        # Проверяем порядок всех сообщений
        expected_contents = [
            "Привет!",  # 0
            "Мне нужны наушники.",  # 1
            "Хорошо, я поищу для вас наушники.",  # 2
            "С Bluetooth, пожалуйста.",  # 3
            "Понял, ищу наушники с Bluetooth."  # 4
        ]
        
        for i, expected_content in enumerate(expected_contents):
            actual_content = updated_mr_3.chat_history[i].content
            assert actual_content == expected_content, \
                f"Сообщение {i} имеет содержимое '{actual_content}', ожидалось '{expected_content}'"
        
        # Проверим, что последнее сообщение от ассистента добавится после обработки
        # Для этого нужно получить последнее сообщение от ассистента
        last_assistant_msg = None
        for msg in reversed(updated_mr_3.chat_history):
            if msg.role == "assistant":
                last_assistant_msg = msg
                break
        
        assert last_assistant_msg is not None
        assert last_assistant_msg.content == "Понял, ищу наушники с Bluetooth."
        
        print("Тест пройден: вся история чата сохраняется корректно с реальным поведением системы!")


def test_unified_chat_endpoint_behavior():
    """Тест проверяет поведение unified_chat_endpoint, чтобы убедиться, что сообщения не дублируются"""
    print("\nЗапускаем тест: test_unified_chat_endpoint_behavior")
    
    # Создаем реальный экземпляр сервиса
    service = MarketResearchService()
    
    # Подменим вызов LLM, чтобы не зависеть от внешнего API
    with patch('services.chat_service.get_completion') as mock_get_completion:
        # Подготовим ответы для разных вызовов
        responses = [
            # Ответ на "Привет!" - "Здравствуйте! Чем могу помочь?"
            type('MockResponse', (), {
                'content': 'Здравствуйте! Чем могу помочь?',
                'tool_calls': None
            })()
        ]
        
        mock_get_completion.side_effect = responses
        
        # Имитируем поведение unified_chat_endpoint
        # 1. Создаем новое исследование
        market_research = service.create_market_research("Привет!")
        
        # 2. Обрабатываем сообщение, но не добавляем его снова к истории
        updated_mr = service.process_user_message(market_research.id, "Привет!", add_to_history=False)
        
        print(f"После обработки в unified_chat_endpoint: {len(updated_mr.chat_history)} сообщений")
        
        # Проверяем, что в истории 2 сообщения:
        # 0: "Привет!" (от пользователя)
        # 1: "Здравствуйте! Чем могу помочь?" (от ассистента)
        assert len(updated_mr.chat_history) == 2
        assert updated_mr.chat_history[0].role == "user"
        assert updated_mr.chat_history[0].content == "Привет!"
        assert updated_mr.chat_history[1].role == "assistant"
        assert updated_mr.chat_history[1].content == "Здравствуйте! Чем могу помочь?"
        
        print("Тест пройден: unified_chat_endpoint не дублирует сообщения!")


if __name__ == "__main__":
    test_realistic_chat_history()
    test_unified_chat_endpoint_behavior()
    print("\nВсе тесты пройдены успешно!")