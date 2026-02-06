"""
Тест для проверки сохранения многоходовой истории чата
"""
import sys
import os
from unittest.mock import MagicMock, patch
from typing import List

# Добавим путь к проекту, чтобы можно было импортировать модули
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.research_models import MarketResearch, ChatMessage, State
from services.research_service import MarketResearchService
from services.chat_service import ChatService
from repositories.research_repository import MarketResearchRepository


def test_long_chat_history_preserved():
    """Тест проверяет, что история чата сохраняется при нескольких сообщениях"""
    print("Запускаем тест: test_long_chat_history_preserved")
    
    # Создаем mock репозитория
    mock_mr_repo = MagicMock(spec=MarketResearchRepository)
    
    # Создаем чат-сервис с mock репозитория
    mock_chat_service = ChatService(mock_mr_repo)
    
    # Создаем исследование с первым сообщением
    initial_mr = MarketResearch(
        id=1,
        state=State.CHAT,
        chat_history=[
            ChatMessage(id="1", role="user", content="Привет!"),
            ChatMessage(id="2", role="assistant", content="Здравствуйте! Чем могу помочь?")
        ]
    )
    
    # Настроим mock, чтобы возвращал это исследование при запросах
    mock_mr_repo.get_by_id.return_value = initial_mr
    mock_mr_repo.update.return_value = initial_mr
    
    # Создаем сервис и подменим chat_service
    service = MarketResearchService()
    service.mr_repo = mock_mr_repo
    service.chat_service = mock_chat_service
    
    # Подменим остальные репозитории
    service.task_repo = MagicMock()
    service.schema_repo = MagicMock()
    service.raw_lot_repo = MagicMock()
    service.analyzed_lot_repo = MagicMock()
    
    # Подменим ответ LLM для теста
    with patch.object(mock_chat_service, 'process_user_message', side_effect=[
        # Первый вызов - для первого сообщения
        (
            MarketResearch(
                id=1,
                state=State.CHAT,
                chat_history=[
                    ChatMessage(id="1", role="user", content="Привет!"),
                    ChatMessage(id="2", role="assistant", content="Здравствуйте! Чем могу помочь?"),
                    ChatMessage(id="3", role="user", content="Мне нужны наушники."),
                    ChatMessage(id="4", role="assistant", content="Хорошо, я поищу для вас наушники.")
                ]
            ),
            False  # is_tool_call = False
        ),
        # Второй вызов - для второго сообщения
        (
            MarketResearch(
                id=1,
                state=State.CHAT,
                chat_history=[
                    ChatMessage(id="1", role="user", content="Привет!"),
                    ChatMessage(id="2", role="assistant", content="Здравствуйте! Чем могу помочь?"),
                    ChatMessage(id="3", role="user", content="Мне нужны наушники."),
                    ChatMessage(id="4", role="assistant", content="Хорошо, я поищу для вас наушники."),
                    ChatMessage(id="5", role="user", content="С Bluetooth, пожалуйста."),
                    ChatMessage(id="6", role="assistant", content="Понял, ищу наушники с Bluetooth.")
                ]
            ),
            False  # is_tool_call = False
        ),
        # Третий вызов - для третьего сообщения
        (
            MarketResearch(
                id=1,
                state=State.CHAT,
                chat_history=[
                    ChatMessage(id="1", role="user", content="Привет!"),
                    ChatMessage(id="2", role="assistant", content="Здравствуйте! Чем могу помочь?"),
                    ChatMessage(id="3", role="user", content="Мне нужны наушники."),
                    ChatMessage(id="4", role="assistant", content="Хорошо, я поищу для вас наушники."),
                    ChatMessage(id="5", role="user", content="С Bluetooth, пожалуйста."),
                    ChatMessage(id="6", role="assistant", content="Понял, ищу наушники с Bluetooth."),
                    ChatMessage(id="7", role="user", content="А сколько примерно стоят?"),
                    ChatMessage(id="8", role="assistant", content="Цены на наушники с Bluetooth варьируются от 1000 до 15000 рублей, в зависимости от качества и бренда.")
                ]
            ),
            False  # is_tool_call = False
        )
    ]):
        # Обрабатываем первое дополнительное сообщение
        result_mr_1 = service.process_user_message(1, "Мне нужны наушники.")
        
        # Проверяем, что история содержит 4 сообщения
        assert len(result_mr_1.chat_history) == 4, f"Ожидалось 4 сообщения, получено {len(result_mr_1.chat_history)}"
        assert result_mr_1.chat_history[0].content == "Привет!"
        assert result_mr_1.chat_history[1].content == "Здравствуйте! Чем могу помочь?"
        assert result_mr_1.chat_history[2].content == "Мне нужны наушники."
        assert result_mr_1.chat_history[3].content == "Хорошо, я поищу для вас наушники."
        
        print(f"После первого сообщения: {len(result_mr_1.chat_history)} сообщений")
        
        # Обрабатываем второе дополнительное сообщение
        result_mr_2 = service.process_user_message(1, "С Bluetooth, пожалуйста.")
        
        # Проверяем, что история содержит 6 сообщений
        assert len(result_mr_2.chat_history) == 6, f"Ожидалось 6 сообщений, получено {len(result_mr_2.chat_history)}"
        assert result_mr_2.chat_history[0].content == "Привет!"
        assert result_mr_2.chat_history[2].content == "Мне нужны наушники."
        assert result_mr_2.chat_history[4].content == "С Bluetooth, пожалуйста."
        assert result_mr_2.chat_history[5].content == "Понял, ищу наушники с Bluetooth."
        
        print(f"После второго сообщения: {len(result_mr_2.chat_history)} сообщений")
        
        # Обрабатываем третье дополнительное сообщение
        result_mr_3 = service.process_user_message(1, "А сколько примерно стоят?")
        
        # Проверяем, что история содержит 8 сообщений
        assert len(result_mr_3.chat_history) == 8, f"Ожидалось 8 сообщений, получено {len(result_mr_3.chat_history)}"
        
        # Проверяем, что все предыдущие сообщения сохранились
        expected_contents = [
            "Привет!",
            "Здравствуйте! Чем могу помочь?",
            "Мне нужны наушники.",
            "Хорошо, я поищу для вас наушники.",
            "С Bluetooth, пожалуйста.",
            "Понял, ищу наушники с Bluetooth.",
            "А сколько примерно стоят?",
            "Цены на наушники с Bluetooth варьируются от 1000 до 15000 рублей, в зависимости от качества и бренда."
        ]
        
        for i, expected_content in enumerate(expected_contents):
            assert result_mr_3.chat_history[i].content == expected_content, \
                f"Сообщение {i} имеет содержимое '{result_mr_3.chat_history[i].content}', ожидалось '{expected_content}'"
        
        print(f"После третьего сообщения: {len(result_mr_3.chat_history)} сообщений")
        
        print("Тест пройден: вся история чата сохраняется корректно!")


