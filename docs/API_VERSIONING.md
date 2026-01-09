# API Versioning Documentation

## Обзор

API Versioning обеспечивает поддержку backward compatibility и позволяет эволюционировать API без нарушения работы существующих клиентов.

## Архитектура

### Компоненты

1. **Middleware** ([`apps/core/api_versioning.py`](apps/core/api_versioning.py:1))
   - `APIVersioningMiddleware` - извлекает версию из запроса
   - Устанавливает `request.api_version`
   - Добавляет заголовки ответа с информацией о версии

2. **Helper Functions**
   - `get_api_version()` - определение версии из URL или заголовка
   - `versioned_url()` - генерация versioned URL
   - `is_version_supported()` - проверка поддержки версии
   - `get_supported_versions()` - список поддерживаемых версий
   - `get_latest_version()` - последняя версия
   - `is_version_outdated()` - проверка устаревания
   - `build_version_headers()` - построение заголовков ответа

3. **URL Configuration** ([`config/urls.py`](config/urls.py:1))
   - Versioned URL patterns для v1, v2, v3
   - Backward compatibility endpoints (без префикса версии)

## Поддерживаемые версии

| Версия | Статус | Описание |
|--------|--------|----------|
| v1 | ⚠️ Устаревшая | Первая версия API |
| v2 | ⚠️ Устаревшая | Вторая версия с улучшениями |
| v3 | ✅ Актуальная | Текущая стабильная версия |

## URL Patterns

### Versioned Endpoints

```
/api/v1/auth/telegram
/api/v1/cargos/
/api/v1/cargos/<id>/
/api/v1/dictionaries/points
/api/v1/payments/create
/api/v1/payments/webhook
/api/v1/promocodes/apply

/api/v2/auth/telegram
/api/v2/cargos/
/api/v2/cargos/<id>/
/api/v2/dictionaries/points
/api/v2/payments/create
/api/v2/payments/webhook
/api/v2/promocodes/apply

/api/v3/auth/telegram
/api/v3/cargos/
/api/v3/cargos/<id>/
/api/v3/dictionaries/points
/api/v3/payments/create
/api/v3/payments/webhook
/api/v3/promocodes/apply
```

### Legacy Endpoints (Backward Compatibility)

```
/api/auth/telegram      → v3
/api/cargos/            → v3
/api/cargos/<id>/       → v3
/api/dictionaries/points → v3
/api/payments/create    → v3
/api/payments/webhook   → v3
/api/promocodes/apply   → v3
```

## Определение версии API

### Из URL Path

Версия определяется из пути URL:

```bash
# v1
GET /api/v1/cargos/

# v2
GET /api/v2/cargos/

# v3
GET /api/v3/cargos/
```

### Из HTTP Header

Версия может быть указана в заголовке `X-API-Version`:

```bash
# Использование заголовка
GET /api/cargos/
X-API-Version: v2
```

**Приоритет:** Заголовок имеет приоритет над URL path.

### Default Version

Если версия не указана, используется версия по умолчанию:

- **Default:** `v3`
- **Legacy endpoints:** также используют `v3`

## Настройки

### Environment Variables

```bash
# Включить/выключить версионирование API
API_VERSIONING_ENABLED=True

# Версия по умолчанию
API_DEFAULT_VERSION=v3

# Поддерживаемые версии (через запятую)
API_SUPPORTED_VERSIONS=v1,v2,v3

# Имя заголовка для версии
API_VERSION_HEADER=X-API-Version
```

### Django Settings ([`config/settings.py`](config/settings.py:183))

```python
# API Versioning settings
API_VERSIONING_ENABLED = True
API_DEFAULT_VERSION = "v3"
API_SUPPORTED_VERSIONS = ["v1", "v2", "v3"]
API_VERSION_HEADER = "X-API-Version"
```

## Middleware

