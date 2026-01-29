from __future__ import annotations

from django.shortcuts import render
from django.http import HttpResponse

from apps.auth.decorators import require_driver
from apps.cargos.services import CargoService
from apps.core.exceptions import ExternalServiceError, NotFoundError, ValidationError as AppValidationError
from apps.core.schemas import CargoListRequest, CargoDetailRequest
from apps.core.validation import validate_query_params
from apps.filtering.services import FilterService
from apps.integrations.cargotech_client import CargoAPIClient

# Import for OpenAPI documentation (graceful degradation if not available)
try:
    from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
    from drf_spectacular.types import OpenApiTypes
    DRF_SPECTACULAR_AVAILABLE = True
except ImportError:
    DRF_SPECTACULAR_AVAILABLE = False
    # Fallback decorators that do nothing
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    class OpenApiExample:
        pass
    class OpenApiResponse:
        pass
    class OpenApiTypes:
        STR = str
        OBJECT = dict


"""
GOAL: Render the main WebApp shell page (Django template + HTMX).

PARAMETERS:
  request: HttpRequest - Any request - No auth required to render shell

RETURNS:
  HttpResponse - Rendered main.html

RAISES:
  None

GUARANTEES:
  - Does not perform API calls (JS/HTMX loads data after auth)
"""
def webapp_home(request):
    return render(request, "main.html")


"""
GOAL: Return cargo list HTML partial for HTMX requests with validated filters and caching.

PARAMETERS:
  request: HttpRequest - Authenticated driver request - Query params include filters/limit/offset

RETURNS:
  HttpResponse - Rendered template with cargo cards - HTTP 200

RAISES:
  None (validation errors return HTTP 400)

GUARANTEES:
  - Requires driver session (JWT)
  - Uses CargoService cache-through fetching
"""
@require_driver
@extend_schema(
    tags=["cargos"],
    summary="Получить список грузов",
    description=(
        "Возвращает HTML-фрагмент со списком грузов для HTMX. "
        "Поддерживает фильтрацию, пагинацию и кэширование."
    ),
    parameters=[
        {
            "name": "limit",
            "type": int,
            "description": "Количество грузов на странице (по умолчанию 20)",
            "required": False,
        },
        {
            "name": "offset",
            "type": int,
            "description": "Смещение для пагинации (по умолчанию 0)",
            "required": False,
        },
        {
            "name": "city_from",
            "type": str,
            "description": "Город отправления",
            "required": False,
        },
        {
            "name": "city_to",
            "type": str,
            "description": "Город назначения",
            "required": False,
        },
        {
            "name": "date_from",
            "type": str,
            "description": "Дата погрузки с (YYYY-MM-DD)",
            "required": False,
        },
        {
            "name": "date_to",
            "type": str,
            "description": "Дата погрузки по (YYYY-MM-DD)",
            "required": False,
        },
        {
            "name": "weight_min",
            "type": int,
            "description": "Минимальный вес (кг)",
            "required": False,
        },
        {
            "name": "weight_max",
            "type": int,
            "description": "Максимальный вес (кг)",
            "required": False,
        },
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-фрагмент с карточками грузов",
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка валидации",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
    },
)
def cargo_list_partial(request):
    """
    Validate filters, build CargoTech query params, fetch cached list, and render list template.
    """
    try:
        validated = validate_query_params(CargoListRequest, request.GET.dict())
        limit = validated.limit
        offset = validated.offset
    except AppValidationError as exc:
        raise exc

    try:
        filters = FilterService.validate_filters(request.GET.dict())
        api_params = FilterService.build_query(filters, limit=limit, offset=offset)
        user_id = int(request.user.id)
        result = CargoService.get_cargos(user_id=user_id, api_params=api_params)
    except AppValidationError as exc:
        raise exc

    cards = result.get("cards") or []
    meta = result.get("meta") or {}
    total_size = int(meta.get("size") or 0)
    page_size = len(cards)
    loaded_count = (offset + page_size) if page_size > 0 else int(offset)
    if total_size > 0:
        loaded_count = min(total_size, loaded_count)
    if page_size <= 0:
        next_offset = None
    elif total_size > 0:
        next_offset = (offset + page_size) if (offset + page_size) < total_size else None
    else:
        next_offset = (offset + page_size) if page_size == limit else None

    if next_offset is not None:
        try:
            prefetch_params = dict(api_params)
            prefetch_params["offset"] = int(next_offset)
            CargoService.prefetch_cargos(user_id=user_id, api_params=prefetch_params)
        except Exception:
            pass

    qs = request.GET.copy()
    qs.pop("offset", None)
    qs.pop("limit", None)
    base_query = qs.urlencode()

    template = "cargos/cargo_list_append.html" if offset > 0 else "cargos/cargo_list.html"
    return render(
        request,
        template,
        {
            "cards": cards,
            "meta": meta,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
            "loaded_count": loaded_count,
            "total_count": total_size,
            "base_query": base_query,
        },
    )


