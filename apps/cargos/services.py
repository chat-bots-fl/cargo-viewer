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
  str - Formatted RUB string (e.g., \"352 500 руб\") or \"—\" - Never None

RAISES:
  None

GUARANTEES:
  - Uses space as thousands separator
  - Uses comma as decimal separator
  - Trims trailing \",00\"
"""
def _format_rub(price_kop: int | None) -> str:
    if not price_kop:
        return "—"
    rub = (Decimal(int(price_kop)) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    s = f"{rub:,.2f}".replace(",", " ").replace(".", ",")
    if s.endswith(",00"):
        s = s[:-3]
    return f"{s} руб"


"""
GOAL: Parse CargoTech ISO-8601 datetime string into a naive datetime preserving the source clock time.

PARAMETERS:
  value: str | None - CargoTech datetime string (may end with 'Z') - Can be empty/None

RETURNS:
  datetime | None - Parsed naive datetime or None when value is missing/invalid

RAISES:
  None

GUARANTEES:
  - Never raises on malformed input (returns None)
  - Returned datetime is naive (tzinfo is None), so templates show time like on CargoTech
"""
def _parse_cargotech_datetime(value: str | None) -> datetime | None:
    """
    Parse ISO-8601 and drop tzinfo to avoid Django timezone conversion in templates.
    """
    if not value:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    try:
        if normalized.endswith("Z"):
            normalized = normalized[:-1]
        parsed = datetime.fromisoformat(normalized)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        return None


"""
GOAL: Format cargo weight/volume pair to a compact display string.

PARAMETERS:
  weight_kg: int | float | None - Weight in kilograms - >= 0, None/0 means missing
  volume_m3: int | float | None - Volume in cubic meters - >= 0, None/0 means missing

RETURNS:
  str - Display string like \"20,000 т / 86 м³\" or \"\" - Never None

RAISES:
  None

GUARANTEES:
  - Tonnes formatted with 3 decimals and comma decimal separator
  - Omits missing parts (weight or volume) without extra separators
"""
def _format_wv(weight_kg: int | float | None, volume_m3: int | float | None) -> str:
    """
    Convert kilograms to tonnes (3 decimals) and format volume without trailing .0.
    """
    parts: list[str] = []

    if isinstance(weight_kg, (int, float)) and weight_kg:
        tonnes = (Decimal(str(weight_kg)) / Decimal(1000)).quantize(
            Decimal("0.001"),
            rounding=ROUND_HALF_UP,
        )
        tonnes_str = f"{tonnes:,.3f}".replace(",", " ").replace(".", ",")
        parts.append(f"{tonnes_str} т")

    if isinstance(volume_m3, (int, float)) and volume_m3:
        volume = Decimal(str(volume_m3))
        if volume == volume.to_integral():
            volume_str = str(int(volume))
        else:
            volume_str = str(volume.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)).replace(".", ",")
        parts.append(f"{volume_str} м³")

    return " / ".join(parts)


"""
GOAL: Normalize a phone string for use in tel: links.

PARAMETERS:
  phone: str | None - Phone number string (may include spaces/brackets/dashes) - Can be empty/None

RETURNS:
  str - Normalized phone (digits and leading '+') suitable for tel: or empty string - Never None

RAISES:
  None

GUARANTEES:
  - Keeps only digits and an optional leading '+'
  - Converts leading '8' to '+7' when length suggests RU phone
  - Never raises on unexpected input (returns empty string)
"""
def _normalize_phone_for_tel(phone: str | None) -> str:
    """
    Strip formatting characters and keep digits with optional leading plus for tel: usage.
    """
    if not phone:
        return ""

    raw = str(phone).strip()
    if not raw:
        return ""

    cleaned = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if not cleaned:
        return ""

    if cleaned.startswith("8") and len(cleaned) == 11:
        return f"+7{cleaned[1:]}"

    if cleaned.startswith("+"):
        return cleaned

    return f"+{cleaned}" if len(cleaned) >= 11 else cleaned


class CargoService:
    CACHE_TIMEOUT_LIST = 300  # 5 minutes
    CACHE_TIMEOUT_DETAIL = 900  # 15 minutes
    CACHE_KEY_VERSION_LIST = "v2"
    CACHE_KEY_VERSION_DETAIL = "v3"

    """
    GOAL: Format a CargoTech cargo card to a UI-friendly structure for templates.

    PARAMETERS:
      cargo: Mapping[str, Any] - Raw cargo item from /v2/cargos/views - Must include id and points

    RETURNS:
      dict[str, Any] - UI-ready card fields for list templates - Never None

    RAISES:
      None (missing fields become empty strings)

    GUARANTEES:
      - Does not raise on missing optional fields
      - Includes display fields (price_display, wv_display) for templates
    """
    @staticmethod
    def format_cargo_card(cargo: Mapping[str, Any]) -> dict[str, Any]:
        """
        Normalize CargoCardDTO fields and enrich with display-ready values for templates.
        """
        cargo_id = str(cargo.get("id") or "")
        start_city = safe_get(cargo, "points", "start", "city", "name", default="")
        finish_city = safe_get(cargo, "points", "finish", "city", "name", default="")
        title = " → ".join([s for s in [start_city, finish_city] if s]) or cargo_id

        start_date = safe_get(cargo, "points", "start", "first_date", default="")
        finish_date = safe_get(cargo, "points", "finish", "first_date", default="")
        loading_date = _parse_cargotech_datetime(start_date)
        unloading_date = _parse_cargotech_datetime(finish_date)

        weight = cargo.get("weight")
        volume = cargo.get("volume")

        load_types = cargo.get("load_types") or []
        truck_types = cargo.get("truck_types") or []
        load_name = safe_get(load_types[0], "name", default="") if isinstance(load_types, list) and load_types else ""
        load_short = safe_get(load_types[0], "short_name", default="") if isinstance(load_types, list) and load_types else ""
        truck_name = safe_get(truck_types[0], "name", default="") if isinstance(truck_types, list) and truck_types else ""
        truck_short = safe_get(truck_types[0], "short_name", default="") if isinstance(truck_types, list) and truck_types else ""

        price_kop = cargo.get("price_carrier") or cargo.get("price")

        card = dto_to_dict(
            CargoCardDTO(
                id=int(cargo_id) if cargo_id.isdigit() else 0,
                cargo_id=cargo_id,
                title=title,
                route_from=start_city,
                route_to=finish_city,
                distance=cargo.get("distance"),
                price=Decimal(str(price_kop)) / Decimal(100) if price_kop else None,
                cargo_type=load_short,
                weight=float(weight) if weight else None,
                volume=float(volume) if volume else None,
                loading_date=loading_date,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        card.update(
            {
                "unloading_date": unloading_date,
                "price_display": _format_rub(price_kop),
                "wv_display": _format_wv(weight, volume),
                "truck_type": truck_name or truck_short,
                "loading_type": load_short or load_name,
            }
        )
        return card

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
        cache_key = f"user:{user_id}:cargos:{cls.CACHE_KEY_VERSION_LIST}:{filter_hash}"
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

        cache_key = f"cargo:{cargo_id}:detail:{cls.CACHE_KEY_VERSION_DETAIL}"
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
        title = " → ".join([s for s in [start_city, finish_city] if s]) or cargo_id

        start_addr = safe_get(data, "points", "start", "address", default="")
        finish_addr = safe_get(data, "points", "finish", "address", default="")
        start_date = safe_get(data, "points", "start", "first_date", default="")
        finish_date = safe_get(data, "points", "finish", "first_date", default="")

        comment = safe_get(data, "extra", "note", default="") or ""
        shipper_name = safe_get(data, "shipper", "name", default="")
        shipper_inn = safe_get(data, "shipper", "inn", default="")

        load_types = data.get("load_types") or []
        truck_types = data.get("truck_types") or []
        load_name = safe_get(load_types[0], "name", default="") if isinstance(load_types, list) and load_types else ""
        load_short = safe_get(load_types[0], "short_name", default="") if isinstance(load_types, list) and load_types else ""
        truck_name = safe_get(truck_types[0], "name", default="") if isinstance(truck_types, list) and truck_types else ""
        truck_short = safe_get(truck_types[0], "short_name", default="") if isinstance(truck_types, list) and truck_types else ""
        cargo_type_name = (
            str(safe_get(data, "extra", "custom_cargo_type", default="") or "").strip()
            or safe_get(data, "cargo_type", "name", default="")
            or ""
        )

        company_name = safe_get(data, "company", "name", default="") or ""
        contacts_person_name = ""
        contacts_phone = ""
        contacts = data.get("contacts") or []
        if isinstance(contacts, list):
            preferred = [c for c in contacts if isinstance(c, dict) and (c.get("type") in {"broker", "company"})]
            others = [c for c in contacts if c not in preferred]
            for contact in preferred + others:
                if not isinstance(contact, dict):
                    continue
                name = str(contact.get("name") or "").strip()
                phone = ""
                phones = contact.get("phones")
                if isinstance(phones, list):
                    for p in phones:
                        p_str = str(p or "").strip()
                        if p_str:
                            phone = p_str
                            break
                if not phone:
                    phone = str(contact.get("phone") or "").strip()

                if name or phone:
                    contacts_person_name = name
                    contacts_phone = phone
                    break

        weight = data.get("weight")
        volume = data.get("volume")
        loading_date = _parse_cargotech_datetime(start_date)
        unloading_date = _parse_cargotech_datetime(finish_date)

        price_kop = data.get("price_carrier") or data.get("price")

        detail = dto_to_dict(
            CargoDetailDTO(
                id=int(cargo_id) if cargo_id.isdigit() else 0,
                cargo_id=cargo_id,
                title=title,
                description=comment,
                route_from=start_city,
                route_to=finish_city,
                distance=data.get("distance"),
                price=Decimal(str(price_kop)) / Decimal(100) if price_kop else None,
                cargo_type=cargo_type_name or None,
                weight=float(data.get("weight")) if data.get("weight") else None,
                volume=float(data.get("volume")) if data.get("volume") else None,
                loading_date=loading_date,
                unloading_date=unloading_date,
                loading_address=start_addr,
                unloading_address=finish_addr,
                requirements=[],
                contact_phone="",
                contact_name=shipper_name,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        detail.update(
            {
                "price_display": _format_rub(price_kop),
                "wv_display": _format_wv(weight, volume),
                "truck_type": truck_name or truck_short,
                "loading_type": load_short or load_name,
                "shipper_inn": shipper_inn,
                "contacts_company_name": company_name,
                "contacts_person_name": contacts_person_name,
                "contacts_phone": contacts_phone,
                "contacts_phone_tel": _normalize_phone_for_tel(contacts_phone),
            }
        )
        return detail
