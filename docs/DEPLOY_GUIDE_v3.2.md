# 🚀 DEPLOY GUIDE v3.2

**Дата:** 7 января 2026  
**Версия:** 3.2 (v3.1 + HAR Validation Updates)

---

## ✅ Предпосылки

- Python + virtualenv
- PostgreSQL (или совместимая БД)
- Redis
- (Рекомендуется) Celery worker + Celery beat
- Домен + HTTPS (обязательно для Telegram WebApp и webhooks)

---

## 🔑 Переменные окружения (.env)

Минимальный набор для базового функционала:

```bash
DEBUG=False
SECRET_KEY=...
TELEGRAM_BOT_TOKEN=...
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://...

# CargoTech (server-side login)
CARGOTECH_PHONE=+7 911 111 11 11
CARGOTECH_PASSWORD=123-123
```

M5 (платежи/подписки):

- ЮKassa `shop_id`/`secret_key` хранятся **в БД** (SystemSetting, encrypted) и настраиваются через admin panel.
- Webhook endpoint ЮKassa должен быть доступен извне и защищён проверкой подписи + идемпотентностью.

---

## 🗄️ Миграции

```bash
python manage.py migrate
```

Если приложения разделены по пакетам, миграции должны включать как минимум:
- `payments`, `subscriptions`, `promocodes` (M5)

---

## 🧵 Фоновые задачи

 - (Опционально) auth health check/alerting для CargoTech (P5)
- Обработка платежных событий/очистки (M5, по необходимости)

Рекомендуемая схема:
- Celery worker
- Celery beat (периодические задачи)

---

## 🌐 Webhooks

Убедитесь, что настроены и доступны:

- Telegram Bot webhooks (M4)
- ЮKassa webhooks (M5)

Требования:
- HTTPS
- Логи без секретов
- Проверка подписи/целостности
- Идемпотентная обработка событий

---

## ✅ Smoke Test (после деплоя)

1. Telegram auth flow проходит (session создаётся).
2. Cargo list/detail работает (server-side token валиден).
3. Telegram Bot отклик проходит (status update).
4. M5: paywall отображается при отсутствии подписки.
5. M5: создание платежа возвращает `confirmation_url`.
6. M5: webhook `payment.succeeded` активирует подписку.

---

## ✅ Валидация после деплоя

### Проверка API интеграции

```bash
# 1. Проверить server-side token
redis-cli GET cargotech:api:token

# 2. Проверить login через Django shell
python manage.py shell
>>> from apps.integrations.cargotech_auth import CargoTechAuthService
>>> print(CargoTechAuthService.get_token())

# 3. Тестовый запрос cargo list
TOKEN=$(redis-cli GET cargotech:api:token)
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.cargotech.pro/v2/cargos/views?include=contacts&limit=1&offset=0&filter[mode]=my&filter[user_id]=0"
```

---

## 📅 План разработки (сводка)

- База (M1–M4 + Contract 1.4 server‑side login): 14 дней
- M5 (подписки/платежи): +10 дней
- Итого: 24 дня

Подробный план: `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (Часть 8). Legacy v3.1 план: `legacy_3.1/FINAL_COMPLETE_v3.1.md`.

---

## 📌 Где смотреть детали

- Архитектура/чек‑листы: `FINAL_PROJECT_DOCUMENTATION_v3.2.md`
- Контракты: `API_CONTRACTS_v3.2.md`
- Reference код реализации: `IMPLEMENTATION_CODE_v3.2.md`
- M5 подробно: `M5_SUBSCRIPTION_PAYMENT_FULL.md`
