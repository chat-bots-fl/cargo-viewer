# 🐧 Linux Deploy (step-by-step) — CargoTech Driver WebApp (v3.2.1)

Цель: развернуть Django+HTMX приложение за Nginx с HTTPS, Redis и PostgreSQL, настроить Telegram webhook и (опционально) ЮKassa webhook.

> Основа требований: `docs/DEPLOY_GUIDE_v3.2.md` и переменные из `.env.example`.

---

## 0) Предпосылки

- Публичный домен и **HTTPS** (обязательно для Telegram WebApp и webhooks).
- Linux (пример ниже для Ubuntu/Debian).

---

## 1) Установить системные пакеты

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nginx redis-server postgresql postgresql-contrib
sudo systemctl enable --now redis-server postgresql nginx
```

---

## 2) Создать пользователя и директорию приложения

```bash
sudo adduser --system --group --home /opt/cargotech_driver_app cargoweb
sudo mkdir -p /opt/cargotech_driver_app
sudo chown -R cargoweb:cargoweb /opt/cargotech_driver_app
```

---

## 3) Залить код на сервер

Вариант A: git clone (если есть репозиторий):

```bash
sudo -u cargoweb git clone <REPO_URL> /opt/cargotech_driver_app/app
```

Вариант B: rsync/scp (если код на локальной машине).

---

## 4) Создать virtualenv и поставить зависимости

```bash
sudo -u cargoweb python3 -m venv /opt/cargotech_driver_app/venv
sudo -u cargoweb /opt/cargotech_driver_app/venv/bin/pip install -r /opt/cargotech_driver_app/app/requirements.txt
```

---

## 5) Подготовить PostgreSQL и DATABASE_URL

```bash
sudo -u postgres psql
```

В psql:

```sql
CREATE USER cargoweb WITH PASSWORD 'CHANGE_ME';
CREATE DATABASE cargoweb OWNER cargoweb;
GRANT ALL PRIVILEGES ON DATABASE cargoweb TO cargoweb;
```

`DATABASE_URL` (пример):

```bash
DATABASE_URL=postgresql://cargoweb:CHANGE_ME@127.0.0.1:5432/cargoweb
```

---

## 6) Создать `.env` (prod)

Скопируйте шаблон:

```bash
sudo -u cargoweb cp /opt/cargotech_driver_app/app/.env.example /opt/cargotech_driver_app/app/.env
sudo -u cargoweb nano /opt/cargotech_driver_app/app/.env
```

Минимально обязательно (пример):

```bash
DEBUG=False
SECRET_KEY=...случайная_строка...
ALLOWED_HOSTS=example.com
WEBAPP_URL=https://example.com/

TELEGRAM_BOT_TOKEN=123:xxx
TELEGRAM_RESPONSES_CHAT_ID=-1001234567890

REDIS_URL=redis://127.0.0.1:6379/0
DATABASE_URL=postgresql://...

CARGOTECH_PHONE=+7...
CARGOTECH_PASSWORD=...
```

Опционально (M5):

```bash
YOOKASSA_WEBHOOK_SECRET=...случайная_строка...
SETTINGS_ENCRYPTION_KEY=...Fernet key...
```

Fernet key можно сгенерировать:

```bash
/opt/cargotech_driver_app/venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 7) Миграции + админ

```bash
cd /opt/cargotech_driver_app/app
sudo -u cargoweb /opt/cargotech_driver_app/venv/bin/python manage.py migrate
sudo -u cargoweb /opt/cargotech_driver_app/venv/bin/python manage.py createsuperuser
sudo -u cargoweb /opt/cargotech_driver_app/venv/bin/python manage.py collectstatic --noinput
```

Важно: директория `logs/` должна существовать и быть доступна на запись для `cargoweb`.

---

## 8) Gunicorn systemd service

Создайте файл `/etc/systemd/system/cargoweb.service`:

```ini
[Unit]
Description=CargoTech Driver WebApp (gunicorn)
After=network.target

[Service]
User=cargoweb
Group=cargoweb
WorkingDirectory=/opt/cargotech_driver_app/app
Environment=DJANGO_SETTINGS_MODULE=config.settings
ExecStart=/opt/cargotech_driver_app/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

Применить:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cargoweb
sudo systemctl status cargoweb --no-pager
```

---

## 9) Nginx reverse proxy + HTTPS

Создайте `/etc/nginx/sites-available/cargoweb.conf`:

```nginx
server {
  server_name example.com;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```

Включить и перезагрузить:

```bash
sudo ln -s /etc/nginx/sites-available/cargoweb.conf /etc/nginx/sites-enabled/cargoweb.conf
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS (Let’s Encrypt):

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com
```

---

## 10) Настроить Telegram webhook

```bash
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -d "url=https://example.com/telegram/webhook/"
```

Важно:
- `WEBAPP_URL` должен совпадать с публичным HTTPS URL WebApp.
- `TELEGRAM_RESPONSES_CHAT_ID` — чат/группа, куда уходят отклики (нужен реальный chat_id).

---

## 11) Настроить ЮKassa webhook (опционально)

- Endpoint: `https://example.com/api/payments/webhook`
- Если задан `YOOKASSA_WEBHOOK_SECRET`, отправляйте заголовок `X-Webhook-Token: <secret>`.

ЮKassa credentials (`shop_id`, `secret_key`) можно:
- задать env (`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`), или
- положить в БД через `SystemSetting` (секреты шифруются при наличии `SETTINGS_ENCRYPTION_KEY`).

---

## 12) Smoke checks

```bash
curl -s https://example.com/healthz
curl -s "https://example.com/healthz?deep=1"
```

Проверки из `docs/DEPLOY_GUIDE_v3.2.md`:
- Telegram auth flow проходит (session создаётся).
- Cargo list/detail работает (server-side token валиден).
- Telegram Bot отклик проходит.

---

## 13) Логи и отладка

```bash
sudo journalctl -u cargoweb -f
tail -n 200 /opt/cargotech_driver_app/app/logs/error.log
tail -n 200 /opt/cargotech_driver_app/app/logs/cargotech_auth.log
```