### Расположение в Middleware Stack

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.ExceptionHandlingMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.api_versioning.APIVersioningMiddleware",  # ← Здесь
    "django.middleware.csrf.CsrfViewMiddleware",
    # ... остальные middleware
]
```

### Поведение Middleware

1. **Извлечение версии:** Из URL path или заголовка
2. **Валидация:** Проверка, что версия поддерживается
3. **Fallback:** Использование default версии при ошибке
4. **Logging:** Логирование всех запросов с версией
5. **Response Headers:** Добавление заголовков версии в ответ

## Response Headers

Все API ответы включают следующие заголовки:

```http
X-API-Version: v3
X-API-Latest-Version: v3
X-API-Supported-Versions: v1, v2, v3
```

### Deprecation Warning

Для устаревших версий добавляется предупреждение:

```http
X-API-Deprecation: Version v1 is outdated. Please upgrade to v3
```

## Helper Functions

### get_api_version()

Определяет версию API из запроса.

```python
from apps.core.api_versioning import get_api_version

def my_view(request):
    version = get_api_version(request)
    # version = "v1", "v2", или "v3"
```

### versioned_url()

Генерирует versioned URL.

```python
from apps.core.api_versioning import versioned_url

# /api/v3/auth/telegram
url = versioned_url("/auth/telegram")

# /api/v1/cargos/
url = versioned_url("/cargos/", version="v1")
```

### is_version_supported()

Проверяет поддержку версии.

```python
from apps.core.api_versioning import is_version_supported

if is_version_supported("v2"):
    # v2 поддерживается
    pass
```

### get_supported_versions()

Возвращает список поддерживаемых версий.

```python
from apps.core.api_versioning import get_supported_versions

versions = get_supported_versions()
# versions = ["v1", "v2", "v3"]
```

### get_latest_version()

Возвращает последнюю версию.

```python
from apps.core.api_versioning import get_latest_version

latest = get_latest_version()
# latest = "v3"
```

### is_version_outdated()

Проверяет, устарела ли версия.

```python
from apps.core.api_versioning import is_version_outdated

if is_version_outdated("v1"):
    # v1 устарела, рекомендуем обновление
    pass
```

### build_version_headers()

Строит заголовки ответа с информацией о версии.

```python
from apps.core.api_versioning import build_version_headers

headers = build_version_headers("v1", include_deprecation=True)
# headers = {
#     "X-API-Version": "v1",
#     "X-API-Latest-Version": "v3",
#     "X-API-Supported-Versions": "v1, v2, v3",
#     "X-API-Deprecation": "Version v1 is outdated. Please upgrade to v3"
# }
```

## Использование в Views

### Доступ к версии

```python
from django.http import JsonResponse

def my_view(request):
    # Версия доступна через middleware
    version = request.api_version
    
    # Логика в зависимости от версии
    if version == "v1":
        # v1 логика
        data = {"version": "v1", "legacy": True}
    else:
        # v2/v3 логика
        data = {"version": version, "modern": True}
    
    return JsonResponse(data)
```

### Добавление заголовков версии

```python
from django.http import JsonResponse
from apps.core.api_versioning import build_version_headers

def my_view(request):
    data = {"message": "success"}
    response = JsonResponse(data)
    
    # Добавить заголовки версии
    headers = build_version_headers(request.api_version)
    for key, value in headers.items():
        response[key] = value
    
    return response
