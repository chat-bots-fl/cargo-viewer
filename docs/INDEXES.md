# Database Indexes Documentation

**Version:** 1.0  
**Date:** 2026-01-09  
**Database:** PostgreSQL  

---

## Overview

This document describes all database indexes in the cargo-viewer project, their purpose, and the queries they optimize.

---

## Index Summary

| App | Model | Index | Purpose |
|-----|-------|-------|---------|
| auth | DriverProfile | `["user", "revoked_at"]` | Find active driver profiles by user |
| auth | TelegramSession | `["expires_at"]` | Clean up expired sessions |
| auth | TelegramSession | `["user", "revoked_at"]` | Find active sessions by user |
| subscriptions | Subscription | `["user_id", "is_active", "expires_at"]` | Find active subscriptions by user |
| subscriptions | Subscription | `["access_token"]` | Look up subscriptions by token |
| audit | AuditLog | `["user", "action_type", "created_at"]` | Query audit logs by user and action |
| payments | Payment | `["user", "created_at"]` | List user's payments by date |
| payments | Payment | `["yukassa_payment_id"]` | Look up payments by Yukassa ID |
| payments | Payment | `["status", "created_at"]` | Filter payments by status and date |
| payments | PaymentHistory | `["event_type", "created_at"]` | Query history by event type |
| payments | PaymentHistory | `["payment", "created_at"]` | Get payment history by payment |
| promocodes | PromoCode | `["action", "valid_until"]` | Find active promo codes by action |
| promocodes | PromoCode | `["disabled", "valid_until"]` | Find enabled promo codes |
| promocodes | PromoCodeUsage | `["promo_code", "used_at"]` | Query promo code usage |
| promocodes | PromoCodeUsage | `["user", "used_at"]` | Find user's promo code usage |
| promocodes | PromoCodeUsage | `["success", "used_at"]` | Filter usage by success status |
| telegram_bot | DriverCargoResponse | `["cargo_id", "created_at"]` | Find responses for a cargo |
| telegram_bot | DriverCargoResponse | `["user", "created_at"]` | List user's cargo responses |
| telegram_bot | DriverCargoResponse | `["status", "created_at"]` | Filter responses by status |
| feature_flags | SystemSetting | `["is_secret", "created_at"]` | Query settings by secret status |
| feature_flags | FeatureFlag | `["enabled", "created_at"]` | Query enabled feature flags |
| cargos | CargoCache | `["user", "cache_key"]` | Find cache entry by user and key |
| cargos | CargoCache | `["user", "created_at"]` | List user's cache entries by date |

---

## Detailed Index Descriptions

### 1. Authentication App (`apps/auth`)

#### DriverProfile
- **Index:** `["user", "revoked_at"]`
- **Name:** `auth_driver_prof_user_rev_idx`
- **Purpose:** Quickly find active driver profiles for a user
- **Optimizes:** `DriverProfile.objects.filter(user=user, revoked_at__isnull=True)`
- **Selectivity:** High (user_id is foreign key)

#### TelegramSession
- **Index:** `["expires_at"]`
- **Name:** `auth_telegram_sess_exp_idx`
- **Purpose:** Efficient cleanup of expired sessions
- **Optimizes:** `TelegramSession.objects.filter(expires_at__lt=now).delete()`
- **Selectivity:** Medium (time-based)

- **Index:** `["user", "revoked_at"]`
- **Name:** `auth_telegram_sess_user_rev_idx`
- **Purpose:** Find active sessions for a user
- **Optimizes:** `TelegramSession.objects.filter(user=user, revoked_at__isnull=True)`
- **Selectivity:** High (user_id is foreign key)

---

### 2. Subscriptions App (`apps/subscriptions`)

#### Subscription
- **Index:** `["user_id", "is_active", "expires_at"]`
- **Name:** `subscriptions_user_act_exp_idx`
- **Purpose:** Find active subscriptions for a user
- **Optimizes:** `Subscription.objects.filter(user_id=user_id, is_active=True, expires_at__gt=now)`
- **Selectivity:** High (user_id is foreign key)

- **Index:** `["access_token"]`
- **Name:** `subscriptions_acc_tok_idx`
- **Purpose:** Look up subscriptions by access token
- **Optimizes:** `Subscription.objects.get(access_token=token)`
- **Selectivity:** High (unique field)

---

### 3. Audit App (`apps/audit`)

#### AuditLog
- **Index:** `["user", "action_type", "created_at"]`
- **Name:** `audit_log_user_act_cr_idx`
- **Purpose:** Query audit logs by user and action type
- **Optimizes:** `AuditLog.objects.filter(user=user, action_type=action_type).order_by('-created_at')`
- **Selectivity:** High (user_id is foreign key)

---

### 4. Payments App (`apps/payments`)

