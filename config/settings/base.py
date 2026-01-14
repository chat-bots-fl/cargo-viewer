from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent


"""
GOAL: Read an environment variable with optional default.

PARAMETERS:
  name: str - Environment variable name - Must be non-empty
  default: str | None - Fallback value - Optional

RETURNS:
  str | None - Environment value or default - Never raises on missing var

RAISES:
  None

GUARANTEES:
  - Does not strip or coerce the value
"""
def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass


SECRET_KEY = _env("SECRET_KEY", "dev-secret-key-change-me")

ALLOWED_HOSTS = [h.strip() for h in (_env("ALLOWED_HOSTS", "") or "").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "apps.core.apps.CoreConfig",
    "apps.auth.apps.DriverAuthConfig",
    "apps.integrations.apps.IntegrationsConfig",
    "apps.cargos.apps.CargosConfig",
    "apps.filtering.apps.FilteringConfig",
    "apps.telegram_bot.apps.TelegramBotConfig",
    "apps.feature_flags.apps.FeatureFlagsConfig",
    "apps.audit.apps.AuditConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.subscriptions.apps.SubscriptionsConfig",
    "apps.promocodes.apps.PromoCodesConfig",
    "apps.admin_panel.apps.AdminPanelConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.security_headers.SecurityHeadersMiddleware",
    "apps.core.middleware.ExceptionHandlingMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.core.api_versioning.APIVersioningMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.auth.middleware.JWTAuthenticationMiddleware",
    "apps.core.rate_limit_middleware.RateLimitMiddleware",
    "apps.core.csrf_protection.APICSRFProtectionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES: dict[str, Any] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "CONN_MAX_AGE": 600,
    }
}

DATABASE_URL = (_env("DATABASE_URL", "") or "").strip()
if DATABASE_URL:
    DATABASES["default"] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)
else:
    postgres_db = (_env("POSTGRES_DB", "") or "").strip()
    postgres_user = (_env("POSTGRES_USER", "") or "").strip()
    postgres_password = _env("POSTGRES_PASSWORD", "") or ""
    if postgres_db and postgres_user and postgres_password:
        postgres_host = (_env("DB_HOST", "") or _env("POSTGRES_HOST", "") or "").strip()
        postgres_port = (_env("DB_PORT", "") or _env("POSTGRES_PORT", "") or "").strip()
        in_docker = Path("/.dockerenv").exists()

        DATABASES["default"] = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": postgres_db,
            "USER": postgres_user,
            "PASSWORD": postgres_password,
            "HOST": postgres_host or ("db" if in_docker else "localhost"),
            "PORT": postgres_port or "5432",
            "CONN_MAX_AGE": 600,
        }

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# CDN Settings
CDN_ENABLED = (_env("CDN_ENABLED", "False") or "").lower() in {"1", "true", "yes", "on"}
CDN_URL = _env("CDN_URL", "") or ""
CDN_STATIC_PREFIX = _env("CDN_STATIC_PREFIX", "static") or "static"

# Build STATIC_URL based on CDN settings
if CDN_ENABLED and CDN_URL:
    STATIC_URL = f"{CDN_URL.rstrip('/')}/{CDN_STATIC_PREFIX.lstrip('/')}/"
else:
    STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# External integration settings
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN", "") or ""
WEBAPP_URL = _env("WEBAPP_URL", "") or ""
TELEGRAM_RESPONSES_CHAT_ID = int(_env("TELEGRAM_RESPONSES_CHAT_ID", "0") or "0")

CARGOTECH_PHONE = _env("CARGOTECH_PHONE", "") or ""
CARGOTECH_PASSWORD = _env("CARGOTECH_PASSWORD", "") or ""
CARGOTECH_TOKEN_CACHE_TTL = int(_env("CARGOTECH_TOKEN_CACHE_TTL", "86400") or "86400")

YOOKASSA_SHOP_ID = _env("YOOKASSA_SHOP_ID", "") or ""
YOOKASSA_SECRET_KEY = _env("YOOKASSA_SECRET_KEY", "") or ""
YOOKASSA_WEBHOOK_SECRET = _env("YOOKASSA_WEBHOOK_SECRET", "") or ""

SETTINGS_ENCRYPTION_KEY = _env("SETTINGS_ENCRYPTION_KEY", "") or ""

