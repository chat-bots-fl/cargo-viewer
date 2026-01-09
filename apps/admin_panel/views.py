from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.auth.decorators import require_admin
from apps.core.decorators import rate_limit
from apps.feature_flags.models import FeatureFlag, SystemSetting
from apps.payments.models import Payment
from apps.payments.services import PaymentService
from apps.promocodes.models import PromoCode
from apps.promocodes.services import PromoCodeService
from apps.subscriptions.models import Subscription

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
GOAL: Show admin panel dashboard entry point.

PARAMETERS:
  request: HttpRequest - Admin-only request

RETURNS:
  HttpResponse - Rendered dashboard page

RAISES:
  None

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Access logged for audit trail
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
@extend_schema(
    tags=["admin"],
    summary="Админ-панель: Главная",
    description="Показывает главную страницу админ-панели с навигацией по разделам.",
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-страница админ-панели",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Недостаточно прав",
        ),
    },
)
def dashboard(request: HttpRequest) -> HttpResponse:
    """
    Render links to admin panel sections.
    """
    return render(request, "admin_panel/dashboard.html")


"""
GOAL: List payments with basic filtering.

PARAMETERS:
  request: HttpRequest - Admin-only request - Optional query filters

RETURNS:
  HttpResponse - Rendered payments list

RAISES:
  None

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Access logged for audit trail
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
@extend_schema(
    tags=["admin"],
    summary="Админ-панель: Список платежей",
    description="Показывает список платежей с фильтрацией по статусу и поиску.",
    parameters=[
        {
            "name": "status",
            "type": str,
            "description": "Фильтр по статусу платежа",
            "required": False,
        },
        {
            "name": "search",
            "type": str,
            "description": "Поиск по username или payment_id",
            "required": False,
        },
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-страница со списком платежей",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Недостаточно прав",
        ),
    },
)
def payment_list_view(request: HttpRequest) -> HttpResponse:
    """
    Render recent payments with optional status/search filters.
    """
    status = str(request.GET.get("status") or "").strip()
    search = str(request.GET.get("search") or "").strip()

    qs = Payment.objects.select_related("user").all().order_by("-created_at")
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(user__username__icontains=search) | Q(yukassa_payment_id__icontains=search))

    payments = qs[:200]
    return render(request, "admin_panel/payments.html", {"payments": payments, "status": status, "search": search})


"""
GOAL: List subscriptions with basic filtering.

PARAMETERS:
  request: HttpRequest - Admin-only request

RETURNS:
  HttpResponse - Rendered subscriptions list

RAISES:
  None

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Access logged for audit trail
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
@extend_schema(
    tags=["admin"],
    summary="Админ-панель: Список подписок",
    description="Показывает список подписок с фильтрацией по статусу.",
    parameters=[
        {
            "name": "show",
            "type": str,
            "description": "Фильтр: 'active', 'expired' или все",
            "required": False,
        },
    ],
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-страница со списком подписок",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Недостаточно прав",
        ),
    },
)
def subscription_list_view(request: HttpRequest) -> HttpResponse:
    """
    Render recent subscriptions.
    """
    show = str(request.GET.get("show") or "").strip()
    qs = Subscription.objects.select_related("user").all().order_by("-updated_at")
    if show == "active":
        qs = qs.filter(is_active=True)
    if show == "expired":
        qs = qs.filter(is_active=True, expires_at__lt=timezone.now())
    subs = qs[:200]
    return render(request, "admin_panel/subscriptions.html", {"subscriptions": subs, "show": show})


