from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import path, include

from apps.admin_panel import views as admin_panel_views
from apps.admin_panel.urls import urlpatterns as admin_panel_urls
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
    path("cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="v1_cargo_detail_partial"),
    # Dictionaries
    path("dictionaries/points", filtering_views.search_cities, name="v1_search_cities"),
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
    path("cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="v2_cargo_detail_partial"),
    # Dictionaries
    path("dictionaries/points", filtering_views.search_cities, name="v2_search_cities"),
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
    path("cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="v3_cargo_detail_partial"),
    # Dictionaries
    path("dictionaries/points", filtering_views.search_cities, name="v3_search_cities"),
    # Payments + promos
    path("payments/create", payments_views.create_payment, name="v3_create_payment"),
    path("payments/webhook", payments_views.yookassa_webhook, name="v3_yookassa_webhook"),
    path("promocodes/apply", promocodes_views.apply_promocode, name="v3_apply_promocode"),
]

urlpatterns = [
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
    path("api/cargos/<str:cargo_id>/", cargo_views.cargo_detail_partial, name="cargo_detail_partial"),
    # Dictionaries (legacy)
    path("api/dictionaries/points", filtering_views.search_cities, name="search_cities"),
    # Payments + promos (legacy)
    path("api/payments/create", payments_views.create_payment, name="create_payment"),
    path("api/payments/webhook", payments_views.yookassa_webhook, name="yookassa_webhook"),
    path("api/promocodes/apply", promocodes_views.apply_promocode, name="apply_promocode"),
]

urlpatterns += admin_panel_urls

# OpenAPI/Swagger documentation (conditional based on OPENAPI_ENABLED)
if getattr(settings, "OPENAPI_ENABLED", True):
    from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
    
    urlpatterns += [
        # OpenAPI schema endpoints
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]
