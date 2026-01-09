"""
Custom decorators for Django views.

This module provides reusable decorators for common view functionality,
including rate limiting with configurable limits and circuit breaker pattern.
"""

import functools
import logging
import time
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.core.circuit_breaker import CircuitBreakerOpenError, get_circuit_breaker
from apps.core.exceptions import ExternalServiceError, RateLimitError

logger = logging.getLogger(__name__)


"""
GOAL: Create a decorator that applies rate limiting to individual view functions.

PARAMETERS:
  requests_per_minute: int - Maximum requests allowed per minute - Must be > 0, default 60
  endpoint_type: str - Type identifier for logging - Default "custom"

RETURNS:
  Callable - Decorator function - Not None

RAISES:
  ValueError: If requests_per_minute <= 0

GUARANTEES:
  - Returns a decorator that can be applied to view functions
  - Rate limit is applied before view execution
  - Returns HTTP 429 with Retry-After header when limit exceeded
  - Uses same token bucket algorithm as middleware
  - Gracefully degrades if cache is unavailable
"""
def rate_limit(requests_per_minute: int = 60, endpoint_type: str = "custom") -> Callable:
    """
    Create rate limiting decorator with configurable limits.
    """
    if requests_per_minute <= 0:
        raise ValueError("requests_per_minute must be > 0")
    
    """
    GOAL: Decorator that wraps view function with rate limiting check.

    PARAMETERS:
      view_func: Callable - Django view function to wrap - Not None

    RETURNS:
      Callable - Wrapped view function - Not None

    RAISES:
      None (all exceptions caught)

    GUARANTEES:
      - Rate limit is checked before view execution
      - Authenticated users have per-user limits
      - Anonymous users have per-IP limits
      - Returns 429 response when limit exceeded
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            # Skip rate limiting if disabled globally
            if not getattr(settings, "RATE_LIMIT_ENABLED", False):
                return view_func(request, *args, **kwargs)
            
            # Generate cache key for this user+endpoint
            if hasattr(request, "user") and request.user.is_authenticated:
                identifier = f"user_{request.user.id}"
            else:
                # Get IP address from various headers (supports proxies)
                ip = (
                    request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                    or request.META.get("HTTP_X_REAL_IP", "").strip()
                    or request.META.get("REMOTE_ADDR", "").strip()
                )
                identifier = f"ip_{ip}" if ip else "ip_unknown"
            
            cache_key = f"rate_limit:{endpoint_type}:{identifier}:{view_func.__name__}"
            
            # Check rate limit using token bucket algorithm
            try:
                state = cache.get(cache_key, {"tokens": requests_per_minute, "last_update": time.time()})
                
                now = time.time()
                elapsed = now - state["last_update"]
                
                # Refill tokens based on elapsed time
                refill_rate = requests_per_minute / 60.0
                new_tokens = elapsed * refill_rate
                state["tokens"] = min(requests_per_minute, state["tokens"] + new_tokens)
                state["last_update"] = now
                
                if state["tokens"] >= 1.0:
                    state["tokens"] -= 1.0
                    cache.set(cache_key, state, timeout=60)
                else:
                    # Calculate retry time
                    tokens_needed = 1.0 - state["tokens"]
                    retry_after = int((tokens_needed / refill_rate) + 0.5)
                    retry_after = max(1, min(60, retry_after))
                    cache.set(cache_key, state, timeout=60)
                    
                    # Log rate limit violation
                    logger.warning(
                        "Rate limit exceeded for %s view: %s - Path: %s - Retry after: %d seconds",
                        view_func.__name__,
                        cache_key,
                        request.path,
                        retry_after,
                        extra={"request": request, "endpoint_type": endpoint_type},
                    )
                    
                    # Return 429 Too Many Requests
                    response = JsonResponse(
                        {
                            "error": {
                                "code": "RATE_LIMIT_ERROR",
                                "message": "Too many requests. Please try again later.",
                                "retry_after": retry_after,
                            }
                        },
                        status=429,
                    )
                    response["Retry-After"] = str(retry_after)
                    return response
            
            except Exception as exc:
                # Graceful degradation: if cache fails, allow request but log error
                logger.error("Rate limit check failed (allowing request): %s", exc)
            
            # Request is allowed, proceed to view
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    
    return decorator


"""
GOAL: Create a decorator that applies circuit breaker protection to functions.

