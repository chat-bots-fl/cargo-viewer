#!/bin/bash
# ============================================
# Скрипт для локального запуска проекта Cargo Viewer
# ============================================
# Автоматизирует процесс настройки и запуска проекта:
# - Проверяет наличие .env файла (требуется создать вручную)
# - Создаёт и активирует виртуальное окружение
# - Устанавливает зависимости
# - Применяет миграции базы данных
# - Собирает статические файлы
# - Запускает Redis (опционально)
# - Запускает сервер разработки
#
# Использование:
#   ./run_local.sh                    # Запуск с настройками по умолчанию
#   ./run_local.sh --skip-redis       # Запуск без Redis
#   ./run_local.sh --port 8080        # Запуск на порту 8080
# ============================================

set -e  # Остановить скрипт при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Параметры по умолчанию
SKIP_REDIS=false
SKIP_MIGRATIONS=false
SKIP_STATIC=false
SKIP_DEPS=false
PORT="8000"
HOST="127.0.0.1"

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-redis)
            SKIP_REDIS=true
            shift
            ;;
        --skip-migrations)
            SKIP_MIGRATIONS=true
            shift
            ;;
        --skip-static)
            SKIP_STATIC=true
            shift
            ;;
        --skip-deps)
            SKIP_DEPS=true
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        -h|--help)
            echo "Использование: $0 [ОПЦИИ]"
            echo ""
            echo "ОПЦИИ:"
            echo "  --skip-redis          Пропустить запуск Redis"
            echo "  --skip-migrations     Пропустить миграции БД"
            echo "  --skip-static         Пропустить сбор статики"
            echo "  --skip-deps           Пропустить установку зависимостей"
            echo "  --port PORT           Порт сервера (по умолчанию: 8000)"
            echo "  --host HOST           Хост сервера (по умолчанию: 127.0.0.1)"
            echo "  -h, --help            Показать эту справку"
            exit 0
            ;;
        *)
            echo -e "${RED}Неизвестный параметр: $1${NC}"
            exit 1
            ;;
    esac
done

# Функция для выполнения команд с выводом
run_command() {
    echo -e "${CYAN}>>> Выполняю: $@${NC}"
    "$@"
}

# Функция для проверки существования команды
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Основной блок
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Cargo Viewer - Локальный запуск${NC}"
echo -e "${GREEN}========================================${NC}"

# Переход в директорию скрипта
cd "$(dirname "$0")"

# 1. Проверка .env файла
echo -e "\n${YELLOW}[1/7] Проверка конфигурации...${NC}"
if [ ! -f ".env" ]; then
    echo -e "  ${RED}❌ Файл .env не найден!${NC}"
    echo -e "  ${YELLOW}Создайте .env файл из .env.example:${NC}"
    echo -e "    ${CYAN}cp .env.example .env${NC}"
    echo -e "  ${YELLOW}Затем отредактируйте .env и добавьте свои настройки.${NC}"
    echo -e "\nДля продолжения нажмите Enter или Ctrl+C для выхода..."
    read
    if [ ! -f ".env" ]; then
        echo -e "\n${RED}❌ Файл .env не создан. Запуск отменён.${NC}"
        exit 1
    fi
fi
echo -e "  ${GREEN}✓ Файл .env найден${NC}"

# 2. Проверка виртуального окружения
echo -e "\n${YELLOW}[2/7] Проверка виртуального окружения...${NC}"
VENV_DIR="venv"

# Проверяем, существует ли venv и есть ли в нём python для Linux/macOS
if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/python" ] && [ -f "$VENV_DIR/bin/pip" ]; then
    echo -e "  ${GREEN}✓ Виртуальное окружение существует и совместимо${NC}"
else
    # venv не существует, создан в Windows или повреждён
    if [ -d "$VENV_DIR" ]; then
        if [ -d "$VENV_DIR/Scripts" ]; then
            echo -e "  ${YELLOW}⚠ Виртуальное окружение создано в Windows, пересоздаю для Linux...${NC}"
        else
            echo -e "  ${YELLOW}⚠ Виртуальное окружение повреждено, пересоздаю...${NC}"
        fi
        echo -e "  ${CYAN}Удаляю старое виртуальное окружение...${NC}"
        rm -rf "$VENV_DIR"
    fi
    echo -e "  ${CYAN}Создаю виртуальное окружение...${NC}"
    run_command python3 -m venv "$VENV_DIR"
    echo -e "  ${GREEN}✓ Виртуальное окружение создано${NC}"