"""
GOAL: Return a lightweight HTMX fragment that updates only cargo price elements (OOB) for periodic UI refresh.

PARAMETERS:
  request: HttpRequest - Authenticated driver request - Query params include filters + optional limit

RETURNS:
  HttpResponse - HTML fragment with hx-swap-oob updates (prices + optional deletions) - HTTP 200

RAISES:
  None (validation errors return HTTP 400; upstream errors degrade to empty response)

GUARANTEES:
  - Requires driver session (JWT)
  - Does not re-render cargo cards list (only OOB updates specific nodes by id)
  - Removes unavailable cargos from DOM when they disappear from CargoTech listing
  - Never raises on upstream API errors (returns empty fragment)
"""
@require_driver
@extend_schema(
    tags=["cargos"],
    summary="Обновить цены в списке грузов (HTMX OOB)",
    description=(
        "Возвращает HTML-фрагмент для HTMX с `hx-swap-oob`, который обновляет только цены "
        "по `id=cargo-price-<cargo_id>` без перерисовки списка и без сброса прокрутки."
    ),
    parameters=[
        {
            "name": "limit",
            "type": int,
            "description": "Сколько карточек (с начала списка) обновить (1..100). Обычно = числу отображаемых карточек.",
            "required": False,
        },
        {
            "name": "seen_ids",
            "type": str,
            "description": "CSV cargo_id, которые сейчас отображаются в DOM (для удаления пропавших из выдачи).",
            "required": False,
        },
        {
            "name": "mode",
            "type": str,
            "description": "Режим списка: my/all",
            "required": False,
        },
    ],
    responses={
        200: OpenApiResponse(response=OpenApiTypes.STR, description="HTML-фрагмент с OOB-элементами цен"),
        400: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Ошибка валидации query params"),
        401: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Требуется аутентификация"),
    },
)
def cargo_prices_oob_partial(request):
    """
    Fetch CargoTech listing to update price spans and delete missing cards via HTMX OOB swaps.
    """

    """
    GOAL: Parse and validate a comma-separated list of cargo ids coming from the WebApp DOM.

    PARAMETERS:
      raw: str | None - Raw query string value - Can be empty/None
      max_items: int - Maximum ids to keep - Must be >= 1

    RETURNS:
      list[str] - Normalized cargo ids (digits-only), deduplicated preserving order - Never None

    RAISES:
      None

    GUARANTEES:
      - Only returns ids containing digits (0-9)
      - Output length <= max_items
      - Preserves first occurrence order
    """
    def _parse_seen_ids(raw: str | None, *, max_items: int = 200) -> list[str]:
        """
        Split CSV, keep digits-only ids, dedupe while preserving order, and cap the output length.
        """
        if not raw:
            return []
        if max_items < 1:
            return []

        out: list[str] = []
        seen: set[str] = set()
        for part in str(raw).split(","):
            s = str(part).strip()
            if not s or not s.isdigit():
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= max_items:
                break
        return out

    try:
        validated = validate_query_params(CargoListRequest, request.GET.dict())
        page_limit = validated.limit
    except AppValidationError as exc:
        raise exc

    try:
        filters = FilterService.validate_filters(request.GET.dict())
        seen_ids = _parse_seen_ids(request.GET.get("seen_ids"), max_items=200)
        if not seen_ids:
            return HttpResponse("", content_type="text/html; charset=utf-8")

        scan_limit = 100
        max_pages = 3
        all_cards_by_id: dict[str, dict[str, Any]] = {}
        missing_ids = list(seen_ids)
        total_count = 0
        scan_complete = True

        for page_idx in range(max_pages):
            api_params = FilterService.build_query(filters, limit=scan_limit, offset=page_idx * scan_limit)
            try:
                payload = CargoAPIClient.fetch_cargos(api_params)
            except Exception:
                if page_idx == 0:
                    raise
                scan_complete = False
                break
            meta = payload.get("meta") or {}
            if page_idx == 0:
                total_count = int(meta.get("size") or 0)

            data = payload.get("data") or []
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    cargo_id = str(item.get("id") or "").strip()
                    if not cargo_id:
                        continue
                    all_cards_by_id[cargo_id] = CargoService.format_cargo_card(item)

            if not seen_ids:
                break

            missing_ids = [cid for cid in seen_ids if cid not in all_cards_by_id]
            if not missing_ids:
                break

            # Stop if we've exhausted the upstream result set (meta.size may be absent/0 in some cases).
            if total_count and (page_idx + 1) * scan_limit >= total_count:
                break
    except Exception:
        return HttpResponse("", content_type="text/html; charset=utf-8")

    # If we couldn't scan enough (e.g. partial upstream failure), never delete cards based on incomplete evidence.
    if not scan_complete:
        missing_ids = []

    price_cards = [all_cards_by_id[cid] for cid in seen_ids if cid in all_cards_by_id]

    loaded_count = max(0, len(seen_ids) - len(missing_ids))
    if total_count > 0 and loaded_count > 0 and loaded_count < total_count:
        next_offset: int | None = loaded_count
    else:
        next_offset = None

    qs = request.GET.copy()
    for key in ("offset", "limit", "seen_ids", "_rid"):
        qs.pop(key, None)
    base_query = qs.urlencode()

    return render(
        request,
        "cargos/cargo_prices_oob.html",
        {
            "price_cards": price_cards,
            "missing_ids": missing_ids,
            "limit": page_limit,
            "next_offset": next_offset,
            "loaded_count": loaded_count,
            "total_count": total_count,
            "base_query": base_query,
        },
    )


