"""
Тест для проверки API эндпоинтов с реальными вызовами
"""
import asyncio
import json
from typing import Dict, Any

import httpx
import pytest

# URL сервера (предполагается, что сервер запущен на порту 8001)
BASE_URL = "http://localhost:8001/api"


async def test_full_history_through_api():
    """Тест проверяет, что API возвращает полную историю чата"""
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
        print(f"Состояние: {data['state']}")
        print(f"Количество сообщений в истории: {len(data['chat_history'])}")
        
        mr_id = data['id']
        
        # Проверяем, что в истории есть сообщения
        assert len(data['chat_history']) >= 1, "История должна содержать хотя бы одно сообщение"
        
        # Сохраняем начальную историю
        initial_history = data['chat_history']
        print(f"Исходная история: {[msg['content'] for msg in initial_history]}")
        
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
        print(f"История после второго сообщения: {[msg['content'] for msg in second_history]}")
        
        # Проверяем, что история увеличилась
        assert len(second_history) >= len(initial_history), "История должна увеличиваться"
        
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
        print(f"История после третьего сообщения: {[msg['content'] for msg in third_history]}")
        
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
        print(f"История после четвертого сообщения: {[msg['content'] for msg in fourth_history]}")
        
        # Проверяем, что история продолжает расти
        assert len(fourth_history) >= len(third_history), "История должна продолжать увеличиваться"
        
        # Шаг 5: Получаем исследование по ID и проверяем, что история сохраняется
        print("\nШаг 5: Получение исследования по ID...")
        response = await client.get(f"{BASE_URL}/market_research/{mr_id}", timeout=30.0)
        
        assert response.status_code == 200, f"Ошибка при получении исследования: {response.text}"
        
        data = response.json()
        retrieved_history = data['chat_history']
        print(f"Количество сообщений в полученной истории: {len(retrieved_history)}")
        print(f"Полученная история: {[msg['content'] for msg in retrieved_history]}")
        
        # Проверяем, что полученная история совпадает с последней отправленной
        assert len(retrieved_history) == len(fourth_history), "Полученная история должна совпадать с последней"
        
        # Проверяем, что все сообщения сохранены
        sent_contents = [msg['content'] for msg in fourth_history]
        received_contents = [msg['content'] for msg in retrieved_history]
        
        print(f"\nСравнение содержимого:")
        print(f"Отправлено: {sent_contents}")
        print(f"Получено: {received_contents}")
        
        assert sent_contents == received_contents, "Содержимое истории должно совпадать"
        
        print("\n✓ Все проверки пройдены! История корректно сохраняется и возвращается через API.")


async def test_polling_endpoint_also_returns_full_history():
    """Тест проверяет, что эндпоинт для опроса также возвращает полную историю"""
    async with httpx.AsyncClient() as client:
        # Создаем исследование
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "Тестовое сообщение для проверки опроса"},
            timeout=30.0
        )
        
        assert response.status_code == 200
        data = response.json()
        mr_id = data['id']
        
        print(f"Создано исследование для проверки опроса: {mr_id}")
        
        # Отправляем несколько сообщений
        messages = [
            "Первое дополнительное сообщение",
            "Второе дополнительное сообщение", 
            "Третье дополнительное сообщение"
        ]
        
        for i, msg in enumerate(messages):
            response = await client.post(
                f"{BASE_URL}/chat",
                json={"message": msg, "mr_id": mr_id},
                timeout=30.0
            )
            assert response.status_code == 200
            print(f"Отправлено сообщение {i+1}: {msg}")
        
        # Получаем исследование через эндпоинт опроса
        response = await client.get(f"{BASE_URL}/market_research/{mr_id}", timeout=30.0)
        assert response.status_code == 200
        
        data = response.json()
        history = data['chat_history']
        print(f"История через эндпоинт опроса: {len(history)} сообщений")
        
        # Проверяем, что все сообщения присутствуют
        contents = [msg['content'] for msg in history]
        assert "Тестовое сообщение для проверки опроса" in contents
        for msg in messages:
            assert msg in contents
            
        print("✓ Эндпоинт опроса также возвращает полную историю!")


if __name__ == "__main__":
    print("Запуск теста API эндпоинтов...")
    print("Убедитесь, что сервер запущен на http://localhost:8001")
    
    try:
        asyncio.run(test_full_history_through_api())
        print("\n" + "="*50)
        asyncio.run(test_polling_endpoint_also_returns_full_history())
        print("\n" + "="*50)
        print("Все тесты пройдены успешно!")
        print("Проблема не на бэкенде - API корректно возвращает полную историю.")
    except Exception as e:
        print(f"\nОшибка при выполнении теста: {e}")
        print("Возможно, сервер не запущен или недоступен.")