```

## Backward Compatibility

### Стратегия миграции

1. **Legacy Endpoints** - продолжают работать, используют v3
2. **Versioned Endpoints** - явное указание версии
3. **Deprecation Warnings** - информирование клиентов об устаревании
4. **Graceful Degradation** - ошибки версионирования не ломают API

### План устаревания версий

- **v1:** Устарела, будет удалена через 6 месяцев
- **v2:** Устарела, будет удалена через 3 месяца
- **v3:** Актуальная, поддержка продолжается

### Рекомендации для клиентов

1. **Использовать versioned URLs:** `/api/v3/...`
2. **Указывать версию в заголовке:** `X-API-Version: v3`
3. **Следить за deprecation warnings:** в заголовках ответа
4. **Обновляться до последней версии:** v3

## Логирование

### Log Files

API versioning логируется в:

- **Console:** Вывод в консоль для отладки
- **File:** `logs/api_versioning.log`

### Log Levels

- **INFO:** Все API запросы с версией
- **WARNING:** Неверная версия, fallback к default
- **ERROR:** Ошибки версионирования

### Пример лога

```
2026-01-09 10:30:45 INFO api_versioning: API Request: GET /api/v1/cargos/ (version: v1, user: AnonymousUser)
2026-01-09 10:30:50 WARNING api_versioning: Invalid API version 'v99', using default 'v3'
```

## Тестирование

### Запуск тестов

```bash
# Все тесты API versioning
pytest apps/core/tests_api_versioning.py -v

# Специфический тест
pytest apps/core/tests_api_versioning.py::TestGetAPIVersion::test_extract_version_from_url_path -v

# Покрытие кода
pytest apps/core/tests_api_versioning.py --cov=apps.core.api_versioning --cov-report=html
```

### Покрытие тестами

Тесты покрывают:

- ✅ Извлечение версии из URL path
- ✅ Извлечение версии из HTTP header
- ✅ Приоритет заголовка над URL
- ✅ Default version fallback
- ✅ Graceful degradation при ошибках
- ✅ Helper функции
- ✅ Middleware поведение
- ✅ Интеграционные тесты URL routing
- ✅ Отключение версионирования

## Troubleshooting

### Проблема: Версия не определяется

**Симптом:** `request.api_version` не установлен

**Решение:**
1. Проверьте, что middleware добавлен в `MIDDLEWARE`
2. Убедитесь, что `API_VERSIONING_ENABLED=True`
3. Проверьте логи в `logs/api_versioning.log`

### Проблема: Legacy endpoints не работают

**Симптом:** Ошибка 404 на `/api/cargos/`

**Решение:**
1. Проверьте, что legacy patterns добавлены в `config/urls.py`
2. Убедитесь, что они идут ПОСЛЕ versioned patterns

### Проблема: Неверная версия в заголовке

**Симптом:** `X-API-Version` всегда `v3`

**Решение:**
1. Проверьте приоритет: header > URL path > default
2. Убедитесь, что заголовок называется `X-API-Version`
3. Проверьте настройки `API_VERSION_HEADER`

## Безопасность

### Валидация версии

- Только версии из `API_SUPPORTED_VERSIONS` принимаются
- Неверные версии автоматически fallback к default
- Логирование всех попыток использования неверных версий

### Rate Limiting

Versioning не влияет на rate limiting - все версии используют одинаковые лимиты.

### CSRF Protection

Versioning работает с существующим CSRF protection middleware.

## Производительность

### Накладные расходы

- **Middleware:** < 1ms на запрос
- **Helper функции:** < 0.1ms на вызов
- **Memory:** Минимальный (строковые операции)

### Кэширование

Версия кэшируется в `request.api_version` для повторного доступа.

## Будущие улучшения

1. **Version-specific Views:** Разные view для разных версий
2. **Schema Versioning:** Разные JSON schemas для версий
3. **Version Negotiation:** Content negotiation для версий
4. **Version Deprecation Timeline:** Автоматическое удаление старых версий

## Ссылки

- [API Contracts](API_CONTRACTS_v3.2.md)
- [Deployment Guide](DEPLOY_GUIDE_v3.2.md)
- [Technical Debt Report](../plans/technical_debt_report.md)

## Изменения

### v3.2.0 (2026-01-09)

- ✅ Добавлено API Versioning middleware
- ✅ Helper функции для versioning
- ✅ Versioned URL patterns
- ✅ Backward compatibility endpoints
- ✅ Тесты для API versioning
- ✅ Документация

---

**Версия документа:** 1.0  
**Последнее обновление:** 2026-01-09  
**Статус:** ✅ Production Ready
