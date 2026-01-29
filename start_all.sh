#!/bin/bash
# ============================================
# Автоматический запуск ngrok, Django и webhook
# ============================================
# Скрипт автоматически:
# 1. Запускает ngrok на порту 8000
# 2. Получает URL ngrok
# 3. Обновляет .env с новым URL
# 4. Запускает Django сервер
# 5. Настраивает webhook для Telegram бота
# ============================================

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Автоматический запуск проекта${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Проверяем наличие ngrok (WSL или Windows)
NGROK_CMD=""

# Сначала пробуем через команду ngrok (если доступна в WSL)
if command -v ngrok &> /dev/null; then
    NGROK_CMD="ngrok"
# Затем пробуем через snap (где устанавливается snap)
elif [ -f "/snap/bin/ngrok" ]; then
    NGROK_CMD="/snap/bin/ngrok"
# Затем пробуем через WindowsApps (где установлен у вас)
elif [ -f "/mnt/c/Users/DenAdmin/AppData/Local/Microsoft/WindowsApps/ngrok.exe" ]; then
    NGROK_CMD="/mnt/c/Users/DenAdmin/AppData/Local/Microsoft/WindowsApps/ngrok.exe"
# Затем пробуем Program Files
elif [ -f "/mnt/c/Program Files/ngrok/ngrok.exe" ]; then
    NGROK_CMD="/mnt/c/Program Files/ngrok/ngrok.exe"
# Затем пробуем обычный AppData
elif [ -f "/mnt/c/Users/DenAdmin/AppData/Local/ngrok/ngrok.exe" ]; then
    NGROK_CMD="/mnt/c/Users/DenAdmin/AppData/Local/ngrok/ngrok.exe"
fi

if [ -z "$NGROK_CMD" ]; then
    echo -e "${RED}[ERROR] ngrok не найден${NC}"
    echo -e "${YELLOW}Варианты:${NC}"
    echo -e "  1. Установите ngrok: https://ngrok.com/download"
    echo -e "  2. Запустите ngrok в Windows: ${CYAN}ngrok http 8000${NC}"
    echo -e "  3. Установите ngrok в WSL: ${CYAN}sudo snap install ngrok${NC}"
    exit 1
fi

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 не найден${NC}"
    exit 1
fi

# Проверяем наличие .env
if [ ! -f ".env" ]; then
    echo -e "${RED}[ERROR] Файл .env не найден${NC}"
    exit 1
fi

# Dev/staging: ensure local PostgreSQL is running in Docker.
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
        echo -e "${CYAN}[INFO] DATABASE_URL not set; using local Docker PostgreSQL (${DEFAULT_POSTGRES_DB})${NC}"
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
            echo -e "${CYAN}[INFO] [${ENV_LABEL}] Starting PostgreSQL in Docker...${NC}"

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

            echo -e "${CYAN}[INFO] Waiting for PostgreSQL to be ready...${NC}"
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
                echo -e "${YELLOW}[INFO] Check logs: ${CYAN}${DOCKER_COMPOSE_CMD[*]} logs db${NC}"
                exit 1
            fi

            DB_NAME_FROM_URL="${DATABASE_URL_VALUE##*/}"
            DB_NAME_FROM_URL="${DB_NAME_FROM_URL%%\?*}"
            DB_NAME_FROM_URL="${DB_NAME_FROM_URL%%#*}"

            if [ -n "$DB_NAME_FROM_URL" ] && [[ "$DB_NAME_FROM_URL" =~ ^[a-zA-Z0-9_]+$ ]]; then
                if ! "${DOCKER_COMPOSE_CMD[@]}" exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME_FROM_URL}'\" | grep -q 1" > /dev/null 2>&1; then
                    echo -e "${CYAN}[INFO] Creating database: ${DB_NAME_FROM_URL}${NC}"
                    if ! "${DOCKER_COMPOSE_CMD[@]}" exec -T db sh -c "createdb -U \"\$POSTGRES_USER\" \"${DB_NAME_FROM_URL}\"" > /dev/null 2>&1; then
                        echo -e "${RED}[ERROR] Failed to create database: ${DB_NAME_FROM_URL}${NC}"
                        exit 1
                    fi
                fi
            fi
        fi
    fi
