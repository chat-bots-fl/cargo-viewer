@echo off
chcp 65001 >nul
REM ============================================
REM Скрипт запуска сервисов для Windows
REM ============================================
REM Выполняется каждый раз:
REM - Запуск ngrok
REM - Получение URL ngrok
REM - Обновление .env с новым URL
REM - Запуск Django сервера
REM - Настройка webhook для Telegram бота
REM ============================================

setlocal enabledelayedexpansion

echo ==========================================
echo   Запуск сервисов (Windows)
echo ==========================================
echo.

REM Проверяем наличие .env
if not exist .env (
    echo [ERROR] Файл .env не найден
    echo Сначала запустите setup.bat для подготовки окружения
    pause
    exit /b 1
)

REM Проверяем наличие venv
if not exist venv\Scripts\python.exe (
    echo [ERROR] Виртуальное окружение не найдено
    echo Сначала запустите setup.bat для подготовки окружения
    pause
    exit /b 1
)

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

REM 1. Запуск ngrok
echo [1/5] Запуск ngrok в отдельном окне...
start "ngrok" ngrok http 8000 --log=stdout

REM Ждём запуска ngrok
echo [2/5] Ожидание запуска ngrok (10 секунд)...
timeout /t 10 /nobreak >nul

REM 2. Получение URL ngrok
echo [3/5] Получение URL ngrok...
set NGROK_URL=
set RETRY=0

:retry_get_url
if %RETRY% LSS 5 (
    for /f "tokens=2 delims=:" %%A in (
      'curl -s http://127.0.0.1:4040/api/tunnels 2^>nul ^| findstr "https://"'
    ) do (
      set NGROK_URL=%%A
      set NGROK_URL=!NGROK_URL:,=!
      set NGROK_URL=!NGROK_URL:"=!
      goto :url_found
    )
    set /a RETRY+=1
    echo [INFO] Попытка !RETRY!/5...
    timeout /t 2 /nobreak >nul
    goto :retry_get_url
)

:url_found
if defined NGROK_URL (
    echo [SUCCESS] Получен URL ngrok: %NGROK_URL%
) else (
    echo [WARNING] Не удалось автоматически получить URL ngrok
    echo.
    echo Пожалуйста:
    echo 1. Откройте окно ngrok
    echo 2. Скопируйте URL (Forwarding)
    echo 3. Вставьте его ниже
    echo.
    set /p NGROK_URL="URL ngrok (например: https://xxxx-xxxx.ngrok-free.app): "
)

REM Проверяем, что URL начинается с https
if not "%NGROK_URL:~0,5%"=="https" (
    echo [ERROR] URL должен начинаться с https
    pause
    exit /b 1
)

REM Удаляем слеш в конце, если есть
if "%NGROK_URL:~-1%"=="/" set NGROK_URL=%NGROK_URL:~0,-1%

REM Получаем домен без https
set NGROK_DOMAIN=%NGROK_URL:~8%

REM 3. Обновление .env
echo [4/5] Обновление .env с новым URL...
powershell -Command "(Get-Content .env) -replace 'WEBAPP_URL=https://[^ ]*', 'WEBAPP_URL=%NGROK_URL%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'ALLOWED_HOSTS=[^ ]*', 'ALLOWED_HOSTS=localhost,127.0.0.1,%NGROK_DOMAIN%' | Set-Content .env"

echo [SUCCESS] .env обновлён с URL: %NGROK_URL%

REM 4. Запуск Django
echo [5/5] Запуск Django сервера в отдельном окне...
start "Django Server" cmd /k "call venv\Scripts\activate.bat && python manage.py runserver"

REM Ждём запуска Django
echo [INFO] Ожидание запуска Django (3 секунды)...
timeout /t 3 /nobreak >nul

REM 5. Настройка webhook
echo [INFO] Настройка webhook для Telegram бота...
call venv\Scripts\activate.bat
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
echo   - Закройте окно "ngrok"
echo   - Закройте окно "Django Server"
echo.
pause
