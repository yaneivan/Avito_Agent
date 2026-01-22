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

# Получаем абсолютный путь к директории, где находится этот скрипт
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCRIPT_DIR, "chat_history.json")
SERVER_URL = "http://localhost:8001/api/deep_research/chat"
CHAT_HISTORY_DB_URL = "http://localhost:8001/api/chats"
CHAT_MESSAGES_DB_URL = "http://localhost:8001/api/chats/{chat_id}/messages"

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

def create_new_chat_session():
    """Создать новую сессию чата в базе данных"""
    try:
        response = requests.post(CHAT_HISTORY_DB_URL)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка при создании сессии чата: {response.status_code}")
            print(response.text)
            return None
    except requests.exceptions.ConnectionError:
        print(f"Ошибка подключения к серверу. Убедитесь, что сервер запущен на {CHAT_HISTORY_DB_URL.split('/api')[0]}")
        return None
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
        return None

def add_message_to_db(chat_id, role, content, message_type=None, metadata=None):
    """Добавить сообщение в базу данных"""
    try:
        message_data = {
            "role": role,
            "content": content,
            "message_type": message_type,
            "extra_metadata": json.dumps(metadata) if metadata else None
        }
        url = CHAT_MESSAGES_DB_URL.format(chat_id=chat_id)
        response = requests.post(url, json=message_data)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка при добавлении сообщения в БД: {response.status_code}")
            print(response.text)
            return None
    except requests.exceptions.ConnectionError:
        print(f"Ошибка подключения к серверу. Убедитесь, что сервер запущен на {CHAT_MESSAGES_DB_URL.split('/api')[0]}")
        return None
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
        return None

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
        print(f"Ошибка подключения к серверу. Убедитесь, что сервер запущен на {SERVER_URL.split('/api')[0]}")
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
    parser.add_argument("--db-chat-id", type=int, help="ID сессии чата в базе данных для использования")
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
        print("Для указания ID чата в БД: python chat_client.py --db-chat-id 1 'Ваше сообщение'")
        return

    # Получаем или создаем ID чата в базе данных
    db_chat_id = args.db_chat_id
    if not db_chat_id:
        # Создаем новую сессию чата в базе данных
        chat_session = create_new_chat_session()
        if chat_session:
            db_chat_id = chat_session.get("id")
            print(f"Создана новая сессия чата в базе данных с ID: {db_chat_id}")
        else:
            print("Не удалось создать сессию чата в базе данных")
            return

    # Добавляем новое сообщение к истории
    new_message = {
        "role": "user",
        "content": args.message,
        "timestamp": datetime.now().isoformat()
    }
    history.append(new_message)

    # Добавляем сообщение в базу данных
    user_msg_added = add_message_to_db(db_chat_id, "user", args.message, "user_request")
    if not user_msg_added:
        print("Предупреждение: Не удалось добавить сообщение пользователя в базу данных")

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

        # Добавляем ответ сервера в базу данных
        assistant_msg_added = add_message_to_db(
            db_chat_id,
            "assistant",
            response.get("message", ""),
            response.get("type", "chat_response"),
            {
                "stage": response.get("stage"),
                "search_id": response.get("search_id"),
                "reasoning": response.get("reasoning"),
                "internal_thoughts": response.get("internal_thoughts")
            }
        )
        if not assistant_msg_added:
            print("Предупреждение: Не удалось добавить ответ ассистента в базу данных")

        # Сохраняем обновленную историю
        save_history(history)

        # Выводим ответ сервера
        print_response(response)
    else:
        # Если произошла ошибка, все равно сохраним историю с пользовательским сообщением
        save_history(history)

if __name__ == "__main__":
    main()