#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Скрипт для локального запуска проекта Cargo Viewer

.DESCRIPTION
    Автоматизирует процесс настройки и запуска проекта:
    - Проверяет наличие .env файла (требуется создать вручную)
    - Создаёт и активирует виртуальное окружение
    - Устанавливает зависимости
    - Применяет миграции базы данных
    - Собирает статические файлы
    - Запускает Redis (опционально)
    - Запускает сервер разработки

.EXAMPLE
    .\run_local.ps1
    Запуск с настройками по умолчанию

.EXAMPLE
    .\run_local.ps1 -SkipRedis
    Запуск без Redis (используется локальный кэш)
#>

[CmdletBinding()]
param(
    [switch]$SkipRedis,
    [switch]$SkipMigrations,
    [switch]$SkipStatic,
    [switch]$SkipDeps,
    [string]$Port = "8000",
    [string]$ServerHost = "127.0.0.1"
)

<#
GOAL: Выполнить команду с отображением её вывода

PARAMETERS:
  Command: string - Команда для выполнения
  Args: string[] - Аргументы команды

RETURNS:
  int - Код возврата команды

RAISES:
  System.InvalidOperationException: Если команда завершилась с ошибкой

GUARANTEES:
  - Вывод команды отображается в консоли
  - При ошибке скрипт завершается с кодом 1
#>
function Invoke-CommandSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        
        [Parameter(Mandatory = $false)]
        [string[]]$Args = @()
    )
    
    Write-Host "`n>>> Выполняю: $Command $($Args -join ' ')" -ForegroundColor Cyan
    
    $processInfo = New-Object System.Diagnostics.ProcessStartInfo
    $processInfo.FileName = $Command
    $processInfo.Arguments = $Args -join ' '
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    $processInfo.CreateNoWindow = $true
    
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $processInfo
    $process.Start() | Out-Null
    
    $outputTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    
    $process.WaitForExit()
    
    $output = $outputTask.Result
    $stderr = $stderrTask.Result
    
    if ($output) { Write-Host $output }
    if ($stderr) { Write-Host $stderr -ForegroundColor Red }
    
    if ($process.ExitCode -ne 0) {
        throw "Команда завершилась с кодом $($process.ExitCode)"
    }
    
    return $process.ExitCode
}

<#
GOAL: Проверить наличие команды в PATH

PARAMETERS:
  Command: string - Имя команды для проверки

RETURNS:
  bool - True если команда существует, иначе False

RAISES:
  None

GUARANTEES:
  - Возвращает корректный результат для любой команды
#>
function Test-CommandExists {
    param([string]$Command)
    
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try {
        if (Get-Command $Command) { return $true }
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $oldPreference
    }
    return $false
}

