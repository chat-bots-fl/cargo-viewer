# 🧩 IMPLEMENTATION CODE v3.1 (reference)

**Дата:** 4 января 2026  
**Версия:** v3.1 (v3.0 + интеграция M5)

Этот файл закрепляет **copy‑paste код критических компонентов**, который в v2.0/v2.1 был описан в deprecated‑документах, а в v3.1 остался в основном на уровне контрактов/архитектуры.

**Источники (v2.1):**
- `docs/[DEPRECATED]_risk_analysis_final.md`
- `docs/[DEPRECATED]_package_readme.md`
- `docs/[DEPRECATED]_summary_of_changes.md`

> Примечание: код ниже — reference implementation. Перед использованием адаптируйте импорты/пути/HTTP‑клиент под реальный код проекта.

---

## 1) Rate limiting + retries (Token Bucket + backoff)

Компоненты:
- `RateLimiter` (Token Bucket)
- `RequestQueue` (очередь + приоритет)
- Retry wrapper для 429 (exponential backoff + jitter)

### apps/integrations/rate_limiter.py

```python
import heapq
import logging
import random
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class RateLimitError(RuntimeError):
    pass


class RateLimiter:
    """
    Token Bucket limiter.

    capacity = requests_per_minute
    refill_rate = capacity / 60 tokens per second
    """

    def __init__(self, requests_per_minute: int = 600):
        self.capacity = float(requests_per_minute)
        self.tokens = float(requests_per_minute)
        self.last_update = time.monotonic()
        self.lock = Lock()

    def can_request(self) -> bool:
        """Return True if request is allowed (consumes 1 token)."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Refill tokens since last check.
            new_tokens = elapsed * (self.capacity / 60.0)
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_update = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


def _sleep_backoff(attempt: int, base_ms: int = 500, jitter_ms: int = 100) -> None:
    """500ms → 1500ms → 3000ms (+ jitter)."""
    wait_ms = base_ms * (2**attempt) + random.randint(0, jitter_ms)
    time.sleep(wait_ms / 1000.0)


@dataclass(order=True)
class _QueuedRequest:
    priority: int
    enqueued_at: float = field(compare=False)
    fn: Callable[[], T] = field(compare=False)


class RequestQueue:
    """
    In‑memory queue for work that should run when RateLimiter allows.

    NOTE: Для production обычно лучше Redis/Celery, но логика остаётся той же.
    """

    def __init__(self, max_queue_size: int = 1000):
        self.queue: list[_QueuedRequest] = []
        self.max_size = max_queue_size
        self.lock = Lock()

    def enqueue(self, fn: Callable[[], T], priority: int = 1) -> bool:
        with self.lock:
            if len(self.queue) >= self.max_size:
                return False
            heapq.heappush(
                self.queue,
                _QueuedRequest(priority=priority, enqueued_at=time.monotonic(), fn=fn),
            )
            return True

    def pop(self) -> Optional[Callable[[], T]]:
        with self.lock:
            if not self.queue:
                return None
            item = heapq.heappop(self.queue)
            return item.fn

    def process_once(self, limiter: RateLimiter) -> bool:
        """
        Process a single queued item if limiter allows it.
        Returns True if something was processed.
        """
        if not limiter.can_request():
            return False
        fn = self.pop()
        if fn is None:
            return False
        fn()
        return True
```

### apps/integrations/http_retry.py (пример)

```python
import logging
from typing import Callable, Mapping, Protocol, TypeVar

from .rate_limiter import RateLimitError, _sleep_backoff

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]


def fetch_with_retry(request_fn: Callable[[], ResponseLike], *, max_attempts: int = 4) -> ResponseLike:
    """
    Retry wrapper for HTTP requests (handles 429 + exponential backoff).

    - attempt 1: 500ms + jitter
    - attempt 2: 1500ms + jitter
    - attempt 3: 3000ms + jitter
    - attempt 4: fail
    """

    for attempt in range(max_attempts):
        response = request_fn()

        if response.status_code != 429:
            return response

        logger.warning("Rate limited (HTTP 429), attempt=%s", attempt + 1)
        if attempt >= max_attempts - 1:
            break

        _sleep_backoff(attempt)

    raise RateLimitError("Max retries exceeded after 4 attempts")
```

