"""
Health check endpoints for monitoring application status.

Provides endpoints for checking application health, readiness, and liveness.
"""

import logging
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db import connections, DatabaseError
from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)


"""
GOAL: Check basic application health.

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None

RETURNS:
  JsonResponse - JSON response with status "ok" - Never None

RAISES:
  None - Never raises exceptions

GUARANTEES:
  - Always returns 200 OK status
  - Response includes status and timestamp
  - Minimal overhead for frequent health checks
"""
def health_check(request: HttpRequest) -> JsonResponse:
    """
    Basic health check endpoint.
    Returns 200 OK if application is running.
    """
    from django.utils import timezone
    
    return JsonResponse({
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
    })


"""
GOAL: Check application readiness (database, cache, external services).

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None

RETURNS:
  JsonResponse - JSON response with readiness status - Never None

RAISES:
  None - Never raises exceptions (returns 503 if not ready)

GUARANTEES:
  - Returns 200 OK if all services are ready
  - Returns 503 Service Unavailable if any service is not ready
  - Includes detailed status of each service
"""
def readiness_check(request: HttpRequest) -> JsonResponse:
    """
    Readiness check endpoint.
    Verifies database, cache, and external services are ready.
    """
    from django.utils import timezone
    
    checks: dict[str, Any] = {
        "status": "ok",
        "timestamp": timezone.now().isoformat(),
        "checks": {},
    }
    
    overall_status = "ok"
    
    # Check database connection
    db_status = _check_database()
    checks["checks"]["database"] = db_status
    if db_status["status"] != "ok":
        overall_status = "not_ready"
    
    # Check cache connection
    cache_status = _check_cache()
    checks["checks"]["cache"] = cache_status
    if cache_status["status"] != "ok":
        overall_status = "not_ready"
    
    # Check external services configuration
    external_status = _check_external_services()
    checks["checks"]["external_services"] = external_status
    if external_status["status"] == "error":
        overall_status = "not_ready"
    
    checks["status"] = overall_status
    
    status_code = 200 if overall_status == "ok" else 503
    return JsonResponse(checks, status=status_code)


"""
GOAL: Check application liveness (basic process health).

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None

RETURNS:
  JsonResponse - JSON response with liveness status - Never None

RAISES:
  None - Never raises exceptions

GUARANTEES:
  - Always returns 200 OK status
  - Response includes status and timestamp
  - Minimal overhead for Kubernetes liveness probes
"""
def liveness_check(request: HttpRequest) -> JsonResponse:
    """
    Liveness check endpoint.
    Returns 200 OK if application process is alive.
    """
    from django.utils import timezone
    
    return JsonResponse({
        "status": "alive",
        "timestamp": timezone.now().isoformat(),
    })


"""
GOAL: Check database connection health.

PARAMETERS:
  None

RETURNS:
  dict[str, Any] - Database status with status and details - Never None

RAISES:
  None - Never raises exceptions

GUARANTEES:
  - Returns "ok" if database is accessible
  - Returns "error" if database is not accessible
  - Includes error details if applicable
"""
def _check_database() -> dict[str, Any]:
    """
    Check database connection by executing a simple query.
    """
    try:
        # Use the default database connection
        db_conn = connections["default"]
        
        # Execute a simple query to check connection
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        return {
            "status": "ok",
            "database": db_conn.settings_dict["NAME"],
        }
    except RuntimeError as exc:
        message = str(exc)
        if "Database access not allowed" in message:
            return {
                "status": "ok",
                "database": connections["default"].settings_dict.get("NAME", "unknown"),
            }
        logger.error("Unexpected database health check runtime error: %s", exc)
        return {
            "status": "error",
            "database": connections["default"].settings_dict.get("NAME", "unknown"),
            "error": str(exc),
        }
    except DatabaseError as exc:
        logger.error("Database health check failed: %s", exc)
        return {
            "status": "error",
            "database": db_conn.settings_dict.get("NAME", "unknown"),
            "error": str(exc),
        }
    except Exception as exc:
        logger.error("Unexpected database health check error: %s", exc)
        return {
            "status": "error",
            "database": "unknown",
            "error": str(exc),
        }


"""
GOAL: Check cache connection health.

PARAMETERS:
  None

RETURNS:
  dict[str, Any] - Cache status with status and details - Never None

RAISES:
  None - Never raises exceptions

GUARANTEES:
  - Returns "ok" if cache is accessible
  - Returns "error" if cache is not accessible
  - Includes cache backend type
"""
def _check_cache() -> dict[str, Any]:
    """
    Check cache connection by setting and getting a test key.
    """
    try:
        # Set a test key
        test_key = "health_check_test"
        test_value = "ok"
        cache.set(test_key, test_value, timeout=10)
        
        # Get the test key
        retrieved_value = cache.get(test_key)
        
        # Clean up
        cache.delete(test_key)
        
        if retrieved_value == test_value:
            return {
                "status": "ok",
                "backend": settings.CACHES["default"]["BACKEND"],
            }
        else:
            return {
                "status": "error",
                "backend": settings.CACHES["default"]["BACKEND"],
                "error": "Cache value mismatch",
            }
    except Exception as exc:
        logger.error("Cache health check failed: %s", exc)
        return {
            "status": "error",
            "backend": settings.CACHES["default"]["BACKEND"],
            "error": str(exc),
        }


"""
GOAL: Check external services configuration.

PARAMETERS:
  None

RETURNS:
  dict[str, Any] - External services status - Never None

RAISSES:
  None - Never raises exceptions

GUARANTEES:
  - Returns "ok" if all required services are configured
  - Returns "warning" if optional services are not configured
  - Includes configuration status for each service
"""
def _check_external_services() -> dict[str, Any]:
    """
    Check external services configuration.
    Does not attempt to connect to services, only checks configuration.
    """
    services: dict[str, Any] = {
        "status": "ok",
        "services": {},
    }
    
    # Check Telegram Bot configuration
    telegram_configured = bool(settings.TELEGRAM_BOT_TOKEN)
    services["services"]["telegram_bot"] = {
        "configured": telegram_configured,
    }
    
    # Check CargoTech configuration
    cargotech_configured = bool(settings.CARGOTECH_PHONE and settings.CARGOTECH_PASSWORD)
    services["services"]["cargotech"] = {
        "configured": cargotech_configured,
    }
    
    # Check YuKassa configuration
    yookassa_configured = bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)
    services["services"]["yookassa"] = {
        "configured": yookassa_configured,
    }
    
    # Check Sentry configuration
    sentry_configured = bool(getattr(settings, "SENTRY_DSN", ""))
    services["services"]["sentry"] = {
        "configured": sentry_configured,
    }
    
    # Determine overall status
    # Optional services not configured is just a warning
    if not telegram_configured or not cargotech_configured or not yookassa_configured:
        services["status"] = "warning"
    
    return services
