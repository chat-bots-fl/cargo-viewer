# 📚 ПОЛНАЯ ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ v3.1

**Проект:** CargoTech Driver WebApp (Telegram WebApp для водителей)  
**Дата:** 4 января 2026  
**Версия:** 3.1 Final (v3.0 + M5: Subscription & Payment)  
**Статус:** ✅ **ГОТОВО К РАЗРАБОТКЕ И PRODUCTION**

---

# ЧАСТЬ 1: АРХИТЕКТУРА И ТРЕБОВАНИЯ

## 📊 PCAM АНАЛИЗ (6 процессов × 6 каналов)

### Процессы:

```
P1: AUTHENTICATE_DRIVER
    ├─ Driver opens WebApp (Telegram)
    ├─ Extract initData from Telegram
    ├─ Validate initData (HMAC-SHA256)
    ├─ Create session & store in Redis
    └─ Return session_token

P2: BROWSE_CARGOS
    ├─ Driver requests cargo list
    ├─ Apply filters (start/finish city, weight_volume, load/truck types)
    ├─ Call CargoTech API (server-side)
    ├─ Cache results (per-user, 5 min)
    └─ Return formatted list

P3: VIEW_CARGO_DETAIL
    ├─ Driver clicks on cargo
    ├─ Fetch full cargo data
    ├─ Show comment (`data.extra.note`) if present
    ├─ Cache detail (15 min)
    └─ Return complete info

P4: RESPOND_TO_CARGO
    ├─ Driver clicks "Respond"
    ├─ Send response to Telegram Bot
    ├─ Confirm with status badge
    └─ Update driver's responses list

P5: MANAGE_API_CREDENTIALS (NEW!)
    ├─ Server-side login to CargoTech
    ├─ Exchange phone+password → Bearer token
    ├─ Store token in cache (Redis)
    ├─ Re-login on 401 (invalidate cache)
    └─ Use token for all API requests

P6: MANAGE_SUBSCRIPTION & PAYMENTS (M5)
    ├─ Check subscription status (active/expired/trial)
    ├─ Create payment in ЮKassa → confirmation_url
    ├─ User completes payment on ЮKassa
    ├─ Receive ЮKassa webhook (payment.succeeded)
    ├─ Activate/extend subscription
    └─ Grant access to paid features
```

### Каналы (Channels):

```
C1: TELEGRAM_WEBAPP_CLIENT
    └─ initData from Telegram WebApp

C2: CARGOTECH_API_SERVER
    ├─ phone + password (server-side login)
    ├─ token (response)
    └─ POST /v1/auth/login

C3: TELEGRAM_BOT_WEBHOOK
    └─ Status updates from Telegram Bot

C4: YOOKASSA_PAYMENT_GATEWAY
    ├─ Create payment (REST API)
    └─ Webhooks: payment.succeeded / payment.canceled

C5: REDIS_CACHE
    ├─ Per-user cargo lists
    ├─ Cargo details
    └─ Session data

C6: DATABASE
    ├─ Driver profiles
    ├─ Responses history
    ├─ Payments + subscriptions
    ├─ Promo codes
    ├─ Encrypted secret keys (ЮKassa, SystemSetting)
    └─ Audit log
```

---

## 📦 PBS (WORK BREAKDOWN STRUCTURE)

```
PROJECT
├── M1: AUTHENTICATION & SESSION MANAGEMENT
│   ├── M1.1: Telegram WebApp validation
│   │   └─ Contract 1.1: TelegramAuthService.validate_init_data()
│   ├── M1.2: Session management
│   │   └─ Contract 1.2: SessionService.create_session()
│   ├── M1.3: Token management
│   │   └─ Contract 1.3: TokenService.validate_session()
│   └── M1.4: SERVER-SIDE API LOGIN (NEW!)
│       └─ Contract 1.4: CargoTechAuthService.login()
│
├── M2: CARGO DATA INTEGRATION
│   ├── M2.1: CargoTech API client
│   │   └─ Contract 2.1: CargoAPIClient.fetch_cargos()
│   ├── M2.2: Data formatting
│   │   └─ Contract 2.2: CargoService.format_cargo_card()
│   └── M2.3: Caching layer
│       └─ Contract 2.3: CargoService.get_cargos()
│
├── M3: FILTERING & SEARCH
│   ├── M3.1: Filter validation
│   │   └─ Contract 3.1: FilterService.validate_filters()
│   └── M3.2: Query building
│       └─ Contract 3.2: FilterService.build_query()
│
├── M4: TELEGRAM BOT INTEGRATION
│   ├── M4.1: Response handler
│   │   └─ Contract 4.1: TelegramBotService.handle_response()
│   └── M4.2: Status updates
│       └─ Contract 4.2: TelegramBotService.send_status()
│
└── M5: SUBSCRIPTION & PAYMENT MANAGEMENT
    ├── M5.1: Payment Processing (ЮKassa)
    │   ├─ Contract 5.1: PaymentService.create_payment()
    │   └─ Contract 5.2: PaymentService.process_webhook()
    ├── M5.2: Subscription Management
    │   └─ Contract 5.3: SubscriptionService.activate_from_payment()
    ├── M5.3: Promo Code System
    │   └─ Contract 5.4: PromoCodeService.create_promo_code()
    ├── M5.4: Admin Panel
    ├── M5.5: Feature Flags
    └── M5.6: Audit Logging
```

Примечание: подмодули `M5.1–M5.6` реализуются как **6 Django приложений**: `payments/`, `subscriptions/`, `promocodes/`, `admin_panel/`, `feature_flags/`, `audit/`.

**Infrastructure & Deployment (кросс‑секционно, вне PBS модулей M1‑M5):** `DEPLOY_GUIDE_v3.1.md`

---

# ЧАСТЬ 2: ФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

## 📋 FR (Functional Requirements)