#### Payment
- **Index:** `["user", "created_at"]`
- **Name:** `payments_user_id_03af7e_idx`
- **Purpose:** List user's payments ordered by date
- **Optimizes:** `Payment.objects.filter(user=user).order_by('-created_at')`
- **Selectivity:** High (user_id is foreign key)

- **Index:** `["yukassa_payment_id"]`
- **Name:** `payments_yukassa_b1bc9f_idx`
- **Purpose:** Look up payments by Yukassa payment ID
- **Optimizes:** `Payment.objects.get(yukassa_payment_id=payment_id)`
- **Selectivity:** High (unique-ish field)

- **Index:** `["status", "created_at"]`
- **Name:** `payments_status_cr_idx`
- **Purpose:** Filter payments by status and date
- **Optimizes:** `Payment.objects.filter(status='succeeded').order_by('-created_at')`
- **Selectivity:** Medium (status has limited values)

#### PaymentHistory
- **Index:** `["event_type", "created_at"]`
- **Name:** `payment_his_event_t_45050d_idx`
- **Purpose:** Query payment history by event type
- **Optimizes:** `PaymentHistory.objects.filter(event_type='webhook_received').order_by('-created_at')`
- **Selectivity:** Medium (event_type has limited values)

- **Index:** `["payment", "created_at"]`
- **Name:** `payment_hist_pay_cr_idx`
- **Purpose:** Get payment history for a specific payment
- **Optimizes:** `PaymentHistory.objects.filter(payment=payment).order_by('-created_at')`
- **Selectivity:** High (payment_id is foreign key)

---

### 5. Promocodes App (`apps/promocodes`)

#### PromoCode
- **Index:** `["action", "valid_until"]`
- **Name:** `promo_codes_act_v_idx`
- **Purpose:** Find active promo codes by action type
- **Optimizes:** `PromoCode.objects.filter(action='extend_subscription', valid_until__gt=now)`
- **Selectivity:** Medium (action has limited values)

- **Index:** `["disabled", "valid_until"]`
- **Name:** `promo_codes_dis_v_idx`
- **Purpose:** Find enabled promo codes
- **Optimizes:** `PromoCode.objects.filter(disabled=False, valid_until__gt=now)`
- **Selectivity:** Medium (disabled is boolean)

#### PromoCodeUsage
- **Index:** `["promo_code", "used_at"]`
- **Name:** `promo_code_use_pro_us_idx`
- **Purpose:** Query promo code usage
- **Optimizes:** `PromoCodeUsage.objects.filter(promo_code=promo_code).order_by('-used_at')`
- **Selectivity:** High (promo_code_id is foreign key)

- **Index:** `["user", "used_at"]`
- **Name:** `promo_code_use_user_idx`
- **Purpose:** Find user's promo code usage
- **Optimizes:** `PromoCodeUsage.objects.filter(user=user).order_by('-used_at')`
- **Selectivity:** High (user_id is foreign key)

- **Index:** `["success", "used_at"]`
- **Name:** `promo_code_use_suc_idx`
- **Purpose:** Filter usage by success status
- **Optimizes:** `PromoCodeUsage.objects.filter(success=True).order_by('-used_at')`
- **Selectivity:** Medium (success is boolean)

---

### 6. Telegram Bot App (`apps/telegram_bot`)

#### DriverCargoResponse
- **Index:** `["cargo_id", "created_at"]`
- **Name:** `driver_cargo_car_cr_idx`
- **Purpose:** Find responses for a specific cargo
- **Optimizes:** `DriverCargoResponse.objects.filter(cargo_id=cargo_id).order_by('-created_at')`
- **Selectivity:** Medium (cargo_id is string)

- **Index:** `["user", "created_at"]`
- **Name:** `driver_cargo_us_cr_idx`
- **Purpose:** List user's cargo responses
- **Optimizes:** `DriverCargoResponse.objects.filter(user=user).order_by('-created_at')`
- **Selectivity:** High (user_id is foreign key)

- **Index:** `["status", "created_at"]`
- **Name:** `driver_cargo_st_cr_idx`
- **Purpose:** Filter responses by status
- **Optimizes:** `DriverCargoResponse.objects.filter(status='pending').order_by('-created_at')`
- **Selectivity:** Medium (status has limited values)

---

### 7. Feature Flags App (`apps/feature_flags`)

#### SystemSetting
- **Index:** `["is_secret", "created_at"]`
- **Name:** `system_settings_sec_idx`
- **Purpose:** Query settings by secret status
- **Optimizes:** `SystemSetting.objects.filter(is_secret=False).order_by('-created_at')`
- **Selectivity:** Medium (is_secret is boolean)

#### FeatureFlag
- **Index:** `["enabled", "created_at"]`
- **Name:** `feature_flags_en_idx`
- **Purpose:** Query enabled feature flags
- **Optimizes:** `FeatureFlag.objects.filter(enabled=True).order_by('-created_at')`
- **Selectivity:** Medium (enabled is boolean)

---

### 8. Cargos App (`apps/cargos`)

