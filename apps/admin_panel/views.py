from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.contrib import admin
from django.db.models import Q
from django.core.cache import cache
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.admin_panel.cache_diagnostics import (
    clear_user_cargo_cache,
    format_cache_value,
    get_cache_ttl_seconds,
    iter_cache_keys,
    summarize_cargo_list_cache,
)
from apps.auth.models import TelegramSession
from apps.auth.services import SessionService
from apps.audit.models import AuditLog
from apps.auth.decorators import require_admin
from apps.core.decorators import rate_limit
from apps.feature_flags.models import FeatureFlag, SystemSetting
from apps.integrations.cargotech_auth import CargoTechAuthService
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
    context = {"payments": payments, "status": status, "search": search}

    use_django_admin_urls = str(request.path or "").startswith("/admin/")
    template_name = "admin_panel/payments.html"
    if use_django_admin_urls:
        template_name = "admin/cargo_viewer/payments.html"
        context = {**admin.site.each_context(request), **context, "title": "Платежи"}

    return render(request, template_name, context)


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
    context = {"subscriptions": subs, "show": show}

    use_django_admin_urls = str(request.path or "").startswith("/admin/")
    template_name = "admin_panel/subscriptions.html"
    if use_django_admin_urls:
        template_name = "admin/cargo_viewer/subscriptions.html"
        context = {**admin.site.each_context(request), **context, "title": "Подписки"}

    return render(request, template_name, context)


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
    use_django_admin_urls = str(request.path or "").startswith("/admin/")

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
            if use_django_admin_urls:
                return redirect("admin_cargo_viewer_promocodes")
            return redirect("admin_panel_promocodes")
        except Exception as exc:
            error = str(exc)

    promos = PromoCode.objects.select_related("created_by").all().order_by("-created_at")[:200]

    context = {
        "promocodes": promos,
        "actions": list(PromoCodeService.ACTION_TO_DAYS.keys()),
        "error": error,
        "now": timezone.now(),
        "now_plus_30": timezone.now() + timedelta(days=30),
    }

    template_name = "admin_panel/promocodes.html"
    if use_django_admin_urls:
        template_name = "admin/cargo_viewer/promocodes.html"
        context = {**admin.site.each_context(request), **context, "title": "Промокоды"}

    return render(request, template_name, context)


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
    use_django_admin_urls = str(request.path or "").startswith("/admin/")

    error: str | None = None
    if request.method == "POST":
        try:
            payments_enabled = bool(request.POST.get("payments_enabled"))
            SystemSetting.set_setting("payments_enabled", payments_enabled, is_secret=False)

            ff, _ = FeatureFlag.objects.get_or_create(key="payments_enabled", defaults={"enabled": payments_enabled})
            ff.enabled = payments_enabled
            ff.save(update_fields=["enabled", "updated_at"])

            if use_django_admin_urls:
                return redirect("admin_cargo_viewer_settings")
            return redirect("admin_panel_settings")
        except Exception as exc:
            error = str(exc)

    payments_enabled_val = bool(SystemSetting.get_setting("payments_enabled", True))
    tariffs = SystemSetting.get_setting("tariffs", PaymentService.DEFAULT_TARIFFS)
    flags = FeatureFlag.objects.all().order_by("key")

    context = {"payments_enabled": payments_enabled_val, "tariffs": tariffs, "flags": flags, "error": error}

    template_name = "admin_panel/settings.html"
    if use_django_admin_urls:
        template_name = "admin/cargo_viewer/settings.html"
        context = {**admin.site.each_context(request), **context, "title": "Настройки"}

    return render(request, template_name, context)


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
    context = {"logs": logs}

    use_django_admin_urls = str(request.path or "").startswith("/admin/")
    template_name = "admin_panel/audit_log.html"
    if use_django_admin_urls:
        template_name = "admin/cargo_viewer/audit_log.html"
        context = {**admin.site.each_context(request), **context, "title": "Журнал аудита"}

    return render(request, template_name, context)