# Основной блок скрипта
try {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Cargo Viewer - Локальный запуск" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $scriptDir
    
    # 1. Проверка .env файла
    Write-Host "`n[1/7] Проверка конфигурации..." -ForegroundColor Yellow
    if (-not (Test-Path ".env")) {
        Write-Host "  ❌ Файл .env не найден!" -ForegroundColor Red
        Write-Host "  Создайте .env файл из .env.example:" -ForegroundColor Yellow
        Write-Host "    cp .env.example .env" -ForegroundColor Cyan
        Write-Host "  Затем отредактируйте .env и добавьте свои настройки." -ForegroundColor Yellow
        Write-Host "`nДля продолжения нажмите Enter или Ctrl+C для выхода..."
        $null = Read-Host
        if (-not (Test-Path ".env")) {
            Write-Host "`n❌ Файл .env не создан. Запуск отменён." -ForegroundColor Red
            exit 1
        }
    }
    Write-Host "  ✓ Файл .env найден" -ForegroundColor Green
    
    # 2. Проверка виртуального окружения
    Write-Host "`n[2/7] Проверка виртуального окружения..." -ForegroundColor Yellow
    $venvDir = "venv"
    
    if (-not (Test-Path $venvDir)) {
        Write-Host "  Создаю виртуальное окружение..." -ForegroundColor Cyan
        Invoke-CommandSafe -Command "python" -Args @("-m", "venv", $venvDir)
        Write-Host "  ✓ Виртуальное окружение создано" -ForegroundColor Green
    } else {
        Write-Host "  ✓ Виртуальное окружение существует" -ForegroundColor Green
    }
    
    # Определение пути к Python в виртуальном окружении
    $pythonPath = if ($IsWindows -or $env:OS -eq "Windows_NT") {
        Join-Path $venvDir "Scripts/python.exe"
    } else {
        Join-Path $venvDir "bin/python"
    }
    
    $pipPath = if ($IsWindows -or $env:OS -eq "Windows_NT") {
        Join-Path $venvDir "Scripts/pip.exe"
    } else {
        Join-Path $venvDir "bin/pip"
    }
    
    # 3. Установка зависимостей
    Write-Host "`n[3/7] Проверка зависимостей..." -ForegroundColor Yellow
    
    if ($SkipDeps) {
        Write-Host "  ⚠ Установка зависимостей пропущена (-SkipDeps)" -ForegroundColor Yellow
        Write-Host "  ✓ Пропущено" -ForegroundColor Green
    } else {
        $requirementsHash = (Get-FileHash "requirements.txt" -Algorithm SHA256).Hash
        $installedHash = if (Test-Path ".installed_hash") { Get-Content ".installed_hash" } else { "" }
        
        if ($requirementsHash -ne $installedHash) {
            Write-Host "  Устанавливаю зависимости из requirements.txt..." -ForegroundColor Cyan
            Write-Host "  ⚠ Это может занять несколько минут..." -ForegroundColor Yellow
            Invoke-CommandSafe -Command $pipPath -Args @("install", "-r", "requirements.txt")
            $requirementsHash | Out-File -FilePath ".installed_hash" -Encoding utf8
            Write-Host "  ✓ Зависимости установлены" -ForegroundColor Green
        } else {
            Write-Host "  ✓ Зависимости уже установлены" -ForegroundColor Green
        }
    }
    
    # 4. Запуск Redis (если требуется)
    if (-not $SkipRedis) {
        Write-Host "`n[4/7] Проверка Redis..." -ForegroundColor Yellow
        
        if (Test-CommandExists "docker") {
            $redisRunning = docker ps --filter "name=redis" --format "{{.Names}}" | Select-String "redis"
             
            if (-not $redisRunning) {
                Write-Host "  Запускаю Redis через Docker Compose..." -ForegroundColor Cyan
                $dockerOutput = docker-compose up -d redis 2>&1
                if ($dockerOutput -match "authentication required") {
                    Write-Host "  ❌ Ошибка: Docker требует аутентификацию" -ForegroundColor Red
                    Write-Host "  ⚠ Войдите в Docker Desktop или используйте -SkipRedis" -ForegroundColor Yellow
                    Write-Host "  ⚠ Для запуска без Redis: .\run_local.ps1 -SkipRedis" -ForegroundColor Yellow
                    Write-Host "  ✓ Используется локальный кэш" -ForegroundColor Green
                } else {
                    Write-Host "  ✓ Redis запущен" -ForegroundColor Green
                }
            } else {
                Write-Host "  ✓ Redis уже запущен" -ForegroundColor Green
            }
        } else {
            Write-Host "  ⚠ Docker не найден, используется локальный кэш" -ForegroundColor Yellow
        }
    }
    
    # 5. Применение миграций
    if (-not $SkipMigrations) {
        Write-Host "`n[5/7] Применение миграций базы данных..." -ForegroundColor Yellow
        Invoke-CommandSafe -Command $pythonPath -Args @("manage.py", "migrate", "--noinput")
        Write-Host "  ✓ Миграции применены" -ForegroundColor Green
    }
    
    # 6. Сбор статических файлов
    if (-not $SkipStatic) {
        Write-Host "`n[6/7] Сбор статических файлов..." -ForegroundColor Yellow
        Invoke-CommandSafe -Command $pythonPath -Args @("manage.py", "collectstatic", "--noinput", "--clear")
        Write-Host "  ✓ Статические файлы собраны" -ForegroundColor Green
    }
    
    # 7. Запуск сервера
    Write-Host "`n[7/7] Запуск сервера разработки..." -ForegroundColor Yellow
    Write-Host "  Сервер будет доступен по адресу: http://${ServerHost}:${Port}" -ForegroundColor Cyan
    Write-Host "  Для остановки нажмите Ctrl+C" -ForegroundColor Yellow
    Write-Host "`n========================================" -ForegroundColor Green
    
    & $pythonPath manage.py runserver $ServerHost":"$Port
    
} catch {
    Write-Host "`n❌ Ошибка: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Стек вызовов:" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
    exit 1
}
