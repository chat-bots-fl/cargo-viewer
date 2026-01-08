# 📋 СВОДКА ВСЕХ ИЗМЕНЕНИЙ

> ⚠️ **DEPRECATED (v2.0/v2.1).** Актуальная документация: `INDEX_v3.1.md` (v3.1, 4 января 2026). Файл сохранён только для истории.

**Дата:** 29 декабря 2025  
**Версия:** 2.0 (Final)  
**Статус:** ✅ ГОТОВО К РАЗРАБОТКЕ

---

## 🔍 ОБЗОР ВСЕХ 6 ИСПРАВЛЕНИЙ

### ❌→✅ ИСПРАВЛЕНИЕ #1: extranote в FR-4

**ПРОБЛЕМА:**
```
FR-4 "Детальная карточка груза" не включает extranote поле
Это поле содержит критическую информацию:
- "Груз готов, оплачено авансам, рефриж обязателен"
- "Только ИП, ограничения по времени, без наличных"
- "ТРЕБУЕТСЯ ДОПОГ, опасный груз класс 3"
```

**РЕШЕНИЕ:**
```diff
FR-4: Детальная карточка груза

  - Основная информация (всегда видна)
  - Маршрут (город отправления → город прибытия)
  - Параметры груза (вес, объем, тип)
  - Дополнительные условия ← ДОБАВЛЕНО
+   - Источник: extranote (raw text from API)
+   - Обязательность: Показывать только если not NULL
+   - Оформление: monospace шрифт (сохранение структуры)
+   - Примеры: 
+     - "Груз готов ✓ | Оплачено авансом | Рефриж обязателен"
+     - "Только ИП | Ограничения по времени | ДОПОГ запрет"
```

**КОНТРАКТЫ:**
```diff
Contract 2.1: CargoAPIClient.fetch_cargos()
RETURNS добавить:
+ - extranote: Optional[str]  # Additional requirements from shipper
```

**КОД (Django template):**
```html
{% if cargo.extranote %}
<div class="extra-requirements">
  <h4>⚠️ Дополнительные условия</h4>
  <pre>{{ cargo.extranote }}</pre>
</div>
{% endif %}
```

---

### ❌→✅ ИСПРАВЛЕНИЕ #2: weight_volume категоризация

**ПРОБЛЕМА:**
```
API запрос: filter[w][v]=10-54 (непонятно что это)
- Это вес (тонны)? Объем (м³)? Оба?
- Диапазон 10-54 или две отдельные цифры?
- Какие юниты использует API?
```

**РЕШЕНИЕ:**
```diff
API Specification: Query Parameters

БЫЛО:
{
  "filter[w][v]": "10-54",  # Неясный формат
}

ИСПРАВИТЬ НА:
{
  "filter[weight_volume]": "1_3"     # 1-3 т / до 15 м³
  "filter[weight_volume]": "3_5"     # 3-5 т / 15-25 м³
  "filter[weight_volume]": "5_10"    # 5-10 т / 25-40 м³
  "filter[weight_volume]": "10_15"   # 10-15 т / 40-60 м³
  "filter[weight_volume]": "15_20"   # 15-20 т / 60-82 м³
  "filter[weight_volume]": "20"      # 20+ т / 82+ м³
  "filter[weight_volume]": "any"     # Без фильтра (default)
}
```

**ТАБЛИЦА МАППИНГА:**
```
Значение | Вес мин     | Объем мин | Объем макс | Описание
---------|-----------|----------|-----------|------------------------
"1_3"    | 1000 кг   | 0 м³     | 15 м³     | Маленькие грузы
"3_5"    | 3000 кг   | 15 м³    | 25 м³     | Легкая фура (3-5т)
"5_10"   | 5000 кг   | 25 м³    | 40 м³     | Средняя фура (5-10т)
"10_15"  | 10000 кг  | 40 м³    | 60 м³     | Полуприцеп 40t
"15_20"  | 15000 кг  | 60 м³    | 82 м³     | Полуприцеп 82t
"20"     | 20000 кг  | 82 м³    | ∞         | Мегаложи (20+ т)
```

**КОНТРАКТЫ:**
```diff
Contract 3.1: FilterService.validate_filters()

PARAMETERS добавить:
+ - weight_volume: Optional[str] 
+   in ["1_3", "3_5", "5_10", "10_15", "15_20", "20", "any"]
+   @constraint: Predefined categories only
+   @default: "any"
```

