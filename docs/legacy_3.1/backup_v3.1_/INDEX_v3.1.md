# 📋 INDEX v3.1 (единая навигация)

**Дата актуализации:** 4 января 2026  
**Версия документации:** v3.1 (v3.0 + интеграция M5: подписки/платежи)

**Ключевые метрики v3.1:**
- PCAM: 6 процессов × 6 каналов
- PBS: 5 модулей (M1–M5)
- Контракты: 15 (1.1–5.4)
- План разработки: 24 дня (14 базовых + 10 на M5)

---

## 🚀 Начать

- 3 минуты: `ONE_PAGE_SUMMARY_v3.1.md`
- 10–15 минут: `QUICK_REFERENCE_v3.1.md` + этот индекс
- Начать кодить: `API_CONTRACTS_v3.1.md` + `FINAL_PROJECT_DOCUMENTATION_v3.1.md`
- Развернуть: `DEPLOY_GUIDE_v3.1.md`

---

## ✅ Актуальные файлы (v3.1)

1. `DOCUMENTATION_STATUS.md` — статус версий + список deprecated файлов
2. `ONE_PAGE_SUMMARY_v3.1.md` — 1‑страничная сводка
3. `QUICK_REFERENCE_v3.1.md` — что изменилось (server‑side login + M5)
4. `FINAL_COMPLETE_v3.1.md` — обзор + итоговый статус + план
5. `FINAL_PROJECT_DOCUMENTATION_v3.1.md` — полный документ (архитектура, FR/NFR, контракты)
6. `API_CONTRACTS_v3.1.md` — единая таблица контрактов `1.1–5.4`
7. `IMPLEMENTATION_CODE_v3.1.md` — reference код критических компонентов (rate limiting, cache, Telegram security, weight_volume)
8. `DEPLOY_GUIDE_v3.1.md` — deploy + чек‑листы + smoke tests
9. `M5_SUBSCRIPTION_PAYMENT_SUMMARY.md` — M5 кратко
10. `M5_SUBSCRIPTION_PAYMENT_FULL.md` — M5 подробно
11. `FINAL_READY_v3.1.md` — быстрый onboarding команды
12. `FINAL_STATUS_v3.1.md` — итоговый статус пакета
13. `final_compliance_report.md` — отчет о согласованности документации v3.1

---

## 🧭 Что где искать

- Архитектура PCAM/PBS/FR/NFR: `FINAL_PROJECT_DOCUMENTATION_v3.1.md`
- Контракты (единый список): `API_CONTRACTS_v3.1.md`
- Контракты `1.1–4.2` (детали): `FINAL_PROJECT_DOCUMENTATION_v3.1.md`
- Контракты `5.1–5.4` (детали): `M5_SUBSCRIPTION_PAYMENT_FULL.md`
- Reference код реализации: `IMPLEMENTATION_CODE_v3.1.md`
- План разработки (24 дня): `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (Часть 8) + `FINAL_COMPLETE_v3.1.md`
- Deploy checklist + smoke test: `DEPLOY_GUIDE_v3.1.md`

---

## 👥 Маршруты чтения по ролям

**CTO/PM (10 минут)**
- `ONE_PAGE_SUMMARY_v3.1.md`
- `QUICK_REFERENCE_v3.1.md`
- `FINAL_COMPLETE_v3.1.md` (ИТОГОВЫЙ СТАТУС)

**Lead Developer (1–2 часа)**
- `FINAL_COMPLETE_v3.1.md`
- `API_CONTRACTS_v3.1.md`
- `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (Development Plan + Contracts)
- `M5_SUBSCRIPTION_PAYMENT_SUMMARY.md` (если берёте M5 в спринт)

**Backend Developer (1–2 часа)**
- `QUICK_REFERENCE_v3.1.md`
- `API_CONTRACTS_v3.1.md`
- `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (контракты вашей зоны)
- `M5_SUBSCRIPTION_PAYMENT_FULL.md` (если отвечаете за M5)

**QA (45–60 минут)**
- `API_CONTRACTS_v3.1.md` (контракты → test cases)
- `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (FR/NFR)
- `DEPLOY_GUIDE_v3.1.md` (smoke test + checklist)

**DevOps (45–60 минут)**
- `DEPLOY_GUIDE_v3.1.md`
- `QUICK_REFERENCE_v3.1.md` (.env)
- `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (NFR + webhooks)

---

## ⚠️ Deprecated (v2.0/v2.1 — только для истории)

- `docs/[DEPRECATED]_START_HERE.md`
- `docs/[DEPRECATED]_INDEX.md`
- `docs/[DEPRECATED]_README.md`
- `docs/[DEPRECATED]_FINAL_SUMMARY.md`
- `docs/[DEPRECATED]_summary_of_changes.md`
- `docs/[DEPRECATED]_final_compliance_report.md`
- `docs/[DEPRECATED]_risk_analysis_final.md`
- `docs/[DEPRECATED]_package_readme.md`
