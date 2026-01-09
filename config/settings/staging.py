from __future__ import annotations

from .base import *

"""
GOAL: Configure staging environment settings with debug disabled and production-like configuration.

PARAMETERS:
  None

RETURNS:
  None - Module-level configuration

RAISES:
  None

GUARANTEES:
  - DEBUG mode is disabled
  - Production-like security settings
  - Staging-specific database configuration
  - Moderate logging level
"""

# Debug mode
DEBUG = False

# Staging hosts (should be configured via ALLOWED_HOSTS env var)
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["staging.cargo-viewer.com"]

# Static files storage (compressed with manifest)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    }
}

# Staging logging configuration
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        "cargotech_auth_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "cargotech_auth.log"),
            "formatter": "default",
        },
        "cargotech_api_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "cargotech_api.log"),
            "formatter": "default",
        },
        "telegram_auth_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "telegram_auth.log"),
            "formatter": "default",
        },
        "error_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "error.log"),
            "formatter": "default",
        },
        "rate_limit_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "rate_limit.log"),
            "formatter": "default",
        },
        "security_headers_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "security_headers.log"),
            "formatter": "default",
        },
        "circuit_breaker_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "circuit_breaker.log"),
            "formatter": "default",
        },
        "api_versioning_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "api_versioning.log"),
            "formatter": "default",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
        },
        "telegram_auth": {
            "handlers": ["console", "telegram_auth_file"],
            "level": "INFO",
        },
        "apps.integrations.cargotech_auth": {
            "handlers": ["console", "cargotech_auth_file"],
            "level": "INFO",
        },
        "apps.integrations.cargotech_client": {
            "handlers": ["console", "cargotech_api_file"],
            "level": "INFO",
        },
        "django.request": {
            "handlers": ["console", "error_file"],
            "level": "WARNING",
        },
        "apps.core.rate_limit_middleware": {
            "handlers": ["console", "rate_limit_file"],
            "level": "WARNING",
        },
        "apps.core.decorators": {
            "handlers": ["console", "rate_limit_file"],
            "level": "WARNING",
        },
        "security_headers": {
            "handlers": ["console", "security_headers_file"],
            "level": "INFO",
        },
        "apps.core.circuit_breaker": {
            "handlers": ["console", "circuit_breaker_file"],
            "level": "INFO",
        },
        "apps.core.csrf_protection": {
            "handlers": ["console", "error_file"],
            "level": "WARNING",
        },
        "admin_auth": {
            "handlers": ["console", "error_file"],
            "level": "INFO",
        },
        "api_versioning": {
            "handlers": ["console", "api_versioning_file"],
            "level": "INFO",
        },
    },
}

# Staging-specific settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = _env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(_env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = _env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = _env("EMAIL_HOST_PASSWORD", "")

# Enable rate limiting in staging
RATE_LIMIT_ENABLED = True

# Enable circuit breaker in staging
CIRCUIT_BREAKER_ENABLED = True

# Moderate CSP for staging
CSP_SCRIPT_SRC = "'self' 'unsafe-inline'"
CSP_STYLE_SRC = "'self' 'unsafe-inline'"

# Enable HSTS in staging
HSTS_ENABLED = True
HSTS_MAX_AGE = 86400  # 1 day for staging (shorter than production)
HSTS_INCLUDE_SUBDOMAINS = True
HSTS_PRELOAD = False

# Sentry environment override
SENTRY_ENVIRONMENT = "staging"
SENTRY_TRACES_SAMPLE_RATE = 0.5  # Sample 50% of traces in staging
SENTRY_PROFILES_SAMPLE_RATE = 0.5  # Profile 50% of requests in staging

# Staging database (can be overridden via DATABASE_URL env var)
# Uses the default from base.py, but can be configured via env vars