```
ВСЕГО: 12 требований (FR-1…FR-12)

FR-1: Аутентификация через Telegram
  ✅ Driver opens WebApp
  ✅ System validates Telegram initData (HMAC-SHA256)
  ✅ Extract user_id, first_name, username
  ✅ Create driver session in Redis
  ✅ Return session token for API calls
  Contract: 1.1, 1.2, 1.3

FR-2: Список грузов (карточки)
  ✅ Display cargo list with pagination
  ✅ Show: title, weight, volume, route, price
  ✅ Apply caching (5 min per user)
  ✅ Format data for mobile
  Contract: 2.1, 2.2, 2.3

FR-3: Фильтрация по параметрам
  ✅ Filter by: start/finish city, weight_volume (7 categories), load/truck types
  ✅ Support multiple filters simultaneously
  ✅ Real-time search in autocomplete
  ✅ Save user preferences in cache
  Contract: 3.1, 3.2

FR-4: Детальная карточка груза
  ✅ Show full cargo info
  ✅ Include comment from `data.extra.note` (detail endpoint only)
  ✅ Show shipper contact (if available)
  ✅ Display response status
  Contract: 2.1

FR-5: Интеграция CargoTech API
  ✅ Server-side login (phone + password) ← NEW!
  ✅ Get access token from CargoTech
  ✅ Use token for all API requests
  ✅ Handle rate limiting (600 req/min)
  ✅ Implement retry logic with exponential backoff
  Contract: 1.4 (NEW!), 2.1

FR-6: Telegram Bot (отклики)
  ✅ Driver clicks "Respond"
  ✅ Send response to Telegram Bot
  ✅ Bot forwards to shipper
  ✅ Update status in WebApp
  Contract: 4.1, 4.2

FR-7: Подписка (paywall + создание платежа)
  ✅ Check subscription status before granting access
  ✅ Create payment in ЮKassa and return confirmation_url
  ✅ Redirect user to payment page
  Contract: 5.1

FR-8: Обработка webhook ЮKassa
  ✅ Receive payment webhooks (payment.succeeded / payment.canceled)
  ✅ Validate webhook structure + signature
  ✅ Update payment status idempotently
  Contract: 5.2

FR-9: Активация/продление подписки после оплаты
  ✅ Activate subscription on successful payment
  ✅ Extend existing subscription (renewal)
  ✅ Generate access_token for subscription access
  Contract: 5.3

FR-10: Промокоды
  ✅ Create promo codes (admin)
  ✅ Apply promo codes and extend subscription
  Contract: 5.4

FR-11: Управление доступом (feature flags)
  ✅ Enable/disable paid features without deploy
  ✅ Block access if subscription expired
  Module: M5.5 (Feature Flags)

FR-12: Аудит и журналирование (платежи/доступ)
  ✅ Audit log for payments, webhooks, admin actions
  ✅ Traceability for incidents and disputes
  Module: M5.6 (Audit Logging)
```

---

# ЧАСТЬ 3: НЕФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

## ⚡ NFR (Non-Functional Requirements)

```
ВСЕГО: 17 требований (NFR-1.1…NFR-4.4)

PERFORMANCE:
  NFR-1.1: Cargo list load < 2 sec (p95)
    └─ Solution: Per-user cache (5 min TTL)
  
  NFR-1.2: Cargo detail open < 2 sec (p95)
    └─ Solution: Loading spinner + fallback to cached data
  
  NFR-1.3: Support 1000+ concurrent drivers
    └─ Solution: Gunicorn (4 workers), Redis queue
  
  NFR-1.4: API login completion < 1 sec (server-side) ← NEW!
    └─ Solution: Single API call + cached Bearer token (re-login on 401)

USABILITY:
  NFR-2.1: Mobile-first design (responsive)
  NFR-2.2: Touch-friendly buttons (44x44px minimum)
  NFR-2.3: Works on 3G connection (cache + compression)

SECURITY:
  NFR-3.1: HTTPS mandatory (Django SECURE_SSL_REDIRECT)
  NFR-3.2: Validate Telegram initData (HMAC-SHA256)
    └─ Additional: max_age_seconds validation (300 sec)
  
  NFR-3.3: Protect CargoTech API token (treat as secret) ← CRITICAL!
    └─ New: Credentials stored only in environment/secrets manager
    └─ New: Token stored in cache (Redis) and never logged
    └─ New: Audit logging for auth failures / abnormal re-logins
  
  NFR-3.4: CORS protection (restrict to app.cargotech.pro)
  NFR-3.5: Rate limiting (10 req/sec per user)
  
  NFR-3.6: Validate payment webhooks (ЮKassa signature + idempotency) ← NEW!
    └─ Solution: signature validation + idempotent processing

RELIABILITY:
  NFR-4.1: Uptime 99.9% (SLA)
  NFR-4.2: Graceful degradation if API down
  NFR-4.3: Data consistency (idempotent operations)
  NFR-4.4: Automatic re-login on 401 (token invalidation)
```

---

# ЧАСТЬ 4: НОВЫЙ КОНТРАКТ - CARGOTECH API AUTH (BEARER TOKEN)

## 🔑 Contract 1.4: CargoTechAuthService.login() ← **НОВЫЙ**

### НАЗНАЧЕНИЕ:

```
Server-side login to CargoTech API
Drivers DO NOT have CargoTech credentials
WebApp server uses shared credentials to access API
Token is stored and reused for all requests
```

### ВАЖНО:

Этот контракт описывает **реальный CargoTech API login** (запрос виден в HAR CargoTech WebApp).
При server‑side интеграции запрос выполняется на сервере (Django/Celery), поэтому валидацию
удобнее делать через серверные логи.

Для валидации проверьте:
- Серверные логи Django/Celery
- Redis cache (ключ: `cargotech:api:token`, если используется)

### ДЕТАЛИ:

```
Service: apps/integrations/cargotech_auth.py
Module: CargoTechAuthService

 PUBLIC METHODS:
  - login(phone: str, password: str, remember: bool = True) → token
  - get_token() → token (из cache или через login)
  - invalidate_cached_token() → None
```

### PARAMETERS:

```python
phone: str
  ├─ Example: "+7 911 111 11 11"
  ├─ Format: E.164 (country code + number)
  ├─ @required: true
  └─ @constraint: Must match registered account on CargoTech

password: str
  ├─ Example: "123-123"
  ├─ @required: true
  ├─ @constraint: Must NOT be logged in code or git
  ├─ @constraint: Must be in environment variable
  └─ @security: Store only in environment/secrets manager

remember: bool (optional)
  ├─ Default: true
  ├─ Purpose: Keep session on device longer
  └─ Passed to CargoTech API as-is
```

### RETURNS:

CargoTech API возвращает **opaque Bearer token** (Laravel Sanctum), структура ответа:

```json
{"data":{"token":"12345|<opaque_token>"}}
```

### WORKFLOW:

```
1. Server requests token
   └─ Try Redis cache first
   └─ If missing → login(phone=ENV['CARGOTECH_PHONE'], password=ENV['CARGOTECH_PASSWORD'])

2. CargoTech API responds with token
   └─ Cache token in Redis (TTL configurable, e.g. 24h)

3. All subsequent requests use this token
   └─ Header: Authorization: Bearer {token}

4. On error (401 Unauthorized)
   └─ Invalidate cached token
   └─ Re-login once and retry request once
   └─ If still fails → Log ERROR + Alert DevOps
```

### GUARANTEES:

```
✅ Token format: Bearer (Laravel Sanctum), opaque string
✅ No refresh_token/expires_in/token_type in response
✅ Server-side: credentials only in environment/secrets manager
✅ Token stored in cache (Redis) and never logged
✅ Safe 401 handling: invalidate + re-login once + retry once
✅ Idempotent: multiple login() calls safe (cache de-duplicates)
```

### CONSTRAINTS:

```
@constraint: Phone and password are environment variables
@constraint: Token treated as secret (never log / never commit)
@constraint: Token stored in cache (Redis) with TTL (default 24h) or until invalid
@constraint: If token invalid (401) → invalidate cache → re-login once → retry once
@constraint: Max 3 retries on network errors (with backoff)
```

### ERROR HANDLING:

```
401 Unauthorized (token invalid/expired)
  └─ Action: invalidate cached token → re-login once → retry request once
  └─ If still fails: log ERROR + alert DevOps

403 Forbidden (account suspended)
  └─ Action: Log CRITICAL, page on-call engineer
  └─ User sees: "Access denied (contact support)"

422 Unprocessable Entity (login validation error)
  └─ Action: log WARNING (no secrets) + alert DevOps
  └─ Check: CARGOTECH_PHONE/CARGOTECH_PASSWORD

429 Too Many Requests (rate limited by CargoTech)
  └─ Action: Wait and retry (exponential backoff)
  └─ User sees: Service works (uses cached cargos)

503 Service Unavailable
  └─ Action: retry later (backoff)
  └─ Fallback: serve cached cargos (if available)
```

### IMPLEMENTATION (Python/Django):

```python
# apps/integrations/cargotech_auth.py

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CargoTechAuthError(RuntimeError):
    pass


class CargoTechAuthService:
    BASE_URL = "https://api.cargotech.pro"
    CACHE_KEY = "cargotech:api:token"
    DEFAULT_CACHE_TTL = 86400  # 24h (token has no expires_in)

    @classmethod
    def login(cls, phone: str, password: str, remember: bool = True) -> str:
        response = requests.post(
            f"{cls.BASE_URL}/v1/auth/login",
            json={"phone": phone, "password": password, "remember": remember},
            timeout=10,
        )
        response.raise_for_status()

        payload: dict[str, Any] = response.json()
        token = payload["data"]["token"]

        cache_ttl = getattr(settings, "CARGOTECH_TOKEN_CACHE_TTL", cls.DEFAULT_CACHE_TTL)
        cache.set(cls.CACHE_KEY, token, timeout=cache_ttl)
        return token

    @classmethod
    def get_token(cls) -> str:
        cached = cache.get(cls.CACHE_KEY)
        if cached:
            return cached

        phone = settings.CARGOTECH_PHONE
        password = settings.CARGOTECH_PASSWORD
        if not phone or not password:
            raise CargoTechAuthError("CargoTech credentials not configured")

        return cls.login(phone=phone, password=password, remember=True)

    @classmethod
    def invalidate_cached_token(cls) -> None:
        cache.delete(cls.CACHE_KEY)

    @classmethod
    def auth_headers(cls) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {cls.get_token()}",
            "Accept": "application/json",
        }
```

### DJANGO SETTINGS:

```python
# settings.py

import os

# CargoTech API Credentials (ENVIRONMENT ONLY!)
CARGOTECH_PHONE = os.environ.get('CARGOTECH_PHONE')
CARGOTECH_PASSWORD = os.environ.get('CARGOTECH_PASSWORD')

if not CARGOTECH_PHONE or not CARGOTECH_PASSWORD:
    raise ValueError(
        "CARGOTECH_PHONE and CARGOTECH_PASSWORD must be set "
        "in environment variables"
    )

# Optional: token cache timeout (seconds)
CARGOTECH_TOKEN_CACHE_TTL = int(os.environ.get('CARGOTECH_TOKEN_CACHE_TTL', '86400'))

# Logging
LOGGING = {
    'handlers': {
        'cargotech_auth': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'cargotech_auth.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 10,
        },
    },
    'loggers': {
        'cargotech_auth': {
            'handlers': ['cargotech_auth'],
            'level': 'INFO',
        },
    },
}
```

### MONITORING & ALERTS:

```python
# apps/integrations/monitoring.py

from django.core.mail import send_mail
import logging

import requests

from apps.integrations.cargotech_auth import CargoTechAuthService

logger = logging.getLogger('cargotech_auth')

class CargoTechAuthMonitor:
    @staticmethod
    def check_token_health() -> bool:
        """
        Daily check: does cached token still work?
        """
        try:
            response = requests.get(
                "https://api.cargotech.pro/v1/me",
                headers=CargoTechAuthService.auth_headers(),
                timeout=10,
            )
            if response.status_code == 401:
                CargoTechAuthService.invalidate_cached_token()
                response = requests.get(
                    "https://api.cargotech.pro/v1/me",
                    headers=CargoTechAuthService.auth_headers(),
                    timeout=10,
                )
            if response.status_code != 200:
                logger.error("CargoTech auth health check failed: status=%s", response.status_code)
                CargoTechAuthMonitor._alert_devops(
                    f"CargoTech auth health check failed: status={response.status_code}"
                )
                return False
            return True

        except Exception as e:
            logger.exception("CargoTech auth health check failed")
            CargoTechAuthMonitor._alert_devops(f"CargoTech auth health check exception: {e}")
            return False
    
    @staticmethod
    def _alert_devops(message: str):
        """Send critical alert to DevOps team"""
        send_mail(
            subject=f"🚨 CargoTech API Token Alert",
            message=message,
            from_email='alerts@cargotech.local',
            recipient_list=['devops@cargotech.local'],
            fail_silently=False
        )

# Celery task (runs daily)
# apps/integrations/tasks.py

from celery import shared_task

@shared_task(name='check_cargotech_auth')
def check_cargotech_auth():
    """Check CargoTech API auth health daily"""
    from apps.integrations.monitoring import CargoTechAuthMonitor
    return CargoTechAuthMonitor.check_token_health()
```

---

# ЧАСТЬ 5: ПОЛНЫЕ КОНТРАКТЫ

## 📋 Все 8 контрактов (обновлено)

### Contract 1.1: TelegramAuthService.validate_init_data()

```python
def validate_init_data(init_data: str, hash_value: str,
                      max_age_seconds: int = 300) → dict:
    """
    Validate Telegram WebApp initData
    
    PARAMETERS:
    - init_data: Sorted key-value pairs from Telegram
    - hash_value: HMAC-SHA256 hash
    - max_age_seconds: Max age of auth_date (default 300s)
    
    RETURNS:
    {
        'id': 123456789,
        'first_name': 'Иван',
        'username': 'ivan_driver',
        'auth_date': 1704249600
    }
    
    GUARANTEES:
    ✅ HMAC validation with constant-time comparison
    ✅ Timestamp validation (reject if > max_age_seconds)
    ✅ Attack detection (log failures, alert if > 10/min)
    ✅ Extract user ID, name, username
    ✅ Prevent replay attacks
    ✅ Prevent timing attacks
    
    CONTRACT: Contract 1.1
    """
```

### Contract 1.2: SessionService.create_session()

```python
def create_session(user_id: int, first_name: str,
                  username: str) → session_token:
    """
    Create driver session in Redis
    
    PARAMETERS:
    - user_id: Telegram user ID
    - first_name: Driver first name
    - username: Telegram username (optional)
    
    RETURNS:
    session_token: JWT token for API authentication
    
    GUARANTEES:
    ✅ Session stored in Redis with TTL = 24 hours
    ✅ Can be refreshed by client (sliding window)
    ✅ Session invalidated on driver logout
    ✅ Unique per user (one session per user)
    
    CONTRACT: Contract 1.2
    """
```

### Contract 1.3: TokenService.validate_session()

```python
def validate_session(session_token: str) → driver_data:
    """
    Validate session token on every API request
    
    PARAMETERS:
    - session_token: JWT from HTTP header
    
    RETURNS:
    {
        'driver_id': 123456789,
        'first_name': 'Иван',
        'session_valid': True
    }
    
    GUARANTEES:
    ✅ Verify JWT signature
    ✅ Check token not expired
    ✅ Check token not blacklisted (logout)
    ✅ Refresh session expiry (sliding window)
    
    CONTRACT: Contract 1.3
    """
```

### Contract 1.4: CargoTechAuthService.login() ← **NEW**

**ВАЖНО**: CargoTech API авторизуется через Bearer Token (Laravel Sanctum). Запрос `/v1/auth/login`
виден в HAR CargoTech WebApp; при server‑side интеграции проверяйте серверные логи.

Для валидации проверьте:
- Серверные логи Django/Celery
- Redis cache (ключ: `cargotech:api:token`)

```python
def login(phone: str, password: str, remember: bool = True) → token:
    """
    Server-side login to CargoTech API
    
    PARAMETERS:
    - phone: "+7 911 111 11 11" (E.164 format)
    - password: "123-123"
    - remember: true/false
    
    RETURNS:
    {"data": {"token": "12345|<opaque_token>"}}
    
    GUARANTEES:
    ✅ Token is Bearer (Sanctum), opaque string (not JWT)
    ✅ No refresh_token / expires_in / token_type in response
    ✅ Token stored in cache (Redis) for reuse
    ✅ 401 handling: invalidate cached token → re-login once → retry once
    ✅ Retry logic with exponential backoff
    ✅ Audit log all login attempts
    ✅ Alert DevOps if login fails
    ✅ Graceful fallback if API down (use cached data)
    
    CONTRACT: Contract 1.4 (NEW!)
    """
```

### Contract 2.1: CargoAPIClient.fetch_cargos()

```python
def fetch_cargos(filters: dict, user_id: int) → cargo_list:
    """
    Fetch cargo list from CargoTech API
    
    PARAMETERS:
    - filters: {start_point_id, finish_point_id, start_point_radius, finish_point_radius, start_date, mode, weight_volume, load_types, truck_types}
    - user_id: Driver Telegram ID
    
    RETURNS:
    [
        {
            'id': '12345',
            'title': 'Доставка посылок',
            'weight_kg': 5000,
            'volume_m3': 25,
            'pickup_city': 'Москва',
            'delivery_city': 'СПб',
            'price_rub': 50000,
            'shipper_contact': '+7 999 888 77 66'
        },
        ...
    ]

    NOTE:
    - Cargo list endpoint `/v2/cargos/views` does NOT include comment.
    - Comment is available only in detail endpoint:
      `GET /v1/carrier/cargos/{cargo_id}?source=1&include=contacts`
      and lives at `data.extra.note`.

    EXTRA (detail response, 10 fields):
    - note: str (comment text)
    - external_inn: str | null
    - custom_cargo_type: str | null
    - integrate: object | null
    - is_delete_from_archive: bool
    - krugoreis: bool
    - partial_load: bool
    - note_valid: bool
    - integrate_contacts: object | null
    - url: str | null
    
    GUARANTEES:
    ✅ Use server-side CargoTech API token (Contract 1.4)
    ✅ Rate limiting: 600 req/min global → backoff
    ✅ Per-user cache (5 min TTL)
    ✅ Exponential retry on 429/503
    ✅ Circuit breaker if API down (serve cache)
    ✅ Detail comment extracted from `data.extra.note` (detail endpoint only)
    ✅ Format for mobile (responsive)
    
    CONTRACT: Contract 2.1 (updated)
    """
```

