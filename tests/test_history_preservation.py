"""
Тест для проверки сохранения истории чата с учетом реального поведения LLM
"""
import sys
import os
from unittest.mock import patch

# Добавим путь к проекту, чтобы можно было импортировать модули
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.research_models import MarketResearch, ChatMessage, State
from services.research_service import MarketResearchService


def test_history_preservation_with_multiple_exchanges():
    """Тест проверяет, что история сохраняется при нескольких обменах сообщениями"""
    print("Запускаем тест: test_history_preservation_with_multiple_exchanges")
    
    # Создаем реальный экземпляр сервиса
    service = MarketResearchService()
    
    # Подменим вызов LLM, чтобы не зависеть от внешнего API
    with patch('services.chat_service.get_completion') as mock_get_completion:
        # Подготовим ответы для разных вызовов
        # Важно: LLM может отвечать по-разному в зависимости от всей истории
        responses = [
            # Ответ на историю: ["Привет!"] -> "Здравствуйте! Чем могу помочь?"
            type('MockResponse', (), {
                'content': 'Здравствуйте! Чем могу помочь?',
                'tool_calls': None
            })(),
            # Ответ на историю: ["Привет!", "Здравствуйте! Чем могу помочь?", "Мне нужны наушники."]
            # -> "Хорошо, я поищу для вас наушники."
            type('MockResponse', (), {
                'content': 'Хорошо, я поищу для вас наушники.',
                'tool_calls': None
            })(),
            # Ответ на историю: ["Привет!", "Здравствуйте! Чем могу помочь?", "Мне нужны наушники.", 
            # "Хорошо, я поищу для вас наушники.", "С Bluetooth, пожалуйста."]
            # -> "Понял, ищу наушники с Bluetooth."
            type('MockResponse', (), {
                'content': 'Понял, ищу наушники с Bluetooth.',
                'tool_calls': None
            })(),
            # Ответ на историю: ["Привет!", "Здравствуйте! Чем могу помочь?", "Мне нужны наушники.", 
            # "Хорошо, я поищу для вас наушники.", "С Bluetooth, пожалуйста.",
            # "Понял, ищу наушники с Bluetooth.", "А сколько примерно стоят?"]
            # -> "Цены на наушники с Bluetooth варьируются..."
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
        
        # Проверяем, что в истории 3 сообщения
        assert len(updated_mr_1.chat_history) == 3
        
        # Проверяем, что все сообщения на своих местах
        assert updated_mr_1.chat_history[0].content == "Привет!"
        assert updated_mr_1.chat_history[1].content == "Мне нужны наушники."
        # Второе сообщение от ассистента (ответ на "Мне нужны наушники.")
        assert "наушники" in updated_mr_1.chat_history[2].content.lower()
        
        # Обрабатываем третье сообщение
        updated_mr_2 = service.process_user_message(updated_mr_1.id, "С Bluetooth, пожалуйста.", add_to_history=True)
        
        print(f"После третьего сообщения: {len(updated_mr_2.chat_history)} сообщений")
        
        # Проверяем, что в истории 4 сообщения
        assert len(updated_mr_2.chat_history) == 4
        
        # Проверяем, что все предыдущие сообщения сохранились
        assert updated_mr_2.chat_history[0].content == "Привет!"
        assert updated_mr_2.chat_history[1].content == "Мне нужны наушники."
        assert "наушники" in updated_mr_2.chat_history[2].content.lower()
        assert updated_mr_2.chat_history[3].content == "С Bluetooth, пожалуйста."
        
        # Обрабатываем четвертое сообщение
        updated_mr_3 = service.process_user_message(updated_mr_2.id, "А сколько примерно стоят?", add_to_history=True)
        
        print(f"После четвертого сообщения: {len(updated_mr_3.chat_history)} сообщений")
        
        # Проверяем, что в истории 5 сообщений
        assert len(updated_mr_3.chat_history) == 5
        
        # Проверяем, что все предыдущие сообщения сохранились
        assert updated_mr_3.chat_history[0].content == "Привет!"
        assert updated_mr_3.chat_history[1].content == "Мне нужны наушники."
        assert "наушники" in updated_mr_3.chat_history[2].content.lower()
        assert updated_mr_3.chat_history[3].content == "С Bluetooth, пожалуйста."
        assert updated_mr_3.chat_history[4].content == "А сколько примерно стоят?"
        
        # Проверим, что последнее сообщение от ассистента добавится после обработки
        # Для этого нужно получить последнее сообщение от ассистента
        last_assistant_msg = None
        for msg in reversed(updated_mr_3.chat_history):
            if msg.role == "assistant":
                last_assistant_msg = msg
                break
        
        assert last_assistant_msg is not None
        assert "наушники" in last_assistant_msg.content.lower()
        assert "bluetooth" in last_assistant_msg.content.lower()
        
        print("Тест пройден: вся история чата сохраняется корректно!")
        print(f"Итоговая история ({len(updated_mr_3.chat_history)} сообщений):")
        for i, msg in enumerate(updated_mr_3.chat_history):
            print(f"  {i}: [{msg.role}] {msg.content}")


def test_no_message_loss_in_long_conversation():
    """Тест проверяет, что сообщения не теряются в долгом разговоре"""
    print("\nЗапускаем тест: test_no_message_loss_in_long_conversation")
    
    # Создаем реальный экземпляр сервиса
    service = MarketResearchService()
    
    # Подменим вызов LLM, чтобы не зависеть от внешнего API
    with patch('services.chat_service.get_completion') as mock_get_completion:
        # Создадим достаточно много ответов для LLM
        responses = []
        for i in range(10):  # 10 обменов
            responses.append(type('MockResponse', (), {
                'content': f'Ответ на сообщение #{i+1}',
                'tool_calls': None
            })())
        
        mock_get_completion.side_effect = responses
        
        # Создаем новое исследование
        mr = service.create_market_research("Привет! Как дела?")
        
        initial_length = len(mr.chat_history)
        print(f"Начальная длина истории: {initial_length}")
        
        # Делаем несколько обменов
        for i in range(10):
            # Добавляем сообщение пользователя
            user_msg = f"Сообщение пользователя #{i+1}"
            mr = service.process_user_message(mr.id, user_msg, add_to_history=True)
            
            current_length = len(mr.chat_history)
            print(f"После сообщения #{i+1}: {current_length} сообщений")
            
            # Проверяем, что длина истории увеличивается
            # (после каждого сообщения пользователя добавляется ответ ассистента)
            expected_length = initial_length + (i + 1) * 2  # +1 для сообщения пользователя, +1 для ответа ассистента
            assert len(mr.chat_history) == expected_length, \
                f"Ожидалось {expected_length} сообщений, получено {len(mr.chat_history)}"
        
        # Проверим, что все сообщения на своих местах
        history = mr.chat_history
        print(f"Итоговая длина истории: {len(history)}")
        
        # Проверим, что первое сообщение все еще на месте
        assert history[0].content == "Привет! Как дела?"
        
        # Проверим, что все сообщения пользователя на своих местах
        for i in range(10):
            user_msg_index = 1 + i * 2  # 1, 3, 5, 7, ...
            expected_user_msg = f"Сообщение пользователя #{i+1}"
            assert history[user_msg_index].content == expected_user_msg, \
                f"Сообщение пользователя #{i+1} не на своем месте"
        
        # Проверим, что все ответы ассистента на своих местах
        for i in range(10):
            assistant_msg_index = 2 + i * 2  # 2, 4, 6, 8, ...
            expected_assistant_response = f'Ответ на сообщение #{i+1}'
            assert expected_assistant_response in history[assistant_msg_index].content, \
                f"Ответ ассистента #{i+1} не на своем месте"
        
        print("Тест пройден: сообщения не теряются в долгом разговоре!")


if __name__ == "__main__":
    test_history_preservation_with_multiple_exchanges()
    test_no_message_loss_in_long_conversation()
    print("\nВсе тесты пройдены успешно!")