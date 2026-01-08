# 🧩 IMPLEMENTATION CODE v3.2 (reference)

**Дата:** 7 января 2026  
**Версия:** v3.2 (v3.1 + HAR Validation Updates)

Этот файл закрепляет **copy‑paste код критических компонентов**, который в v2.0/v2.1 был описан в deprecated‑документах, а в v3.2 приведён к актуальному поведению production API (HAR‑validated).

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

## 4) Weight/Volume normalization (Contract 3.1) (v3.2)

**ВАЖНО:** CargoTech API принимает **произвольные** значения `filter[wv]` в формате `{weight}-{volume}`
и поддерживает десятичные значения (например: `1.5-9`, `7.5-45`).

Компоненты:
- `FilterService.validate_weight_volume()` (валидация + нормализация в формат `filter[wv]`)

### apps/filtering/services.py (v3.2)

```python
# apps/filtering/services.py

from django.core.exceptions import ValidationError
import re

class FilterService:

    @staticmethod
    def validate_weight_volume(value: str) -> dict:
        """
        Валидация и нормализация фильтра вес/объем.

        Args:
            value: строка формата "{weight}-{volume}"
                   или пустая строка для отключения фильтра

        Returns:
            {"filter[wv]": value} или {} если пусто

        Raises:
            ValidationError: если формат некорректен
        """
        if not value or value == "any":
            return {}

        # Валидация формата: число/десятичное + дефис + число/десятичное
        pattern = r'^\d+(\.\d+)?-\d+(\.\d+)?$'
        if not re.match(pattern, value):
            raise ValidationError(
                f"Invalid weight_volume format: '{value}'. "
                f"Expected format: '{{weight}}-{{volume}}', "
                f"example: '15-65' or '1.5-9'"
            )

        # Проверка диапазонов (разумные пределы)
        weight, volume = value.split('-')
        weight_val = float(weight)
        volume_val = float(volume)

        if not (0.1 <= weight_val <= 1000):
            raise ValidationError(
                f"Weight {weight_val}t out of range (0.1-1000)"
            )

        if not (0.1 <= volume_val <= 200):
            raise ValidationError(
                f"Volume {volume_val}m³ out of range (0.1-200)"
            )

        return {"filter[wv]": value}
```

---

## 5) CargoTech API auth (Bearer Token) (Contract 1.4)

Компоненты:
- `CargoTechAuthService` (получить и кэшировать Bearer token)
- `CargoAPIClient` (делать запросы с `Authorization: Bearer <token>`, re-login на `401`)

### apps/integrations/cargotech_auth.py (reference)

```python
import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CargoTechAuthError(RuntimeError):
    pass


class CargoTechAuthService:
    """
    CargoTech API auth (Laravel Sanctum).

    Login response shape:
        {"data": {"token": "12345|<opaque_token>"}}
    """

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

### apps/integrations/cargotech_client.py (reference)

```python
import requests
from .cargotech_auth import CargoTechAuthService


class CargoAPIClient:
    BASE_URL = "https://api.cargotech.pro"

    @classmethod
    def request(cls, method: str, path: str, *, params=None, json=None, timeout: int = 15):
        url = f"{cls.BASE_URL}{path}"
        response = requests.request(
            method,
            url,
            headers=CargoTechAuthService.auth_headers(),
            params=params,
            json=json,
            timeout=timeout,
        )

        if response.status_code == 401:
            CargoTechAuthService.invalidate_cached_token()
            response = requests.request(
                method,
                url,
                headers=CargoTechAuthService.auth_headers(),
                params=params,
                json=json,
                timeout=timeout,
            )

        response.raise_for_status()
        return response.json()
```

---

## 6) Cargo comment field (`data.extra.note`) (detail only)

Комментарий к грузу находится **только** в detail endpoint:
`GET /v1/carrier/cargos/{cargo_id}?source=1&include=contacts`

### JS/TypeScript (safe access)

```ts
const comment = cargo.data?.extra?.note || "";
```

### Python (safe access)

```python
cargo_data = payload.get("data", {})
comment = (cargo_data.get("extra") or {}).get("note") or ""
```

### TypeScript types (extra object: 10 fields)

```ts
export interface CargoExtra {
  note: string | null;
  external_inn: string | null;
  custom_cargo_type: string | null;
  integrate: unknown | null;
  is_delete_from_archive: boolean;
  krugoreis: boolean;
  partial_load: boolean;
  note_valid: boolean;
  integrate_contacts: unknown | null;
  url: string | null;
}

export interface CargoDetailResponse {
  data: {
    extra?: CargoExtra | null;
  } & Record<string, unknown>;
}
```

---

## 7) Где это связано с актуальными контрактами v3.2

- Контракты (что именно должно быть реализовано): `API_CONTRACTS_v3.2.md`
- Полные контракты/архитектура: `FINAL_PROJECT_DOCUMENTATION_v3.2.md` (Часть 5)
- Deprecated‑источники (история решений + контекст): `docs/[DEPRECATED]_risk_analysis_final.md`, `docs/[DEPRECATED]_summary_of_changes.md`, `docs/[DEPRECATED]_package_readme.md`
