from __future__ import annotations

import json
import logging
from typing import Any

from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)


"""
GOAL: Convert cache key values to a stable string representation.

PARAMETERS:
  key: Any - Key value returned by cache/Redis iteration - Usually str or bytes

RETURNS:
  str - Normalized cache key string - Never None

RAISES:
  None

GUARANTEES:
  - Bytes are decoded as UTF-8 with replacement
  - Never raises on unexpected input (falls back to str())
"""
def normalize_cache_key(key: Any) -> str:
    """
    Coerce cache key value to a readable string.
    """
    if isinstance(key, bytes):
        return key.decode("utf-8", errors="replace")
    return str(key)


"""
GOAL: Return a best-effort cache TTL in seconds for a given key.

PARAMETERS:
  key: str - Cache key - Must be non-empty

RETURNS:
  int | None - TTL seconds, or None when unsupported/unknown

RAISES:
  None

GUARANTEES:
  - Never raises on backend differences (returns None)
  - Negative TTL values are normalized to None
"""
def get_cache_ttl_seconds(key: str) -> int | None:
    """
    Use cache.ttl() when available; otherwise return None.
    """
    if not key:
        return None

    ttl_fn = getattr(cache, "ttl", None)
    if not callable(ttl_fn):
        return None

    try:
        ttl = ttl_fn(key)
    except Exception:
        return None

    if ttl is None:
        return None

    try:
        ttl_int = int(ttl)
    except (TypeError, ValueError):
        return None

    return ttl_int if ttl_int >= 0 else None


"""
GOAL: Iterate cache keys matching a glob pattern with an optional limit.

PARAMETERS:
  pattern: str - Glob-like key pattern (Redis match) - Must be non-empty
  limit: int - Max keys to return - Must be >= 1

RETURNS:
  list[str] - Matching keys (normalized), up to limit - Never None

RAISES:
  ValueError: If pattern is empty or limit < 1

GUARANTEES:
  - Uses SCAN-based iteration when supported (avoids KEYS)
  - Never returns more than limit items
"""
def iter_cache_keys(pattern: str, *, limit: int = 200) -> list[str]:
    """
    Prefer cache.iter_keys() when provided by backend; normalize to list[str].
    """
    pattern = str(pattern or "").strip()
    if not pattern:
        raise ValueError("pattern must be non-empty")
    if limit < 1:
        raise ValueError("limit must be >= 1")

    iter_keys_fn = getattr(cache, "iter_keys", None)
    if not callable(iter_keys_fn):
        return []

    keys: list[str] = []
    try:
        for key in iter_keys_fn(pattern):
            keys.append(normalize_cache_key(key))
            if len(keys) >= limit:
                break
    except Exception:
        return []

    keys.sort()
    return keys


"""
GOAL: Convert a Python value into a readable JSON string for diagnostics UI.

PARAMETERS:
  value: Any - Cached value (may include datetime/Decimal/etc) - Any type
  max_chars: int - Max output length - Must be >= 100

RETURNS:
  str - Pretty JSON (or repr fallback), possibly truncated - Never None

RAISES:
  ValueError: If max_chars < 100

GUARANTEES:
  - Uses DjangoJSONEncoder to handle common Django types
  - Output is always a string suitable for HTML <pre> block
"""
def format_cache_value(value: Any, *, max_chars: int = 50_000) -> str:
    """
    Pretty-print value as JSON with a safe fallback to repr().
    """
    if max_chars < 100:
        raise ValueError("max_chars must be >= 100")

    try:
        text = json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        text = repr(value)

    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n\n... (truncated, total={len(text)} chars)"


