#!/usr/bin/env python
"""
Скрипт для запуска Avito Agent
"""
import uvicorn
import os
import signal
import sys
from pathlib import Path

def signal_handler(sig, frame):
    print('\nПолучен сигнал завершения. Завершение работы...')
    sys.exit(0)

def main():
    # Создаем директории, если они не существуют
    Path("./data").mkdir(exist_ok=True)
    Path("./logs").mkdir(exist_ok=True)
    Path("./data/images").mkdir(exist_ok=True)

    # Регистрируем обработчик сигнала
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Запуск Avito Agent на порту 8001...")
    print("Убедитесь, что локальная LLM модель запущена на http://localhost:8080/v1")

    # Для production лучше отключить reload
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
        # reload=False  # Отключаем hot-reload для лучшей обработки сигналов
        # Если нужен reload для разработки, можно вернуть reload=True
    )

if __name__ == "__main__":
    main()