fi

# Проверяем наличие venv
if [ ! -d "venv" ] || [ ! -f "venv/bin/python" ]; then
    echo -e "${RED}[ERROR] Виртуальное окружение не найдено${NC}"
    echo -e "${YELLOW}Сначала запустите ./setup.sh для подготовки окружения${NC}"
    exit 1
fi

# Активируем виртуальное окружение
echo -e "${CYAN}[INFO] Активация виртуального окружения...${NC}"
source venv/bin/activate

# 1. Запуск ngrok
echo -e "${CYAN}[1/5] Запуск ngrok на порту 8000...${NC}"
$NGROK_CMD http 8000 --log=stdout > /dev/null 2>&1 &
NGROK_PID=$!

# Ждём запуска ngrok
echo -e "${YELLOW}[2/5] Ожидание запуска ngrok (5 секунд)...${NC}"
sleep 5

# 2. Получение URL ngrok
echo -e "${CYAN}[3/5] Получение URL ngrok...${NC}"
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"https://[^"]*"' | cut -d'"' -f4)

if [ -z "$NGROK_URL" ]; then
    echo -e "${YELLOW}[WARNING] Не удалось автоматически получить URL ngrok${NC}"
    echo -e "${CYAN}Пожалуйста, введите URL ngrok вручную:${NC}"
    read -p "URL ngrok (например: https://xxxx-xxxx.ngrok-free.app): " NGROK_URL
fi