**КОД (apps/filtering/constants.py):**
```python
WEIGHT_VOLUME_CATEGORIES = {
    "1_3": {
        "label": "1-3 т / до 15 м³",
        "weight_min_kg": 1000,
        "weight_max_kg": 3000,
        "volume_min_m3": 0,
        "volume_max_m3": 15,
    },
    "3_5": {
        "label": "3-5 т / 15-25 м³",
        "weight_min_kg": 3000,
        "weight_max_kg": 5000,
        "volume_min_m3": 15,
        "volume_max_m3": 25,
    },
    # ... остальные 5 категорий
}

WEIGHT_VOLUME_OPTIONS = [
    ("any", "Любой вес и объем"),
    ("1_3", "1-3 т / до 15 м³"),
    ("3_5", "3-5 т / 15-25 м³"),
    # ... остальные опции
]
```

**КОД (HTML форма):**
```html
<select name="weight_volume">
  {% for value, label in weight_volume_options %}
    <option value="{{ value }}">{{ label }}</option>
  {% endfor %}
</select>
```

---

### ❌→✅ ИСПРАВЛЕНИЕ #3: NFR-1.2 Performance Requirement

**ПРОБЛЕМА:**
```
Требование: "Открытие деталей груза: < 1 сек"
Реальность: API ответ может быть 700-2000ms (сетевая задержка + API)
Итого: невозможно выполнить < 1 сек гарантию
```

**РЕШЕНИЕ:**
```diff
NFR-1.2: Открытие детальной карточки

БЫЛО:
- Открытие деталей: < 1 сек (абсолютное требование)

ИСПРАВИТЬ НА:
+ Открытие деталей: < 2 сек (p95)
+   - p50: < 500ms (cached data shown immediately)
+   - p95: < 2000ms (with fetch + loading spinner)
+   - Fallback: Show cached data if API timeout
+   - UI: Show loading indicator while fetching
```

**АРХИТЕКТУРА:**
```
Frontend действия:
1. Клик на карточку груза
2. Показываем spinner + данные из списка (моментально)
3. В фоне: fetch деталей (может быть до 2s)
4. При ответе: обновляем UI с полными данными
5. При timeout: показываем cached версию (если есть)
```

**КОД (HTMX):**
```html
<div hx-get="/api/cargos/{{ cargo.id }}/"
     hx-target="#detail-modal"
     hx-trigger="click"
     hx-swap="innerHTML"
     hx-indicator="#loading-spinner"
     class="cargo-card">
  <!-- Карточка груза -->
</div>

<div id="loading-spinner" class="spinner htmx-request">
  <div class="spinner-icon"></div> Загрузка...
</div>
```

---

### ❌→✅ ИСПРАВЛЕНИЕ #4: Rate Limiting стратегия

**ПРОБЛЕМА:**
```
API лимит: 600 requests/minute (10 req/sec)
Максимум пользователей: 1000+
Потребление: 1000 × 60 req = 60,000 запросов/минуту
Доступно: 600 запросов/минуту
КОНФЛИКТ: 60,000 >> 600 = ПЕРЕГРУЗ!
```

**РЕШЕНИЕ:**
```diff
Contract 2.1: CargoAPIClient.fetch_cargos()

GUARANTEES добавить:
+ Rate Limit Handling:
+   - Per-request headers: X-RateLimit-Limit, X-RateLimit-Remaining
+   - On 429: Retry after X-RateLimit-Reset-After
+   - Backoff pattern: 500ms → 1500ms → 3000ms (+ random jitter)
+   - Max attempts: 4 (then error to user)
+   - Soft limit: Start queuing at 80% capacity
+   - Queue strategy: FIFO with max 1000 requests in queue
```

**АЛГОРИТМ TOKEN BUCKET:**
```python
class RateLimiter:
    def __init__(self, requests_per_minute=600):
        self.capacity = requests_per_minute
        self.tokens = requests_per_minute
        self.last_update = time.time()
    
    def can_request(self):
        now = time.time()
        elapsed = now - self.last_update
        
        # Добавляем токены за прошедшее время
        new_tokens = elapsed * (self.capacity / 60)
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
```

