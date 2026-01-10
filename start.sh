#!/bin/bash
# ============================================
# Скрипт запуска сервисов для WSL/Linux
# ============================================
# Выполняется каждый раз:
# - Запуск ngrok
# - Получение URL ngrok
# - Обновление .env с новым URL
# - Запуск Django сервера
# - Настройка webhook для Telegram бота
# ============================================

set -e  # Остановить скрипт при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Запуск сервисов (WSL/Linux)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Переход в директорию скрипта
cd "$(dirname "$0")"

# Проверяем наличие .env
if [ ! -f ".env" ]; then
    echo -e "${RED}[ERROR] Файл .env не найден${NC}"
    echo -e "${YELLOW}Сначала запустите ./setup.sh для подготовки окружения${NC}"
    exit 1
fi

# Проверяем наличие venv
if [ ! -d "venv" ] || [ ! -f "venv/bin/python" ]; then
    echo -e "${RED}[ERROR] Виртуальное окружение не найдено${NC}"
    echo -e "${YELLOW}Сначала запустите ./setup.sh для подготовки окружения${NC}"
    exit 1
fi

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
    echo -e "  4. Затем запустите этот скрипт снова"
    exit 1
fi

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 не найден${NC}"
    exit 1
fi

# Активируем виртуальное окружение
source venv/bin/activate

# 1. Проверка ngrok
echo -e "${CYAN}[1/5] Проверка ngrok...${NC}"

# Проверяем, запущен ли ngrok
if curl -s http://127.0.0.1:4040/api/tunnels > /dev/null 2>&1; then
    echo -e "${GREEN}[INFO] ngrok уже запущен${NC}"
    NGROK_PID=$(pgrep -f "ngrok" | head -1 || echo "unknown")
else
    echo -e "${YELLOW}[WARNING] ngrok не запущен${NC}"
    echo -e "${CYAN}Пожалуйста, запустите ngrok в отдельном окне:${NC}"
    echo -e "  ${YELLOW}ngrok http 8000${NC}"
    echo ""
    read -p "Нажмите Enter после запуска ngrok..."
    
    # Проверяем снова
    if ! curl -s http://127.0.0.1:4040/api/tunnels > /dev/null 2>&1; then
        echo -e "${RED}[ERROR] ngrok всё ещё не запущен${NC}"
        echo -e "${YELLOW}Проверьте, что ngrok запущен на порту 8000${NC}"
        exit 1
    fi
    NGROK_PID=$(pgrep -f "ngrok" | head -1 || echo "unknown")
fi

# Ждём запуска ngrok
echo -e "${YELLOW}[2/5] Ожидание запуска ngrok (10 секунд)...${NC}"
sleep 10

# 2. Получение URL ngrok
echo -e "${CYAN}[3/5] Получение URL ngrok...${NC}"
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"https://[^"]*"' | cut -d'"' -f4)

if [ -z "$NGROK_URL" ]; then
    echo -e "${YELLOW}[WARNING] Не удалось автоматически получить URL ngrok${NC}"
    echo ""
    echo -e "${CYAN}Пожалуйста:${NC}"
    echo "  1. Откройте окно ngrok (или проверьте процесс)"
    echo "  2. Скопируйте URL (Forwarding)"
    echo "  3. Вставьте его ниже"
    echo ""
    read -p "URL ngrok (например: https://xxxx-xxxx.ngrok-free.app): " NGROK_URL
fi

# Проверяем, что URL начинается с https
if [[ ! "$NGROK_URL" =~ ^https:// ]]; then
    echo -e "${RED}[ERROR] URL должен начинаться с https${NC}"
    kill $NGROK_PID 2>/dev/null || true
    exit 1
fi

# Удаляем слеш в конце, если есть
NGROK_URL=${NGROK_URL%/}
NGROK_DOMAIN=${NGROK_URL#https://}

echo -e "${GREEN}[SUCCESS] Получен URL ngrok: $NGROK_URL${NC}"

# 3. Обновление .env
echo -e "${CYAN}[4/5] Обновление .env с новым URL...${NC}"
sed -i.bak "s|^WEBAPP_URL=.*|WEBAPP_URL=$NGROK_URL|" .env
sed -i.bak "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1,$NGROK_DOMAIN|" .env
rm -f .env.bak

echo -e "${GREEN}[SUCCESS] .env обновлён с URL: $NGROK_URL${NC}"

# 4. Запуск Django
echo -e "${CYAN}[5/5] Запуск Django сервера в фоновом режиме...${NC}"
python manage.py runserver > django.log 2>&1 &
DJANGO_PID=$!

# Ждём запуска Django
echo -e "${YELLOW}[INFO] Ожидание запуска Django (3 секунды)...${NC}"
sleep 3

# 5. Настройка webhook
echo -e "${CYAN}[INFO] Настройка webhook для Telegram бота...${NC}"
python setup_telegram_webhook.py setup

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Запуск завершён!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}Информация:${NC}"
echo -e "  - ngrok URL: $NGROK_URL"
echo -e "  - Webhook настроен на: $NGROK_URL/telegram/webhook/"
echo -e "  - ngrok PID: $NGROK_PID"
echo -e "  - Django PID: $DJANGO_PID"
echo ""
echo -e "${CYAN}Для проверки webhook:${NC}"
echo -e "  ${YELLOW}python setup_telegram_webhook.py info${NC}"
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