"""
GOAL: Show cache diagnostics dashboard with per-session cache inspection tools.

PARAMETERS:
  request: HttpRequest - Admin-only request - Optional query filters (q, include_revoked)

RETURNS:
  HttpResponse - Rendered cache diagnostics page - HTTP 200

RAISES:
  None

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Does not call external services (read-only diagnostics)
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
def cache_diagnostics_view(request: HttpRequest) -> HttpResponse:
    """
    List Telegram sessions and show whether cache session binding and cargo caches exist per user.
    """
    query = str(request.GET.get("q") or "").strip()
    include_revoked = str(request.GET.get("include_revoked") or "").strip() in {"1", "true", "yes", "on"}
    use_django_admin_urls = str(request.path or "").startswith("/admin/")

    qs = TelegramSession.objects.select_related("user", "user__driverprofile").all().order_by("-created_at")
    if not include_revoked:
        qs = qs.filter(revoked_at__isnull=True)

    if query:
        q_filters = Q(user__username__icontains=query) | Q(user__email__icontains=query)
        if query.isdigit():
            q_int = int(query)
            q_filters |= Q(user_id=q_int) | Q(user__driverprofile__telegram_user_id=q_int)
        qs = qs.filter(q_filters)

    sessions = qs[:200]
    session_rows: list[dict[str, Any]] = []
    for session in sessions:
        telegram_user_id: int | None = None
        telegram_username: str | None = None
        try:
            dp = session.user.driverprofile  # type: ignore[attr-defined]
            telegram_user_id = int(getattr(dp, "telegram_user_id", 0)) or None
            telegram_username = str(getattr(dp, "telegram_username", "") or "").strip() or None
        except Exception:
            telegram_user_id = None
            telegram_username = None

        driver_cache_key = SessionService.CACHE_KEY_FMT.format(user_id=session.user_id)
        cached_sid = cache.get(driver_cache_key)
        cached_ttl = get_cache_ttl_seconds(driver_cache_key)
        sid_matches = bool(cached_sid and str(cached_sid) == str(session.session_id))

        has_cargo_cache = False
        try:
            has_cargo_cache = bool(iter_cache_keys(f"user:{session.user_id}:cargos:*", limit=1))
        except Exception:
            has_cargo_cache = False

        session_rows.append(
            {
                "session": session,
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username,
                "driver_cache_key": driver_cache_key,
                "cached_sid": cached_sid,
                "cached_ttl": cached_ttl,
                "sid_matches": sid_matches,
                "has_cargo_cache": has_cargo_cache,
            }
        )

    cargotech_token = cache.get(CargoTechAuthService.CACHE_KEY)
    cargotech_token_ttl = get_cache_ttl_seconds(CargoTechAuthService.CACHE_KEY)

    context = {
        "query": query,
        "include_revoked": include_revoked,
        "session_rows": session_rows,
        "cargotech_token_present": bool(cargotech_token),
        "cargotech_token_ttl": cargotech_token_ttl,
        "cache_diagnostics_url_name": "admin_cache_diagnostics"
        if use_django_admin_urls
        else "admin_panel_cache_diagnostics",
        "cache_diagnostics_session_url_name": "admin_cache_diagnostics_session"
        if use_django_admin_urls
        else "admin_panel_cache_diagnostics_session",
    }

    template_name = "admin_panel/cache_diagnostics.html"
    if use_django_admin_urls:
        template_name = "admin/cache_diagnostics.html"
        context = {**admin.site.each_context(request), **context, "title": "Сессии пользователей"}

    return render(request, template_name, context)


"""
GOAL: Show per-session cache details and allow clearing cargo cache for the session owner.

PARAMETERS:
  request: HttpRequest - Admin-only request - GET renders; POST performs cache actions
  session_id: str - TelegramSession.session_id (UUID) - Must be non-empty

RETURNS:
  HttpResponse - Rendered session cache detail page - HTTP 200/404

RAISES:
  None

GUARANTEES:
  - Admin-only access (staff/superuser)
  - Cache reset only affects cargo keys for the session's user
