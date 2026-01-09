from __future__ import annotations

import re
from datetime import date
from typing import Any

from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.core.schemas import FilterRequest
from apps.core.validation import validate_request_body
from apps.integrations.cargotech_client import CargoAPIClient


class FilterService:
    WV_PATTERN = re.compile(r"^\d+(\.\d+)?-\d+(\.\d+)?$")

    """
    GOAL: Validate and normalize the weight/volume filter to CargoTech filter[wv] format.

    PARAMETERS:
      value: str - UI input value "{weight}-{volume}" - Empty/\"any\" disables the filter

    RETURNS:
      dict[str, str] - {"filter[wv]": value} when enabled, else {} - Never None

    RAISES:
      ValidationError: If format invalid or values outside reasonable ranges

    GUARANTEES:
      - Accepts decimals (HAR-validated)
      - Does not coerce formatting beyond validation (pass-through value)
    """
    @staticmethod
    def validate_weight_volume(value: str) -> dict[str, str]:
        """
        Validate "{weight}-{volume}" with decimals and sanity ranges; return CargoTech filter mapping.
        """
        value = str(value or "").strip()
        if not value or value == "any":
            return {}

        if not FilterService.WV_PATTERN.match(value):
            raise ValidationError(
                f"Invalid weight_volume format: '{value}'. Expected '{{weight}}-{{volume}}', e.g. '15-65' or '1.5-9'."
            )

        weight_s, volume_s = value.split("-", 1)
        weight_val = float(weight_s)
        volume_val = float(volume_s)

        if not (0.1 <= weight_val <= 1000):
            raise ValidationError(f"Weight {weight_val} out of range (0.1-1000)")
        if not (0.1 <= volume_val <= 200):
            raise ValidationError(f"Volume {volume_val} out of range (0.1-200)")

        return {"filter[wv]": value}

    """
    GOAL: Validate incoming WebApp filter query parameters into a normalized dict.

    PARAMETERS:
      raw: dict[str, Any] - Query params from request.GET - Can include empty strings

    RETURNS:
      dict[str, Any] - Normalized filters (ints, strings) - Never None

    RAISES:
      ValidationError: If any filter value is invalid

    GUARANTEES:
      - Supports combining multiple filters
      - Does not allow SQL injection (only typed/validated values returned)
    """
    @staticmethod
    def validate_filters(raw: dict[str, Any]) -> dict[str, Any]:
        """
        Parse common filter inputs (ids, date, wv, csv ids) into normalized primitives.
        Uses Pydantic schema for validation while maintaining backward compatibility.
        """
        try:
            validated = validate_request_body(FilterRequest, raw)
            # Convert validated object to dict for backward compatibility
            out = validated.model_dump(exclude_none=True)
            return out
        except Exception as exc:
            # Re-raise as Django ValidationError for backward compatibility
            raise ValidationError(str(exc)) from exc

    """
    GOAL: Build CargoTech API query parameters from validated filters (HAR-aligned).

    PARAMETERS:
      filters: dict[str, Any] - Normalized filters from validate_filters - Can be empty
      limit: int - Pagination limit - Must be within [1, 100], default 20
      offset: int - Pagination offset - Must be >= 0, default 0

    RETURNS:
      dict[str, Any] - Query params for /v2/cargos/views - Never None

    RAISES:
      ValidationError: If filters invalid (wv/date/ids)

    GUARANTEES:
      - Always includes required params: include, limit, offset, filter[mode], filter[user_id]
      - Adds *_point_type when *_point_id is present
    """
    @staticmethod
    def build_query(filters: dict[str, Any], *, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """
        Merge defaults with optional filters and map UI fields to CargoTech filter[...] params.
        """
        if limit < 1 or limit > 100:
            raise ValidationError("limit must be within [1, 100]")
        if offset < 0:
            raise ValidationError("offset must be >= 0")

        params: dict[str, Any] = {
            "include": "contacts",
            "limit": int(limit),
            "offset": int(offset),
            "filter[mode]": filters.get("mode") or "my",
            "filter[user_id]": 0,
        }

        if "start_point_id" in filters:
            params["filter[start_point_id]"] = int(filters["start_point_id"])
            params["filter[start_point_type]"] = 1
            params["filter[start_point_radius]"] = 50
        if "finish_point_id" in filters:
            params["filter[finish_point_id]"] = int(filters["finish_point_id"])
            params["filter[finish_point_type]"] = 1
            params["filter[finish_point_radius]"] = 50

        if "start_date" in filters:
            params["filter[start_date]"] = str(filters["start_date"])

        if "weight_volume" in filters:
            params.update(FilterService.validate_weight_volume(str(filters["weight_volume"])))

        if "load_types" in filters:
            params["filter[load_types]"] = str(filters["load_types"])
        if "truck_types" in filters:
            params["filter[truck_types]"] = str(filters["truck_types"])

        return params


class DictionaryService:
    CACHE_TTL_SECONDS = 86400

    """
    GOAL: Search cities by name with Redis caching for autocomplete.

    PARAMETERS:
      query: str - User-entered prefix - Can be empty
      limit: int - Max items - 1..50, default 10

    RETURNS:
      list[dict[str, Any]] - Items like {id, name, type} - Never None

    RAISES:
      None (API errors return empty list)

    GUARANTEES:
      - Cached per normalized query (lowercased/stripped)
      - Cache TTL ~24h
    """
    @staticmethod
    def search_cities(query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """
        Cache-through autocomplete: returns cached list or fetches from CargoTech dictionaries endpoint.
        """
        q = str(query or "").strip().lower()
        cache_key = f"cities:{q}:{int(limit)}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            payload = CargoAPIClient.search_cities(q, limit=limit, offset=0)
            items = payload.get("data") or []
            result = items if isinstance(items, list) else []
            cache.set(cache_key, result, timeout=DictionaryService.CACHE_TTL_SECONDS)
            return result
        except Exception:
            return []

