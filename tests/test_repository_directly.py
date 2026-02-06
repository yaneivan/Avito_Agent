"""
Тест для проверки работы репозитория MarketResearchRepository напрямую
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
from utils.logger import logger

def test_repository_directly():
    """Тест проверяет работу репозитория напрямую"""
    # Создаем временную базу данных в памяти
    engine = create_engine('sqlite:///test_db.sqlite3', echo=True)
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        repo = MarketResearchRepository(db)
        
        print("=== Тест 1: Создание исследования ===")
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
        
        created_mr = repo.create(initial_mr)
        print(f"Создано исследование с ID: {created_mr.id}")
        print(f"Количество сообщений в созданном исследовании: {len(created_mr.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in created_mr.chat_history]}")
        
        print("\n=== Тест 2: Получение исследования по ID ===")
        retrieved_mr = repo.get_by_id(created_mr.id)
        print(f"Количество сообщений в полученном исследовании: {len(retrieved_mr.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in retrieved_mr.chat_history]}")
        
        print("\n=== Тест 3: Добавление сообщения и обновление ===")
        # Добавляем новое сообщение к истории
        retrieved_mr.chat_history.append(
            ChatMessage(id=str(uuid.uuid4()), role="user", content="Мне нужны наушники.")
        )
        retrieved_mr.chat_history.append(
            ChatMessage(id=str(uuid.uuid4()), role="assistant", content="Хорошо, ищу наушники.")
        )
        
        print(f"Количество сообщений перед обновлением: {len(retrieved_mr.chat_history)}")
        print(f"Содержимое истории перед обновлением: {[msg.content for msg in retrieved_mr.chat_history]}")
        
        # Обновляем исследование
        updated_mr = repo.update(retrieved_mr)
        print(f"Количество сообщений после обновления: {len(updated_mr.chat_history)}")
        print(f"Содержимое истории после обновления: {[msg.content for msg in updated_mr.chat_history]}")
        
        print("\n=== Тест 4: Проверка получения обновленного исследования ===")
        # Получаем исследование снова, чтобы проверить, сохранены ли изменения
        re_retrieved_mr = repo.get_by_id(created_mr.id)
        print(f"Количество сообщений в повторно полученном исследовании: {len(re_retrieved_mr.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in re_retrieved_mr.chat_history]}")
        
        print("\n=== Тест 5: Добавление еще одного сообщения ===")
        # Добавляем еще одно сообщение
        re_retrieved_mr.chat_history.append(
            ChatMessage(id=str(uuid.uuid4()), role="user", content="С Bluetooth, пожалуйста.")
        )
        re_retrieved_mr.chat_history.append(
            ChatMessage(id=str(uuid.uuid4()), role="assistant", content="Ищу Bluetooth наушники.")
        )
        
        print(f"Количество сообщений перед вторым обновлением: {len(re_retrieved_mr.chat_history)}")
        print(f"Содержимое истории перед вторым обновлением: {[msg.content for msg in re_retrieved_mr.chat_history]}")
        
        # Обновляем исследование снова
        final_mr = repo.update(re_retrieved_mr)
        print(f"Количество сообщений после второго обновления: {len(final_mr.chat_history)}")
        print(f"Содержимое истории после второго обновления: {[msg.content for msg in final_mr.chat_history]}")
        
        print("\n=== Тест 6: Финальная проверка ===")
        # Получаем исследование в третий раз
        final_check_mr = repo.get_by_id(created_mr.id)
        print(f"Количество сообщений в финальной проверке: {len(final_check_mr.chat_history)}")
        print(f"Содержимое истории: {[msg.content for msg in final_check_mr.chat_history]}")
        
        # Проверяем, все ли сообщения сохранились
        expected_messages = [
            "Привет!",
            "Привет! Как могу помочь?",
            "Мне нужны наушники.",
            "Хорошо, ищу наушники.",
            "С Bluetooth, пожалуйста.",
            "Ищу Bluetooth наушники."
        ]
        
        actual_messages = [msg.content for msg in final_check_mr.chat_history]
        
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
            
    finally:
        db.close()


if __name__ == "__main__":
    test_repository_directly()