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
| 1.4 | M1 | `CargoTechAuthService.login()` | Server‑side логин в CargoTech API + получение токенов | `FINAL_PROJECT_DOCUMENTATION_v3.1.md` |
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
