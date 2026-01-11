from __future__ import annotations

from django.shortcuts import render
from django.http import HttpResponse

from apps.auth.decorators import require_driver
from apps.cargos.services import CargoService
from apps.core.exceptions import ExternalServiceError, NotFoundError, ValidationError as AppValidationError
from apps.core.schemas import CargoListRequest, CargoDetailRequest
from apps.core.validation import validate_query_params
from apps.filtering.services import FilterService

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
    size = int(meta.get("size") or 0)
    next_offset = offset + limit if size == limit else None

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
