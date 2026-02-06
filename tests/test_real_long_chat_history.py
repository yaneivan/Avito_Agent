"""
Тест для проверки сохранения многоходовой истории чата с использованием реальных сервисов
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


def test_real_long_chat_history():
    """Тест проверяет, что история чата сохраняется при нескольких сообщениях с использованием реальных сервисов"""
    print("Запускаем тест: test_real_long_chat_history")
    
    # Создаем реальный экземпляр сервиса
    service = MarketResearchService()
    
    # Подменим вызов LLM, чтобы не зависеть от внешнего API
    with patch('services.chat_service.get_completion') as mock_get_completion:
        # Подготовим ответы для разных вызовов
        responses = [
            # Первый ответ
            type('MockResponse', (), {
                'content': 'Здравствуйте! Чем могу помочь?',
                'tool_calls': None
            })(),
            # Второй ответ
            type('MockResponse', (), {
                'content': 'Хорошо, я поищу для вас наушники.',
                'tool_calls': None
            })(),
            # Третий ответ
            type('MockResponse', (), {
                'content': 'Понял, ищу наушники с Bluetooth.',
                'tool_calls': None
            })(),
            # Четвертый ответ
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
        updated_mr_1 = service.process_user_message(initial_mr.id, "Мне нужны наушники.")
        
        print(f"После второго сообщения: {len(updated_mr_1.chat_history)} сообщений")
        
        # Проверяем, что в истории 3 сообщения (пользователь -> ассистент -> пользователь)
        assert len(updated_mr_1.chat_history) == 3
        assert updated_mr_1.chat_history[0].content == "Привет!"
        assert updated_mr_1.chat_history[1].content == "Здравствуйте! Чем могу помочь?"
        assert updated_mr_1.chat_history[2].content == "Мне нужны наушники."
        
        # Обрабатываем третье сообщение
        updated_mr_2 = service.process_user_message(updated_mr_1.id, "С Bluetooth, пожалуйста.")
        
        print(f"После третьего сообщения: {len(updated_mr_2.chat_history)} сообщений")
        
        # Проверяем, что в истории 5 сообщений
        assert len(updated_mr_2.chat_history) == 5
        assert updated_mr_2.chat_history[0].content == "Привет!"
        assert updated_mr_2.chat_history[1].content == "Здравствуйте! Чем могу помочь?"
        assert updated_mr_2.chat_history[2].content == "Мне нужны наушники."
        assert updated_mr_2.chat_history[3].content == "Хорошо, я поищу для вас наушники."
        assert updated_mr_2.chat_history[4].content == "С Bluetooth, пожалуйста."
        
        # Обрабатываем четвертое сообщение
        updated_mr_3 = service.process_user_message(updated_mr_2.id, "А сколько примерно стоят?")
        
        print(f"После четвертого сообщения: {len(updated_mr_3.chat_history)} сообщений")
        
        # Проверяем, что в истории 7 сообщений
        assert len(updated_mr_3.chat_history) == 7
        
        # Проверяем порядок всех сообщений
        expected_contents = [
            "Привет!",  # 0
            "Здравствуйте! Чем могу помочь?",  # 1
            "Мне нужны наушники.",  # 2
            "Хорошо, я поищу для вас наушники.",  # 3
            "С Bluetooth, пожалуйста.",  # 4
            "Понял, ищу наушники с Bluetooth.",  # 5
            "А сколько примерно стоят?"  # 6
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
        assert "Цены на наушники" in last_assistant_msg.content
        
        print("Тест пройден: вся история чата сохраняется корректно с реальными сервисами!")


if __name__ == "__main__":
    test_real_long_chat_history()
    print("\nТест с реальными сервисами пройден успешно!")