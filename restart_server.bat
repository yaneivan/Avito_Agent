@echo off
echo Остановка сервера...
taskkill /f /im python.exe 2>nul
timeout /t 2 /nobreak >nul
echo Запуск сервера...
start cmd /k "cd /d E:\Ucheba\DLS_sem2\Avito_Agent && python server.py"
echo Сервер запущен в новом окне
pause