---

## 2) CargoService: 3‑уровневое кэширование

Уровни:
- L1: per‑user cargo list cache (TTL 5 min)
- L2: cargo detail cache (TTL 15 min)
- L3: autocomplete/cities cache (TTL 24h)

### apps/cargos/services.py (reference)

```python
import hashlib
import json
import logging
from typing import Any, Mapping

from django.core.cache import cache

logger = logging.getLogger(__name__)


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


class CargoService:
    CACHE_TIMEOUT_LIST = 300  # 5 minutes
    CACHE_TIMEOUT_DETAIL = 900  # 15 minutes
    CACHE_TIMEOUT_CITIES = 86400  # 24 hours

    @staticmethod
    def get_cargo_list(user_id: int, filters: Mapping[str, Any]):
        """L1: per-user list cache (key depends on filters)."""
        filter_hash = _stable_hash(dict(filters))
        cache_key = f"user:{user_id}:cargos:{filter_hash}"

        cargos = cache.get(cache_key)
        if cargos is not None:
            logger.debug("Cache hit: %s", cache_key)
            return cargos

        logger.debug("Cache miss: %s", cache_key)
        cargos = CargoAPIClient.fetch_cargos(filters)  # TODO: implement client
        cache.set(cache_key, cargos, timeout=CargoService.CACHE_TIMEOUT_LIST)
        return cargos

    @staticmethod
    def get_cargo_detail(cargo_id: str):
        """L2: detail cache."""
        cache_key = f"cargo:{cargo_id}:detail"

        detail = cache.get(cache_key)
        if detail is not None:
            return detail, "cached"

        detail = CargoAPIClient.fetch_detail(cargo_id)  # TODO: implement client
        cache.set(cache_key, detail, timeout=CargoService.CACHE_TIMEOUT_DETAIL)
        return detail, "fresh"

    @staticmethod
    def get_cities_reference():
        """L3: autocomplete cache."""
        cache_key = "autocomplete:cities"
        cities = cache.get(cache_key)
        if cities is not None:
            return cities

        cities = CargoAPIClient.fetch_cities()  # TODO: implement client
        cache.set(cache_key, cities, timeout=CargoService.CACHE_TIMEOUT_CITIES)
        return cities

    @staticmethod
    def invalidate_user_cache(user_id: int) -> None:
        """
        Invalidate all cached cargo lists for a user.

        If you're using django-redis, prefer:
          cache.delete_pattern(f\"user:{user_id}:cargos:*\")
        """
        delete_pattern = getattr(cache, "delete_pattern", None)
        if callable(delete_pattern):
            delete_pattern(f"user:{user_id}:cargos:*")
            return

        logger.warning(
            "Cache backend doesn't support delete_pattern; "
            "consider storing per-user cache keys explicitly."
        )

    @staticmethod
    def invalidate_cargo_cache(cargo_id: str) -> None:
        """Invalidate cargo detail cache (e.g. webhook/status change)."""
        cache.delete(f"cargo:{cargo_id}:detail")
```

---

## 3) TelegramAuthService: security (max_age + constant‑time)

Компоненты:
- `max_age_seconds` (защита от replay)
- `hmac.compare_digest()` (constant‑time сравнение)
- логирование ошибок без утечки секретов

### apps/auth/services.py (reference)

```python
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from urllib.parse import parse_qsl

from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger("telegram_auth")


class TelegramAuthService:
    @staticmethod
    def validate_init_data(init_data: str, *, max_age_seconds: int = 300) -> dict:
        """
        Validate Telegram WebApp initData.

        Security contract:
        - HMAC-SHA256 validation (constant-time comparison)
        - Timestamp validation (reject if older than max_age_seconds)
        """

        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token:
            raise ValidationError("TELEGRAM_BOT_TOKEN is not configured")

        # Parse query-string into pairs.
        pairs = parse_qsl(init_data, strict_parsing=False, keep_blank_values=True)
        data = dict(pairs)

        hash_value = data.pop("hash", None)
        if not hash_value:
            raise ValidationError("Missing Telegram hash")

        # Build check string (sorted, joined with \\n).
        data_check_string = "\\n".join(f"{k}={v}" for k, v in sorted(data.items()))

        # Telegram WebApp secret key = sha256(bot_token)
        secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
        calculated_hash = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, hash_value):
            logger.warning("Invalid Telegram hash (init_data_prefix=%r)", init_data[:64])
            raise ValidationError("Invalid Telegram hash")

        # Timestamp validation
        try:
            auth_date = int(data.get("auth_date", "0"))
        except ValueError:
            raise ValidationError("Invalid auth_date")

        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        age = now_ts - auth_date

        if age > max_age_seconds:
            logger.warning("Telegram auth too old: age=%ss max=%ss", age, max_age_seconds)
            raise ValidationError("Authentication expired")
        if age < -10:
            logger.warning("Telegram auth_date is in the future: age=%ss", age)
            raise ValidationError("Invalid auth_date")

        return data
```