PARAMETERS:
  service_name: str - Service identifier for circuit breaker - Must be non-empty
  failure_threshold: int - Failures before opening - Optional, overrides settings
  recovery_timeout: int - Seconds before HALF_OPEN - Optional, overrides settings
  success_threshold: int - Successes before closing - Optional, overrides settings

RETURNS:
  Callable - Decorator function - Not None

RAISES:
  ValueError: If service_name is empty

GUARANTEES:
  - Returns a decorator that can be applied to any callable
  - Circuit breaker check happens before function execution
  - Raises ExternalServiceError when circuit is OPEN
  - Records success/failure based on function execution
  - Gracefully degrades if circuit breaker disabled
"""
def circuit_breaker(
    service_name: str,
    failure_threshold: int | None = None,
    recovery_timeout: int | None = None,
    success_threshold: int | None = None
) -> Callable:
    """
    Create circuit breaker decorator with configurable parameters.
    """
    if not service_name or not service_name.strip():
        raise ValueError("service_name must be non-empty")

    """
    GOAL: Decorator that wraps function with circuit breaker protection.

    PARAMETERS:
      func: Callable - Function to wrap - Not None

    RETURNS:
      Callable - Wrapped function - Not None

    RAISES:
      ExternalServiceError: If circuit breaker is OPEN
      Exception: Any exception from wrapped function

    GUARANTEES:
      - Circuit breaker checked before function execution
      - Success recorded if function completes without exception
      - Failure recorded if function raises exception
      - ExternalServiceError raised when circuit is OPEN
      - Logs all circuit breaker state transitions
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            # Skip circuit breaker if disabled globally
            if not getattr(settings, "CIRCUIT_BREAKER_ENABLED", True):
                return func(*args, **kwargs)

            # Get circuit breaker instance
            cb = get_circuit_breaker(service_name)

            # Override config if custom parameters provided
            if failure_threshold is not None or recovery_timeout is not None or success_threshold is not None:
                from apps.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
                config = CircuitBreakerConfig(
                    failure_threshold=failure_threshold or cb.config.failure_threshold,
                    recovery_timeout=recovery_timeout or cb.config.recovery_timeout,
                    success_threshold=success_threshold or cb.config.success_threshold
                )
                # Create new circuit breaker instance with custom config
                cb = CircuitBreaker(service_name=service_name, config=config)

            try:
                # Check if request is allowed
                cb.allow_request()

                # Execute function
                result = func(*args, **kwargs)

                # Record success
                cb.record_success()

                return result

            except CircuitBreakerOpenError as exc:
                # Circuit is open, block execution
                logger.warning(
                    "Circuit breaker blocked request for %s.%s: %s",
                    func.__module__,
                    func.__name__,
                    exc.message
                )
                raise ExternalServiceError(
                    message=f"Service {service_name} is temporarily unavailable due to repeated failures. Please try again later.",
                    details={"service": service_name, "circuit_state": "OPEN"}
                ) from exc

            except Exception:
                # Record failure for other exceptions
                cb.record_failure()
                raise

        return wrapped

    return decorator


"""
GOAL: Create a decorator that marks views for API CSRF protection.

PARAMETERS:
  None

RETURNS:
  Callable - Decorator function - Not None

RAISES:
  None

GUARANTEES:
  - Marks view to bypass Django's CSRF token validation
  - Enables Origin/Referer header validation via middleware
  - Works with APICSRFProtectionMiddleware
  - Can be combined with other decorators
"""
def api_csrf_exempt(view_func: Callable) -> Callable:
    """
    Decorator that marks view for API CSRF protection with Origin/Referer validation.
    """
    from django.views.decorators.csrf import csrf_exempt as django_csrf_exempt
    
    # Apply Django's csrf_exempt first
    wrapped = django_csrf_exempt(view_func)
    
    # Mark the view for API CSRF protection
    # This flag is checked by APICSRFProtectionMiddleware
    wrapped._api_csrf_exempt = True  # type: ignore
    
    return wrapped