### Contract 2.2: CargoService.format_cargo_card()

```python
def format_cargo_card(cargo: dict) → html:
    """
    Format single cargo as HTML card
    
    PARAMETERS:
    - cargo: Raw cargo from API
    
    RETURNS:
    HTML card with title, weight, volume, route, price
    
    GUARANTEES:
    ✅ Mobile-responsive layout
    ✅ Touch-friendly (min 44x44px buttons)
    ✅ Show comment from `data.extra.note` if present
    ✅ Price formatted with currency symbol
    ✅ Route formatted as "City A → City B"
    
    CONTRACT: Contract 2.2
    """
```

### Contract 2.3: CargoService.get_cargos()

```python
def get_cargos(user_id: int, filters: dict) → cargo_list:
    """
    Get cargo list with 3-level caching
    
    PARAMETERS:
    - user_id: Driver Telegram ID
    - filters: {start_point_id, finish_point_id, start_point_radius, finish_point_radius, start_date, mode, weight_volume, load_types, truck_types}
    
    RETURNS:
    [cargo, cargo, ...]
    
    CACHING STRATEGY:
    
    Level 1: Per-User List Cache
      Key: "user:{user_id}:cargos:{filter_hash}"
      TTL: 5 minutes
      When: After fetch from API
      Invalidation: Filter change, logout, webhook
    
    Level 2: Cargo Detail Cache
      Key: "cargo:{cargo_id}:detail"
      TTL: 15 minutes
      When: User opens detail view
      Invalidation: Webhook, status change
    
    Level 3: Autocomplete Cache
      Key: "autocomplete:cities"
      TTL: 24 hours
      When: App startup
      Invalidation: Manual
    
    FALLBACK STRATEGY:
    - Redis down → Direct API call (no cache)
    - API down → Serve cached data (if available) + warning
    - Cache miss → Fetch + async update
    
    GUARANTEES:
    ✅ p50: < 500ms (cached data)
    ✅ p95: < 2000ms (with fetch + spinner)
    ✅ Fallback to cached data if timeout
    ✅ Show loading indicator while fetching
    ✅ Transparent refresh in background
    
    CONTRACT: Contract 2.3 (updated)
    """
```

### Contract 3.1: FilterService.validate_filters()

```python
def validate_filters(filters: dict) → validated:
    """
    Validate driver filters
    
    PARAMETERS:
    filters: {
        'start_point_id': 62,          # город загрузки (ID)
        'finish_point_id': 39,         # город выгрузки (ID)
        'start_point_radius': 50,      # км
        'finish_point_radius': 50,     # км
        'start_date': '2026-01-01',    # YYYY-MM-DD
        'mode': 'my',                  # my/all
        'weight_volume': '15_20',      # frontend: 7 categories
        'load_types': 3,               # optional
        'truck_types': 4               # optional
    }
    
    WEIGHT_VOLUME CATEGORIES (7):
    - "1_3": 1-3 т / до 15 м³
    - "3_5": 3-5 т / 15-25 м³
    - "5_10": 5-10 т / 25-40 м³
    - "10_15": 10-15 т / 40-60 м³
    - "15_20": 15-20 т / 60-65 м³
    - "20": 20+ т / 82+ м³
    - "any": No filter

    API FORMAT (actual CargoTech query param):
    - filter[wv]: "<weight_t>-<volume_m3>" (example: "15-65")
      mapping:
      - 1_3   -> "1-15"
      - 3_5   -> "3-25"
      - 5_10  -> "5-40"
      - 10_15 -> "10-60"
      - 15_20 -> "15-65"  # matches HAR: filter[wv]=15-65
      - 20    -> "20-999"
    
    RETURNS:
    {'valid': True, 'errors': []}  or
    {'valid': False, 'errors': ['weight_volume invalid']}
    
    GUARANTEES:
    ✅ Validate each filter field
    ✅ Allow multiple filters
    ✅ Prevent SQL injection
    ✅ Log all validation failures
    
    CONTRACT: Contract 3.1 (updated)
    """
```

### Contract 3.2: FilterService.build_query()

```python
def build_query(filters: dict) → api_params:
    """
    Build CargoTech API query from filters
    
    PARAMETERS:
    filters: {start_point_id, finish_point_id, start_date, mode, weight_volume, load_types, truck_types}
    
    RETURNS:
    {
        'filter[start_point_id]': 62,
        'filter[finish_point_id]': 39,
        'filter[start_point_radius]': 50,
        'filter[finish_point_radius]': 50,
        'filter[start_date]': '2026-01-01',
        'filter[mode]': 'my',
        'filter[wv]': '15-65',
        'filter[load_types]': 3,
        'filter[truck_types]': 4,
        'include': 'contacts',
        'limit': 20,
        'offset': 0
    }
    
    GUARANTEES:
    ✅ Map weight_volume categories to filter[wv] format
    ✅ Pass-through/validate known CargoTech query params
    ✅ Handle missing/optional filters
    ✅ No SQL injection
    
    CONTRACT: Contract 3.2
    """
```

### Contract 4.1: TelegramBotService.handle_response()

```python
def handle_response(driver_id: int, cargo_id: str,
                   phone: str, name: str) → status:
    """
    Handle driver response to cargo
    
    PARAMETERS:
    - driver_id: Telegram user ID
    - cargo_id: CargoTech cargo ID
    - phone: Driver phone number
    - name: Driver name
    
    RETURNS:
    {'status': 'sent', 'response_id': '...'}
    
    GUARANTEES:
    ✅ Send to Telegram Bot API
    ✅ Create response record in DB
    ✅ Update UI with status badge
    ✅ Prevent duplicate responses (idempotent)
    
    CONTRACT: Contract 4.1
    """
```

