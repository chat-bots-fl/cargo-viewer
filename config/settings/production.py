from __future__ import annotations

from .base import *

"""
GOAL: Configure production environment settings with maximum security and performance.

PARAMETERS:
  None

RETURNS:
  None - Module-level configuration

RAISES:
  None

GUARANTEES:
  - DEBUG mode is disabled
  - Maximum security settings enabled
  - Production database configuration
  - Minimal logging level
"""

# Debug mode
DEBUG = False

# Production hosts (should be configured via ALLOWED_HOSTS env var)
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["cargo-viewer.com", "www.cargo-viewer.com"]

# CDN Configuration for Production
CDN_ENABLED = True
CDN_URL = _env("CDN_URL", "https://cdn.cargo-viewer.com") or "https://cdn.cargo-viewer.com"
CDN_STATIC_PREFIX = _env("CDN_STATIC_PREFIX", "static") or "static"

# Rebuild STATIC_URL with CDN settings
STATIC_URL = f"{CDN_URL.rstrip('/')}/{CDN_STATIC_PREFIX.lstrip('/')}/"

# Static files storage (compressed with manifest)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    }
}

# Production logging configuration
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
            "level": "WARNING",
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
            "level": "ERROR",
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
            "level": "WARNING",
        },
        "apps.core.circuit_breaker": {
            "handlers": ["console", "circuit_breaker_file"],
            "level": "WARNING",
        },
        "apps.core.csrf_protection": {
            "handlers": ["console", "error_file"],
            "level": "ERROR",
        },
        "admin_auth": {
            "handlers": ["console", "error_file"],
            "level": "WARNING",
        },
        "api_versioning": {
            "handlers": ["console", "api_versioning_file"],
            "level": "INFO",
        },
    },
}

# Production-specific settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = _env("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(_env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = _env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = _env("EMAIL_HOST_PASSWORD", "")

# Enable rate limiting in production
RATE_LIMIT_ENABLED = True

# Enable circuit breaker in production
CIRCUIT_BREAKER_ENABLED = True

# Strict CSP for production
CSP_SCRIPT_SRC = "'self'"
CSP_STYLE_SRC = "'self'"
CSP_IMG_SRC = "'self' data: https:"
CSP_CONNECT_SRC = "'self'"

# Enable HSTS in production with maximum security
HSTS_ENABLED = True
HSTS_MAX_AGE = 31536000  # 1 year
HSTS_INCLUDE_SUBDOMAINS = True
HSTS_PRELOAD = True

# Sentry environment override
SENTRY_ENVIRONMENT = "production"
SENTRY_TRACES_SAMPLE_RATE = 0.1  # Sample 10% of traces in production
SENTRY_PROFILES_SAMPLE_RATE = 0.1  # Profile 10% of requests in production

# Production database (can be overridden via DATABASE_URL env var)
# Uses the default from base.py, but should be configured via env vars
# Example: DATABASE_URL=postgres://user:password@host:port/dbname

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Cookie settings
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Additional production security
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