---

## 4) Weight/Volume normalization (Contract 3.1)

Компоненты:
- `WEIGHT_VOLUME_CATEGORIES` (маппинг 7 категорий)
- `normalize_weight_volume_filter()` (конвертация select value → API параметры)

### apps/filtering/constants.py (новый)

```python
"""
Weight/Volume filter categories for CargoTech API
Defines predefined cargo capacity ranges
"""

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
    "5_10": {
        "label": "5-10 т / 25-40 м³",
        "weight_min_kg": 5000,
        "weight_max_kg": 10000,
        "volume_min_m3": 25,
        "volume_max_m3": 40,
    },
    "10_15": {
        "label": "10-15 т / 40-60 м³",
        "weight_min_kg": 10000,
        "weight_max_kg": 15000,
        "volume_min_m3": 40,
        "volume_max_m3": 60,
    },
    "15_20": {
        "label": "15-20 т / 60-82 м³",
        "weight_min_kg": 15000,
        "weight_max_kg": 20000,
        "volume_min_m3": 60,
        "volume_max_m3": 82,
    },
    "20": {
        "label": "20+ т / 82+ м³",
        "weight_min_kg": 20000,
        "weight_max_kg": 999999,
        "volume_min_m3": 82,
        "volume_max_m3": 999999,
    },
}

# Frontend select options (order matters)
WEIGHT_VOLUME_OPTIONS = [
    ("any", "Любой вес и объем"),
    ("1_3", "1-3 т / до 15 м³"),
    ("3_5", "3-5 т / 15-25 м³"),
    ("5_10", "5-10 т / 25-40 м³"),
    ("10_15", "10-15 т / 40-60 м³"),
    ("15_20", "15-20 т / 60-82 м³"),
    ("20", "20+ т / 82+ м³"),
]
```

### apps/filtering/services.py

```python
from django.core.exceptions import ValidationError

from .constants import WEIGHT_VOLUME_CATEGORIES


def normalize_weight_volume_filter(value: str) -> dict:
    """
    Convert frontend weight_volume select value to API parameters.

    Args:
        value: "1_3", "3_5", "5_10", "10_15", "15_20", "20", "any", or empty

    Returns:
        {
            "weight_min_kg": int,
            "weight_max_kg": int,
            "volume_min_m3": int,
            "volume_max_m3": int,
        }
        or {} if value is "any" or empty (no filter)
    """

    if not value or value == "any":
        return {}

    if value not in WEIGHT_VOLUME_CATEGORIES:
        raise ValidationError(
            f"Invalid weight_volume value: {value}. "
            f"Must be one of: {', '.join(WEIGHT_VOLUME_CATEGORIES.keys())} or 'any'"
        )

    category = WEIGHT_VOLUME_CATEGORIES[value]
    return {
        "weight_min_kg": category["weight_min_kg"],
        "weight_max_kg": category["weight_max_kg"],
        "volume_min_m3": category["volume_min_m3"],
        "volume_max_m3": category["volume_max_m3"],
    }
```

---

## 5) Где это связано с актуальными контрактами v3.1

- Контракты (что именно должно быть реализовано): `API_CONTRACTS_v3.1.md`
- Полные контракты/архитектура: `FINAL_PROJECT_DOCUMENTATION_v3.1.md` (Часть 5)
- Deprecated‑источники (история решений + контекст): `docs/[DEPRECATED]_risk_analysis_final.md`, `docs/[DEPRECATED]_summary_of_changes.md`, `docs/[DEPRECATED]_package_readme.md`