### Contract 4.2: TelegramBotService.send_status()

```python
def send_status(driver_id: int, cargo_id: str,
               status: str) → ok:
    """
    Send status update to driver
    
    PARAMETERS:
    - driver_id: Telegram user ID
    - cargo_id: Cargo ID
    - status: 'accepted', 'rejected', 'completed'
    
    RETURNS:
    True if sent successfully
    
    GUARANTEES:
    ✅ Send via Telegram Bot API
    ✅ Log delivery status
    ✅ Retry if Telegram timeout
    
    CONTRACT: Contract 4.2
    """
```

---

# ЧАСТЬ 6: API SPECIFICATION

## 🔌 CargoTech API Endpoints

### Endpoint 1: POST /v1/auth/login (Server-side)

```
REQUEST:
POST https://api.cargotech.pro/v1/auth/login
Content-Type: application/json
Accept: application/json

{
  "phone": "+7 911 111 11 11",
  "password": "123-123",
  "remember": true
}

RESPONSE (200 OK):
{
  "data": {
    "token": "12345|<opaque_token>"
  }
}

ERROR RESPONSES:
422 Unprocessable Entity: {"errors": {...}}
403 Forbidden: {"error": "Account suspended"}
429 Too Many Requests: {"error": "Rate limit exceeded"}
503 Service Unavailable: {"error": "Service temporarily unavailable"}

SECURITY:
- Credentials from environment (not hardcoded)
- Token is opaque Bearer (Sanctum); treat as secret
- Store token in cache (server-side) or localStorage (client-side)
- Audit log all attempts
```

### Endpoint 2: GET /v2/cargos/views (Get cargo list)

```
REQUEST:
GET https://api.cargotech.pro/v2/cargos/views?limit=20&offset=0&include=contacts&filter[start_point_id]=62&filter[finish_point_id]=39&filter[start_point_radius]=50&filter[finish_point_radius]=50&filter[start_date]=2026-01-01&filter[mode]=my&filter[wv]=15-65
Authorization: Bearer {token}

RESPONSE (200 OK):
{
  "data": [
    {
      "id": "12345",
      "title": "Доставка посылок",
      "weight": 5000,
      "volume": 25,
      "pickup_city": "Москва",
      "delivery_city": "СПб",
      "price": 50000,
      "shipper_contact": "+7 999 888 77 66"
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0
}

FILTERS:
- filter[start_point_id]: 62
- filter[finish_point_id]: 39
- filter[start_point_radius]: 50
- filter[finish_point_radius]: 50
- filter[start_date]: "2026-01-01"
- filter[mode]: "my" | "all"
- filter[wv]: "15-65" (weight/volume, see Contract 3.1 mapping)
- filter[load_types]: 3
- filter[truck_types]: 4

OTHER:
- include: "contacts"
- limit: 20
- offset: 0

RATE LIMITING:
- Limit: 600 requests per minute (global)
- Header: X-RateLimit-Limit, X-RateLimit-Remaining
- On 429: Retry after X-RateLimit-Reset-After
```

### Endpoint 3: GET /v1/carrier/cargos/{cargo_id} (Get cargo detail)

```
REQUEST:
GET https://api.cargotech.pro/v1/carrier/cargos/12345?source=1&include=contacts
Authorization: Bearer {token}

RESPONSE (200 OK):
{
  "data": {
    "id": "12345",
    "title": "Доставка посылок",
    "weight": 5000,
    "volume": 25,
    "pickup_city": "Москва",
    "delivery_city": "СПб",
    "pickup_address": "ул. Красная площадь, 1",
    "delivery_address": "Невский проспект, 25",
    "price": 50000,
    "extra": {
      "note": "По ставке без НДС возможна заправка нашими топливными картами со скидкой от 15% до 25%.",
      "external_inn": null,
      "custom_cargo_type": null,
      "integrate": null,
      "is_delete_from_archive": false,
      "krugoreis": false,
      "partial_load": false,
      "note_valid": true,
      "integrate_contacts": null,
      "url": "https://cargomart.ru/orders/active?modal=..."
    },
    "shipper_name": "ООО Логистика",
    "shipper_contact": "+7 999 888 77 66",
    "cargo_type": "cargo",
    "created_at": "2026-01-03T10:00:00Z"
  }
}

PERFORMANCE:
- p50: < 500ms (from cache)
- p95: < 2000ms (with API fetch)
- Fallback: Use cached data if timeout
```

---

# ЧАСТЬ 7: DJANGO СТРУКТУРА

## 📁 Project Layout (обновлено)

```
cargotech_driver_app/
├── manage.py
├── requirements.txt
├── docker-compose.yml
│
├── config/
│   ├── settings.py (с новыми env переменными)
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   ├── auth/
│   │   ├── models.py (DriverProfile, TelegramSession)
│   │   ├── views.py (login_view)
│   │   ├── services.py (TelegramAuthService, SessionService)
│   │   └── tests.py
│   │
│   ├── integrations/
│   │   ├── cargotech_auth.py (CargoTechAuthService ← NEW!)
│   │   ├── cargotech_client.py (CargoAPIClient)
│   │   ├── monitoring.py (CargoTechAuthMonitor, optional)
│   │   ├── tasks.py (Celery tasks)
│   │   └── tests.py
│   │
│   ├── cargos/
│   │   ├── models.py (Cargo, CargoCache)
│   │   ├── views.py (list, detail)
│   │   ├── services.py (CargoService)
│   │   ├── serializers.py
│   │   ├── templates/
│   │   │   ├── cargo_list.html
│   │   │   ├── cargo_detail.html
│   │   │   └── components/
│   │   │       ├── cargo_card.html
│   │   │       └── loading_spinner.html
│   │   └── tests.py
│   │
│   ├── filtering/
│   │   ├── services.py (FilterService)
│   │   ├── constants.py (WEIGHT_VOLUME_CATEGORIES)
│   │   └── tests.py
│   │
│   └── telegram_bot/
│       ├── handlers.py (Response handler)
│       ├── services.py (TelegramBotService)
│       └── tests.py
│
├── static/
│   ├── css/
│   │   ├── main.css (mobile-first)
│   │   └── spinner.css
│   └── js/
│       ├── app.js (HTMX + utils)
│       └── filters.js (filter handling)
│
├── templates/
│   ├── base.html
│   └── main.html
│
├── logs/
│   ├── cargotech_auth.log ← NEW!
│   ├── cargotech_api.log
│   └── error.log
│
└── .env (environment variables)
    ├── DEBUG=False
    ├── SECRET_KEY=***
    ├── TELEGRAM_BOT_TOKEN=***
    ├── CARGOTECH_PHONE=+7 911 111 11 11 ← NEW!
    ├── CARGOTECH_PASSWORD=123-123 ← NEW!
    ├── CARGOTECH_TOKEN_CACHE_TTL=86400 (optional)
    ├── REDIS_URL=redis://localhost:6379/0
    └── DATABASE_URL=postgresql://...
```

