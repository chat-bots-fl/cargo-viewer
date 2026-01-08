# 📑 API CONTRACTS v3.1 (Contracts 1.1–5.4)

**Дата:** 4 января 2026  
**Версия:** 3.1 (актуализация v3.0 + M5)

---

## 🧾 Единая таблица контрактов (15)

| Contract | Модуль | Метод/сервис | Назначение | Где описано |
|---|---|---|---|---|
| 1.1 | M1 | `TelegramAuthService.validate_init_data()` | Валидация `initData` Telegram WebApp (HMAC + max_age) | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 1.2 | M1 | `SessionService.create_session()` | Создание сессии водителя (Redis) | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 1.3 | M1 | `TokenService.validate_session()` | Проверка session token | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 1.4 | M1 | `CargoTechAuthService.login()` | Логин в CargoTech API + получение Bearer token | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 2.1 | M2 | `CargoAPIClient.fetch_cargos()` | Запрос списка/деталей грузов в CargoTech API | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 2.2 | M2 | `CargoService.format_cargo_card()` | Форматирование ответа API в UI‑карточки | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 2.3 | M2 | `CargoService.get_cargos()` | Агрегация + кэширование (per‑user) | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 3.1 | M3 | `FilterService.validate_filters()` | Валидация фильтров (в т.ч. `weight_volume`) | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 3.2 | M3 | `FilterService.build_query()` | Построение query для CargoTech API | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 4.1 | M4 | `TelegramBotService.handle_response()` | Обработка отклика водителя | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 4.2 | M4 | `TelegramBotService.send_status()` | Отправка статусов/обновлений в Telegram | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
| 5.1 | M5 | `PaymentService.create_payment()` | Создание платежа в ЮKassa (возврат `confirmation_url`) | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |
| 5.2 | M5 | `PaymentService.process_webhook()` | Обработка webhook ЮKassa (signature + idempotency) | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |
| 5.3 | M5 | `SubscriptionService.activate_from_payment()` | Активация/продление подписки после оплаты | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |
| 5.4 | M5 | `PromoCodeService.create_promo_code()` | Создание промокодов (админ) | `M5_SUBSCRIPTION_PAYMENT_FULL.md` |

---

## 🧭 Навигация по деталям

- Contracts `1.1–4.2`: `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (разделы `Contract 1.1` … `Contract 4.2`)
- Contracts `5.1–5.4`: `M5_SUBSCRIPTION_PAYMENT_FULL.md` (разделы `Contract 5.1` … `Contract 5.4`)

---

### Contract 1.4: Авторизация CargoTech API (Bearer Token)

CargoTech API использует **Bearer Token** (Laravel Sanctum). Токен получается через `/v1/auth/login` и
передаётся во всех последующих запросах через заголовок `Authorization`.

**Login**

- Endpoint: `POST https://api.cargotech.pro/v1/auth/login`
- Request JSON: `{"phone":"+7 ...","password":"***","remember":true}`
- Response `200`:

```json
{"data":{"token":"12345|<opaque_token>"}}
```

**Use token**

- Header: `Authorization: Bearer <token>`
- Проверка: `GET https://api.cargotech.pro/v1/me`
- Cargo list: `GET https://api.cargotech.pro/v2/cargos/views?...`

Примечание: в реальном CargoTech WebApp токен хранится в `localStorage`. В server‑side интеграции
токен можно хранить в кэше (Redis) и получать заново при `401`.

### Contract 2.1: Фактические параметры запроса

| Параметр | Тип | Описание | Пример |
|---|---|---|---|
| `filter[start_point_id]` | int | ID города загрузки | 62 |
| `filter[finish_point_id]` | int | ID города выгрузки | 39 |
| `filter[start_point_radius]` | int | Радиус от точки загрузки (км) | 50 |
| `filter[finish_point_radius]` | int | Радиус от точки выгрузки (км) | 50 |
| `filter[start_date]` | date | Дата загрузки | 2026-01-01 |
| `filter[mode]` | string | Режим (my/all) | my |
| `filter[wv]` | string | Вес/объем | 15-65 |
| `filter[load_types]` | int | ID типа загрузки | 3 |
| `filter[truck_types]` | int | ID типа транспорта | 4 |
| `include` | string | Включить доп. данные | contacts |
| `limit` | int | Количество на страницу | 20 |
| `offset` | int | Смещение для пагинации | 0 |

### Contract 2.1: Комментарий к грузу (`data.extra.note`) (detail)

Cargo list endpoint `GET /v2/cargos/views` возвращает карточки грузов и **не содержит** комментарий.
Комментарий доступен только в detail view:

- Endpoint: `GET https://api.cargotech.pro/v1/carrier/cargos/{cargo_id}?source=1&include=contacts`
- Поле комментария: `data.extra.note`

Структура `extra` (10 полей):

```json
{
  "note": "По ставке без НДС возможна заправка...",
  "external_inn": null,
  "custom_cargo_type": null,
  "integrate": null,
  "is_delete_from_archive": false,
  "krugoreis": false,
  "partial_load": false,
  "note_valid": true,
  "integrate_contacts": null,
  "url": "https://cargomart.ru/orders/active?modal=..."
}
```

Полезные поля:
- `note_valid` — валидность комментария
- `url` — ссылка на источник (CargoMart)
- `krugoreis`, `partial_load` — признаки рейса/частичной загрузки
- `integrate_contacts` — интеграция контактов (если есть)

### Contract 3.1: Формат weight/volume (`filter[wv]`)

Фронтенд передаёт `weight_volume` как значение селекта (например: `15_20`), а CargoTech API ожидает
`filter[wv]` в формате `"weight-volume"` (пример из HAR: `filter[wv]=15-65`).

| Frontend `weight_volume` | API `filter[wv]` |
|---|---|
| `1_3` | `1-15` |
| `3_5` | `3-25` |
| `5_10` | `5-40` |
| `10_15` | `10-60` |
| `15_20` | `15-65` |
| `20` | `20-999` |
| `any` | (omit) |
