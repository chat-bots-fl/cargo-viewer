# Запуск проекта локально

Этот документ описывает, как запустить проект Cargo Viewer локально одной командой.

## Быстрый старт

### Windows (PowerShell)

```powershell
.\run_local.ps1
```

### Linux / macOS / WSL (Bash)

```bash
bash run_local.sh
```

Или дайте права на выполнение и запустите:

```bash
chmod +x run_local.sh
./run_local.sh
```

После запуска скрипт автоматически:
1. Проверит наличие `.env` файла
2. Создаст виртуальное окружение Python (если его нет)
3. Установит все зависимости из `requirements.txt`
4. Запустит Redis через Docker Compose (если Docker установлен)
5. Применит миграции базы данных
6. Соберёт статические файлы
7. Запустит сервер разработки на `http://127.0.0.1:8000`

## Дополнительные опции

### Windows (PowerShell)

```powershell
# Запуск без Redis (используется локальный кэш)
.\run_local.ps1 -SkipRedis

# Пропустить миграции
.\run_local.ps1 -SkipMigrations

# Пропустить сбор статики
.\run_local.ps1 -SkipStatic

# Пропустить установку зависимостей (если уже установлены)
.\run_local.ps1 -SkipDeps

# Указать порт
.\run_local.ps1 -Port 8080

# Указать хост
.\run_local.ps1 -Host 0.0.0.0

# Комбинация опций
.\run_local.ps1 -SkipRedis -Port 9000
```

### Linux / macOS (Bash)

```bash
# Показать справку
./run_local.sh --help

# Запуск без Redis
./run_local.sh --skip-redis

# Пропустить миграции
./run_local.sh --skip-migrations

# Пропустить сбор статики
./run_local.sh --skip-static

# Пропустить установку зависимостей (если уже установлены)
./run_local.sh --skip-deps

# Указать порт
./run_local.sh --port 8080

# Указать хост
./run_local.sh --host 0.0.0.0

# Комбинация опций
./run_local.sh --skip-redis --port 9000
```

## Требования

### Обязательные

- **Python 3.11+** - для запуска приложения
- **pip** - для установки зависимостей

### Опциональные

- **Docker** + **Docker Compose** - для запуска Redis (если не установлен, используется локальный кэш)

### Установка Docker в WSL (Windows Subsystem for Linux)

Если вы используете WSL и хотите установить Docker:

#### Вариант 1: Docker Desktop (рекомендуется)

1. Скачайте Docker Desktop для Windows: https://www.docker.com/products/docker-desktop/
2. Установите Docker Desktop
3. В настройках Docker Desktop включите интеграцию с WSL:
   - Откройте Docker Desktop
   - Перейдите в Settings → Resources → WSL Integration
   - Включите интеграцию для вашего дистрибутива WSL
4. Перезапустите WSL:
   ```bash
   wsl --shutdown
   wsl
   ```

#### Вариант 2: Установка Docker напрямую в WSL (Ubuntu)

```bash
# Обновите индекс пакетов
sudo apt-get update

# Установите зависимости
sudo apt-get install -y ca-certificates curl gnupg

# Добавьте официальный GPG-ключ Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавьте репозиторий Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Обновите индекс пакетов
sudo apt-get update

# Установите Docker Engine
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Добавьте вашего пользователя в группу docker
sudo usermod -aG docker $USER

# Выйдите и войдите снова или выполните:
newgrp docker

# Проверьте установку
docker --version
docker compose version
```

#### Проверка работы Docker в WSL

```bash
# Запустите тестовый контейнер
docker run hello-world

# Проверьте Docker Compose
docker compose version
```

#### Устранение проблем

**Проблема: Docker не запускается в WSL**

```bash
# Проверьте статус службы Docker
sudo service docker status

# Запустите Docker вручную
sudo service docker start
```

**Проблема: Ошибка permission denied**

```bash
# Добавьте пользователя в группу docker
sudo usermod -aG docker $USER

# Выйдите и войдите снова
exit
# Затем снова войдите в WSL
```

## Настройка окружения

### 1. Создание .env файла (обязательно!)

Перед запуском скрипта создайте `.env` файл из `.env.example`:

```bash
# Linux/macOS
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env

# Windows (CMD)
copy .env.example .env
```

