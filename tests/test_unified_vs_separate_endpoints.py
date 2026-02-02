"""
Тест для сравнения поведения unified endpoint и отдельных эндпоинтов
"""
import asyncio
import json
from typing import Dict, Any

import httpx
import pytest

# URL сервера (предполагается, что сервер запущен на порту 8001)
BASE_URL = "http://localhost:8001/api"


async def test_unified_endpoint():
    """Тест проверяет поведение unified endpoint (создание + генерация в одном вызове)"""
    print("=== Тест 1: Совмещенный эндпоинт (unified endpoint) ===")
    async with httpx.AsyncClient() as client:
        # Создаем новое исследование с первым сообщением через unified endpoint
        print("Отправка первого сообщения через unified endpoint...")
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
        
        initial_history = data['chat_history']
        print(f"Исходная история: {[msg['content'] for msg in initial_history]}")
        
        # Отправляем второе сообщение в тот же чат
        print("\nОтправка второго сообщения в тот же чат...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "Мне нужны наушники.", "mr_id": data['id']},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при отправке второго сообщения: {response.text}"
        
        data = response.json()
        print(f"Количество сообщений в истории после второго сообщения: {len(data['chat_history'])}")
        
        second_history = data['chat_history']
        print(f"История после второго сообщения: {[msg['content'] for msg in second_history]}")
        
        # Отправляем третье сообщение
        print("\nОтправка третьего сообщения...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "С Bluetooth, пожалуйста.", "mr_id": data['id']},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при отправке третьего сообщения: {response.text}"
        
        data = response.json()
        print(f"Количество сообщений в истории после третьего сообщения: {len(data['chat_history'])}")
        
        third_history = data['chat_history']
        print(f"История после третьего сообщения: {[msg['content'] for msg in third_history]}")
        
        return {
            'initial_history': initial_history,
            'second_history': second_history,
            'third_history': third_history
        }


async def test_separate_endpoints():
    """Тест проверяет поведение отдельных эндпоинтов (создание, потом генерация)"""
    print("\n=== Тест 2: Отдельные эндпоинты (создание + генерация отдельно) ===")
    async with httpx.AsyncClient() as client:
        # Сначала создаем исследование через отдельный эндпоинт
        print("Создание исследования через отдельный эндпоинт...")
        response = await client.post(
            f"{BASE_URL}/market_research",
            json={"message": "Привет!"},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при создании исследования: {response.text}"
        
        creation_data = response.json()
        print(f"ID созданного исследования: {creation_data['id']}")
        print(f"Состояние после создания: {creation_data['state']}")
        print(f"Количество сообщений в истории после создания: {len(creation_data['chat_history'])}")
        
        # Теперь отправляем сообщение в созданный чат
        print("\nОтправка первого сообщения в созданный чат...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "Привет! Какие наушники посоветуете?", "mr_id": creation_data['id']},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при отправке сообщения: {response.text}"
        
        first_response_data = response.json()
        print(f"Количество сообщений в истории после первого сообщения: {len(first_response_data['chat_history'])}")
        
        first_history = first_response_data['chat_history']
        print(f"История после первого сообщения: {[msg['content'] for msg in first_history]}")
        
        # Отправляем второе сообщение
        print("\nОтправка второго сообщения...")
        response = await client.post(
            f"{BASE_URL}/chat",
            json={"message": "С Bluetooth, пожалуйста.", "mr_id": creation_data['id']},
            timeout=30.0
        )
        
        assert response.status_code == 200, f"Ошибка при отправке второго сообщения: {response.text}"
        
        second_response_data = response.json()
        print(f"Количество сообщений в истории после второго сообщения: {len(second_response_data['chat_history'])}")
        
        second_history = second_response_data['chat_history']
        print(f"История после второго сообщения: {[msg['content'] for msg in second_history]}")
        
        return {
            'first_history': first_history,
            'second_history': second_history
        }


async def compare_behaviors():
    """Сравниваем поведение двух подходов"""
    print("Начинаем сравнение поведения unified и отдельных эндпоинтов...")
    
    # Тестируем unified endpoint
    unified_result = await test_unified_endpoint()
    
    # Тестируем отдельные эндпоинты
    separate_result = await test_separate_endpoints()
    
    print("\n=== Сравнение результатов ===")
    
    # Проверяем количество сообщений в каждом случае
    unified_initial_count = len(unified_result['initial_history'])
    unified_second_count = len(unified_result['second_history'])
    unified_third_count = len(unified_result['third_history'])
    
    separate_first_count = len(separate_result['first_history'])
    separate_second_count = len(separate_result['second_history'])
    
    print(f"Unified endpoint - после 1 сообщения: {unified_initial_count} сообщений")
    print(f"Unified endpoint - после 2 сообщений: {unified_second_count} сообщений")
    print(f"Unified endpoint - после 3 сообщений: {unified_third_count} сообщений")
    
    print(f"Отдельные эндпоинты - после 1 сообщения: {separate_first_count} сообщений")
    print(f"Отдельные эндпоинты - после 2 сообщений: {separate_second_count} сообщений")
    
    # Проверяем, есть ли дублирование в каждом случае
    def has_duplicates(history_list):
        seen = set()
        for msg in history_list:
            key = (msg['role'], msg['content'])
            if key in seen:
                return True, key
            seen.add(key)
        return False, None
    
    unified_has_dups, unified_dup = has_duplicates(unified_result['third_history'])
    separate_has_dups, separate_dup = has_duplicates(separate_result['second_history'])
    
    print(f"\nUnified endpoint - дубликаты: {'ДА' if unified_has_dups else 'НЕТ'}")
    if unified_has_dups:
        print(f"  Дубликат: {unified_dup}")
    
    print(f"Отдельные эндпоинты - дубликаты: {'ДА' if separate_has_dups else 'НЕТ'}")
    if separate_has_dups:
        print(f"  Дубликат: {separate_dup}")
    
    # Проверяем, все ли сообщения присутствуют
    unified_contents = [msg['content'] for msg in unified_result['third_history']]
    separate_contents = [msg['content'] for msg in separate_result['second_history']]
    
    print(f"\nUnified endpoint - содержимое: {unified_contents}")
    print(f"Отдельные эндпоинты - содержимое: {separate_contents}")
    
    # Проверяем наличие ожидаемых сообщений
    expected_unified = ["Привет!", "Мне нужны наушники.", "С Bluetooth, пожалуйста."]
    expected_separate = ["Привет!", "Привет! Какие наушники посоветуете?", "С Bluetooth, пожалуйста."]
    
    unified_missing = [msg for msg in expected_unified if not any(msg in content for content in unified_contents)]
    separate_missing = [msg for msg in expected_separate if not any(msg in content for content in separate_contents)]
    
    print(f"\nUnified endpoint - отсутствующие ожидаемые сообщения: {unified_missing}")
    print(f"Отдельные эндпоинты - отсутствующие ожидаемые сообщения: {separate_missing}")
    
    print("\nСравнение завершено!")


if __name__ == "__main__":
    print("Запуск теста сравнения unified и отдельных эндпоинтов...")
    print("Убедитесь, что сервер запущен на http://localhost:8001")
    
    try:
        asyncio.run(compare_behaviors())
    except Exception as e:
        print(f"\nОшибка при выполнении теста: {e}")
        print("Возможно, сервер не запущен или недоступен.")