#### CargoCache
- **Index:** `["user", "cache_key"]`
- **Name:** `cargo_cache_user_key_idx`
- **Purpose:** Find cache entry by user and key
- **Optimizes:** `CargoCache.objects.get(user=user, cache_key=key)`
- **Selectivity:** High (user_id is foreign key)

- **Index:** `["user", "created_at"]`
- **Name:** `cargo_cache_us_cr_idx`
- **Purpose:** List user's cache entries by date
- **Optimizes:** `CargoCache.objects.filter(user=user).order_by('-created_at')`
- **Selectivity:** High (user_id is foreign key)

---

## Index Monitoring

### Check Index Usage

```sql
-- Check which indexes are being used
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Check index size
SELECT schemaname, tablename, indexname, pg_size_pretty(pg_relation_size(indexname::regclass))
FROM pg_indexes
ORDER BY pg_relation_size(indexname::regclass) DESC;
```

### Find Unused Indexes

```sql
-- Find indexes that have never been used
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY schemaname, tablename, indexname;
```

### Check Index Bloat

```sql
-- Check for index bloat
SELECT schemaname, tablename, indexname,
       pg_size_pretty(pg_relation_size(indexname::regclass)) AS size,
       pg_stat_get_dead_tuples(c.oid) AS dead_tuples
FROM pg_stat_user_indexes
JOIN pg_class c ON pg_stat_user_indexes.indexrelid = c.oid
WHERE pg_stat_get_dead_tuples(c.oid) > 1000
ORDER BY dead_tuples DESC;
```

---

## Index Maintenance

### Rebuild Indexes

```sql
-- Rebuild a specific index
REINDEX INDEX payments_status_cr_idx;

-- Rebuild all indexes on a table
REINDEX TABLE payments;

-- Rebuild all indexes in a schema (requires exclusive lock)
REINDEX SCHEMA public;
```

### Concurrent Index Rebuild (Recommended for Production)

```sql
-- Rebuild index without locking the table
REINDEX INDEX CONCURRENTLY payments_status_cr_idx;
```

---

## Performance Considerations

### Trade-offs

| Factor | Impact |
|--------|--------|
| **Read Performance** | Indexes improve read performance for indexed queries |
| **Write Performance** | Indexes slow down INSERT/UPDATE/DELETE operations |
| **Storage** | Each index consumes additional disk space |
| **Memory** | Indexes are cached in memory when frequently accessed |

### Best Practices

1. **Index Selective Columns:** Index columns with high selectivity (many unique values)
2. **Avoid Over-indexing:** Too many indexes can hurt write performance
3. **Monitor Index Usage:** Regularly check which indexes are actually used
4. **Use Composite Indexes:** Combine frequently queried columns
5. **Consider Query Patterns:** Index based on actual query patterns, not assumptions

### When to Add Indexes

- Queries are slow and EXPLAIN ANALYZE shows sequential scans
- Queries filter on specific columns frequently
- Queries sort on specific columns frequently
- Queries join on specific columns frequently

### When to Remove Indexes

- Index has never been used (idx_scan = 0)
- Query performance is acceptable without the index
- Write performance is critical and read performance is acceptable

---

## Testing Indexes

### Run Index Tests

```bash
# Run all index tests
pytest apps/payments/tests_indexes.py -v
pytest apps/promocodes/tests_indexes.py -v
pytest apps/telegram_bot/tests_indexes.py -v
pytest apps/feature_flags/tests_indexes.py -v
pytest apps/cargos/tests_indexes.py -v

# Run all index tests together
pytest apps/*/tests_indexes.py -v
```

### Verify Index Usage

```python
from django.db import connection
from apps.payments.models import Payment

# Check if index is used
with connection.cursor() as cursor:
    cursor.execute("""
        EXPLAIN ANALYZE
        SELECT * FROM payments 
        WHERE status = 'succeeded' 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(row[0])
```

---

## Migration History

### 2026-01-09: Additional Indexes Added

- **payments**: Added `["status", "created_at"]` and `["payment", "created_at"]` indexes
- **promocodes**: Added `["disabled", "valid_until"]` and `["success", "used_at"]` indexes
- **telegram_bot**: Added `["user", "created_at"]` and `["status", "created_at"]` indexes
- **feature_flags**: Added `["is_secret", "created_at"]` and `["enabled", "created_at"]` indexes
- **cargos**: Added `["user", "created_at"]` index

### Previous Indexes (Already Existed)

- **auth**: DriverProfile and TelegramSession indexes
- **subscriptions**: Subscription indexes
- **audit**: AuditLog indexes

---

## References

- [PostgreSQL Indexes Documentation](https://www.postgresql.org/docs/current/indexes.html)
- [Django Indexes Documentation](https://docs.djangoproject.com/en/5.0/ref/models/indexes/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)

---

**Last Updated:** 2026-01-09  
**Maintained By:** Development Team
