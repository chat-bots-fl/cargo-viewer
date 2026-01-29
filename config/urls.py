from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from apps.admin_panel import views as admin_panel_views
from apps.auth import views as auth_views
from apps.cargos import views as cargo_views
from apps.core.health_views import health_check, readiness_check, liveness_check
from apps.filtering import views as filtering_views
from apps.integrations import views as integrations_views
from apps.payments import views as payments_views
from apps.promocodes import views as promocodes_views
from apps.telegram_bot import views as telegram_views

# Versioned API URL patterns
# Each version has its own URL namespace for clarity
api_v1_patterns = [
    # Auth
    path("auth/telegram", auth_views.telegram_auth, name="v1_telegram_auth"),
    # Cargos
    path("cargos/", cargo_views.cargo_list_partial, name="v1_cargo_list_partial"),
    path("cargos/prices/", cargo_views.cargo_prices_oob_partial, name="v1_cargo_prices_oob_partial"),
    path("cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="v1_cargo_detail_partial"),
    # Dictionaries
    path("dictionaries/points", filtering_views.search_cities, name="v1_search_cities"),
    path("dictionaries/load_types", filtering_views.load_types, name="v1_load_types"),
    path("dictionaries/truck_types", filtering_views.truck_types, name="v1_truck_types"),
    # Payments + promos
    path("payments/create", payments_views.create_payment, name="v1_create_payment"),
    path("payments/webhook", payments_views.yookassa_webhook, name="v1_yookassa_webhook"),
    path("promocodes/apply", promocodes_views.apply_promocode, name="v1_apply_promocode"),
]

api_v2_patterns = [
    # Auth
    path("auth/telegram", auth_views.telegram_auth, name="v2_telegram_auth"),
    # Cargos
    path("cargos/", cargo_views.cargo_list_partial, name="v2_cargo_list_partial"),
    path("cargos/prices/", cargo_views.cargo_prices_oob_partial, name="v2_cargo_prices_oob_partial"),
    path("cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="v2_cargo_detail_partial"),
    # Dictionaries
    path("dictionaries/points", filtering_views.search_cities, name="v2_search_cities"),
    path("dictionaries/load_types", filtering_views.load_types, name="v2_load_types"),
    path("dictionaries/truck_types", filtering_views.truck_types, name="v2_truck_types"),
    # Payments + promos
    path("payments/create", payments_views.create_payment, name="v2_create_payment"),
    path("payments/webhook", payments_views.yookassa_webhook, name="v2_yookassa_webhook"),
    path("promocodes/apply", promocodes_views.apply_promocode, name="v2_apply_promocode"),
]

api_v3_patterns = [
    # Auth
    path("auth/telegram", auth_views.telegram_auth, name="v3_telegram_auth"),
    # Cargos
    path("cargos/", cargo_views.cargo_list_partial, name="v3_cargo_list_partial"),
    path("cargos/prices/", cargo_views.cargo_prices_oob_partial, name="v3_cargo_prices_oob_partial"),
    path("cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="v3_cargo_detail_partial"),
    # Dictionaries
    path("dictionaries/points", filtering_views.search_cities, name="v3_search_cities"),
    path("dictionaries/load_types", filtering_views.load_types, name="v3_load_types"),
    path("dictionaries/truck_types", filtering_views.truck_types, name="v3_truck_types"),
    # Payments + promos
    path("payments/create", payments_views.create_payment, name="v3_create_payment"),
    path("payments/webhook", payments_views.yookassa_webhook, name="v3_yookassa_webhook"),
    path("promocodes/apply", promocodes_views.apply_promocode, name="v3_apply_promocode"),
]

urlpatterns = [
    path(
        "admin-panel/",
        RedirectView.as_view(pattern_name="admin:index", permanent=True, query_string=True),
        name="admin_panel_dashboard",
    ),
    path(
        "admin-panel/payments/",
        RedirectView.as_view(pattern_name="admin_cargo_viewer_payments", permanent=True, query_string=True),
        name="admin_panel_payments",
    ),
    path(
        "admin-panel/subscriptions/",
        RedirectView.as_view(pattern_name="admin_cargo_viewer_subscriptions", permanent=True, query_string=True),
        name="admin_panel_subscriptions",
    ),
    path(
        "admin-panel/promocodes/",
        RedirectView.as_view(pattern_name="admin_cargo_viewer_promocodes", permanent=True, query_string=True),
        name="admin_panel_promocodes",
    ),
    path(
        "admin-panel/settings/",
        RedirectView.as_view(pattern_name="admin_cargo_viewer_settings", permanent=True, query_string=True),
        name="admin_panel_settings",
    ),
    path(
        "admin-panel/audit-log/",
        RedirectView.as_view(pattern_name="admin_cargo_viewer_audit_log", permanent=True, query_string=True),
        name="admin_panel_audit_log",
    ),
    path(
        "admin-panel/cache-diagnostics/",
        RedirectView.as_view(pattern_name="admin_cache_diagnostics", permanent=True, query_string=True),
        name="admin_panel_cache_diagnostics",
    ),
    path(
        "admin-panel/cache-diagnostics/session/<uuid:session_id>/",
        RedirectView.as_view(pattern_name="admin_cache_diagnostics_session", permanent=True, query_string=True),
        name="admin_panel_cache_diagnostics_session",
    ),
    path(
        "admin/cargo-viewer/payments/",
        admin.site.admin_view(admin_panel_views.payment_list_view),
        name="admin_cargo_viewer_payments",
    ),
    path(
        "admin/cargo-viewer/subscriptions/",
        admin.site.admin_view(admin_panel_views.subscription_list_view),
        name="admin_cargo_viewer_subscriptions",
    ),
    path(
        "admin/cargo-viewer/promocodes/",
        admin.site.admin_view(admin_panel_views.promocode_list_view),
        name="admin_cargo_viewer_promocodes",
    ),
    path(
        "admin/cargo-viewer/settings/",
        admin.site.admin_view(admin_panel_views.settings_view),
        name="admin_cargo_viewer_settings",
    ),
    path(
        "admin/cargo-viewer/audit-log/",
        admin.site.admin_view(admin_panel_views.audit_log_view),
        name="admin_cargo_viewer_audit_log",
    ),
    path(
        "admin/cache-diagnostics/",
        admin.site.admin_view(admin_panel_views.cache_diagnostics_view),
        name="admin_cache_diagnostics",
    ),
    path(
        "admin/cache-diagnostics/session/<uuid:session_id>/",
        admin.site.admin_view(admin_panel_views.cache_diagnostics_session_view),
        name="admin_cache_diagnostics_session",
    ),
    path(
        "admin/auth/",
        admin.site.admin_view(admin_panel_views.disabled_auth_app_index),
        name="admin_auth_disabled",
    ),
    path("admin/", admin.site.urls),
    path("", cargo_views.webapp_home, name="webapp_home"),
    # Health checks
    path("health/", health_check, name="health_check"),
    path("health/ready/", readiness_check, name="health_ready"),
    path("health/live/", liveness_check, name="health_live"),
    path("healthz", integrations_views.healthz, name="healthz"),  # Legacy endpoint
    # Versioned API endpoints
    path("api/v1/", include((api_v1_patterns, "api_v1"), namespace="api_v1")),
    path("api/v2/", include((api_v2_patterns, "api_v2"), namespace="api_v2")),
    path("api/v3/", include((api_v3_patterns, "api_v3"), namespace="api_v3")),
    # Telegram bot integration (not versioned)
    path("telegram/webhook/", telegram_views.telegram_webhook, name="telegram_webhook"),
    path("telegram/responses/", telegram_views.handle_response, name="telegram_handle_response"),
    # Payments + promos (non-API endpoints)
    path("paywall", payments_views.paywall, name="paywall"),
]

# Backward compatibility: legacy endpoints (without version prefix)
# These map to v3 for seamless migration
urlpatterns += [
    # Auth (legacy)
    path("api/auth/telegram", auth_views.telegram_auth, name="telegram_auth"),
    # Cargos (legacy)
    path("api/cargos/", cargo_views.cargo_list_partial, name="cargo_list_partial"),
    path("api/cargos/prices/", cargo_views.cargo_prices_oob_partial, name="cargo_prices_oob_partial"),
    path("api/cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="cargo_detail_partial"),
    # Dictionaries (legacy)
    path("api/dictionaries/points", filtering_views.search_cities, name="search_cities"),
    path("api/dictionaries/load_types", filtering_views.load_types, name="load_types"),
    path("api/dictionaries/truck_types", filtering_views.truck_types, name="truck_types"),
    # Payments + promos (legacy)
    path("api/payments/create", payments_views.create_payment, name="create_payment"),
    path("api/payments/webhook", payments_views.yookassa_webhook, name="yookassa_webhook"),
    path("api/promocodes/apply", promocodes_views.apply_promocode, name="apply_promocode"),
]

# OpenAPI/Swagger documentation (conditional based on OPENAPI_ENABLED)
if getattr(settings, "OPENAPI_ENABLED", True):
    from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
    
    urlpatterns += [
        # OpenAPI schema endpoints
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
