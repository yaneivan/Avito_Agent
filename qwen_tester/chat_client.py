#!/usr/bin/env python3
"""
Инструмент для тестирования Avito Agent
Позволяет отправлять сообщения на сервер и управлять историей чата
"""

import argparse
import json
import os
import requests
from datetime import datetime

HISTORY_FILE = "chat_history.json"
SERVER_URL = "http://localhost:8000/api/deep_research/chat"

def load_history():
    """Загрузка истории чата из файла"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"Ошибка чтения файла истории {HISTORY_FILE}, создаем новую историю")
                return []
    return []

def save_history(history):
    """Сохранение истории чата в файл"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def reset_history():
    """Сброс истории чата"""
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
        print("История чата сброшена")
    else:
        print("Файл истории не существует, создадим пустую историю")

def send_message_to_server(history):
    """Отправка истории чата на сервер"""
    try:
        response = requests.post(
            SERVER_URL,
            json={"history": history},
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка при отправке запроса: {response.status_code}")
            print(response.text)
            return None
            
    except requests.exceptions.ConnectionError:
        print("Ошибка подключения к серверу. Убедитесь, что сервер запущен на http://localhost:8000")
        return None
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
        return None

def print_response(response):
    """Вывод ответа сервера в удобном формате"""
    if not response:
        print("Нет ответа от сервера")
        return
        
    print("\n" + "="*50)
    print("ОТВЕТ СЕРВЕРА:")
    print("="*50)
    
    if "message" in response:
        print(f"Сообщение: {response['message']}")
    
    if "type" in response:
        print(f"Тип: {response['type']}")
        
    if "stage" in response:
        print(f"Этап: {response['stage']}")
        
    if "search_id" in response:
        print(f"ID поиска: {response['search_id']}")
        
    if "reasoning" in response and response["reasoning"]:
        print(f"Обоснование: {response['reasoning']}")
        
    if "internal_thoughts" in response and response["internal_thoughts"]:
        print(f"Внутренние мысли: {response['internal_thoughts']}")
        
    if "plan" in response:
        print(f"План: {json.dumps(response['plan'], ensure_ascii=False, indent=2)}")
        
    if "schema_proposal" in response:
        print(f"Предложение схемы: {json.dumps(response['schema_proposal'], ensure_ascii=False, indent=2)}")
        
    print("="*50)

def main():
    parser = argparse.ArgumentParser(description="Инструмент для тестирования Avito Agent")
    parser.add_argument("message", nargs="?", help="Сообщение для отправки серверу")
    parser.add_argument("--reset", action="store_true", help="Сбросить историю чата")
    parser.add_argument("--view", action="store_true", help="Просмотреть текущую историю чата")
    parser.add_argument("--server-url", default=SERVER_URL, help="URL сервера (по умолчанию: http://localhost:8000/api/deep_research/chat)")

    args = parser.parse_args()

    # Обновляем глобальную переменную SERVER_URL значением из аргументов
    globals()['SERVER_URL'] = args.server_url
    
    # Если указан флаг сброса, сбрасываем историю
    if args.reset:
        reset_history()
        return
    
    # Загружаем историю
    history = load_history()
    
    # Если указан флаг просмотра, показываем историю и выходим
    if args.view:
        if history:
            print("Текущая история чата:")
            for i, msg in enumerate(history):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "no timestamp")
                print(f"{i+1}. [{role}] {timestamp}: {content}")
        else:
            print("История чата пуста")
        return
    
    # Если не указано сообщение, выводим справку
    if not args.message:
        print("Использование: python chat_client.py '<сообщение>'")
        print("Пример: python chat_client.py 'Хочу найти хороший смартфон'")
        print("Для просмотра истории: python chat_client.py --view")
        print("Для сброса истории: python chat_client.py --reset")
        return
    
    # Добавляем новое сообщение к истории
    new_message = {
        "role": "user",
        "content": args.message,
        "timestamp": datetime.now().isoformat()
    }
    history.append(new_message)
    
    # Отправляем запрос на сервер
    print(f"Отправляем сообщение: {args.message}")
    response = send_message_to_server(history)
    
    if response:
        # Добавляем ответ сервера к истории
        server_response = {
            "role": "assistant",
            "content": response.get("message", ""),
            "type": response.get("type", ""),
            "timestamp": datetime.now().isoformat()
        }
        history.append(server_response)
        
        # Сохраняем обновленную историю
        save_history(history)
        
        # Выводим ответ сервера
        print_response(response)
    else:
        # Если произошла ошибка, все равно сохраним историю с пользовательским сообщением
        save_history(history)

if __name__ == "__main__":
    main()