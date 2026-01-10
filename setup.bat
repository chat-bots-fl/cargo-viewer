@echo off
chcp 65001 >nul
REM ============================================
REM Скрипт подготовки окружения для Windows
REM ============================================
REM Выполняет один раз или при изменениях:
REM - Проверка .env файла
REM - Создание виртуального окружения
REM - Установка зависимостей
REM - Применение миграций БД
REM - Сбор статических файлов
REM - Запуск Redis (опционально)
REM ============================================

setlocal enabledelayedexpansion

echo ==========================================
echo   Подготовка окружения (Windows)
echo ==========================================
echo.

REM Проверяем наличие Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден в PATH
    pause
    exit /b 1
)

REM 1. Проверка .env файла
echo [1/5] Проверка конфигурации...
if not exist .env (
    echo [ERROR] Файл .env не найден!
    echo Создайте .env файл из .env.example:
    echo   copy .env.example .env
    echo Затем отредактируйте .env и добавьте свои настройки.
    pause
    exit /b 1
)
echo [SUCCESS] Файл .env найден

REM 2. Проверка виртуального окружения
echo.
echo [2/5] Проверка виртуального окружения...
if not exist venv\Scripts\python.exe (
    echo [INFO] Создаю виртуальное окружение...
    python -m venv venv
    echo [SUCCESS] Виртуальное окружение создано
) else (
    echo [SUCCESS] Виртуальное окружение существует
)

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM 3. Установка зависимостей
echo.
echo [3/5] Проверка зависимостей...
if not exist .installed_hash (
    goto :install_deps
)

REM Проверяем хеш requirements.txt
for /f "skip=1 delims=" %%H in ('certutil -hashfile requirements.txt SHA256 ^| findstr /C:"SHA256 hash"') do set CURRENT_HASH=%%H
set CURRENT_HASH=%CURRENT_HASH: =%

if exist .installed_hash (
    set /p INSTALLED_HASH=<.installed_hash
) else (
    set INSTALLED_HASH=
)

if not "%CURRENT_HASH%"=="%INSTALLED_HASH%" (
    goto :install_deps
)

echo [SUCCESS] Зависимости уже установлены
goto :skip_install

:install_deps
echo [INFO] Устанавливаю зависимости из requirements.txt...
echo [WARNING] Это может занять несколько минут...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Ошибка при установке зависимостей
    pause
    exit /b 1
)
echo %CURRENT_HASH% > .installed_hash
echo [SUCCESS] Зависимости установлены

:skip_install

REM 4. Применение миграций
echo.
echo [4/5] Применение миграций базы данных...
python manage.py migrate --noinput
if %errorlevel% neq 0 (
    echo [ERROR] Ошибка при применении миграций
    pause
    exit /b 1
)
echo [SUCCESS] Миграции применены

REM 5. Сбор статических файлов
echo.
echo [5/5] Сбор статических файлов...
python manage.py collectstatic --noinput --clear
if %errorlevel% neq 0 (
    echo [ERROR] Ошибка при сборе статики
    pause
    exit /b 1
)
echo [SUCCESS] Статические файлы собраны

echo.
echo ==========================================
echo   Подготовка завершена!
echo ==========================================
echo.
echo Теперь можно запустить проект:
echo   start.bat
echo.
pause