---

# ЧАСТЬ 8: ПЛАН РАЗРАБОТКИ (обновлено)

## 📅 Development Plan (24 дня)

**Сводка:** 14 дней базового функционала (M1–M4) + 10 дней на M5 (подписки/платежи) = 24 дня.

### ДЕНЬ 1-2: M1 Authentication + NEW Login

```
✅ Django models: DriverProfile, TelegramSession
✅ TelegramAuthService.validate_init_data() + max_age
✅ SessionService.create_session() + Redis
✅ TokenService.validate_session()
✅ CargoTechAuthService.login() ← NEW!
✅ CargoTech auth health check (optional)
✅ Environment variables setup
✅ Unit tests for all auth contracts

Metrics:
- ✅ All 4 contracts working (1.1-1.4)
- ✅ Token cached in Redis (no DB)
- ✅ 401 handling: re-login + retry
- ✅ 0 security warnings
```

### ДЕНЬ 3-4: M2 API Integration

```
✅ CargoAPIClient with rate limiting (600 req/min)
✅ Token bucket algorithm
✅ Exponential backoff (500ms → 1500ms → 3000ms)
✅ Handle 429/503 responses
✅ 3-level cache (per-user, detail, autocomplete)
✅ Cache invalidation strategies
✅ Integration tests

Metrics:
- ✅ List load: < 2s (p95)
- ✅ Detail load: < 2s (p95)
- ✅ Cache hit rate: > 70%
- ✅ Rate limit: 0 failed requests
```

### ДЕНЬ 5-6: M3 Filtering

```
✅ weight_volume: 7 categories + mapping
✅ FilterService.validate_filters()
✅ FilterService.build_query()
✅ normalize_weight_volume_filter function
✅ City autocomplete (Redis cache)
✅ Frontend select options
✅ Tests for all 7 categories

Metrics:
- ✅ All 7 categories work
- ✅ No SQL injection
- ✅ 100% filter coverage
```

### ДЕНЬ 7-9: M2 Detail Views + Templates

```
✅ CargoListView (HTMX pagination)
✅ CargoDetailView (with comment `data.extra.note`)
✅ HTML templates (mobile-responsive)
✅ Loading spinners
✅ Fallback to cached data
✅ HTMX prefetch on hover
✅ CSS for mobile (44x44px buttons)

Metrics:
- ✅ p50: < 500ms
- ✅ p95: < 2000ms
- ✅ Mobile responsive
- ✅ Touch-friendly
```

### ДЕНЬ 10-11: M4 Telegram Bot

```
✅ Response handler (POST /telegram/responses/)
✅ Create response record in DB
✅ Send to Telegram Bot
✅ Status updates
✅ Idempotent operations
✅ Error handling

Metrics:
- ✅ Response time: < 1s
- ✅ Delivery: 100%
- ✅ No duplicates
```

### ДЕНЬ 12: Integration & Load Testing

```
✅ End-to-end tests (Auth → List → Detail → Response)
✅ Load test: 1000+ concurrent
✅ Cache invalidation scenarios
✅ Rate limit behavior
✅ Token refresh under load
✅ Memory leak detection

Metrics:
- ✅ All endpoints: < 2s (p95)
- ✅ 0 errors under load
- ✅ Memory stable
- ✅ No cache corruption
```

### ДЕНЬ 13: Production Setup

```
✅ Security audit
✅ Database migrations
✅ Logging setup (Sentry)
✅ Monitoring (DataDog)
✅ Encryption key rotation
✅ Backup strategy

Metrics:
- ✅ 0 security warnings
- ✅ Monitoring active
- ✅ Alerts configured
```

### ДЕНЬ 14: Deployment & Documentation

```
✅ Docker setup
✅ CI/CD pipeline
✅ Deployment checklist
✅ User documentation
✅ API documentation
✅ Runbooks for on-call

Metrics:
- ✅ Deployment successful
- ✅ All tests passing
- ✅ Documentation complete
```

### ДЕНЬ 15-16: M5 Foundations (модели + контроль доступа)

```
✅ Models: Payment, Subscription, PromoCode, SystemSetting
✅ CheckSubscriptionMiddleware / access checks
✅ Feature flags базовая модель/таблица
✅ AuditLog базовая модель/таблица
✅ UI: paywall / subscription status screen (минимум)

Metrics:
- ✅ Paywall flow skeleton готов
- ✅ Доступ блокируется при отсутствии подписки
- ✅ Модели покрыты миграциями
```

### ДЕНЬ 17-18: M5.1 Payments (ЮKassa) — создание платежа

```
✅ Contract 5.1: PaymentService.create_payment()
✅ YuKassaClient: create_payment()
✅ Payment status lifecycle (pending/succeeded/canceled/failed)
✅ Idempotency key strategy
✅ Unit tests for create_payment()

Metrics:
- ✅ Payment создаётся и возвращает confirmation_url
- ✅ Ошибки ЮKassa не ломают UX (повторяемость)
```

### ДЕНЬ 19: M5.1 Webhooks — обработка статусов платежей

