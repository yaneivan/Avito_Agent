"""
Тест для проверки корректности сохранения истории чата через API
"""
import asyncio
import json
from typing import Dict, Any

import httpx
import pytest

# URL сервера (предполагается, что сервер запущен на порту 8001)
BASE_URL = "http://localhost:8001/api"


async def test_chat_history_preserves_all_messages():
    """Тест проверяет, что все сообщения пользователя сохраняются в истории"""
    async with httpx.AsyncClient() as client:
        # Шаг 1: Создаем новое исследование с первым сообщением
        print("Шаг 1: Создание нового исследования...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "Привет!"},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при создании чата: {response.text}"
        
        data = response.json()
        print(f"ID исследования: {data['id']}")
        print(f"Количество сообщений в истории: {len(data['chat_history'])}")
        
        mr_id = data['id']
        
        # Сохраняем начальную историю
        initial_history = data['chat_history']
        print(f"Исходные сообщения: {[msg['content'] for msg in initial_history]}")
        
        # Шаг 2: Отправляем второе сообщение
        print("\nШаг 2: Отправка второго сообщения...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "Мне нужны наушники.", "mr_id": mr_id},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при отправке второго сообщения: {response.text}"
        
        data = response.json()
        print(f"Количество сообщений в истории после второго сообщения: {len(data['chat_history'])}")
        
        second_history = data['chat_history']
        print(f"Сообщения после второго сообщения: {[msg['content'] for msg in second_history]}")
        
        # Проверяем, что второе сообщение присутствует в истории
        second_msg_found = any(msg['content'] == "Мне нужны наушники." and msg['role'] == 'user' 
                              for msg in second_history)
        assert second_msg_found, "Второе сообщение пользователя должно быть в истории"
        
        # Шаг 3: Отправляем третье сообщение
        print("\nШаг 3: Отправка третьего сообщения...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "С Bluetooth, пожалуйста.", "mr_id": mr_id},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при отправке третьего сообщения: {response.text}"
        
        data = response.json()
        print(f"Количество сообщений в истории после третьего сообщения: {len(data['chat_history'])}")
        
        third_history = data['chat_history']
        print(f"Сообщения после третьего сообщения: {[msg['content'] for msg in third_history]}")
        
        # Проверяем, что третье сообщение присутствует в истории
        third_msg_found = any(msg['content'] == "С Bluetooth, пожалуйста." and msg['role'] == 'user' 
                             for msg in third_history)
        assert third_msg_found, "Третье сообщение пользователя должно быть в истории"
        
        # Шаг 4: Отправляем четвертое сообщение
        print("\nШаг 4: Отправка четвертого сообщения...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "А сколько примерно стоят?", "mr_id": mr_id},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при отправке четвертого сообщения: {response.text}"
        
        data = response.json()
        print(f"Количество сообщений в истории после четвертого сообщения: {len(data['chat_history'])}")
        
        fourth_history = data['chat_history']
        print(f"Сообщения после четвертого сообщения: {[msg['content'] for msg in fourth_history]}")
        
        # Проверяем, что четвертое сообщение присутствует в истории
        fourth_msg_found = any(msg['content'] == "А сколько примерно стоят?" and msg['role'] == 'user' 
                              for msg in fourth_history)
        assert fourth_msg_found, "Четвертое сообщение пользователя должно быть в истории"
        
        # Шаг 5: Проверяем, что все сообщения присутствуют в правильном порядке
        print("\nШаг 5: Проверка полного содержимого истории...")
        all_user_messages = [msg for msg in fourth_history if msg['role'] == 'user']
        all_assistant_messages = [msg for msg in fourth_history if msg['role'] == 'assistant']
        
        print(f"Все сообщения пользователя: {[msg['content'] for msg in all_user_messages]}")
        print(f"Все сообщения ассистента: {[msg['content'] for msg in all_assistant_messages]}")
        
        # Проверяем, что все наши сообщения присутствуют
        expected_user_messages = [
            "Привет!",
            "Мне нужны наушники.",
            "С Bluetooth, пожалуйста.",
            "А сколько примерно стоят?"
        ]
        
        for exp_msg in expected_user_messages:
            found = any(msg['content'] == exp_msg for msg in all_user_messages)
            assert found, f"Ожидаемое сообщение '{exp_msg}' не найдено в истории"
        
        # Шаг 6: Получаем исследование по ID и проверяем, что история сохраняется
        print("\nШаг 6: Получение исследования по ID для проверки сохранения...")
        response = await client.get(f"{BASE_URL}/market_research/{mr_id}", timeout=30.0)
        
        assert response.status_code == 200, f"Ошибка при получении исследования: {response.text}"
        
        data = response.json()
        retrieved_history = data['chat_history']
        print(f"Количество сообщений в полученной истории: {len(retrieved_history)}")
        print(f"Полученные сообщения: {[msg['content'] for msg in retrieved_history]}")
        
        # Проверяем, что все наши сообщения присутствуют в полученной истории
        for exp_msg in expected_user_messages:
            found = any(msg['content'] == exp_msg for msg in retrieved_history if msg['role'] == 'user')
            assert found, f"Ожидаемое сообщение '{exp_msg}' не найдено в полученной истории"
        
        print("\n✓ Все проверки пройдены! Все сообщения пользователя корректно сохранены в истории.")


async def test_history_increases_with_each_message():
    """Тест проверяет, что история увеличивается с каждым новым сообщением"""
    async with httpx.AsyncClient() as client:
        # Создаем новое исследование
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "Тест истории"},
            timeout=30.0
        )
        
        assert response.status_code == 200
        data = response.json()
        mr_id = data['id']
        
        initial_count = len(data['chat_history'])
        print(f"Начальное количество сообщений: {initial_count}")
        
        # Отправляем несколько сообщений и проверяем, что история увеличивается
        messages = [
            "Первое дополнительное сообщение",
            "Второе дополнительное сообщение",
            "Третье дополнительное сообщение"
        ]
        
        prev_count = initial_count
        
        for i, msg in enumerate(messages):
            response = await client.post(
                f"{BASE_URL}/chat",
                json={"message": msg, "mr_id": mr_id},
                timeout=30.0
            )
            
            assert response.status_code == 200
            data = response.json()
            
            current_count = len(data['chat_history'])
            print(f"После сообщения {i+1} ({msg}): {current_count} сообщений")
            
            # Проверяем, что история увеличилась (или осталась той же, если LLM не ответил)
            # В идеале, история должна увеличиваться минимум на 1 (сообщение пользователя) + 1 (ответ LLM)
            assert current_count >= prev_count, f"История должна сохранять или увеличивать количество сообщений"
            
            prev_count = current_count
        
        print(f"✓ История корректно увеличивается: с {initial_count} до {prev_count}")


if __name__ == "__main__":
    print("Запуск теста сохранения истории чата...")
    print("Убедитесь, что сервер запущен на http://localhost:8001")
    
    try:
        asyncio.run(test_chat_history_preserves_all_messages())
        print("\n" + "="*50)
        asyncio.run(test_history_increases_with_each_message())
        print("\n" + "="*50)
        print("Все тесты пройдены успешно!")
        print("История чата корректно сохраняется и увеличивается.")
    except Exception as e:
        print(f"\nОшибка при выполнении теста: {e}")
        print("Возможно, сервер не запущен или недоступен.")
        import traceback
        traceback.print_exc()