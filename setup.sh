#!/bin/bash
# ============================================
# Скрипт подготовки окружения для WSL/Linux
# ============================================
# Выполняет один раз или при изменениях:
# - Проверка .env файла
# - Создание виртуального окружения
# - Установка зависимостей
# - Применение миграций БД
# - Сбор статических файлов
# - Запуск Redis (опционально)
# ============================================

set -e  # Остановить скрипт при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Подготовка окружения (WSL/Linux)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Переход в директорию скрипта
cd "$(dirname "$0")"

# 1. Проверка .env файла
echo -e "${YELLOW}[1/5] Проверка конфигурации...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    echo -e "${YELLOW}Создайте .env файл из .env.example:${NC}"
    echo -e "  ${CYAN}cp .env.example .env${NC}"
    echo -e "${YELLOW}Затем отредактируйте .env и добавьте свои настройки.${NC}"
    exit 1
fi

# Dev/staging: start PostgreSQL in Docker for local debugging/testing.
DJANGO_ENV_VALUE=$(grep -E '^DJANGO_ENV=' .env | head -n1 | cut -d '=' -f2- | tr -d '\r' | tr '[:upper:]' '[:lower:]')
if [ -z "$DJANGO_ENV_VALUE" ]; then
    DJANGO_ENV_VALUE="development"
fi

DEFAULT_POSTGRES_USER="cargo_viewer_dev"
DEFAULT_POSTGRES_PASSWORD="cargo_viewer_dev"
DEFAULT_POSTGRES_HOST="127.0.0.1"
DEFAULT_POSTGRES_PORT="5432"
DEFAULT_POSTGRES_DB="cargo_viewer_dev"
if [ "$DJANGO_ENV_VALUE" = "staging" ]; then
    DEFAULT_POSTGRES_DB="cargo_viewer_test"
fi
DEFAULT_DATABASE_URL="postgresql://${DEFAULT_POSTGRES_USER}:${DEFAULT_POSTGRES_PASSWORD}@${DEFAULT_POSTGRES_HOST}:${DEFAULT_POSTGRES_PORT}/${DEFAULT_POSTGRES_DB}"

