"""
Простой тест для проверки, что история чата не теряется и не дублируется
"""
import sys
import os
from unittest.mock import patch

# Добавим путь к проекту, чтобы можно было импортировать модули
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.research_models import MarketResearch, ChatMessage, State
from services.research_service import MarketResearchService


def test_no_duplicate_messages():
    """Тест проверяет, что сообщения не дублируются при использовании unified_chat_endpoint логики"""
    print("Запускаем тест: test_no_duplicate_messages")
    
    # Создаем реальный экземпляр сервиса
    service = MarketResearchService()
    
    # Подменим вызов LLM, чтобы не зависеть от внешнего API
    with patch('services.chat_service.get_completion') as mock_get_completion:
        # Подготовим ответ
        response = type('MockResponse', (), {
            'content': 'Здравствуйте! Чем могу помочь?',
            'tool_calls': None
        })()
        
        mock_get_completion.return_value = response
        
        # Имитируем поведение unified_chat_endpoint
        # 1. Создаем новое исследование с сообщением пользователя
        market_research = service.create_market_research("Привет!")
        
        # Проверяем, что в истории одно сообщение
        assert len(market_research.chat_history) == 1
        assert market_research.chat_history[0].role == "user"
        assert market_research.chat_history[0].content == "Привет!"
        
        print(f"После создания: {len(market_research.chat_history)} сообщений")
        
        # 2. Обрабатываем сообщение, но не добавляем его снова к истории
        # Это имитирует вызов в unified_chat_endpoint с add_to_history=False
        updated_mr = service.process_user_message(market_research.id, "Привет!", add_to_history=False)
        
        # Проверяем, что в истории 2 сообщения:
        # - "Привет!" (от пользователя)
        # - "Здравствуйте! Чем могу помочь?" (от ассистента)
        assert len(updated_mr.chat_history) == 2
        assert updated_mr.chat_history[0].content == "Привет!"
        assert updated_mr.chat_history[1].role == "assistant"
        
        print(f"После обработки: {len(updated_mr.chat_history)} сообщений")
        
        # Проверяем, что сообщение "Привет!" не дублируется
        user_messages = [msg for msg in updated_mr.chat_history if msg.role == "user"]
        assert len(user_messages) == 1
        assert user_messages[0].content == "Привет!"
        
        print("Тест пройден: сообщения не дублируются!")


def test_history_grows_correctly():
    """Тест проверяет, что история растет правильно при нескольких сообщениях"""
    print("\nЗапускаем тест: test_history_grows_correctly")
    
    # Создаем реальный экземпляр сервиса
    service = MarketResearchService()
    
    # Подменим вызов LLM, чтобы не зависеть от внешнего API
    with patch('services.chat_service.get_completion') as mock_get_completion:
        # Подготовим ответы для разных вызовов
        responses = [
            type('MockResponse', (), {
                'content': 'Ответ на Привет!',
                'tool_calls': None
            })(),
            type('MockResponse', (), {
                'content': 'Ответ на Как дела?',
                'tool_calls': None
            })(),
            type('MockResponse', (), {
                'content': 'Ответ на Что нового?',
                'tool_calls': None
            })()
        ]
        
        mock_get_completion.side_effect = responses
        
        # Создаем новое исследование
        mr = service.create_market_research("Привет!")
        
        initial_length = len(mr.chat_history)
        print(f"После создания: {initial_length} сообщений")
        
        # Обрабатываем второе сообщение
        mr = service.process_user_message(mr.id, "Как дела?", add_to_history=True)
        
        second_length = len(mr.chat_history)
        print(f"После второго сообщения: {second_length} сообщений")
        
        # Обрабатываем третье сообщение
        mr = service.process_user_message(mr.id, "Что нового?", add_to_history=True)
        
        third_length = len(mr.chat_history)
        print(f"После третьего сообщения: {third_length} сообщений")
        
        # Проверяем, что длина истории увеличивается правильно
        # 1 (при создании) + 2 (ответы ассистента) + 2 (новые сообщения пользователя) = 5
        assert third_length == 5
        
        # Проверяем, что все сообщения пользователя на своих местах
        user_messages = [msg for msg in mr.chat_history if msg.role == "user"]
        assert len(user_messages) == 3
        assert user_messages[0].content == "Привет!"
        assert user_messages[1].content == "Как дела?"
        assert user_messages[2].content == "Что нового?"
        
        # Проверяем, что все сообщения ассистента на своих местах
        assistant_messages = [msg for msg in mr.chat_history if msg.role == "assistant"]
        assert len(assistant_messages) == 2
        
        print("Тест пройден: история растет правильно!")


if __name__ == "__main__":
    test_no_duplicate_messages()
    test_history_grows_correctly()
    print("\nВсе тесты пройдены успешно!")