def test_create_and_extend_chat_history():
    """Тест проверяет создание исследования и последующее расширение истории"""
    print("\nЗапускаем тест: test_create_and_extend_chat_history")
    
    # Создаем mock репозитория
    mock_mr_repo = MagicMock(spec=MarketResearchRepository)
    
    # Создаем чат-сервис с mock репозитория
    mock_chat_service = ChatService(mock_mr_repo)
    
    # Создаем исследование
    service = MarketResearchService()
    service.mr_repo = mock_mr_repo
    service.chat_service = mock_chat_service
    
    # Подменим остальные репозитории
    service.task_repo = MagicMock()
    service.schema_repo = MagicMock()
    service.raw_lot_repo = MagicMock()
    service.analyzed_lot_repo = MagicMock()
    
    # Подменим ответ LLM для создания
    initial_mr = MarketResearch(
        id=1,
        state=State.CHAT,
        chat_history=[
            ChatMessage(id="1", role="user", content="Первый запрос")
        ]
    )
    
    # Подменим ответ LLM для обработки
    processed_mr = MarketResearch(
        id=1,
        state=State.CHAT,
        chat_history=[
            ChatMessage(id="1", role="user", content="Первый запрос"),
            ChatMessage(id="2", role="assistant", content="Ответ на первый запрос"),
            ChatMessage(id="3", role="user", content="Второй запрос"),
            ChatMessage(id="4", role="assistant", content="Ответ на второй запрос")
        ]
    )
    
    # Настроим mock возвращать разные значения в зависимости от вызова
    def get_by_id_side_effect(mr_id):
        if mr_id == 1:
            # Возвращаем разные значения в зависимости от этапа теста
            # Сначала возвращаем начальное состояние
            return initial_mr
        return None
    
    mock_mr_repo.get_by_id.side_effect = get_by_id_side_effect
    mock_mr_repo.create.return_value = initial_mr
    mock_mr_repo.update.return_value = processed_mr
    
    # Подменим ответ LLM для теста
    with patch.object(mock_chat_service, 'process_user_message', return_value=(processed_mr, False)):
        # Создаем исследование
        created_mr = service.create_market_research("Первый запрос")
        
        print(f"Создано исследование с {len(created_mr.chat_history)} сообщениями")
        assert len(created_mr.chat_history) == 1
        assert created_mr.chat_history[0].content == "Первый запрос"
        
        # Обрабатываем сообщение
        updated_mr = service.process_user_message(1, "Второй запрос")
        
        print(f"После обработки: {len(updated_mr.chat_history)} сообщений")
        assert len(updated_mr.chat_history) == 4
        
        # Проверяем, что все сообщения на своих местах
        expected_order = [
            ("user", "Первый запрос"),
            ("assistant", "Ответ на первый запрос"),
            ("user", "Второй запрос"),
            ("assistant", "Ответ на второй запрос")
        ]
        
        for i, (role, content) in enumerate(expected_order):
            assert updated_mr.chat_history[i].role == role, f"Роль сообщения {i} не совпадает"
            assert updated_mr.chat_history[i].content == content, f"Содержимое сообщения {i} не совпадает"
        
        print("Тест пройден: история корректно создается и расширяется!")


if __name__ == "__main__":
    test_long_chat_history_preserved()
    test_create_and_extend_chat_history()
    print("\nВсе тесты пройдены успешно!")