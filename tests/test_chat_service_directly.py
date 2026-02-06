"""
Тест для проверки работы ChatService напрямую
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Добавим путь к корню проекта для импорта
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from database import Base, DBMarketResearch
from models.research_models import MarketResearch, ChatMessage, State
from repositories.research_repository import MarketResearchRepository
from services.chat_service import ChatService
from utils.logger import logger


def test_chat_service_directly():
    """Тест проверяет работу ChatService напрямую"""
    # Создаем временную базу данных в памяти
    engine = create_engine('sqlite:///test_db.sqlite3', echo=True)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Создаем репозитории
        mr_repo = MarketResearchRepository(db)
        
        # Создаем мок LLM клиента
        class MockLLM:
            def generate_response(self, history):
                # Возвращаем простой ответ на основе последнего сообщения
                if history:
                    last_msg = history[-1].content
                    if "наушники" in last_msg.lower():
                        return "Хорошо, ищу наушники для вас."
                    elif "bluetooth" in last_msg.lower():
                        return "Ищу Bluetooth наушники."
                    else:
                        return "Понял ваш запрос."
                return "Понял."
        
        # Создаем ChatService
        chat_service = ChatService(mr_repo)
        # Заменяем LLM на мок
        chat_service.llm = MockLLM()
        
        print("=== Тест 1: Создание начального исследования ===")
        # Создаем исследование с начальной историей
        initial_history = [
            ChatMessage(id=str(uuid.uuid4()), role="user", content="Привет!"),
            ChatMessage(id=str(uuid.uuid4()), role="assistant", content="Привет! Как могу помочь?")
        ]
        
        initial_mr = MarketResearch(
            state=State.CHAT,
            chat_history=initial_history,
            search_tasks=[]
        )
        
        created_mr = mr_repo.create(initial_mr)
        print(f"Создано исследование с ID: {created_mr.id}")
        print(f"Количество сообщений в созданном исследовании: {len(created_mr.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in created_mr.chat_history]}")
        
        print("\n=== Тест 2: Обработка сообщения пользователя ===")
        # Обрабатываем сообщение пользователя
        updated_mr, is_tool_call = chat_service.process_user_message(created_mr.id, "Мне нужны наушники.")
        print(f"Количество сообщений после обработки: {len(updated_mr.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in updated_mr.chat_history]}")
        print(f"Вызван ли инструмент: {is_tool_call}")
        
        print("\n=== Тест 3: Обработка второго сообщения пользователя ===")
        # Обрабатываем второе сообщение пользователя
        updated_mr2, is_tool_call2 = chat_service.process_user_message(created_mr.id, "С Bluetooth, пожалуйста.")
        print(f"Количество сообщений после второго обновления: {len(updated_mr2.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in updated_mr2.chat_history]}")
        print(f"Вызван ли инструмент: {is_tool_call2}")
        
        print("\n=== Тест 4: Проверка получения обновленного исследования ===")
        # Получаем исследование снова, чтобы проверить, сохранены ли изменения
        re_retrieved_mr = mr_repo.get_by_id(created_mr.id)
        print(f"Количество сообщений в повторно полученном исследовании: {len(re_retrieved_mr.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in re_retrieved_mr.chat_history]}")
        
        # Проверяем, все ли сообщения сохранились
        expected_messages = [
            "Привет!",
            "Привет! Как могу помочь?",
            "Мне нужны наушники.",
            "Хорошо, ищу наушники для вас.",
            "С Bluetooth, пожалуйста.",
            "Ищу Bluetooth наушники."
        ]
        
        actual_messages = [msg.content for msg in re_retrieved_mr.chat_history]
        
        print(f"\nОжидаемые сообщения: {expected_messages}")
        print(f"Фактические сообщения: {actual_messages}")
        
        all_present = all(msg in actual_messages for msg in expected_messages)
        print(f"Все сообщения присутствуют: {all_present}")
        
        if len(actual_messages) == len(expected_messages):
            print("✓ Количество сообщений совпадает")
        else:
            print(f"✗ Количество сообщений НЕ совпадает: ожидается {len(expected_messages)}, получено {len(actual_messages)}")
            
        if all_present:
            print("✓ Все ожидаемые сообщения присутствуют")
        else:
            missing = [msg for msg in expected_messages if msg not in actual_messages]
            print(f"✗ Отсутствуют сообщения: {missing}")
        
        print("\n=== Тест 5: Проверка с add_to_history=False ===")
        # Проверим, что происходит при вызове с add_to_history=False
        updated_mr3, is_tool_call3 = chat_service.process_user_message(
            created_mr.id, 
            "Это сообщение не должно добавляться к истории", 
            add_to_history=False
        )
        print(f"Количество сообщений после вызова с add_to_history=False: {len(updated_mr3.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in updated_mr3.chat_history]}")
        print(f"Вызван ли инструмент: {is_tool_call3}")
        
        # Проверим, что новое сообщение не добавилось
        if "Это сообщение не должно добавляться к истории" not in [msg.content for msg in updated_mr3.chat_history]:
            print("✓ Сообщение с add_to_history=False не добавилось к истории")
        else:
            print("✗ Сообщение с add_to_history=False добавилось к истории")
        
    finally:
        db.close()


if __name__ == "__main__":
    test_chat_service_directly()