if [ "$DJANGO_ENV_VALUE" = "development" ] || [ "$DJANGO_ENV_VALUE" = "staging" ]; then
    DATABASE_URL_VALUE=$(grep -E '^DATABASE_URL=' .env | head -n1 | cut -d '=' -f2- | tr -d '\r')

    if [ -z "$DATABASE_URL_VALUE" ]; then
        echo -e "${CYAN}DATABASE_URL not set; using local Docker PostgreSQL (${DEFAULT_POSTGRES_DB})${NC}"
        if grep -q '^DATABASE_URL=' .env; then
            sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=${DEFAULT_DATABASE_URL}|" .env
        else
            echo "DATABASE_URL=${DEFAULT_DATABASE_URL}" >> .env
        fi
        rm -f .env.bak
        DATABASE_URL_VALUE="$DEFAULT_DATABASE_URL"
    fi

    if [[ "$DATABASE_URL_VALUE" == postgres://* || "$DATABASE_URL_VALUE" == postgresql://* ]]; then
        if [[ "$DATABASE_URL_VALUE" == *"@localhost"* || "$DATABASE_URL_VALUE" == *"@127.0.0.1"* ]]; then
            ENV_LABEL="DEV"
            if [ "$DJANGO_ENV_VALUE" = "staging" ]; then
                ENV_LABEL="TEST"
            fi
            echo -e "\n${YELLOW}[${ENV_LABEL}] Starting PostgreSQL in Docker...${NC}"

            DOCKER_COMPOSE_CMD=()
            if command -v docker-compose &> /dev/null; then
                DOCKER_COMPOSE_CMD=(docker-compose)
            elif docker compose version &> /dev/null; then
                DOCKER_COMPOSE_CMD=(docker compose)
            fi

            if [ ${#DOCKER_COMPOSE_CMD[@]} -eq 0 ]; then
                echo -e "${RED}[ERROR] Docker Compose not found (need docker-compose or docker compose).${NC}"
                exit 1
            fi

            if ! docker info > /dev/null 2>&1; then
                echo -e "${RED}[ERROR] Docker is not running (docker info failed).${NC}"
                exit 1
            fi

            "${DOCKER_COMPOSE_CMD[@]}" up -d db

            echo -e "${CYAN}Waiting for PostgreSQL to be ready...${NC}"
            DB_READY=0
            for i in {1..30}; do
                if "${DOCKER_COMPOSE_CMD[@]}" exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > /dev/null 2>&1; then
                    DB_READY=1
                    break
                fi
                sleep 1
            done

            if [ $DB_READY -ne 1 ]; then
                echo -e "${RED}[ERROR] PostgreSQL did not become ready in time.${NC}"
                echo -e "${YELLOW}Check logs: ${CYAN}${DOCKER_COMPOSE_CMD[*]} logs db${NC}"
                exit 1
            fi

            echo -e "${GREEN}PostgreSQL is ready.${NC}"

            DB_NAME_FROM_URL="${DATABASE_URL_VALUE##*/}"
            DB_NAME_FROM_URL="${DB_NAME_FROM_URL%%\?*}"
            DB_NAME_FROM_URL="${DB_NAME_FROM_URL%%#*}"

            if [ -n "$DB_NAME_FROM_URL" ] && [[ "$DB_NAME_FROM_URL" =~ ^[a-zA-Z0-9_]+$ ]]; then
                echo -e "${CYAN}Ensuring database exists: ${DB_NAME_FROM_URL}${NC}"
                if ! "${DOCKER_COMPOSE_CMD[@]}" exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME_FROM_URL}'\" | grep -q 1" > /dev/null 2>&1; then
                    if ! "${DOCKER_COMPOSE_CMD[@]}" exec -T db sh -c "createdb -U \"\$POSTGRES_USER\" \"${DB_NAME_FROM_URL}\"" > /dev/null 2>&1; then
                        echo -e "${RED}[ERROR] Failed to create database: ${DB_NAME_FROM_URL}${NC}"
                        exit 1
                    fi
                    echo -e "${GREEN}Database created: ${DB_NAME_FROM_URL}${NC}"
                fi
            fi
        fi
    fi
fi
echo -e "${GREEN}✓ Файл .env найден${NC}"

# 2. Проверка виртуального окружения
echo -e "\n${YELLOW}[2/5] Проверка виртуального окружения...${NC}"
VENV_DIR="venv"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ] && [ -f "$VENV_DIR/bin/pip" ]; then
    echo -e "${GREEN}✓ Виртуальное окружение существует и совместимо${NC}"
else
    if [ -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}⚠ Виртуальное окружение повреждено, пересоздаю...${NC}"
        rm -rf "$VENV_DIR"
    fi
    echo -e "${CYAN}Создаю виртуальное окружение...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Виртуальное окружение создано${NC}"
fi

# Активация виртуального окружения
echo -e "${CYAN}Активирую виртуальное окружение...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ Виртуальное окружение активировано${NC}"

# Определяем пути к Python и pip
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

# 3. Установка зависимостей
echo -e "\n${YELLOW}[3/5] Проверка зависимостей...${NC}"

REQUIREMENTS_HASH=$(sha256sum requirements.txt | awk '{print $1}')
INSTALLED_HASH=""
if [ -f ".installed_hash" ]; then
    INSTALLED_HASH=$(cat .installed_hash)
fi

if [ "$REQUIREMENTS_HASH" != "$INSTALLED_HASH" ]; then
    echo -e "${CYAN}Устанавливаю зависимости из requirements.txt...${NC}"
    echo -e "${YELLOW}⚠ Это может занять несколько минут...${NC}"
    "$PIP_BIN" install -r requirements.txt
    echo "$REQUIREMENTS_HASH" > .installed_hash
    echo -e "${GREEN}✓ Зависимости установлены${NC}"
else
    echo -e "${GREEN}✓ Зависимости уже установлены${NC}"
fi

# 4. Применение миграций
echo -e "\n${YELLOW}[4/5] Применение миграций базы данных...${NC}"
"$PYTHON_BIN" manage.py migrate --noinput
echo -e "${GREEN}✓ Миграции применены${NC}"

# 5. Проверка ngrok
echo -e "\n${YELLOW}[5/6] Проверка ngrok...${NC}"
if ! command -v ngrok &> /dev/null; then
    echo -e "${YELLOW}⚠ ngrok не найден${NC}"
    echo -e "${CYAN}Хотите установить ngrok в WSL?${NC}"
    read -p "Установить ngrok через snap? (y/n): " INSTALL_NGROK
    
    if [[ "$INSTALL_NGROK" =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}Устанавливаю snapd...${NC}"
        sudo apt update
        sudo apt install -y snapd
        
        echo -e "${CYAN}Устанавливаю ngrok через snap...${NC}"
        sudo snap install ngrok
        
        if command -v ngrok &> /dev/null; then
            echo -e "${GREEN}✓ ngrok успешно установлен${NC}"
            echo -e "${CYAN}Версия:${NC}"
            ngrok version
            echo ""
            echo -e "${YELLOW}Для автозаполнения токена:${NC}"
            echo -e "  1. Получите токен: https://dashboard.ngrok.com/get-started/your-authtoken"
            echo -e "  2. Выполните: ${CYAN}ngrok config add-authtoken YOUR_TOKEN${NC}"
            echo ""
            read -p "Нажмите Enter для продолжения или Ctrl+C для отмены..."
        else
            echo -e "${RED}❌ Ошибка при установке ngrok${NC}"
            echo -e "${YELLOW}См. инструкцию: ${CYAN}INSTALL_NGROK_WSL.md${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ ngrok не установлен${NC}"
        echo -e "${CYAN}Установите ngrok вручную или см. инструкцию:${NC}"
        echo -e "  ${YELLOW}INSTALL_NGROK_WSL.md${NC}"
    fi
else
    echo -e "${GREEN}✓ ngrok найден${NC}"
    echo -e "${CYAN}Версия:${NC}"
    ngrok version
fi

# 6. Сбор статических файлов
echo -e "\n${YELLOW}[6/6] Сбор статических файлов...${NC}"
"$PYTHON_BIN" manage.py collectstatic --noinput --clear
echo -e "${GREEN}✓ Статические файлы собраны${NC}"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Подготовка завершена!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}Теперь можно запустить проект:${NC}"
echo -e "  ${YELLOW}./start.sh${NC}"
echo ""