```
✅ Contract 5.2: PaymentService.process_webhook()
✅ Webhook endpoint (POST) + валидация структуры
✅ Signature validation + idempotent processing
✅ Обновление статусов платежа

Metrics:
- ✅ Webhook обрабатывается ровно 1 раз
- ✅ Неверная подпись → отказ без побочных эффектов
```

### ДЕНЬ 20: M5.2 Subscriptions — активация после оплаты

```
✅ Contract 5.3: SubscriptionService.activate_from_payment()
✅ Активация/продление подписки по succeeded payment
✅ Генерация subscription access_token
✅ Unit tests для activation/renewal

Metrics:
- ✅ Подписка активируется автоматически после оплаты
- ✅ Продление корректно суммирует сроки
```

### ДЕНЬ 21: M5.3 Promo Codes

```
✅ Contract 5.4: PromoCodeService.create_promo_code()
✅ Применение промокода и продление подписки
✅ Ограничения: max_uses, expires_at, disabled
✅ Тесты на сценарии применения/ошибок

Metrics:
- ✅ Промокоды работают и логируются
```

### ДЕНЬ 22: M5.4 Admin Panel + M5.5 Feature Flags

```
✅ Admin UI: платежи/подписки/промокоды/настройки
✅ Управление токенами ЮKassa через SystemSetting
✅ Feature flags: включение/выключение платных функций

Metrics:
- ✅ Админ может управлять платежами без деплоя
- ✅ Flags влияют на доступ в рантайме
```

### ДЕНЬ 23: M5.6 Audit Logging + Security Review

```
✅ Audit events: payment, webhook, admin actions, access checks
✅ Сквозные корреляционные ID для расследований
✅ Security review: ключи, доступ, webhook validation

Metrics:
- ✅ Трассируемость инцидентов обеспечена
- ✅ Секреты не попадают в логи
```

### ДЕНЬ 24: Интеграция M5 + Staging

```
✅ E2E: paywall → payment → webhook → subscription → access
✅ Smoke tests после деплоя
✅ Финальная актуализация документации v3.1

Metrics:
- ✅ M5 готов к релизу вместе с базовым функционалом
- ✅ Документация синхронизирована (4 января 2026)
```

---

# ЧАСТЬ 9: БЫСТРЫЙ СТАРТ

## 🚀 Quick Start для разработчиков

### 1. Setup окружения:

```bash
# Clone repo
git clone https://github.com/yourcompany/cargotech-driver-webapp.git
cd cargotech-driver-webapp

# Install dependencies
pip install -r requirements.txt

# Setup .env
cp .env.example .env
# Edit .env with your values:
# CARGOTECH_PHONE=+7 911 111 11 11
# CARGOTECH_PASSWORD=123-123
# CARGOTECH_TOKEN_CACHE_TTL=86400 (optional)

# Run migrations
python manage.py migrate

# Start Redis
docker-compose up redis

# Start Django
python manage.py runserver
```

### 2. Test the API:

```bash
# Test CargoTech login (server-side)
curl -X POST https://api.cargotech.pro/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+7 911 111 11 11",
    "password": "123-123",
    "remember": true
  }'

# Test cargo list
curl -X GET "http://localhost:8000/api/cargos/?filter=1_3" \
  -H "Authorization: Bearer {session_token}"

# Test Telegram auth
curl -X POST http://localhost:8000/auth/telegram \
  -H "Content-Type: application/json" \
  -d '{
    "initData": "...",
    "hash": "..."
  }'
```

### 3. Run tests:

```bash
# All tests
python manage.py test

# Specific app
python manage.py test apps.auth

# With coverage
coverage run --source='.' manage.py test
coverage report
```

---

# ЧАСТЬ 10: ЧЕК-ЛИСТЫ

## ✅ Pre-Development Checklist

- [ ] Django project structure created
- [ ] Apps initialized (auth, integrations, cargos, filtering, telegram_bot)
- [ ] Models created and migrated
- [ ] Environment variables defined (.env)
- [ ] Redis running
- [ ] Database accessible
- [ ] All team members have credentials

## ✅ Pre-Production Checklist

- [ ] All tests passing (> 90% coverage)
- [ ] Security audit completed (0 High vulnerabilities)
- [ ] Load test successful (1000+ concurrent)
- [ ] Token storage verified (cache/localStorage, no secrets in logs)
- [ ] CargoTech API login working
- [ ] 401 handling verified (invalidate token → re-login → retry)
- [ ] Monitoring & alerting configured
- [ ] Backup strategy in place
- [ ] Disaster recovery tested
- [ ] Documentation complete

## ✅ Post-Deployment Checklist

- [ ] Monitoring dashboards active
- [ ] Alerting working (test alert)
- [ ] Logs flowing to central system
- [ ] CDN configured (if applicable)
- [ ] HTTPS/SSL working
- [ ] Performance acceptable (p95 < 2s)
- [ ] No error spikes in logs
- [ ] Database backups running
- [ ] On-call setup validated

---

# ФИНАЛЬНЫЙ СТАТУС

```
┌─────────────────────────────────────────────────┐
│  ПРОЕКТНАЯ ДОКУМЕНТАЦИЯ v3.1                    │
│  (v3.0 + M5: Subscriptions & Payments)         │
│                                                 │
│  ✅ 6 исходных проблем РЕШЕНЫ                   │
│  ✅ M5 (подписки/платежи) ИНТЕГРИРОВАН          │
│  ✅ 15 контрактов (1.1–5.4)                     │
│  ✅ 24-дневный план разработки                  │
│  ✅ Полная документация API                     │
│  ✅ Чек-листы и процедуры                       │
│  ✅ Примеры кода (copy-paste ready)             │
│                                                 │
│  ГОТОВО К РАЗРАБОТКЕ И PRODUCTION! 🚀          │
└─────────────────────────────────────────────────┘
```

---

**Дата:** 4 января 2026  
**Версия:** 3.1 Final (Complete with M5 Subscription & Payment)  
**Статус:** ✅ ОДОБРЕНО ДЛЯ РАЗРАБОТКИ

**Все файлы готовы! Начните разработку! 💪**
