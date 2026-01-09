# OpenAPI Спецификация API

## Обзор

Cargo Viewer API предоставляет RESTful интерфейс для работы с системой просмотра грузов через Telegram WebApp. API поддерживает версионирование (v1, v2, v3) и автоматическую генерацию документации через drf-spectacular.

## Базовый URL

- **Production:** `https://your-domain.com/api/v3/`
- **Development:** `http://localhost:8000/api/v3/`

## Доступ к документации

- **Swagger UI:** `https://your-domain.com/api/docs/`
- **ReDoc:** `https://your-domain.com/api/redoc/`
- **OpenAPI Schema (JSON):** `https://your-domain.com/api/schema/`

## Аутентификация

API использует JWT токены для аутентификации. Токен передаётся через HTTP-only cookie `session_token` или в заголовке `Authorization: Bearer <token>`.

### Получение токена

Используйте endpoint `/api/v3/auth/telegram` для аутентификации через Telegram WebApp.

## Версионирование

API поддерживает три версии:
- **v1** - Устаревшая версия (поддерживается для обратной совместимости)
- **v2** - Промежуточная версия
- **v3** - Текущая версия (рекомендуется)

Используйте заголовок `X-API-Version` для указания версии или включайте версию в URL.

## Endpoints

### Аутентификация (`/api/v3/auth/`)

#### POST `/api/v3/auth/telegram`

Аутентификация водителя через Telegram WebApp initData.

**Тело запроса:**
```json
{
  "init_data": "user=%7B%22id%22%3A123456789%2C%22first_name%22%3A%22%D0%98%D0%B2%D0%B0%D0%BD%22%2C%22username%22%3A%22ivan_driver%22%7D&auth_date=1234567890&hash=..."
}
```

**Успешный ответ (200):**
```json
{
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "driver": {
    "driver_id": 123456789,
    "first_name": "Иван",
    "username": "ivan_driver"
  }
}
```

**Ошибки:**
- `400` - Неверный формат JSON или ошибки валидации
- `401` - Неверный initData или HMAC

### Грузы (`/api/v3/cargos/`)

#### GET `/api/v3/cargos/`

Получить список грузов с фильтрацией и пагинацией. Возвращает HTML-фрагмент для HTMX.

**Query параметры:**
- `limit` (int, optional) - Количество грузов на странице (по умолчанию 20)
- `offset` (int, optional) - Смещение для пагинации (по умолчанию 0)
- `city_from` (str, optional) - Город отправления
- `city_to` (str, optional) - Город назначения
- `date_from` (str, optional) - Дата погрузки с (YYYY-MM-DD)
- `date_to` (str, optional) - Дата погрузки по (YYYY-MM-DD)
- `weight_min` (int, optional) - Минимальный вес (кг)
- `weight_max` (int, optional) - Максимальный вес (кг)

**Пример запроса:**
```
GET /api/v3/cargos/?limit=20&offset=0&city_from=Москва&city_to=Санкт-Петербург
```

**Ответ (200):**
```html
<div class="cargo-list">
  <!-- HTML-фрагмент с карточками грузов -->
</div>
```

**Ошибки:**
- `400` - Ошибка валидации параметров
- `401` - Требуется аутентификация

#### GET `/api/v3/cargos/{cargo_id}/`

Получить детальную информацию о грузе. Возвращает HTML-фрагмент для модального окна.

**Параметры пути:**
- `cargo_id` (str, required) - ID груза в системе CargoTech

**Пример запроса:**
```
GET /api/v3/cargos/12345/
```

**Ответ (200):**
```html
<div class="cargo-detail">
  <!-- HTML-фрагмент с деталями груза -->
</div>
```

**Ошибки:**
- `400` - Неверный формат cargo_id
- `401` - Требуется аутентификация
- `404` - Груз не найден
- `502` - Ошибка внешнего сервиса

### Платежи (`/api/v3/payments/`)

#### POST `/api/v3/payments/create`

Создать платёж в YuKassa для выбранного тарифа.

**Тело запроса:**
```json
{
  "tariff_name": "month",
  "return_url": "https://your-domain.com/"
}
```

**Доступные тарифы:**
- `day` - Дневной тариф
- `week` - Недельный тариф
- `month` - Месячный тариф

**Успешный ответ (200):**
```html
<div><a class="btn" href="https://yoomoney.ru/checkout/..." target="_blank" rel="noopener">Перейти к оплате</a></div>
```

**Ошибки:**
- `400` - Ошибка валидации
- `401` - Требуется аутентификация
- `422` - Ошибка бизнес-логики

#### POST `/api/v3/payments/webhook`

Webhook от YuKassa для обновления статуса платежа. Используется только YuKassa.

**Тело запроса:**
```json
{
  "event": "payment.succeeded",
  "object": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "status": "succeeded",
    "metadata": {
      "user_id": 123,
      "tariff_name": "month"
    }
  }
}
```

**Успешный ответ (200):**
```json
{
  "ok": true,
  "payment_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "succeeded",
  "subscription": "987e6543-e21b-43d2-a876-543219876543"
}
```

**Ошибки:**
- `400` - Неверная подпись или JSON
- `422` - Ошибка бизнес-логики

### Промокоды (`/api/v3/promocodes/`)

#### POST `/api/v3/promocodes/apply`

Применить промокод к подписке пользователя.

**Тело запроса:**
```json
{
  "code": "WELCOME2024"
}
```

**Успешный ответ (200):**
```json
{
  "ok": true,
  "discount_days": 7,
  "new_expires_at": "2024-02-15T12:00:00Z"
}
```