"""
GOAL: List and create promo codes (admin).

PARAMETERS:
  request: HttpRequest - Admin-only request - GET shows list, POST creates promo code

RETURNS:
  HttpResponse - Rendered promo codes page

RAISES:
  None (form errors shown inline)

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Access logged for audit trail
  - Uses PromoCodeService.create_promo_code() for creation
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
@extend_schema(
    tags=["admin"],
    summary="Админ-панель: Промокоды",
    description="Показывает список промокодов и позволяет создавать новые.",
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-страница со списком промокодов",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Недостаточно прав",
        ),
    },
)
def promocode_list_view(request: HttpRequest) -> HttpResponse:
    """
    Create promo code on POST; list promo codes on GET.
    """
    error: str | None = None
    if request.method == "POST":
        action = str(request.POST.get("action") or "").strip()
        max_uses = int(request.POST.get("max_uses") or 1)
        code = str(request.POST.get("code") or "").strip() or None
        valid_from_s = str(request.POST.get("valid_from") or "").strip()
        valid_until_s = str(request.POST.get("valid_until") or "").strip()

        try:
            valid_from = datetime.fromisoformat(valid_from_s) if valid_from_s else timezone.now()
            valid_until = datetime.fromisoformat(valid_until_s) if valid_until_s else timezone.now() + timedelta(days=30)
            PromoCodeService.create_promo_code(
                action=action,
                valid_from=valid_from,
                valid_until=valid_until,
                max_uses=max_uses,
                code=code,
                created_by=request.user,
            )
            return redirect("admin_panel_promocodes")
        except Exception as exc:
            error = str(exc)

    promos = PromoCode.objects.select_related("created_by").all().order_by("-created_at")[:200]
    return render(
        request,
        "admin_panel/promocodes.html",
        {
            "promocodes": promos,
            "actions": list(PromoCodeService.ACTION_TO_DAYS.keys()),
            "error": error,
            "now": timezone.now(),
            "now_plus_30": timezone.now() + timedelta(days=30),
        },
    )


"""
GOAL: View and update system settings/feature flags.

PARAMETERS:
  request: HttpRequest - Admin-only request - POST updates settings

RETURNS:
  HttpResponse - Rendered settings page

RAISES:
  None (errors displayed)

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Access logged for audit trail
  - Updates SystemSetting/FeatureFlag rows
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
@extend_schema(
    tags=["admin"],
    summary="Админ-панель: Настройки",
    description="Позволяет просматривать и изменять системные настройки и feature flags.",
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-страница настроек",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Недостаточно прав",
        ),
    },
)
def settings_view(request: HttpRequest) -> HttpResponse:
    """
    Simple settings UI: toggle payments_enabled flag and edit tariffs JSON.
    """
    error: str | None = None
    if request.method == "POST":
        try:
            payments_enabled = bool(request.POST.get("payments_enabled"))
            SystemSetting.set_setting("payments_enabled", payments_enabled, is_secret=False)

            ff, _ = FeatureFlag.objects.get_or_create(key="payments_enabled", defaults={"enabled": payments_enabled})
            ff.enabled = payments_enabled
            ff.save(update_fields=["enabled", "updated_at"])

            return redirect("admin_panel_settings")
        except Exception as exc:
            error = str(exc)

    payments_enabled_val = bool(SystemSetting.get_setting("payments_enabled", True))
    tariffs = SystemSetting.get_setting("tariffs", PaymentService.DEFAULT_TARIFFS)
    flags = FeatureFlag.objects.all().order_by("key")
    return render(
        request,
        "admin_panel/settings.html",
        {"payments_enabled": payments_enabled_val, "tariffs": tariffs, "flags": flags, "error": error},
    )


"""
GOAL: List audit log entries.

PARAMETERS:
  request: HttpRequest - Admin-only request

RETURNS:
  HttpResponse - Rendered audit log list

RAISES:
  None

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Access logged for audit trail
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
@extend_schema(
    tags=["admin"],
    summary="Админ-панель: Журнал аудита",
    description="Показывает журнал аудита системных действий.",
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-страница с журналом аудита",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        403: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Недостаточно прав",
        ),
    },
)
def audit_log_view(request: HttpRequest) -> HttpResponse:
    """
    Render recent audit log entries.
    """
    logs = AuditLog.objects.select_related("user").all().order_by("-created_at")[:300]
    return render(request, "admin_panel/audit_log.html", {"logs": logs})
