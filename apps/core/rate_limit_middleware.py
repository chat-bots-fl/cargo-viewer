"""
Rate limiting middleware for protecting critical endpoints.

This middleware implements token bucket rate limiting using Django cache backend
(Redis preferred, with fallback to in-memory). Different limits are applied based
on endpoint type and user authentication status.
"""

import logging
import time
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.core.exceptions import RateLimitError

logger = logging.getLogger(__name__)


"""
GOAL: Generate a unique cache key for rate limiting based on user identity and endpoint type.

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None
  endpoint_type: str - Type of endpoint (auth, payment, telegram, admin, api) - Not empty

RETURNS:
  str - Unique cache key for rate limiting - Never empty

RAISES:
  None

GUARANTEES:
  - Authenticated users use user_id in key
  - Anonymous users use IP address in key
  - Key includes endpoint type for separate limits
  - Key is consistent for same user+endpoint combination
"""
def _get_rate_limit_key(request: HttpRequest, endpoint_type: str) -> str:
    """
    Generate cache key combining user identity and endpoint type.
    """
    # Use user_id for authenticated users, IP for anonymous
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
    
    return f"rate_limit:{endpoint_type}:{identifier}"


"""
GOAL: Determine endpoint type and corresponding rate limit based on request path.

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None

RETURNS:
  tuple[str, int] - (endpoint_type, requests_per_minute) - Never None

RAISES:
  None

GUARANTEES:
  - Returns default limit if path doesn't match known patterns
  - Uses settings for configurable limits
  - Endpoint type is one of: auth, payment, telegram, admin, api
"""
def _get_endpoint_limit(request: HttpRequest) -> tuple[str, int]:
    """
    Map request path to endpoint type and rate limit.
    """
    path = request.path.lower()
    
    # Auth endpoints
    if path.startswith("/auth/"):
        return ("auth", getattr(settings, "RATE_LIMIT_AUTH", 10))
    
    # Payment endpoints
    if path.startswith("/payments/"):
        return ("payment", getattr(settings, "RATE_LIMIT_PAYMENT", 5))
    
    # Telegram response endpoints
    if path.startswith("/telegram/response"):
        return ("telegram", getattr(settings, "RATE_LIMIT_TELEGRAM", 20))
    
    # Admin panel endpoints
    if path.startswith("/admin-panel/"):
        return ("admin", getattr(settings, "RATE_LIMIT_ADMIN", 100))
    
    # Default API limit
    return ("api", getattr(settings, "RATE_LIMIT_DEFAULT", 60))


"""
GOAL: Check if request is allowed based on rate limit using token bucket algorithm.

PARAMETERS:
  cache_key: str - Unique key for this user+endpoint - Not empty
  requests_per_minute: int - Maximum requests allowed per minute - Must be > 0

RETURNS:
  tuple[bool, int] - (is_allowed, retry_after_seconds) - Never None

RAISES:
  None

GUARANTEES:
  - Returns True if request is within limits (consumes one token)
  - Returns False with retry_after if limit exceeded
  - Uses token bucket algorithm with 1-minute window
  - Gracefully degrades if cache is unavailable (returns True)
"""
def _check_rate_limit(cache_key: str, requests_per_minute: int) -> tuple[bool, int]:
    """
    Implement token bucket rate limiting using Django cache.
    """
    try:
        # Get current state from cache
        state = cache.get(cache_key, {"tokens": requests_per_minute, "last_update": time.time()})
        
        now = time.time()
        elapsed = now - state["last_update"]
        
        # Refill tokens based on elapsed time (1 minute window)
        refill_rate = requests_per_minute / 60.0  # tokens per second
        new_tokens = elapsed * refill_rate
        state["tokens"] = min(requests_per_minute, state["tokens"] + new_tokens)
        state["last_update"] = now
        
        # Check if we have a token available
        if state["tokens"] >= 1.0:
            state["tokens"] -= 1.0
            # Update cache with 60 second TTL
            cache.set(cache_key, state, timeout=60)
            return (True, 0)
        else:
            # Calculate retry time (when next token will be available)
            tokens_needed = 1.0 - state["tokens"]
            retry_after = int((tokens_needed / refill_rate) + 0.5)
            retry_after = max(1, min(60, retry_after))  # Clamp between 1 and 60 seconds
            # Update cache without consuming token
            cache.set(cache_key, state, timeout=60)
            return (False, retry_after)
    
    except Exception as exc:
        # Graceful degradation: if cache fails, allow request but log error
        logger.error("Rate limit check failed (allowing request): %s", exc)
        return (True, 0)


"""
GOAL: Create Django middleware that applies rate limiting to all requests.

PARAMETERS:
  get_response: Callable - Django middleware get_response callable - Not None

RETURNS:
  Callable - Middleware function - Not None

RAISES:
  None

GUARANTEES:
  - Only applies rate limiting if RATE_LIMIT_ENABLED is True
  - Skips rate limiting for GET requests to static files
  - Returns HTTP 429 with Retry-After header when limit exceeded
  - Logs rate limit violations for monitoring
"""
def RateLimitMiddleware(get_response: Callable) -> Callable:
    """
    Create middleware that wraps request processing with rate limiting.
    """
    
    """
    GOAL: Process request with rate limiting check before passing to view.

    PARAMETERS:
      request: HttpRequest - Incoming HTTP request - Not None

    RETURNS:
      HttpResponse - Either rate limit error or view response - Not None

    RAISES:
      None (all exceptions caught)

    GUARANTEES:
      - Rate limiting is applied before view execution
      - Authenticated users have per-user limits
      - Anonymous users have per-IP limits
      - Different endpoints have different limits
    """
    def middleware(request: HttpRequest) -> HttpResponse:
        """
        Apply rate limiting check before processing request.
        """
        # Skip rate limiting if disabled
        if not getattr(settings, "RATE_LIMIT_ENABLED", False):
            return get_response(request)
        
        # Skip rate limiting for static files and health checks
        path = request.path.lower()
        if path.startswith("/static/") or path.startswith("/media/") or path == "/health/":
            return get_response(request)
        
        # Get endpoint type and limit
        endpoint_type, requests_per_minute = _get_endpoint_limit(request)
        
        # Generate cache key for this user+endpoint
        cache_key = _get_rate_limit_key(request, endpoint_type)
        
        # Check rate limit
        is_allowed, retry_after = _check_rate_limit(cache_key, requests_per_minute)
        
        if not is_allowed:
            # Log rate limit violation
            logger.warning(
                "Rate limit exceeded for %s endpoint: %s - Path: %s - Retry after: %d seconds",
                endpoint_type,
                cache_key,
                request.path,
                retry_after,
                extra={"request": request, "endpoint_type": endpoint_type},
            )
            
            # Return 429 Too Many Requests with Retry-After header
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
        
        # Request is allowed, proceed to view
        return get_response(request)
    
    return middleware
