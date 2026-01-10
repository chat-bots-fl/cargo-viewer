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

# Обновляем WEBAPP_URL
sed -i.bak "s|^WEBAPP_URL=.*|WEBAPP_URL=$NGROK_URL_NO_SLASH|" .env

# Обновляем ALLOWED_HOSTS
sed -i.bak "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1,$NGROK_DOMAIN|" .env

# Удаляем бэкап файл
rm -f .env.bak

echo -e "${GREEN}[INFO] .env обновлён с URL: $NGROK_URL_NO_SLASH${NC}"

# 4. Запуск Django
echo -e "${CYAN}[INFO] Запуск Django сервера в фоновом режиме...${NC}"
python manage.py runserver > django.log 2>&1 &
DJANGO_PID=$!

# Ждём запуска Django
echo -e "${YELLOW}[INFO] Ожидание запуска Django (3 секунды)...${NC}"
sleep 3

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