**ЭКСПОНЕНЦИАЛЬНЫЙ BACKOFF:**
```python
def fetch_with_retry(url, max_attempts=4):
    for attempt in range(max_attempts):
        response = requests.get(url)
        
        if response.status_code == 429:
            wait_time = 500 * (2 ** attempt) + random.randint(0, 100)
            logger.warning(f"Rate limited, retrying after {wait_time}ms")
            time.sleep(wait_time / 1000)
            continue
        
        return response
    
    raise RateLimitError("Max retries exceeded")
```

---

### ❌→✅ ИСПРАВЛЕНИЕ #5: Cache Strategy 3-уровневая

**ПРОБЛЕМА:**
```
Что кэшировать? Как долго? Когда инвалидировать?
- Если TTL = 1 минута → много API запросов → лимит нарушается
- Если TTL = 30 минут → водители видят старые грузы (плохой UX)
- Если кэш глобальный → все видят одни грузы (неправильно!)
```

**РЕШЕНИЕ - 3-УРОВНЕВАЯ CACHE:**
```diff
Contract 2.3: CargoService.get_cargos()

GUARANTEES обновить Cache section:

+ Level 1: Per-User Cargo List Cache
+   Key: "user:{user_id}:cargos:{filter_hash}"
+   Data: List[CargoCard]
+   TTL: 5 minutes
+   When: User applies filter
+   Invalidation: filter change, logout, webhook on new cargo posted
+
+ Level 2: Cargo Detail Cache
+   Key: "cargo:{cargo_id}:detail"
+   Data: Full cargo object with extranote
+   TTL: 15 minutes
+   When: User opens detail view
+   Invalidation: webhook from CargoTech, status change
+
+ Level 3: Autocomplete Cache (Cities/Regions)
+   Key: "autocomplete:cities"
+   Data: City reference dictionary
+   TTL: 24 hours
+   When: App startup (preload)
+   Invalidation: Manual (static data)
```

**FALLBACK СТРАТЕГИЯ:**
```
Redis недоступен → Все запросы → API (no cache)
API недоступен → Serve stale cache (до 1 часа) с warning
Cache miss → Fetch from API + async update Redis
```

**КОД (Django cache):**
```python
from django.views.decorators.cache import cache_page
from django.core.cache import cache

class CargoListView(View):
    def get(self, request):
        # Генерируем ключ с фильтрами
        filter_hash = hash_filters(request.GET)
        cache_key = f"user:{request.user.id}:cargos:{filter_hash}"
        
        # Проверяем кэш
        cargos = cache.get(cache_key)
        if cargos is None:
            # Fetch from API
            cargos = fetch_from_cargotech_api(request.GET)
            # Сохраняем на 5 минут
            cache.set(cache_key, cargos, timeout=300)
        
        return render(request, 'cargos_list.html', {'cargos': cargos})
```

---

### ❌→✅ ИСПРАВЛЕНИЕ #6: Telegram Security усилении

**ПРОБЛЕМА:**
```
Contract 1.1 не валидирует auth_date
- Если bot_token утечет → Злоумышленник может подделать любого пользователя
- Старые credentials могут быть переиспользованы (replay attack)
- Нет механизма обновления token при компрометации
```

**РЕШЕНИЕ:**
```diff
Contract 1.1: TelegramAuthService.validate_init_data()

PARAMETERS добавить:
+ - max_age_seconds: int = 300
+   @constraint: 300-3600 (5 минут - 1 час)
+   @default: 300 (5 минут для session recovery)

GUARANTEES добавить:
+ - Timestamp Validation: auth_date not older than max_age_seconds
+ - Reject: Credentials older than limit (prevent replay attacks)
+ - Constant-time: String comparison (prevent timing attacks)
+ - Secret Management: bot_token from environment (not in code)
+ - Monitoring: All validation failures logged (ERROR level)
+ - Alerts: If > 10 failures in 1 minute (attack detection)
```

