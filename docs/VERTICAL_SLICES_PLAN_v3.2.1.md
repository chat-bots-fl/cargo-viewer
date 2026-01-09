# 🧩 VERTICAL SLICING PLAN v3.2.1 (Django templates + HTMX)

**Проект:** CargoTech Driver WebApp (Telegram WebApp для водителей)  
**Дата:** 8 января 2026  
**Версия:** 3.2.1 (v3.2 + Auth Verification Patch)  
**Основа структуры:** `docs/FINAL_PROJECT_DOCUMENTATION_v3.2.md` (Часть 7, Project Layout — блок `apps/cargos/` начиная с ~строки 1166)

---

## Принципы

- **WebApp = Django templates + HTMX**: сервер рендерит HTML, HTMX обновляет фрагменты (список, пагинация, модалки, статусы).
- **Telegram WebApp auth**: `Telegram.WebApp.initData` → backend → `session_token` (JWT) → `localStorage` → `Authorization: Bearer <jwt>` во всех HTMX запросах (`htmx:configRequest`).
- **Контракты**: реализуем по `docs/API_CONTRACTS_v3.2.md` + “Contract-first” стиль из `AGENTS.md`.
- **Кэширование (Redis)**: per-user cargo list (~5 мин), cargo detail (~15 мин), cities autocomplete (~24ч), CargoTech API token (~24ч, configurable).
- **DoD для каждого слайса**: есть рабочий end-to-end сценарий “UI → backend → интеграция/кэш”, плюс минимальные тесты по контракту/смоук.

---

## Карточки слайсов (Story → файлы/эндпоинты → контракты → acceptance checks)

### VS0 — Skeleton (WebApp открывается из бота)

- **Story:** как водитель, я открываю WebApp из Telegram и вижу базовую оболочку приложения.
- **Файлы (основа):**
  - `manage.py`, `requirements.txt`, `docker-compose.yml`
  - `config/settings.py`, `config/urls.py`
  - `templates/base.html`, `templates/main.html`
  - `static/css/main.css`, `static/js/app.js`
- **Эндпоинты (backend):** `GET /` (WebApp shell), `GET /healthz`
- **Контракты:** —
- **Acceptance checks:**
  - `GET /healthz` → `200 OK`
  - WebApp открывается по кнопке `web_app` из Telegram-бота
  - Статика грузится без ошибок (CSS/JS)

### VS1 — Telegram Auth + Session (M1)

- **Story:** как водитель, я автоматически авторизуюсь через Telegram WebApp и получаю сессию для запросов.
- **Файлы (из структуры):**
  - `apps/auth/models.py`
  - `apps/auth/services.py`
  - `apps/auth/views.py`
  - `apps/auth/tests.py`
  - `config/urls.py`, `config/settings.py`
  - `static/js/app.js`
- **Эндпоинты (backend):**
  - `POST /api/auth/telegram` (initData → session_token)
  - Guard для всех `GET/POST /api/*` через middleware проверки JWT
- **Контракты:**
  - 1.1 `TelegramAuthService.validate_init_data()`
  - 1.2 `SessionService.create_session()`
  - 1.3 `TokenService.validate_session()`
- **Acceptance checks:**
  - Некорректный/просроченный `initData` → `401`
  - Корректный `initData` → возвращает JWT и создаёт сессию в Redis (TTL 24h, sliding window)
  - HTMX запросы после логина уходят с `Authorization: Bearer <jwt>`

### VS2 — CargoTech server-side token (P5 / M1.4)

- **Story:** как система, я получаю и кеширую Bearer token CargoTech и восстанавливаюсь при `401`.
- **Файлы (из структуры):**
  - `apps/integrations/cargotech_auth.py`
  - `apps/integrations/tests.py`
  - `config/settings.py`
  - `logs/cargotech_auth.log`
- **Эндпоинты:**
  - внешние: `POST https://api.cargotech.pro/v1/auth/login`, `GET https://api.cargotech.pro/v1/me`
  - внутренние: расширение `GET /healthz` (опционально) или отдельный `/api/integrations/cargotech/health`
- **Контракты:**
  - 1.4 `CargoTechAuthService.login()`
