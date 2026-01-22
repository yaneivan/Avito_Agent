#!/bin/bash
echo "Остановка сервера..."
pkill -f "python.*server.py" 2>/dev/null
sleep 2
echo "Запуск сервера..."
python server.py &
echo "Сервер запущен в фоне"