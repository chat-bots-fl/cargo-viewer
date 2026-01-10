# 🚀 Быстрый запуск проекта

## Одна команда для запуска

### Windows
```cmd
run_local.bat
```

### Linux / macOS / WSL
```bash
bash run_local.sh
```

Или дайте права на выполнение и запустите:
```bash
chmod +x run_local.sh
./run_local.sh
```

---

## Что происходит автоматически?

1. ✅ Проверяется наличие `.env` файла
2. ✅ Создаётся виртуальное окружение Python
3. ✅ Устанавливаются все зависимости (можно пропустить с `--skip-deps`)
4. ✅ Запускается Redis (через Docker)
5. ✅ Применяются миграции базы данных
6. ✅ Собираются статические файлы
7. ✅ Запускается сервер на `http://127.0.0.1:8000`

## Перед запуском

Создайте `.env` файл из `.env.example`:

```bash
# Linux/macOS
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Затем отредактируйте `.env` и добавьте свои настройки (SECRET_KEY, TELEGRAM_BOT_TOKEN и т.д.).

---

## Дополнительные опции

### Windows
```cmd
REM Без Redis
run_local.bat -SkipRedis

REM Без установки зависимостей
run_local.bat -SkipDeps

REM На другом порту
run_local.bat -Port 8080

REM Комбинация
run_local.bat -SkipRedis -Port 9000
```

### Linux / macOS
```bash
# Показать справку
./run_local.sh --help

# Без Redis
./run_local.sh --skip-redis

# Без установки зависимостей (если уже установлены)
./run_local.sh --skip-deps

# На другом порту
./run_local.sh --port 8080
```

---

## Требования

- **Python 3.11+**
- **Docker** (опционально, для Redis)

### Установка Docker в WSL

**Вариант 1: Docker Desktop (рекомендуется)**

1. Скачайте Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Установите Docker Desktop
3. Включите интеграцию WSL в настройках: Settings → Resources → WSL Integration
4. Перезапустите WSL: `wsl --shutdown`

**Вариант 2: Прямая установка в WSL (Ubuntu)**

```bash
# Установка Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker

# Проверка
docker --version
docker compose version
```

Подробная инструкция в [`LOCAL_RUN.md`](LOCAL_RUN.md).

---

## После запуска

- 🌐 **Сайт**: http://127.0.0.1:8000
- 🔐 **Админка**: http://127.0.0.1:8000/admin
- 📚 **API Docs**: http://127.0.0.1:8000/api/schema/

---

## Подробная документация

См. [`LOCAL_RUN.md`](LOCAL_RUN.md) для подробной информации.