fi

# Активация виртуального окружения
echo -e "  ${CYAN}Активирую виртуальное окружение...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "  ${GREEN}✓ Виртуальное окружение активировано${NC}"

# Определяем пути к Python и pip из виртуального окружения
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

# 3. Установка зависимостей
echo -e "\n${YELLOW}[3/7] Проверка зависимостей...${NC}"

if [ "$SKIP_DEPS" = true ]; then
    echo -e "  ${YELLOW}⚠ Установка зависимостей пропущена (--skip-deps)${NC}"
    echo -e "  ${GREEN}✓ Пропущено${NC}"
else
    REQUIREMENTS_HASH=$(sha256sum requirements.txt | awk '{print $1}')
    INSTALLED_HASH=""
    if [ -f ".installed_hash" ]; then
        INSTALLED_HASH=$(cat .installed_hash)
    fi

    if [ "$REQUIREMENTS_HASH" != "$INSTALLED_HASH" ]; then
        echo -e "  ${CYAN}Устанавливаю зависимости из requirements.txt...${NC}"
        echo -e "  ${YELLOW}⚠ Это может занять несколько минут...${NC}"
        run_command "$PIP_BIN" install -r requirements.txt
        echo "$REQUIREMENTS_HASH" > .installed_hash
        echo -e "  ${GREEN}✓ Зависимости установлены${NC}"
    else
        echo -e "  ${GREEN}✓ Зависимости уже установлены${NC}"
    fi
fi

# 4. Запуск Redis (если требуется)
if [ "$SKIP_REDIS" = false ]; then
    echo -e "\n${YELLOW}[4/7] Проверка Redis...${NC}"
    
    if command_exists docker; then
        REDIS_RUNNING=$(docker ps --filter "name=redis" --format "{{.Names}}" | grep redis || true)
        
        if [ -z "$REDIS_RUNNING" ]; then
            echo -e "  ${CYAN}Запускаю Redis через Docker Compose...${NC}"
            if docker-compose up -d redis 2>&1 | grep -q "authentication required"; then
                echo -e "  ${RED}❌ Ошибка: Docker требует аутентификацию${NC}"
                echo -e "  ${YELLOW}⚠ Войдите в Docker Desktop или используйте --skip-redis${NC}"
                echo -e "  ${YELLOW}⚠ Для запуска без Redis: bash run_local.sh --skip-redis${NC}"
                echo -e "  ${GREEN}✓ Используется локальный кэш${NC}"
            else
                echo -e "  ${GREEN}✓ Redis запущен${NC}"
            fi
        else
            echo -e "  ${GREEN}✓ Redis уже запущен${NC}"
        fi
    else
        echo -e "  ${YELLOW}⚠ Docker не найден, используется локальный кэш${NC}"
    fi
fi

# 5. Применение миграций
if [ "$SKIP_MIGRATIONS" = false ]; then
    echo -e "\n${YELLOW}[5/7] Применение миграций базы данных...${NC}"
    run_command "$PYTHON_BIN" manage.py migrate --noinput
    echo -e "  ${GREEN}✓ Миграции применены${NC}"
fi

# 6. Сбор статических файлов
if [ "$SKIP_STATIC" = false ]; then
    echo -e "\n${YELLOW}[6/7] Сбор статических файлов...${NC}"
    run_command "$PYTHON_BIN" manage.py collectstatic --noinput --clear
    echo -e "  ${GREEN}✓ Статические файлы собраны${NC}"
fi

# 7. Запуск сервера
echo -e "\n${YELLOW}[7/7] Запуск сервера разработки...${NC}"
echo -e "  ${CYAN}Сервер будет доступен по адресу: http://${HOST}:${PORT}${NC}"
echo -e "  ${YELLOW}Для остановки нажмите Ctrl+C${NC}"
echo -e "\n${GREEN}========================================${NC}"

"$PYTHON_BIN" manage.py runserver "$HOST:$PORT"
