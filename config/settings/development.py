from __future__ import annotations

from .base import *
from .base import _env

"""
GOAL: Configure development environment settings with debug enabled and verbose logging.

PARAMETERS:
  None

RETURNS:
  None - Module-level configuration

RAISES:
  None

GUARANTEES:
  - DEBUG mode is enabled
  - Verbose logging is configured
  - Local development hosts are allowed
  - Static files served locally
"""

# Debug mode
DEBUG = True

# Allow local development hosts
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Static files storage (local)
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    }
}

# Verbose logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s:%(lineno)d %(message)s",
        },
        "simple": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "cargotech_auth_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "cargotech_auth.log"),
            "formatter": "verbose",
        },
        "cargotech_api_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "cargotech_api.log"),
            "formatter": "verbose",
        },
        "telegram_auth_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "telegram_auth.log"),
            "formatter": "verbose",
        },
        "error_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "formatter": "verbose",
        },
        "rate_limit_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "rate_limit.log"),
            "formatter": "verbose",
        },
        "security_headers_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "security_headers.log"),
            "formatter": "verbose",
        },
        "circuit_breaker_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "circuit_breaker.log"),
            "formatter": "verbose",
        },
        "api_versioning_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "api_versioning.log"),
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
        "telegram_auth": {
            "handlers": ["console", "telegram_auth_file"],
            "level": "DEBUG",
        },
        "apps.integrations.cargotech_auth": {
            "handlers": ["console", "cargotech_auth_file"],
            "level": "DEBUG",
        },
        "apps.integrations.cargotech_client": {
            "handlers": ["console", "cargotech_api_file"],
            "level": "DEBUG",
        },
        "django.request": {
            "handlers": ["console", "error_file"],
            "level": "DEBUG",
        },
        "apps.core.rate_limit_middleware": {
            "handlers": ["console", "rate_limit_file"],
            "level": "DEBUG",
        },
        "apps.core.decorators": {
            "handlers": ["console", "rate_limit_file"],
            "level": "DEBUG",
        },
        "security_headers": {
            "handlers": ["console", "security_headers_file"],
            "level": "DEBUG",
        },
        "apps.core.circuit_breaker": {
            "handlers": ["console", "circuit_breaker_file"],
            "level": "DEBUG",
        },
        "apps.core.csrf_protection": {
            "handlers": ["console", "error_file"],
            "level": "DEBUG",
        },
        "admin_auth": {
            "handlers": ["console", "error_file"],
            "level": "DEBUG",
        },
        "api_versioning": {
            "handlers": ["console", "api_versioning_file"],
            "level": "DEBUG",
        },
    },
}

# Development-specific settings
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Disable rate limiting in development for easier testing
RATE_LIMIT_ENABLED = False

# Disable circuit breaker in development for easier testing
CIRCUIT_BREAKER_ENABLED = False

# More permissive CSP for development (allow external scripts like HTMX from CDN)
CSP_SCRIPT_SRC = "'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://telegram.org"
CSP_STYLE_SRC = "'self' 'unsafe-inline'"
CSP_CONNECT_SRC = "'self' https://unpkg.com https://telegram.org https://*.telegram.org wss://*.telegram.org"

# Disable HSTS in development (HTTP is allowed)
HSTS_ENABLED = False

# Allow Telegram WebApp to be embedded in Telegram
X_FRAME_OPTIONS = "SAMEORIGIN"

# Telegram validation helpers (can be relaxed via env for local debugging)
TELEGRAM_SKIP_HASH_VALIDATION = (_env("TELEGRAM_SKIP_HASH_VALIDATION", "False") or "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_SKIP_AUTH_DATE_VALIDATION = (
    _env("TELEGRAM_SKIP_AUTH_DATE_VALIDATION", "False") or ""
).lower() in {"1", "true", "yes", "on"}

# Skip cache validation in development (for development without Redis)
SKIP_CACHE_VALIDATION = True

# Sentry environment override
SENTRY_ENVIRONMENT = "development"
SENTRY_TRACES_SAMPLE_RATE = 1.0  # Sample all traces in development
SENTRY_PROFILES_SAMPLE_RATE = 1.0  # Profile all requests in development
