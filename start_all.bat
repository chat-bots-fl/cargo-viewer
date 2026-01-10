@echo off
chcp 65001 >nul
REM ============================================
REM Автоматический запуск ngrok, Django и webhook
REM ============================================
REM Скрипт автоматически:
REM 1. Запускает ngrok на порту 8000
REM 2. Получает URL ngrok
REM 3. Обновляет .env с новым URL
REM 4. Запускает Django сервер
REM 5. Настраивает webhook для Telegram бота
REM ============================================

setlocal enabledelayedexpansion

echo ==========================================
echo   Автоматический запуск проекта
echo ==========================================
echo.

REM Проверяем наличие ngrok
where ngrok >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] ngrok не найден в PATH
    echo Установите ngrok: https://ngrok.com/download
    pause
    exit /b 1
)

REM Проверяем наличие Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден в PATH
    pause
    exit /b 1
)

REM Проверяем наличие .env
if not exist .env (
    echo [ERROR] Файл .env не найден
    pause
    exit /b 1
)

echo [1/5] Запуск ngrok на порту 8000...
start "" ngrok http 8000 --log=stdout

REM Ждём запуска ngrok и получения URL
echo [2/5] Ожидание запуска ngrok (5 секунд)...
timeout /t 5 /nobreak >nul

REM Пытаемся получить URL из ngrok API
echo [3/5] Получение URL ngrok...
for /f "tokens=2 delims=:, " %%A in (
  'curl -s http://127.0.0.1:4040/api/tunnels ^| findstr "public_url"'
) do (
  set NGROK_URL=%%A
  goto :url_found
)

:url_found
if defined NGROK_URL (
    echo [INFO] Получен URL ngrok: %NGROK_URL%
) else (
    echo [WARNING] Не удалось автоматически получить URL ngrok
    echo [INFO] Пожалуйста, введите URL ngrok вручную:
    set /p NGROK_URL="URL ngrok (например: https://xxxx-xxxx.ngrok-free.app): "
)

REM Проверяем, что URL начинается с https
if not "%NGROK_URL:~0,5%"=="https" (
    echo [ERROR] URL должен начинаться с https
    pause
    exit /b 1
)

REM Обновляем .env файл
echo [4/5] Обновление .env с новым URL...
powershell -Command "(Get-Content .env) -replace 'WEBAPP_URL=https://[^ ]*', 'WEBAPP_URL=%NGROK_URL%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'ALLOWED_HOSTS=[^ ]*', 'ALLOWED_HOSTS=localhost,127.0.0.1,%NGROK_URL:~8%' | Set-Content .env"

echo [INFO] .env обновлён с URL: %NGROK_URL%

REM Запускаем Django в новом окне
echo [INFO] Запуск Django сервера в отдельном окне...
start "Django Server" cmd /k "python manage.py runserver"

REM Ждём запуска Django
echo [INFO] Ожидание запуска Django (3 секунды)...
timeout /t 3 /nobreak >nul

REM Настраиваем webhook
echo [5/5] Настройка webhook для Telegram бота...
python setup_telegram_webhook.py setup

echo.
echo ==========================================
echo   Запуск завершён!
echo ==========================================
echo.
echo Информация:
echo   - ngrok URL: %NGROK_URL%
echo   - Webhook настроен на: %NGROK_URL%/telegram/webhook/
echo.
echo Для проверки webhook:
echo   python setup_telegram_webhook.py info
echo.
echo Для остановки:
echo   - Закройте окно ngrok
echo   - Закройте окно Django Server
echo.
pause