- **Acceptance checks:**
  - Token записан в Redis `cargotech:api:token` (TTL)
  - При `401`: invalidate cache → re-login → retry **ровно один** раз
  - Health-check показывает “CargoTech auth ok” при валидном токене

### VS3 — Cargo list (M2: list + formatting + cache)

- **Story:** как водитель, я вижу список грузов карточками и могу подгружать следующую страницу без перезагрузки.
- **Файлы (из структуры):**
  - `apps/integrations/cargotech_client.py`
  - `apps/cargos/models.py`
  - `apps/cargos/views.py`
  - `apps/cargos/services.py`
  - `apps/cargos/serializers.py`
  - `apps/cargos/templates/cargo_list.html`
  - `apps/cargos/templates/components/cargo_card.html`
  - `apps/cargos/templates/components/loading_spinner.html`
  - `apps/cargos/tests.py`
  - `templates/main.html`
- **Эндпоинты:**
  - внутренний: `GET /api/cargos/?limit=&offset=` (возвращает HTML partial для HTMX)
  - внешний: `GET https://api.cargotech.pro/v2/cargos/views`
- **Контракты:**
  - 2.1 `CargoAPIClient.fetch_cargos()`
  - 2.2 `CargoService.format_cargo_card()`
  - 2.3 `CargoService.get_cargos()`
- **Acceptance checks:**
  - Главная страница инициирует HTMX загрузку списка
  - Пагинация (`limit/offset`) работает через HTMX (“Ещё”/infinite scroll)
  - Повтор запроса с теми же фильтрами → cache hit (TTL ~5 минут)

### VS4 — Cargo detail modal (M2: detail)

- **Story:** как водитель, я открываю детальную карточку груза (модалка) и вижу комментарий/контакты.
- **Файлы (из структуры):**
  - `apps/cargos/views.py`
  - `apps/cargos/services.py`
  - `apps/cargos/templates/cargo_detail.html`
  - `apps/cargos/tests.py`
  - `static/js/app.js` (управление модалкой/закрытием)
- **Эндпоинты:**
  - внутренний: `GET /api/cargos/<cargo_id>/` (HTML partial для модалки)
  - внешний: `GET https://api.cargotech.pro/v1/carrier/cargos/<cargo_id>?source=1&include=contacts`
- **Контракты:**
  - 2.1 (detail fetch)
  - 2.2 (форматирование данных под UI)
- **Acceptance checks:**
  - Клик по карточке открывает модалку и показывает спиннер до ответа
  - Если есть `data.extra.note`, он отображается
  - При таймауте/ошибке API используется кеш (если есть) и UI показывает fallback

### VS5 — Filtering + Cities autocomplete (M3 + Contract 2.4)

- **Story:** как водитель, я фильтрую выдачу и получаю подсказки городов (autocomplete).
- **Файлы (из структуры):**
  - `apps/filtering/services.py`
  - `apps/filtering/tests.py`
  - `apps/integrations/cargotech_client.py`
  - `apps/cargos/views.py`
  - `static/js/filters.js`
  - `templates/main.html`
- **Эндпоинты:**
  - внутренние: `GET /api/cargos/?...filters...`, `GET /api/dictionaries/points?name=...`
  - внешний: `GET https://api.cargotech.pro/v1/dictionaries/points?filter[name]=...`
- **Контракты:**
  - 3.1 `FilterService.validate_filters()`
  - 3.2 `FilterService.build_query()`
  - 2.4 `DictionaryService.search_cities()`
- **Acceptance checks:**
  - `weight_volume` валидируется в формате `{weight}-{volume}` (десятичные поддерживаются) и маппится в `filter[wv]`
  - Autocomplete использует debounce + min length (UX), при этом backend терпим к коротким значениям (как в HAR)
  - Фильтры комбинируются и реально меняют выдачу (плюс корректные обязательные параметры списка)

### VS6 — Respond to cargo via Telegram Bot (M4)

- **Story:** как водитель, я нажимаю “Откликнуться”, отклик уходит в Telegram, а статус виден в UI без дублей.
- **Файлы (из структуры):**
  - `apps/telegram_bot/handlers.py`
  - `apps/telegram_bot/services.py`
  - `apps/telegram_bot/tests.py`
  - `apps/cargos/templates/cargo_detail.html`
  - `apps/cargos/templates/components/cargo_card.html`
  - `config/urls.py`