"""
@require_admin
@rate_limit(requests_per_minute=100, endpoint_type="admin")
def cache_diagnostics_session_view(request: HttpRequest, session_id: str) -> HttpResponse:
    """
    Render session details plus related cache keys (list/detail), with reset actions.
    """
    session_id = str(session_id).strip()
    use_django_admin_urls = str(request.path or "").startswith("/admin/")
    session = (
        TelegramSession.objects.select_related("user", "user__driverprofile")
        .filter(session_id=session_id)
        .order_by("-created_at")
        .first()
    )
    if not session:
        return HttpResponse("Session not found", status=404)

    telegram_user_id: int | None = None
    telegram_username: str | None = None
    try:
        dp = session.user.driverprofile  # type: ignore[attr-defined]
        telegram_user_id = int(getattr(dp, "telegram_user_id", 0)) or None
        telegram_username = str(getattr(dp, "telegram_username", "") or "").strip() or None
    except Exception:
        telegram_user_id = None
        telegram_username = None

    message: str | None = None
    if request.method == "POST":
        action = str(request.POST.get("action") or "").strip()
        if action == "clear_user_cargo_cache":
            include_details = bool(request.POST.get("include_details"))
            result = clear_user_cargo_cache(user_id=int(session.user_id), include_details=include_details)
            message = (
                f"Deleted list keys: {result.get('list_keys_deleted', 0)}, "
                f"detail keys: {result.get('detail_keys_deleted', 0)}"
            )

    user_id = int(session.user_id)
    driver_cache_key = SessionService.CACHE_KEY_FMT.format(user_id=user_id)
    cached_sid = cache.get(driver_cache_key)
    cached_ttl = get_cache_ttl_seconds(driver_cache_key)
    sid_matches = bool(cached_sid and str(cached_sid) == str(session.session_id))

    cargo_list_keys = iter_cache_keys(f"user:{user_id}:cargos:*", limit=200)
    cargo_list_key_rows: list[dict[str, Any]] = []
    for index, key in enumerate(cargo_list_keys):
        ttl = get_cache_ttl_seconds(key)
        summary: dict[str, Any] = {"cards_count": None, "meta_size": None, "sample_cargo_ids": []}
        if index < 50:
            summary = summarize_cargo_list_cache(cache.get(key))
        cargo_list_key_rows.append({"key": key, "ttl": ttl, "summary": summary})

    selected_key = str(request.GET.get("key") or "").strip()
    selected_value: str | None = None
    if selected_key and (selected_key == driver_cache_key or selected_key in cargo_list_keys):
        selected_value = format_cache_value(cache.get(selected_key))

    context = {
        "session": session,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "message": message,
        "driver_cache_key": driver_cache_key,
        "cached_sid": cached_sid,
        "cached_ttl": cached_ttl,
        "sid_matches": sid_matches,
        "cargo_list_key_rows": cargo_list_key_rows,
        "selected_key": selected_key,
        "selected_value": selected_value,
        "cache_diagnostics_url_name": "admin_cache_diagnostics"
        if use_django_admin_urls
        else "admin_panel_cache_diagnostics",
    }

    template_name = "admin_panel/cache_diagnostics_session.html"
    if use_django_admin_urls:
        template_name = "admin/cache_diagnostics_session.html"
        context = {
            **admin.site.each_context(request),
            **context,
            "title": "Сессия пользователя",
            "subtitle": f"#{session.user_id} • {session.session_id}",
        }

    return render(request, template_name, context)


"""
GOAL: Disable Django admin app-index page for the auth app.

PARAMETERS:
  request: HttpRequest - Admin request - Not None

RETURNS:
  HttpResponse - Never returned (always raises)

RAISES:
  Http404: Always, to disable /admin/auth/

GUARANTEES:
  - The /admin/auth/ URL never renders an app-index page
"""
def disabled_auth_app_index(request: HttpRequest) -> HttpResponse:
    """
    Raise Http404 so the auth app-index URL cannot be used.
    """
    raise Http404()