Затем откройте `.env` и настройте необходимые параметры:

```bash
# Базовые настройки
DJANGO_ENV=development
DEBUG=True
SECRET_KEY=ваш-секретный-ключ
ALLOWED_HOSTS=localhost,127.0.0.1

# Telegram
TELEGRAM_BOT_TOKEN=ваш-токен-бота
TELEGRAM_RESPONSES_CHAT_ID=ваш-chat-id

# CargoTech
CARGOTECH_PHONE=+7 911 111 11 11
CARGOTECH_PASSWORD=ваш-пароль

# Redis (опционально, для кэширования)
REDIS_URL=redis://localhost:6379/0
```

### 2. Генерация SECRET_KEY

Для генерации безопасного SECRET_KEY можно использовать:

```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

Или онлайн-генератор: https://djecrety.ir/

## Ручной запуск (без скрипта)

Если вы хотите запустить проект вручную:

```bash
# 1. Создать виртуальное окружение
python -m venv venv

# 2. Активировать виртуальное окружение
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать .env файл (обязательно!)
cp .env.example .env
# Отредактируйте .env и добавьте свои настройки

# 5. Применить миграции
python manage.py migrate

# 6. Собрать статику
python manage.py collectstatic --noinput

# 7. Запустить Redis (опционально)
docker-compose up -d redis

# 8. Запустить сервер
python manage.py runserver
```

## Полезные команды

### Команды Django

```bash
# Создать суперпользователя
python manage.py createsuperuser

# Запустить shell
python manage.py shell

# Проверить миграции
python manage.py showmigrations

# Создать новую миграцию
python manage.py makemigrations

# Очистить статику
python manage.py collectstatic --clear --noinput
```

### Команды Docker

```bash
# Запустить Redis
docker-compose up -d redis

# Остановить Redis
docker-compose stop redis

# Посмотреть логи Redis
docker-compose logs redis

# Удалить Redis с данными
docker-compose down -v redis
```

### Команды из Makefile

```bash
# Установить зависимости
make install

# Форматировать код
make format

# Проверить код линтерами
make lint

# Запустить тесты
make test

# Очистить кэш
make clean
```

## Устранение проблем

### Ошибка: "Python не найден"

Убедитесь, что Python 3.11+ установлен и добавлен в PATH:

```bash
python --version
```

### Ошибка: "Django не может быть импортирован"

Активируйте виртуальное окружение:

```bash
# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### Ошибка: "Redis недоступен"

- Проверьте, запущен ли Redis: `docker ps`
- Запустите Redis: `docker-compose up -d redis`
- Или отключите Redis, запустив скрипт с флагом `--skip-redis`

### Ошибка: "authentication required - email must be verified"

Если Docker требует аутентификацию:

1. Войдите в Docker Desktop
2. Проверьте настройки аккаунта Docker Hub
3. Или используйте флаг `--skip-redis` для запуска без Redis:
   ```bash
   bash run_local.sh --skip-redis
   ```

### Ошибка миграций

Если миграции не применяются:

```bash
# Сбросить миграции (осторожно!)
python manage.py migrate --fake-initial

# Или удалить базу данных и применить миграции заново
rm db.sqlite3
python manage.py migrate
```

### Проблемы с правами доступа (Linux/macOS/WSL)

Если скрипт не запускается в WSL:

```bash
# Вариант 1: Запустить через bash (без прав на выполнение)
bash run_local.sh

# Вариант 2: Дать права на выполнение
chmod +x run_local.sh
./run_local.sh
```

Для Windows файловой системы (WSL) права на выполнение могут не сохраняться. Рекомендуется использовать `bash run_local.sh`.

## Доступ к приложению

После запуска сервер будет доступен по адресу:

- **Основной сайт**: http://127.0.0.1:8000
- **Админ-панель**: http://127.0.0.1:8000/admin
- **API документация**: http://127.0.0.1:8000/api/schema/

## Остановка сервера

Для остановки сервера нажмите `Ctrl+C` в терминале.

## Дополнительная информация

- [Документация Django](https://docs.djangoproject.com/)
- [Документация Django REST Framework](https://www.django-rest-framework.org/)
- [Файл LOCAL_SETUP.md](plans/LOCAL_SETUP.md) - подробная инструкция по настройке