# Проверяем, что URL начинается с https
if [[ ! "$NGROK_URL" =~ ^https:// ]]; then
    echo -e "${RED}[ERROR] URL должен начинаться с https${NC}"
    kill $NGROK_PID
    exit 1
fi

echo -e "${GREEN}[INFO] Получен URL ngrok: $NGROK_URL${NC}"

# 3. Обновление .env
echo -e "${CYAN}[4/5] Обновление .env с новым URL...${NC}"
# Удаляем слеш в конце, если есть
NGROK_URL_NO_SLASH=${NGROK_URL%/}
NGROK_DOMAIN=${NGROK_URL_NO_SLASH#https://}
WSL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' | tr -d '\r')

# Обновляем WEBAPP_URL
sed -i.bak "s|^WEBAPP_URL=.*|WEBAPP_URL=$NGROK_URL_NO_SLASH|" .env

# Обновляем ALLOWED_HOSTS
ALLOWED_HOSTS_VALUE="localhost,127.0.0.1"
if [ -n "$WSL_IP" ]; then
    ALLOWED_HOSTS_VALUE="${ALLOWED_HOSTS_VALUE},${WSL_IP}"
fi
ALLOWED_HOSTS_VALUE="${ALLOWED_HOSTS_VALUE},${NGROK_DOMAIN}"
sed -i.bak "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$ALLOWED_HOSTS_VALUE|" .env

# Удаляем бэкап файл
rm -f .env.bak

echo -e "${GREEN}[INFO] .env обновлён с URL: $NGROK_URL_NO_SLASH${NC}"

# 4. Запуск Django
echo -e "${CYAN}[INFO] Запуск Django сервера в фоновом режиме...${NC}"
python -u manage.py runserver 0.0.0.0:8000 > django.log 2>&1 &
DJANGO_PID=$!

# Ждём запуска Django (важно для ngrok, иначе будет ERR_NGROK_8012)
echo -e "${YELLOW}[INFO] Ожидание готовности Django на http://127.0.0.1:8000 ...${NC}"
DJANGO_READY=0
DJANGO_STARTUP_TIMEOUT_SECONDS=${DJANGO_STARTUP_TIMEOUT_SECONDS:-600}
for ((i=1; i<=DJANGO_STARTUP_TIMEOUT_SECONDS; i++)); do
    if ! kill -0 "$DJANGO_PID" > /dev/null 2>&1; then
        echo -e "${RED}[ERROR] Django процесс завершился во время старта (PID: $DJANGO_PID).${NC}"
        if [ -f "django.log" ]; then
            echo -e "${YELLOW}--- tail django.log ---${NC}"
            tail -n 120 django.log || true
        fi
        if [[ "$NGROK_CMD" == *"ngrok.exe"* ]]; then
            taskkill //F //IM ngrok.exe > /dev/null 2>&1 || true
        else
            kill "$NGROK_PID" > /dev/null 2>&1 || true
        fi
        exit 1
    fi

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/" 2>/dev/null || true)
    if [ -n "$HTTP_CODE" ] && [ "$HTTP_CODE" != "000" ]; then
        DJANGO_READY=1
        break
    fi
    if (( i % 15 == 0 )); then
        echo -e "${YELLOW}[INFO] Django ещё стартует... (${i}s/${DJANGO_STARTUP_TIMEOUT_SECONDS}s)${NC}"
    fi
    sleep 1
done

if [ "$DJANGO_READY" -eq 1 ]; then
    echo -e "${GREEN}[INFO] Django готов (HTTP ${HTTP_CODE}).${NC}"
fi

if [ "$DJANGO_READY" -ne 1 ]; then
    echo -e "${RED}[ERROR] Django не отвечает на http://127.0.0.1:8000 (timeout).${NC}"
    if [ -f "django.log" ]; then
        echo -e "${YELLOW}--- tail django.log ---${NC}"
        tail -n 120 django.log || true
    fi
    if [[ "$NGROK_CMD" == *"ngrok.exe"* ]]; then
        taskkill //F //IM ngrok.exe > /dev/null 2>&1 || true
    else
        kill "$NGROK_PID" > /dev/null 2>&1 || true
    fi
    kill "$DJANGO_PID" > /dev/null 2>&1 || true
    exit 1
fi

# 5. Настройка webhook
echo -e "${CYAN}[5/5] Настройка webhook для Telegram бота...${NC}"
python setup_telegram_webhook.py setup

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Запуск завершён!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}Информация:${NC}"
echo -e "  - ngrok URL: $NGROK_URL_NO_SLASH"
if [ -n "$WSL_IP" ]; then
    echo -e "  - Local URL (Windows): http://$WSL_IP:8000"
fi
echo -e "  - Local URL (WSL): http://127.0.0.1:8000"
echo -e "  - Webhook настроен на: $NGROK_URL_NO_SLASH/telegram/webhook/"
echo -e "  - ngrok PID: $NGROK_PID"
echo -e "  - Django PID: $DJANGO_PID"
echo ""
echo -e "${CYAN}Для проверки webhook:${NC}"
echo -e "  python setup_telegram_webhook.py info"
echo ""
echo -e "${CYAN}Для остановки:${NC}"
if [[ "$NGROK_CMD" == *"ngrok.exe"* ]]; then
    echo -e "  ${YELLOW}taskkill //F //IM ngrok.exe${NC}  # Остановить ngrok (Windows)"
else
    echo -e "  ${YELLOW}kill $NGROK_PID${NC}  # Остановить ngrok (WSL)"
fi
echo -e "  ${YELLOW}kill $DJANGO_PID${NC}  # Остановить Django"
echo -e "  Или используйте Ctrl+C"
echo ""
echo -e "${YELLOW}Нажмите Ctrl+C для остановки всех сервисов${NC}"

# Ловим Ctrl+C для остановки
if [[ "$NGROK_CMD" == *"ngrok.exe"* ]]; then
    trap "echo ''; echo -e '${YELLOW}Остановка сервисов...${NC}'; kill $DJANGO_PID 2>/dev/null; taskkill //F //IM ngrok.exe 2>/dev/null; exit 0" INT TERM
else
    trap "echo ''; echo -e '${YELLOW}Остановка сервисов...${NC}'; kill $NGROK_PID $DJANGO_PID 2>/dev/null; exit 0" INT TERM
fi

# Держим скрипт запущенным
wait
