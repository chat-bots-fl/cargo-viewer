# 🎯 КРАТКИЙ СПРАВОЧНИК v3.2

**Дата:** 8 января 2026  
**Версия:** 3.2.1 (v3.2 + Auth Verification Patch)  
**Размер:** 2 страницы (quick reference)

---

## 🆕 ЧТО ИЗМЕНИЛОСЬ В v3.2 (HAR‑validated)

### 1. **Contract 3.1: `filter[wv]` — произвольный формат**

CargoTech API принимает **произвольные** значения `filter[wv]` в формате `{вес}-{объем}` и поддерживает десятичные:

```
filter[wv]=1.5-9
filter[wv]=7.5-45
filter[wv]=15-65
filter[wv]=20-83
```

Backend должен валидировать формат (пример): `^\d+(\.\d+)?-\d+(\.\d+)?$`.

### 2. **Contract 2.1: обязательные параметры списка грузов**

В production запросах используются в 100% случаев:
- `filter[mode]` ("my" | "all")
- `filter[user_id]` (обычно `0`)
- `filter[start_point_type]` (обязателен при `filter[start_point_id]`)
- `filter[finish_point_type]` (обязателен при `filter[finish_point_id]`)

### 3. **NEW Contract 2.4: справочник городов (autocomplete)**

Endpoint: `GET /v1/dictionaries/points?filter[name]={query}` (используется для автокомплита городов).

### 4. **Authorization verified (v3.2.1)**

- ✅ Bearer Token работает (HTTP 200)
- ❌ Cookie auth не поддерживается (CORS blocked)
- Token storage (frontend): `localStorage.accessToken` (format `{id}|{hash}`, len 54)

---

## ✅ Остаётся актуальным (из v3.1)

### 1. **Server-Side API Login** ✨

```
ПРОБЛЕМА:  Водители не имеют доступа к CargoTech API
РЕШЕНИЕ:   Сервер логинится один раз → получает token → используется всем

НОВЫЙ CONTRACT:
Contract 1.4: CargoTechAuthService.login()
├─ phone: "+7 911 111 11 11" (из .env)
├─ password: "123-123" (из .env)
├─ returns: {data: {token}} (Bearer, Sanctum)
├─ storage: Redis cache (server-side) / localStorage.accessToken (client)
└─ 401: invalidate token → re-login → retry once
```

### 2. **Новая архитектура (P5)**

```
P5: MANAGE_API_CREDENTIALS (новый процесс)
├─ Server starts → login to CargoTech
├─ Get token (Bearer, Sanctum)
├─ Cache token in Redis (TTL configurable, e.g. 24h)
├─ All requests use this token
└─ On 401 → invalidate cache → re-login → retry once

Flow:
Django startup
    ↓
CargoTechAuthService.login(phone, password)
    ↓
Get token from API
    ↓
Cache token in Redis (TTL configurable, e.g. 24h)
    ↓
Use token for all requests
    ↓
On 401 → invalidate cache → re-login → retry once
```

### 3. **M5: Подписки и платежи (ЮKassa)** ⭐

```
Добавлено:
├─ Paywall + проверка подписки перед доступом
├─ ЮKassa платежи + webhook обработка
├─ Подписки (активация/продление) + access_token
├─ Промокоды
└─ Admin Panel + Feature Flags + Audit Logging

Новые контракты:
Contract 5.1: PaymentService.create_payment()
Contract 5.2: PaymentService.process_webhook()
Contract 5.3: SubscriptionService.activate_from_payment()
Contract 5.4: PromoCodeService.create_promo_code()

Документы: M5_SUBSCRIPTION_PAYMENT_SUMMARY.md / M5_SUBSCRIPTION_PAYMENT_FULL.md
```

### 4. **Storage (CargoTech token)**

- Token не требует таблиц/моделей в БД — хранится в cache (Redis).
- Рекомендуемый ключ: `cargotech:api:token`

### 5. **Новые env переменные**

```bash
.env:
├─ CARGOTECH_PHONE=+7 911 111 11 11        ← NEW!
├─ CARGOTECH_PASSWORD=123-123              ← NEW!
├─ CARGOTECH_TOKEN_CACHE_TTL=86400         ← optional
└─ Остальные как было...
```

### 5.1 **TTL кэша (по умолчанию)**

- Cargo list cache: 5 минут (300 сек)
- Cargo detail cache: 15 минут (900 сек)
- Cities autocomplete cache: 24 часа (86400 сек)
- CargoTech API token cache: 24 часа (86400 сек, configurable)

### 6. **Новые зависимости**

```
django-redis>=5.4.0   # For token caching
```

---

## 📋 ВСЕ 16 КОНТРАКТОВ

```
M1: AUTHENTICATION & SESSION (4 контракта)
├─ 1.1: TelegramAuthService.validate_init_data()
├─ 1.2: SessionService.create_session()
├─ 1.3: TokenService.validate_session()
└─ 1.4: CargoTechAuthService.login() ← NEW!

M2: CARGO DATA (4 контракта)
├─ 2.1: CargoAPIClient.fetch_cargos()
├─ 2.2: CargoService.format_cargo_card()
├─ 2.3: CargoService.get_cargos()
└─ 2.4: DictionaryService.search_cities() ← NEW!

M3: FILTERING (2 контракта)
├─ 3.1: FilterService.validate_filters()
└─ 3.2: FilterService.build_query()

M4: TELEGRAM BOT (2 контракта)
├─ 4.1: TelegramBotService.handle_response()
└─ 4.2: TelegramBotService.send_status()

M5: SUBSCRIPTIONS & PAYMENTS (4 контракта)
├─ 5.1: PaymentService.create_payment()
├─ 5.2: PaymentService.process_webhook()
├─ 5.3: SubscriptionService.activate_from_payment()
└─ 5.4: PromoCodeService.create_promo_code()

ВСЕГО: 16 контрактов (1.1–5.4 + 2.4)
```