"""
GOAL: Return cargo detail HTML partial (modal body) for a specific cargo id.

PARAMETERS:
  request: HttpRequest - Authenticated driver request - Must include cargo_id in path
  cargo_id: str - CargoTech cargo id - Must be non-empty

RETURNS:
  HttpResponse - Rendered cargo detail template - HTTP 200

RAISES:
  None (errors return HTTP 400/502)

GUARANTEES:
  - Requires driver session (JWT)
  - Uses CargoService cached detail (15 min) with fallback when possible
"""
@require_driver
@extend_schema(
    tags=["cargos"],
    summary="Получить детали груза",
    description=(
        "Возвращает HTML-фрагмент с детальной информацией о грузе для модального окна. "
        "Использует кэширование (15 минут) с fallback при недоступности."
    ),
    parameters=[
        {
            "name": "cargo_id",
            "type": str,
            "description": "ID груза в системе CargoTech",
            "required": True,
            "in": "path",
        },
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-фрагмент с деталями груза",
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка валидации cargo_id",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Груз не найден",
        ),
        502: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка внешнего сервиса",
        ),
    },
)
def cargo_detail_partial(request, cargo_id: str):
    """
    Fetch cargo detail (cached) and render modal content.
    """
    try:
        validated = CargoDetailRequest(cargo_id=cargo_id)
        cargo_id = validated.cargo_id
    except Exception as exc:
        raise AppValidationError(f"Invalid cargo_id: {str(exc)}")

    try:
        detail = CargoService.get_cargo_detail(cargo_id=cargo_id)
    except NotFoundError:
        raise
    except Exception as exc:
        raise ExternalServiceError(f"Failed to fetch cargo detail: {str(exc)}")

    return render(request, "cargos/cargo_detail.html", {"cargo": detail})