"""
GOAL: Summarize a cached CargoService list payload for display in admin tables.

PARAMETERS:
  value: Any - Cached payload (expected dict with cards/meta) - Any type

RETURNS:
  dict[str, Any] - Summary with cards_count/meta_size/sample_ids - Never None

RAISES:
  None

GUARANTEES:
  - Never raises on unexpected payload shape (returns empty/zero summary)
"""
def summarize_cargo_list_cache(value: Any) -> dict[str, Any]:
    """
    Extract counts and a small sample of cargo ids from a cached list payload.
    """
    summary: dict[str, Any] = {"cards_count": 0, "meta_size": None, "sample_cargo_ids": []}
    if not isinstance(value, dict):
        return summary

    cards = value.get("cards") or []
    if isinstance(cards, list):
        summary["cards_count"] = len(cards)
        sample_ids: list[str] = []
        for card in cards[:5]:
            if isinstance(card, dict):
                cargo_id = str(card.get("cargo_id") or card.get("id") or "").strip()
                if cargo_id:
                    sample_ids.append(cargo_id)
        summary["sample_cargo_ids"] = sample_ids

    meta = value.get("meta") or {}
    if isinstance(meta, dict) and "size" in meta:
        try:
            summary["meta_size"] = int(meta.get("size")) if meta.get("size") is not None else None
        except (TypeError, ValueError):
            summary["meta_size"] = None

    return summary


"""
GOAL: Clear CargoService-related cached data for a specific user.

PARAMETERS:
  user_id: int - Django user id - Must be > 0
  include_details: bool - Whether to also clear cargo detail caches referenced by lists
  scan_limit: int - Max list keys to inspect/delete - Must be >= 1
  max_detail_ids: int - Max cargo ids to use for detail invalidation - Must be >= 1

RETURNS:
  dict[str, int] - Counts {"list_keys_deleted", "detail_keys_deleted"} - Never None

RAISES:
  ValueError: If user_id <= 0 or scan_limit/max_detail_ids invalid

GUARANTEES:
  - Only deletes keys under user:{user_id}:cargos:* and cargo:{id}:detail:{version}
  - Never raises on missing keys (delete is idempotent)
"""
def clear_user_cargo_cache(
    *,
    user_id: int,
    include_details: bool = True,
    scan_limit: int = 500,
    max_detail_ids: int = 500,
) -> dict[str, int]:
    """
    Scan per-user cargo list cache keys, delete them, and optionally delete referenced cargo details.
    """
    if user_id <= 0:
        raise ValueError("user_id must be > 0")
    if scan_limit < 1:
        raise ValueError("scan_limit must be >= 1")
    if max_detail_ids < 1:
        raise ValueError("max_detail_ids must be >= 1")

    list_pattern = f"user:{user_id}:cargos:*"
    list_keys = iter_cache_keys(list_pattern, limit=scan_limit)

    cargo_ids: list[str] = []
    if include_details:
        for key in list_keys:
            payload = cache.get(key)
            if not isinstance(payload, dict):
                continue
            cards = payload.get("cards") or []
            if not isinstance(cards, list):
                continue
            for card in cards:
                if not isinstance(card, dict):
                    continue
                cargo_id = str(card.get("cargo_id") or "").strip()
                if cargo_id and cargo_id not in cargo_ids:
                    cargo_ids.append(cargo_id)
                if len(cargo_ids) >= max_detail_ids:
                    break
            if len(cargo_ids) >= max_detail_ids:
                break

    deleted_list = 0
    if list_keys:
        try:
            cache.delete_many(list_keys)
        except Exception:
            for key in list_keys:
                try:
                    cache.delete(key)
                except Exception:
                    pass
        deleted_list = len(list_keys)

    deleted_detail = 0
    if include_details and cargo_ids:
        from apps.cargos.services import CargoService

        detail_keys = [f"cargo:{cid}:detail:{CargoService.CACHE_KEY_VERSION_DETAIL}" for cid in cargo_ids]
        try:
            cache.delete_many(detail_keys)
        except Exception:
            for key in detail_keys:
                try:
                    cache.delete(key)
                except Exception:
                    pass
        deleted_detail = len(detail_keys)

    return {"list_keys_deleted": deleted_list, "detail_keys_deleted": deleted_detail}