**КОД (Django):**
```python
import hmac
import hashlib
from datetime import datetime, timedelta

class TelegramAuthService:
    def validate_init_data(self, init_data: str, hash_value: str, 
                          max_age_seconds: int = 300):
        """
        Validate Telegram WebApp initData
        
        Args:
            init_data: Sorted key-value pairs from Telegram
            hash_value: HMAC-SHA256 hash from Telegram
            max_age_seconds: Max age of auth_date (default 300s = 5 min)
        
        Raises:
            ValidationError: If validation fails
        """
        # 1. Проверяем HMAC-SHA256
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        secret = hashlib.sha256(bot_token.encode()).digest()
        
        calculated_hash = hmac.new(
            secret, 
            init_data.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison (prevent timing attacks)
        if not hmac.compare_digest(calculated_hash, hash_value):
            logger.error("Invalid Telegram hash")
            raise ValidationError("Invalid Telegram hash")
        
        # 2. Проверяем auth_date не старше max_age_seconds
        data_dict = dict(pair.split('=') for pair in init_data.split('&'))
        auth_date = int(data_dict.get('auth_date', 0))
        current_time = int(datetime.now().timestamp())
        
        age = current_time - auth_date
        if age > max_age_seconds:
            logger.warning(f"Auth too old: {age}s > {max_age_seconds}s")
            raise ValidationError(f"Auth expired ({age}s old)")
        
        logger.info(f"Telegram auth valid for user {data_dict.get('id')}")
        return data_dict
```

**НАСТРОЙКИ DJANGO:**
```python
# settings.py
import os

# Bot token НИКОГДА не в коде!
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# Максимальный возраст auth_date (5 минут по умолчанию)
TELEGRAM_MAX_AUTH_AGE = int(os.environ.get('TELEGRAM_MAX_AUTH_AGE', 300))

# Logging для атак
LOGGING = {
    'handlers': {
        'telegram_auth': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'telegram_auth.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
        },
    },
}
```

---

## 📊 МАТРИЦА ИЗМЕНЕНИЙ

| № | Проблема | Тип | Где | Что изменилось | Статус |
|---|----------|-----|-----|-----------------|--------|
| 1 | extranote отсутствует | FR | FR-4 + Contract 2.1 | + extranote поле + template | ✅ |
| 2 | filter[w][v] неясен | API | Contract 3.1 + API spec | 7 категорий + маппинг | ✅ |
| 3 | NFR-1.2 < 1s невозможно | NFR | Technical spec | < 2s (p95) + spinner | ✅ |
| 4 | Rate limiting неполно | Contract | Contract 2.1 | Token bucket + backoff | ✅ |
| 5 | Cache strategy неясна | Contract | Contract 2.3 | 3-уровневая + TTL + invalidation | ✅ |
| 6 | Telegram security неполна | Contract | Contract 1.1 | max_age + constant-time + logging | ✅ |

---

## ✅ ЧЕК-ЛИСТ ПЕРЕД РАЗРАБОТКОЙ

Убедитесь, что ВСЕ сделано:

- [ ] **FR-4:** extranote добавлена в шаблон html
- [ ] **weight_volume:** 7 категорий определены в constants.py
- [ ] **NFR-1.2:** Изменена на < 2s (p95) в техническом заданииselect
- [ ] **Contract 1.1:** max_age_seconds параметр добавлен
- [ ] **Contract 2.1:** Rate limiting стратегия описана
- [ ] **Contract 2.3:** 3-уровневая cache определена
- [ ] **Code:** apps/filtering/constants.py создан
- [ ] **Code:** normalize_weight_volume_filter функция реализована
- [ ] **Code:** TelegramAuthService.validate_init_data обновлена
- [ ] **Tests:** Contract tests написаны для всех 6 изменений
- [ ] **Django:** TELEGRAM_BOT_TOKEN в environment (не в коде!)
- [ ] **Redis:** Кэш сервер поднят и тестирован
- [ ] **API:** Все endpoints протестированы с реальным CargoTech API

---

## 🚀 ИТОГОВЫЙ СТАТУС

```
┌─────────────────────────────────────────┐
│  ВСЕ 6 ПРОБЛЕМ РЕШЕНЫ ✅                │
│  ДОКУМЕНТАЦИЯ: 100% ПОЛНАЯ              │
│  ГОТОВО К РАЗРАБОТКЕ: ДА                │
└─────────────────────────────────────────┘

Можно начинать разработку ДА!
```

---

**Дата:** 29 декабря 2025  
**Версия:** 2.0 Final  
**Одобрено:** ✅ Готово к разработке