# Cache (Redis preferred)
REDIS_URL = _env("REDIS_URL", "") or ""
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Rate limiting settings
RATE_LIMIT_ENABLED = (_env("RATE_LIMIT_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}
RATE_LIMIT_DEFAULT = int(_env("RATE_LIMIT_DEFAULT", "60") or "60")
RATE_LIMIT_AUTH = int(_env("RATE_LIMIT_AUTH", "10") or "10")
RATE_LIMIT_PAYMENT = int(_env("RATE_LIMIT_PAYMENT", "5") or "5")
RATE_LIMIT_TELEGRAM = int(_env("RATE_LIMIT_TELEGRAM", "20") or "20")
RATE_LIMIT_ADMIN = int(_env("RATE_LIMIT_ADMIN", "100") or "100")

# Circuit breaker settings
CIRCUIT_BREAKER_ENABLED = (_env("CIRCUIT_BREAKER_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(_env("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5") or "5")
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(_env("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60") or "60")
CIRCUIT_BREAKER_SUCCESS_THRESHOLD = int(_env("CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "2") or "2")

# Service-specific circuit breaker settings
CIRCUIT_BREAKER_CARGOTECH_FAILURE_THRESHOLD = int(_env("CIRCUIT_BREAKER_CARGOTECH_FAILURE_THRESHOLD", "5") or "5")
CIRCUIT_BREAKER_CARGOTECH_RECOVERY_TIMEOUT = int(_env("CIRCUIT_BREAKER_CARGOTECH_RECOVERY_TIMEOUT", "60") or "60")
CIRCUIT_BREAKER_CARGOTECH_SUCCESS_THRESHOLD = int(_env("CIRCUIT_BREAKER_CARGOTECH_SUCCESS_THRESHOLD", "2") or "2")

CIRCUIT_BREAKER_YUKASSA_FAILURE_THRESHOLD = int(_env("CIRCUIT_BREAKER_YUKASSA_FAILURE_THRESHOLD", "3") or "3")
CIRCUIT_BREAKER_YUKASSA_RECOVERY_TIMEOUT = int(_env("CIRCUIT_BREAKER_YUKASSA_RECOVERY_TIMEOUT", "120") or "120")
CIRCUIT_BREAKER_YUKASSA_SUCCESS_THRESHOLD = int(_env("CIRCUIT_BREAKER_YUKASSA_SUCCESS_THRESHOLD", "2") or "2")

# API CSRF protection settings
API_CSRF_ENABLED = (_env("API_CSRF_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}
API_CSRF_ALLOWED_ORIGINS = [o.strip() for o in (_env("API_CSRF_ALLOWED_ORIGINS", "") or "").split(",") if o.strip()]
API_CSRF_ALLOW_SAME_ORIGIN = (_env("API_CSRF_ALLOW_SAME_ORIGIN", "True") or "").lower() in {"1", "true", "yes", "on"}

# Security Headers settings
SECURITY_HEADERS_ENABLED = (_env("SECURITY_HEADERS_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}

# Content Security Policy (CSP) settings
CSP_ENABLED = (_env("CSP_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}
CSP_DEFAULT_SRC = _env("CSP_DEFAULT_SRC", "'self'") or "'self'"
CSP_SCRIPT_SRC = _env("CSP_SCRIPT_SRC", "'self' 'unsafe-inline' 'unsafe-eval'") or "'self' 'unsafe-inline' 'unsafe-eval'"
CSP_STYLE_SRC = _env("CSP_STYLE_SRC", "'self' 'unsafe-inline'") or "'self' 'unsafe-inline'"
CSP_IMG_SRC = _env("CSP_IMG_SRC", "'self' data: https:") or "'self' data: https:"
CSP_CONNECT_SRC = _env("CSP_CONNECT_SRC", "'self'") or "'self'"
CSP_FONT_SRC = _env("CSP_FONT_SRC", "'self'") or "'self'"
CSP_OBJECT_SRC = _env("CSP_OBJECT_SRC", "'none'") or "'none'"
CSP_MEDIA_SRC = _env("CSP_MEDIA_SRC", "'self'") or "'self'"
CSP_FRAME_SRC = _env("CSP_FRAME_SRC", "'none'") or "'none'"
CSP_BASE_URI = _env("CSP_BASE_URI", "'self'") or "'self'"
CSP_FORM_ACTION = _env("CSP_FORM_ACTION", "'self'") or "'self'"

# HTTP Strict Transport Security (HSTS) settings
HSTS_ENABLED = (_env("HSTS_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}
HSTS_MAX_AGE = int(_env("HSTS_MAX_AGE", "31536000") or "31536000")  # 1 год
HSTS_INCLUDE_SUBDOMAINS = (_env("HSTS_INCLUDE_SUBDOMAINS", "True") or "").lower() in {"1", "true", "yes", "on"}
HSTS_PRELOAD = (_env("HSTS_PRELOAD", "True") or "").lower() in {"1", "true", "yes", "on"}

# Other security headers
X_FRAME_OPTIONS = _env("X_FRAME_OPTIONS", "DENY") or "DENY"
X_CONTENT_TYPE_OPTIONS = _env("X_CONTENT_TYPE_OPTIONS", "nosniff") or "nosniff"
X_XSS_PROTECTION = _env("X_XSS_PROTECTION", "1; mode=block") or "1; mode=block"
REFERRER_POLICY = _env("REFERRER_POLICY", "strict-origin-when-cross-origin") or "strict-origin-when-cross-origin"
PERMISSIONS_POLICY = _env("PERMISSIONS_POLICY", "geolocation=(), camera=(), microphone=()") or "geolocation=(), camera=(), microphone=()"

# API Versioning settings
API_VERSIONING_ENABLED = (_env("API_VERSIONING_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}
API_DEFAULT_VERSION = _env("API_DEFAULT_VERSION", "v3") or "v3"
API_SUPPORTED_VERSIONS = [v.strip() for v in (_env("API_SUPPORTED_VERSIONS", "v1,v2,v3") or "").split(",") if v.strip()]
API_VERSION_HEADER = _env("API_VERSION_HEADER", "X-API-Version") or "X-API-Version"

# Lazy loading settings
LAZY_LOADING_ENABLED = (_env("LAZY_LOADING_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}
LAZY_LOADING_PLACEHOLDER = _env("LAZY_LOADING_PLACEHOLDER", "/static/img/placeholder.svg") or "/static/img/placeholder.svg"
LAZY_LOADING_ROOT_MARGIN = _env("LAZY_LOADING_ROOT_MARGIN", "50px") or "50px"

# Admin access settings
ADMIN_REQUIRE_SUBSCRIPTION = (_env("ADMIN_REQUIRE_SUBSCRIPTION", "False") or "").lower() in {"1", "true", "yes", "on"}
ADMIN_SUBSCRIPTION_FEATURE = _env("ADMIN_SUBSCRIPTION_FEATURE", "admin_access") or "admin_access"

# Sentry monitoring settings
SENTRY_DSN = _env("SENTRY_DSN", "") or ""
SENTRY_ENVIRONMENT = _env("SENTRY_ENVIRONMENT", "development") or "development"
SENTRY_TRACES_SAMPLE_RATE = float(_env("SENTRY_TRACES_SAMPLE_RATE", "0.1") or "0.1")
SENTRY_PROFILES_SAMPLE_RATE = float(_env("SENTRY_PROFILES_SAMPLE_RATE", "0.1") or "0.1")

# Initialize Sentry if DSN is provided
if SENTRY_DSN:
    try:
        from apps.core.monitoring import init_sentry
        
        init_sentry(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to initialize Sentry: {e}", exc_info=True)

LOG_DIR = BASE_DIR / "logs"

# Django REST Framework settings
REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [],
}

# OpenAPI/Spectacular settings
OPENAPI_ENABLED = (_env("OPENAPI_ENABLED", "True") or "").lower() in {"1", "true", "yes", "on"}

SPECTACULAR_SETTINGS: dict[str, Any] = {
    "TITLE": "Cargo Viewer API",
    "DESCRIPTION": "API для просмотра грузов через Telegram WebApp",
    "VERSION": "3.2.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api",
    "SERVERS": [
        {"url": "/", "description": "Production server"},
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
    "TAGS": [
        {"name": "auth", "description": "Аутентификация и авторизация"},
        {"name": "cargos", "description": "Работа с грузами"},
        {"name": "payments", "description": "Платежи и подписки"},
        {"name": "promocodes", "description": "Промокоды"},
        {"name": "telegram", "description": "Telegram бот интеграция"},
        {"name": "admin", "description": "Админ-панель"},
        {"name": "health", "description": "Health checks"},
    ],
    "SCHEMA_PATH_PREFIX_OVERRIDE": "/api",
    "ENUM_NAME_OVERRIDES": {
        "PaymentStatus": "apps.payments.models.Payment.Status",
        "SubscriptionStatus": "apps.subscriptions.models.Subscription.Status",
    },
}