---

## 🔑 Key Changes v3.1 → v3.2

### ДО v3.1:

```
Frontend (Driver):
├─ Login with Telegram ✓
├─ Browse cargos ✓
├─ Filter ✓
└─ Respond ✓

Backend (Server):
├─ Validate Telegram ✓
├─ Call CargoTech API ? ← No auth method defined
├─ Cache results ✓
└─ Handle responses ✓

PROBLEM: Как сервер логинится на CargoTech API + как ограничить доступ подпиской?
```

### ПОСЛЕ v3.1:

```
Frontend (Driver):
├─ Login with Telegram ✓
├─ Browse cargos ✓
├─ Filter ✓
└─ Respond ✓

Backend (Server):
├─ Validate Telegram ✓
├─ Server-side login to CargoTech ✓ ← NEW!
├─ Call CargoTech API with token ✓ ← NEW!
├─ Cache results ✓
└─ Handle responses ✓

SOLUTION: Contract 1.4 + Bearer token caching
PLUS: M5 paywall + payments + subscriptions
```

---

## 🔄 Login Flow (Updated)

### СТАРЫЙ FLOW (v2.0):

```
1. Driver opens WebApp
2. Telegram → initData
3. Server validates initData
4. Server creates session (Redis)
5. [PROBLEM: How to access CargoTech API?]
```

### НОВЫЙ FLOW (v3.2):

```
1. Server startup (once per deployment)
   └─ CargoTechAuthService.login()
   └─ Get token from CargoTech (Bearer, Sanctum)
   └─ Cache token in Redis (TTL configurable, e.g. 24h)

2. Driver opens WebApp
   └─ Telegram → initData
   └─ Server validates initData
   └─ Server creates session (Redis)

3. Driver requests cargo list
   └─ Server uses stored token
   └─ Call CargoTech API
   └─ Return data to driver

4. If 401 from CargoTech
   └─ Invalidate cached token
   └─ Re-login and retry once
```

---

## 💾 Database Changes

CargoTech auth: без новых таблиц (token хранится в Redis cache).

---

## 🔐 Security Improvements

### Что защищено в v3.2:

```
✅ API credentials (phone + password)
   └─ Storage: Django environment variables only
   └─ Never in code or git

✅ CargoTech token
   └─ Storage: Redis cache (server-side) / localStorage.accessToken (client-side)
   └─ Transmission: HTTPS only
   └─ Logging: token value never logged

✅ Token invalidation handling
   └─ On 401: invalidate cached token → re-login → retry once

✅ ЮKassa secret keys
   └─ Storage: Encrypted in database (SystemSetting)
   └─ Access: Admin-only settings UI

✅ ЮKassa webhooks
   └─ Signature validation + idempotency

✅ Driver data
   └─ Session token via Telegram validation
   └─ Per-driver cargo list cache
   └─ No credential leakage
```

---

## 📊 Performance Impact

### API Login (server-side)

```
When:    Server startup / first request / on 401
Frequency: Rare (depends on TTL / invalidation)
Duration:  < 1 second
Impact:    ZERO (background task, no user wait)
Cache:     TTL configurable (default 24 hours)
```

### Cargo Requests (driver-facing)

```
Before: Request → Server → CargoTech API (700ms) → Response
After:  Request → Server (uses cached token) → CargoTech API (700ms) → Response

Difference: ZERO (same network call)
Benefit: Driver doesn't need credentials
```

---

## 🚀 Implementation Checklist

### Week 1: Setup

- [ ] Add env variables (.env)
- [ ] Create CargoTechAuthService
- [ ] Add tests for Contract 1.4

### Week 2: Integration

- [ ] Update CargoAPIClient to use token
- [ ] Add monitoring & alerting

### Week 3: Testing

- [ ] End-to-end tests
- [ ] Security audit
- [ ] Disaster recovery test

### Deployment

- [ ] Set environment variables in production
- [ ] Deploy code
- [ ] Verify token cached (/v1/me OK)
- [ ] Alert if auth repeatedly fails

---

## 🔧 How to Deploy

### 1. Set environment variables:

```bash
# Production environment
export CARGOTECH_PHONE="+7 911 111 11 11"
export CARGOTECH_PASSWORD="123-123"
export CARGOTECH_TOKEN_CACHE_TTL="86400"  # optional
```

### 2. Run migrations:

```bash
python manage.py migrate
```

### 3. Test login manually:

```bash
python manage.py shell
>>> from apps.integrations.cargotech_auth import CargoTechAuthService
>>> token = CargoTechAuthService.get_token()
>>> print(token)  # Should return valid token
```

### 4. Start monitoring:

```bash
# Add to crontab or Celery beat
celery -A config beat --loglevel=info
```

---

## 📞 Support

### If token login fails:

1. Check environment variables:
   ```bash
   echo $CARGOTECH_PHONE
   echo $CARGOTECH_PASSWORD
   ```

2. Check CargoTech API status:
   ```bash
   curl -X POST https://api.cargotech.pro/v1/auth/login
   ```

3. Check logs:
   ```bash
   tail -f logs/cargotech_auth.log
   ```

4. Clear cached token and re-login:
    ```bash
    redis-cli DEL cargotech:api:token
    python manage.py shell
    >>> from apps.integrations.cargotech_auth import CargoTechAuthService
    >>> CargoTechAuthService.get_token()
    ```

---

**Версия:** 3.1 Final  
**Статус:** ✅ ГОТОВО К РАЗРАБОТКЕ  
**Дополнительно:** Полная документация в `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (в составе v3.2)
