from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Any, Mapping, Optional, List

from django.core.cache import cache

from apps.cargos.serializers import safe_get
from apps.core.dtos import (
    CargoCardDTO,
    CargoDetailDTO,
    dto_to_dict,
)
from apps.integrations.cargotech_client import CargoAPIClient

logger = logging.getLogger(__name__)


"""
GOAL: Produce a stable hash for JSON-serializable values (used for cache keys).

PARAMETERS:
  value: Any - JSON-serializable object - Must be deterministic after sorting keys

RETURNS:
  str - Hex md5 hash of stable JSON representation - Never empty

RAISES:
  TypeError: If value is not JSON-serializable

GUARANTEES:
  - Same input structure produces same hash (stable ordering)
"""
def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


"""
GOAL: Format CargoTech integer price in коп into a human-readable RUB string.

PARAMETERS:
  price_kop: int | None - Price in kopecks - None or 0 treated as missing

RETURNS:
  str - Formatted RUB string (e.g., \"352 500 ₽\") or \"—\" - Never None

RAISES:
  None

GUARANTEES:
  - Rounds to 2 decimals and trims trailing .00
"""
def _format_rub(price_kop: int | None) -> str:
    if not price_kop:
        return "—"
    rub = (Decimal(int(price_kop)) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{rub:,.2f}".replace(",", " ")
    if s.endswith(".00"):
        s = s[:-3]
    return f"{s} ₽"


class CargoService:
    CACHE_TIMEOUT_LIST = 300  # 5 minutes
    CACHE_TIMEOUT_DETAIL = 900  # 15 minutes

    """
    GOAL: Format a CargoTech cargo card to a UI-friendly structure for templates.

    PARAMETERS:
      cargo: Mapping[str, Any] - Raw cargo item from /v2/cargos/views - Must include id and points

    RETURNS:
      dict[str, Any] - UI-ready card fields (id, route, date, wv, price, pills) - Never None

    RAISES:
      None (missing fields become empty strings)

    GUARANTEES:
      - Does not raise on missing optional fields
      - Price formatted in RUB from коп
    """
    @staticmethod
    def format_cargo_card(cargo: Mapping[str, Any]) -> dict[str, Any]:
        """
        Extract route/date and format price/metrics into concise UI strings.
        """
        cargo_id = str(cargo.get("id") or "")
        start_city = safe_get(cargo, "points", "start", "city", "name", default="")
        finish_city = safe_get(cargo, "points", "finish", "city", "name", default="")
        route = " → ".join([s for s in [start_city, finish_city] if s]) or cargo_id

        start_date = safe_get(cargo, "points", "start", "first_date", default="")

        weight = cargo.get("weight")
        volume = cargo.get("volume")
        weight_t = ""
        if isinstance(weight, (int, float)) and weight:
            weight_t = f"{(Decimal(str(weight)) / Decimal(1000)).quantize(Decimal('0.1'))} т"
        volume_m3 = f"{volume} м³" if isinstance(volume, (int, float)) and volume else ""
        wv = " / ".join([x for x in [weight_t, volume_m3] if x]) or ""

        load_types = cargo.get("load_types") or []
        truck_types = cargo.get("truck_types") or []
        load_short = safe_get(load_types[0], "short_name", default="") if isinstance(load_types, list) and load_types else ""
        truck_short = safe_get(truck_types[0], "short_name", default="") if isinstance(truck_types, list) and truck_types else ""
        pills = [p for p in [load_short, truck_short] if p]

        return dto_to_dict(
            CargoCardDTO(
                id=int(cargo_id) if cargo_id.isdigit() else 0,
                cargo_id=cargo_id,
                title=route,
                route_from=start_city,
                route_to=finish_city,
                distance=cargo.get("distance"),
                price=Decimal(str(cargo.get("price", 0))) / Decimal(100) if cargo.get("price") else None,
                cargo_type=load_short,
                weight=float(weight) if weight else None,
                volume=float(volume) if volume else None,
                loading_date=datetime.fromisoformat(start_date) if start_date else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

    """
    GOAL: Get cargo list for a user with caching, fetching from CargoTech on cache miss.

    PARAMETERS:
      user_id: int - Django user id - Must be > 0
      api_params: dict[str, Any] - CargoTech query params - Must be JSON-serializable

    RETURNS:
      dict[str, Any] - {"cards": list[dict], "meta": dict} - Never None

    RAISES:
      Exception: Propagates unexpected errors when no cached fallback exists

    GUARANTEES:
      - Cache key is per-user + stable hash of api_params
      - On API failure, returns cached result when available
    """
    @classmethod
    def get_cargos(cls, *, user_id: int, api_params: dict[str, Any]) -> dict[str, Any]:
        """
        Cache-through strategy: prefer Redis cached list; fetch from API and store on miss.
        """
        if user_id <= 0:
            raise ValueError("user_id must be > 0")

        filter_hash = _stable_hash(api_params)
        cache_key = f"user:{user_id}:cargos:{filter_hash}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            payload = CargoAPIClient.fetch_cargos(api_params)
            data = payload.get("data") or []
            cards = [cls.format_cargo_card(item) for item in data] if isinstance(data, list) else []
            result = {"cards": cards, "meta": payload.get("meta") or {}}
            cache.set(cache_key, result, timeout=cls.CACHE_TIMEOUT_LIST)
            return result
        except Exception as exc:
            logger.warning("Cargo list fetch failed: %s", exc)
            if cached:
                return cached
            raise

    """
    GOAL: Get cargo detail with caching (detail endpoint includes comment field).

    PARAMETERS:
      cargo_id: str - CargoTech cargo id - Must be non-empty

    RETURNS:
      dict[str, Any] - UI-ready detail payload - Never None

    RAISES:
      Exception: Propagates when no cached fallback exists

    GUARANTEES:
      - Uses Redis cache key cargo:{id}:detail with TTL ~15 min
      - On API failure, returns cached detail when available
    """
    @classmethod
    def get_cargo_detail(cls, *, cargo_id: str) -> dict[str, Any]:
        """
        Cache-through detail fetch with safe field extraction and fallback to cached data.
        """
        cargo_id = str(cargo_id).strip()
        if not cargo_id:
            raise ValueError("cargo_id is required")

        cache_key = f"cargo:{cargo_id}:detail"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            payload = CargoAPIClient.fetch_cargo_detail(cargo_id)
            data = payload.get("data") or {}
            result = cls._format_detail(data)
            cache.set(cache_key, result, timeout=cls.CACHE_TIMEOUT_DETAIL)
            return result
        except Exception as exc:
            logger.warning("Cargo detail fetch failed: %s", exc)
            if cached:
                return cached
            raise

    """
    GOAL: Convert CargoTech cargo detail payload into template-friendly fields.

    PARAMETERS:
      data: Mapping[str, Any] - CargoTech detail `data` object - Must be dict-like

    RETURNS:
      dict[str, Any] - Normalized detail fields for templates - Never None

    RAISES:
      None (missing fields become empty strings)

    GUARANTEES:
      - Safely extracts comment from extra.note
      - Does not raise on missing optional fields
    """
    @staticmethod
    def _format_detail(data: Mapping[str, Any]) -> dict[str, Any]:
        """
        Convert CargoTech detail payload into template-friendly fields.
        """
        cargo_id = str(data.get("id") or "")
        start_city = safe_get(data, "points", "start", "city", "name", default="")
        finish_city = safe_get(data, "points", "finish", "city", "name", default="")
        route = " → ".join([s for s in [start_city, finish_city] if s]) or cargo_id

        start_addr = safe_get(data, "points", "start", "address", default="")
        finish_addr = safe_get(data, "points", "finish", "address", default="")
        start_date = safe_get(data, "points", "start", "first_date", default="")
        finish_date = safe_get(data, "points", "finish", "first_date", default="")

        comment = safe_get(data, "extra", "note", default="") or ""
        shipper_name = safe_get(data, "shipper", "name", default="")
        shipper_inn = safe_get(data, "shipper", "inn", default="")

        return dto_to_dict(
            CargoDetailDTO(
                id=int(cargo_id) if cargo_id.isdigit() else 0,
                cargo_id=cargo_id,
                title=route,
                description=comment,
                route_from=start_city,
                route_to=finish_city,
                distance=data.get("distance"),
                price=Decimal(str(data.get("price", 0))) / Decimal(100) if data.get("price") else None,
                cargo_type="",
                weight=float(data.get("weight")) if data.get("weight") else None,
                volume=float(data.get("volume")) if data.get("volume") else None,
                loading_date=datetime.fromisoformat(start_date) if start_date else None,
                unloading_date=datetime.fromisoformat(finish_date) if finish_date else None,
                loading_address=start_addr,
                unloading_address=finish_addr,
                requirements=[],
                contact_phone="",
                contact_name=shipper_name,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
