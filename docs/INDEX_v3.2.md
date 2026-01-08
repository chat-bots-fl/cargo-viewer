# 📋 INDEX v3.2 (единая навигация)

**Дата актуализации:** 8 января 2026  
**Версия документации:** v3.2.1 (v3.2 + Auth Verification)

**Ключевые метрики v3.2:**
- PCAM: 6 процессов × 6 каналов
- PBS: 5 модулей (M1–M5)
- Контракты: 16 (1.1–5.4 + 2.4)
- План разработки: 24 дня (14 базовых + 10 на M5)

---

## 🚀 Начать

- 3 минуты: `ONE_PAGE_SUMMARY_v3.2.md`
- 10–15 минут: `QUICK_REFERENCE_v3.2.md` + этот индекс
- Начать кодить: `API_CONTRACTS_v3.2.md` + `FINAL_PROJECT_DOCUMENTATION_v3.2.md`
- Развернуть: `DEPLOY_GUIDE_v3.2.md`

---

## ✅ Актуальные файлы (v3.2.1)

1. `DOCUMENTATION_STATUS.md` — статус версий + список deprecated файлов
2. `ONE_PAGE_SUMMARY_v3.2.md` — 1‑страничная сводка
3. `QUICK_REFERENCE_v3.2.md` — что изменилось (HAR validation updates)
4. `FINAL_PROJECT_DOCUMENTATION_v3.2.md` — полный документ (архитектура, FR/NFR, контракты)
5. `API_CONTRACTS_v3.2.md` — единая таблица контрактов `1.1–5.4` + `2.4`
6. `IMPLEMENTATION_CODE_v3.2.md` — reference код критических компонентов (rate limiting, cache, Telegram security, filter[wv])
7. `DEPLOY_GUIDE_v3.2.md` — deploy + чек‑листы + smoke tests
8. `M5_SUBSCRIPTION_PAYMENT_SUMMARY.md` — M5 кратко
9. `M5_SUBSCRIPTION_PAYMENT_FULL.md` — M5 подробно
10. `CHANGELOG_v3.1_to_v3.2.md` — список изменений
11. `compliance_analysis_report.txt` — отчет анализа HAR (v3.2)
12. `auth_test_verification_results.txt` — результаты проверки авторизации (browser testing)

---

## 🧭 Что где искать

- Архитектура PCAM/PBS/FR/NFR: `FINAL_PROJECT_DOCUMENTATION_v3.2.md`
- Контракты (единый список): `API_CONTRACTS_v3.2.md`
- Контракты `1.1–4.2` (детали): `FINAL_PROJECT_DOCUMENTATION_v3.2.md`
- Контракты `5.1–5.4` (детали): `M5_SUBSCRIPTION_PAYMENT_FULL.md`
- Reference код реализации: `IMPLEMENTATION_CODE_v3.2.md`
- План разработки (24 дня): `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (Часть 8)
- Deploy checklist + smoke test: `DEPLOY_GUIDE_v3.2.md`
- Auth verification details: `API_CONTRACTS_v3.2.md` (Contract 1.4) + `auth_test_verification_results.txt`

---

## 👥 Маршруты чтения по ролям

**CTO/PM (10 минут)**
- `ONE_PAGE_SUMMARY_v3.2.md`
- `QUICK_REFERENCE_v3.2.md`

**Lead Developer (1–2 часа)**
- `API_CONTRACTS_v3.2.md`
- `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (Development Plan + Contracts)
- `M5_SUBSCRIPTION_PAYMENT_SUMMARY.md` (если берёте M5 в спринт)

**Backend Developer (1–2 часа)**
- `QUICK_REFERENCE_v3.2.md`
- `API_CONTRACTS_v3.2.md`
- `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (контракты вашей зоны)
- `M5_SUBSCRIPTION_PAYMENT_FULL.md` (если отвечаете за M5)

**QA (45–60 минут)**
- `API_CONTRACTS_v3.2.md` (контракты → test cases)
- `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (FR/NFR)
- `DEPLOY_GUIDE_v3.2.md` (smoke test + checklist)

**DevOps (45–60 минут)**
- `DEPLOY_GUIDE_v3.2.md`
- `QUICK_REFERENCE_v3.2.md` (.env)
- `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (NFR + webhooks)

---

## 🗄️ Legacy

Файлы v3.1 и исторические `[DEPRECATED]_*` перемещены в `legacy_3.1/` (только для контекста/истории).