- **Эндпоинты:**
  - внутренний: `POST /telegram/responses/` (handler)
  - внешние: Telegram Bot API (sendMessage/notify)
- **Контракты:**
  - 4.1 `TelegramBotService.handle_response()`
  - 4.2 `TelegramBotService.send_status()`
- **Acceptance checks:**
  - Повторный отклик на тот же `(driver_id, cargo_id)` не создаёт дубль (idempotent)
  - UI показывает бейдж статуса (`sent/accepted/rejected/completed`)
  - Таймаут Telegram → retry и логирование delivery status

### VS7 — Paywall skeleton + access control (M5 foundation)

- **Story:** как водитель без подписки, я вижу paywall и не могу пользоваться платными действиями (например, откликом).
- **Файлы (из структуры M5.1–M5.6):**
  - `apps/subscriptions/*`
  - `apps/feature_flags/*`
  - `apps/audit/*`
  - `templates/paywall.html` (или в `templates/main.html` блок paywall)
- **Эндпоинты:**
  - `GET /paywall`
  - `GET /api/subscription/status`
  - защита платных действий (минимум: `POST /telegram/responses/`)
- **Контракты:** подготовка под 5.1–5.3 (контроль доступа по FR-7/FR-11)
- **Acceptance checks:**
  - Без активной подписки платные эндпоинты возвращают `payment_required`
  - UI показывает paywall/экран статуса подписки
  - При активной подписке ограничения снимаются

### VS8 — Create payment (M5.1 / Contract 5.1)

- **Story:** как водитель, я инициирую оплату и получаю ссылку на оплату (`confirmation_url`).
- **Файлы (из структуры M5.1–M5.6):**
  - `apps/payments/*`
  - `templates/paywall.html`
  - `config/urls.py`
- **Эндпоинты:**
  - внутренний: `POST /api/payments/create`
  - внешний: ЮKassa API (create payment)
- **Контракты:**
  - 5.1 `PaymentService.create_payment()`
- **Acceptance checks:**
  - Payment создаётся со статусом `pending`, возвращается `confirmation_url`
  - Повтор запроса с тем же idempotency key не создаёт новые платежи
  - UI корректно открывает `confirmation_url`

### VS9 — Webhook + subscription activation (M5.1/M5.2 / Contracts 5.2–5.3)

- **Story:** как система, я принимаю webhook, обновляю платёж и активирую/продлеваю подписку автоматически.
- **Файлы:**
  - `apps/payments/*`
  - `apps/subscriptions/*`
  - `config/urls.py`
- **Эндпоинты:**
  - `POST /api/payments/webhook`
  - `GET /api/subscription/status`
  - внешние: webhooks ЮKassa
- **Контракты:**
  - 5.2 `PaymentService.process_webhook()`
  - 5.3 `SubscriptionService.activate_from_payment()`
- **Acceptance checks:**
  - Неверная подпись webhook → отказ без побочных эффектов
  - Корректный webhook обрабатывается ровно 1 раз (idempotent)
  - Подписка активируется/продлевается, и UI после refresh видит доступ открыт

### VS10 — Promo + Admin minimum (M5.3/M5.4 / Contract 5.4)

- **Story:** как администратор, я создаю промокоды; как водитель, применяю промокод для доступа/продления.
- **Файлы:**
  - `apps/promocodes/*`
  - `apps/admin_panel/*`
  - `apps/audit/*`
  - `templates/admin/*.html`
  - `templates/paywall.html`
  - `config/urls.py`
- **Эндпоинты:**
  - `POST /api/promocodes/apply`
  - admin UI endpoints (минимум: списки платежей/подписок/промокодов/настроек)
- **Контракты:**
  - 5.4 `PromoCodeService.create_promo_code()`
- **Acceptance checks:**
  - Промокод учитывает ограничения (`expires_at`, `max_uses`, `disabled`) и меняет состояние подписки
  - Операции создания/применения/ошибок пишутся в audit log
  - Админ видит базовые списки (payments/subscriptions/promocodes/settings)

