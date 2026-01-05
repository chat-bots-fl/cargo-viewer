# 🎯 КРАТКИЙ СПРАВОЧНИК v3.1

**Дата:** 4 января 2026  
**Версия:** 3.1 (server-side login + M5 подписки/платежи)  
**Размер:** 2 страницы (quick reference)

---

## 🆕 ЧТО ДОБАВЛЕНО В v3.1

### 1. **Server-Side API Login** ✨

```
ПРОБЛЕМА:  Водители не имеют доступа к CargoTech API
РЕШЕНИЕ:   Сервер логинится один раз → получает token → используется всем

НОВЫЙ CONTRACT:
Contract 1.4: CargoTechAuthService.login()
├─ phone: "+7 911 111 11 11" (из .env)
├─ password: "123-123" (из .env)
├─ returns: access_token + refresh_token
├─ storage: Encrypted in database
└─ refresh: Auto-refresh before 1 hour expiry
```

### 2. **Новая архитектура (P5)**

```
P5: MANAGE_API_CREDENTIALS (новый процесс)
├─ Server starts → login to CargoTech
├─ Get access_token
├─ Store encrypted in DB
├─ All requests use this token
└─ Auto-refresh before expiry

Flow:
Django startup
    ↓
CargoTechAuthService.login(phone, password)
    ↓
Get access_token from API
    ↓
Store encrypted in APIToken model
    ↓
Cache token (55 min)
    ↓
Use token for all requests
    ↓
Before expiry → auto-refresh
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

### 4. **Новые модели**

```python
# apps/integrations/models.py

class APIToken(models.Model):
    access_token = models.TextField()  # Encrypted
    refresh_token = models.TextField()  # Encrypted
    driver_id = models.IntegerField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
```

### 5. **Новые env переменные**

```bash
.env:
├─ CARGOTECH_PHONE=+7 911 111 11 11        ← NEW!
├─ CARGOTECH_PASSWORD=123-123              ← NEW!
├─ ENCRYPTION_KEY=<Fernet key>             ← NEW!
├─ CARGOTECH_TOKEN_CACHE_TTL=3300          ← NEW!
└─ Остальные как было...
```

### 6. **Новые зависимости**

```
cryptography>=41.0.0  # For token encryption
django-redis>=5.4.0   # For token caching
```

---

## 📋 ВСЕ 15 КОНТРАКТОВ

```
M1: AUTHENTICATION & SESSION (4 контракта)
├─ 1.1: TelegramAuthService.validate_init_data()
├─ 1.2: SessionService.create_session()
├─ 1.3: TokenService.validate_session()
└─ 1.4: CargoTechAuthService.login() ← NEW!

M2: CARGO DATA (3 контракта)
├─ 2.1: CargoAPIClient.fetch_cargos()
├─ 2.2: CargoService.format_cargo_card()
└─ 2.3: CargoService.get_cargos()

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

ВСЕГО: 15 контрактов (1.1–5.4)
```

---

## 🔑 Key Changes в v3.1

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

SOLUTION: Contract 1.4 + encrypted token storage
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

### НОВЫЙ FLOW (v3.1):

```
1. Server startup (once per deployment)
   └─ CargoTechAuthService.login()
   └─ Get access_token from CargoTech
   └─ Store encrypted in DB
   └─ Cache token (55 min)

2. Driver opens WebApp
   └─ Telegram → initData
   └─ Server validates initData
   └─ Server creates session (Redis)

3. Driver requests cargo list
   └─ Server uses stored token
   └─ Call CargoTech API
   └─ Return data to driver

4. Token refresh (background)
   └─ Before 1 hour expiry
   └─ Call refresh_token()
   └─ Store new token
   └─ Invalidate old token
```

---

## 💾 Database Changes

### Новая таблица: `APIToken`

```sql
CREATE TABLE integrations_apitoken (
    id BIGINT PRIMARY KEY,
    access_token TEXT NOT NULL,    -- Encrypted
    refresh_token TEXT NOT NULL,   -- Encrypted
    driver_id INTEGER NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_expires_at ON integrations_apitoken(expires_at);
CREATE INDEX idx_driver_id ON integrations_apitoken(driver_id);
```

### Migration:

```bash
python manage.py makemigrations integrations
python manage.py migrate integrations
```

---

## 🔐 Security Improvements

### Что защищено в v3.1:

```
✅ API credentials (phone + password)
   └─ Storage: Django environment variables only
   └─ Never in code or git

✅ Access token
   └─ Storage: Encrypted in database (Fernet)
   └─ Cache: Redis (encrypted at rest)
   └─ Transmission: HTTPS only

✅ Token refresh
   └─ Automatic before expiry
   └─ Old token immediately invalidated
   └─ Audit log all refresh events

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
When:    Server startup + auto-refresh (before 1h expiry)
Frequency: 1-2 times per day (unless errors)
Duration:  < 1 second
Impact:    ZERO (background task, no user wait)
Cache:     55 minutes (avoid repeated logins)
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

- [ ] Add APIToken model
- [ ] Create migration
- [ ] Add env variables (.env)
- [ ] Create CargoTechAuthService
- [ ] Create TokenMonitor
- [ ] Add tests for Contract 1.4

### Week 2: Integration

- [ ] Update CargoAPIClient to use token
- [ ] Add auto-refresh task (Celery)
- [ ] Add monitoring & alerting
- [ ] Load test token refresh under load

### Week 3: Testing

- [ ] End-to-end tests
- [ ] Security audit
- [ ] Token encryption verification
- [ ] Disaster recovery test

### Deployment

- [ ] Set environment variables in production
- [ ] Run migrations
- [ ] Deploy code
- [ ] Verify token creation
- [ ] Monitor token refresh
- [ ] Alert if token invalid

---

## 🔧 How to Deploy

### 1. Set environment variables:

```bash
# Production environment
export CARGOTECH_PHONE="+7 911 111 11 11"
export CARGOTECH_PASSWORD="123-123"
export ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### 2. Run migrations:

```bash
python manage.py migrate integrations
```

### 3. Test login manually:

```bash
python manage.py shell
>>> from apps.integrations.cargotech_auth import CargoTechAuthService
>>> token = CargoTechAuthService.get_valid_token()
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

4. Manually refresh token:
   ```bash
   python manage.py shell
   >>> from apps.integrations.cargotech_auth import CargoTechAuthService
   >>> CargoTechAuthService.login("+7 911 111 11 11", "123-123")
   ```

---

**Версия:** 3.1 Final  
**Статус:** ✅ ГОТОВО К РАЗРАБОТКЕ  
**Дополнительно:** Полная документация в `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (в составе v3.1)