**Ошибки:**
- `400` - Неверный формат запроса
- `401` - Требуется аутентификация
- `404` - Промокод не найден
- `422` - Промокод недействителен или уже использован

### Telegram (`/telegram/`)

#### POST `/telegram/webhook/`

Webhook от Telegram Bot API. Используется только Telegram.

**Тело запроса:**
```json
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 123456789,
      "first_name": "Иван",
      "username": "ivan_driver"
    },
    "chat": {
      "id": 123456789,
      "type": "private"
    },
    "text": "/start"
  }
}
```

**Успешный ответ (200):**
```json
{
  "ok": true,
  "handled": true
}
```

**Ошибки:**
- `400` - Метод не разрешён или неверный JSON
- `500` - Внутренняя ошибка сервера

#### POST `/telegram/responses/`

Отправить отклик водителя на груз из WebApp.

**Тело запроса:**
```json
{
  "cargo_id": "12345",
  "phone": "+79001234567",
  "name": "Иван Иванов"
}
```

**Успешный ответ (200):**
```html
<div class="muted">✅ Отправлено (id: 123).</div>
```

**Ошибки:**
- `400` - Ошибка валидации или отправки
- `402` - Требуется подписка
- `405` - Метод не разрешён

### Словари (`/api/v3/dictionaries/`)

#### GET `/api/v3/dictionaries/points`

Поиск городов для фильтрации грузов.

**Query параметры:**
- `q` (str, required) - Поисковый запрос

**Пример запроса:**
```
GET /api/v3/dictionaries/points?q=Мос
```

**Успешный ответ (200):**
```json
{
  "results": [
    {
      "id": "1",
      "name": "Москва",
      "region": "Московская область"
    },
    {
      "id": "2",
      "name": "Московск",
      "region": "Кемеровская область"
    }
  ]
}
```

### Health Checks

#### GET `/health/`

Базовый health check.

**Успешный ответ (200):**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

#### GET `/health/ready/`

Readiness check (готовность к приему трафика).

**Успешный ответ (200):**
```json
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "cache": "ok",
    "external_services": "ok"
  }
}
```

#### GET `/health/live/`

Liveness check (жив ли сервис).

**Успешный ответ (200):**
```json
{
  "status": "alive",
  "timestamp": "2024-01-15T12:00:00Z"
}
```

## Коды ошибок

| Код | Описание |
|-----|----------|
| `200` | Успешный запрос |
| `202` | Принято, но обработка ещё не завершена |
| `400` | Неверный запрос (ошибка валидации) |
| `401` | Не авторизован |
| `402` | Требуется оплата |
| `403` | Доступ запрещён |
| `404` | Ресурс не найден |
| `405` | Метод не разрешён |
| `422` | Ошибка бизнес-логики |
| `429` | Слишком много запросов (rate limit) |
| `500` | Внутренняя ошибка сервера |
| `502` | Ошибка внешнего сервиса |

## Rate Limiting

API применяет rate limiting для защиты от злоупотреблений:

| Тип endpoint | Лимит | Период |
|--------------|--------|--------|
| Auth | 10 | минута |
| Payment | 5 | минута |
| Telegram | 20 | минута |
| Admin | 100 | минута |
| Default | 60 | минута |

При превышении лимита возвращается код `429` с заголовком `Retry-After`.

## Формат ошибок

Все ошибки возвращаются в формате JSON:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": {
    "field": "error description"
  }
}
```

## Общие коды ошибок

| `error_code` | Описание |
|--------------|----------|
| `VALIDATION_ERROR` | Ошибка валидации входных данных |
| `AUTHENTICATION_ERROR` | Ошибка аутентификации |
| `PERMISSION_ERROR` | Недостаточно прав |
| `NOT_FOUND` | Ресурс не найден |
| `RATE_LIMIT_ERROR` | Превышен лимит запросов |
| `EXTERNAL_SERVICE_ERROR` | Ошибка внешнего сервиса |
| `BUSINESS_LOGIC_ERROR` | Ошибка бизнес-логики |
| `INTERNAL_ERROR` | Внутренняя ошибка сервера |

## Graceful Degradation

OpenAPI документация может быть отключена через переменную окружения `OPENAPI_ENABLED=False`. В этом случае endpoints `/api/schema/`, `/api/docs/` и `/api/redoc/` будут недоступны.

## Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|---------------|
| `OPENAPI_ENABLED` | Включить OpenAPI документацию | `True` |

### Настройки drf-spectacular

```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'Cargo Viewer API',
    'DESCRIPTION': 'API для просмотра грузов через Telegram WebApp',
    'VERSION': '3.2.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api',
}
```

## Примеры использования

### Пример 1: Аутентификация и получение грузов

```bash
# 1. Аутентификация
curl -X POST https://your-domain.com/api/v3/auth/telegram \
  -H "Content-Type: application/json" \
  -d '{"init_data": "..."}' \
  -c cookies.txt

# 2. Получение списка грузов
curl https://your-domain.com/api/v3/cargos/ \
  -b cookies.txt
```

### Пример 2: Создание платежа

```bash
curl -X POST https://your-domain.com/api/v3/payments/create \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"tariff_name": "month", "return_url": "https://your-domain.com/"}'
```

### Пример 3: Отправка отклика на груз

```bash
curl -X POST https://your-domain.com/telegram/responses/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"cargo_id": "12345", "phone": "+79001234567", "name": "Иван Иванов"}'
```

## Дополнительные ресурсы

- [Django REST Framework](https://www.django-rest-framework.org/)
- [drf-spectacular](https://drf-spectacular.readthedocs.io/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [AGENTS.md](../AGENTS.md) - Контрактное программирование в проекте
