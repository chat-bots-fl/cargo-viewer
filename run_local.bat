@echo off
REM ============================================
REM Скрипт для локального запуска проекта Cargo Viewer (Windows)
REM ============================================
REM Этот bat-файл запускает PowerShell скрипт run_local.ps1
REM
REM Использование:
REM   run_local.bat                    # Запуск с настройками по умолчанию
REM   run_local.bat -SkipRedis         # Запуск без Redis
REM   run_local.bat -SkipDeps          # Пропустить установку зависимостей
REM   run_local.bat -Port 8080         # Запуск на порту 8080
REM ============================================

PowerShell -ExecutionPolicy Bypass -File "%~dp0run_local.ps1" %*

REM Если скрипт завершился с ошибкой, подождите перед закрытием
if errorlevel 1 (
    echo.
    echo Произошла ошибка. Нажмите любую клавишу для выхода...
    pause >nul
)
