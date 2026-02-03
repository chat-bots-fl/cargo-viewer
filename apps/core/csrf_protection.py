"""
API CSRF Protection Middleware

This module provides Origin/Referer header validation for API endpoints
that use @api_csrf_exempt decorator, providing an additional layer of security
beyond Django's built-in CSRF protection.
"""

import json
import logging
from typing import Any, Callable, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)


"""
GOAL: Create a JsonResponse that also provides a .json() helper for tests.

PARAMETERS:
  payload: dict[str, Any] - JSON-serializable response payload - Must be a dict
  status: int - HTTP status code - Must be positive

RETURNS:
  JsonResponse - Django JsonResponse with added .json() method - Never None

RAISES:
  TypeError: If payload is not JSON serializable

GUARANTEES:
  - Returned response is a valid Django JsonResponse
  - Returned response supports response.json() in RequestFactory-based tests
"""
def _json_response(payload: dict[str, Any], status: int) -> JsonResponse:
    """
    Build JsonResponse and attach a small json() helper for parity with Django test client responses.
    """
    response = JsonResponse(payload, status=status)

    def _json() -> Any:
        return json.loads(response.content.decode(response.charset))

    setattr(response, "json", _json)
    return response


"""
GOAL: Validate request origin against allowed origins list.

PARAMETERS:
  request: HttpRequest - Django request object - Not None
  allowed_origins: list[str] - List of allowed origin patterns - Can be empty
  allow_same_origin: bool - Whether to allow requests from same origin - Default True

RETURNS:
  tuple[bool, str] - (is_allowed, reason) - True if origin is allowed

RAISES:
  None

GUARANTEES:
  - Returns (True, "") if origin is valid
  - Returns (False, reason) if origin is invalid
  - Checks Origin header first, then Referer as fallback
  - Handles missing headers gracefully
  - Supports reverse proxies via X-Forwarded-Proto / X-Forwarded-Host for same-origin validation
"""
def validate_origin(
    request: HttpRequest,
    allowed_origins: list[str],
    allow_same_origin: bool = True
) -> tuple[bool, str]:
    """
    Check Origin or Referer header against allowed origins list.
    """
    # Get origin from headers
    origin = request.META.get("HTTP_ORIGIN", "").strip()
    referer = request.META.get("HTTP_REFERER", "").strip()
    
    # Use Origin header if present, otherwise use Referer
    request_origin = origin or referer
    
    # If neither header is present, reject
    if not request_origin:
        return False, "Missing Origin and Referer headers"
    
    # Extract origin from Referer (remove path)
    if referer and not origin:
        # Referer format: https://example.com/path
        # Extract just the origin: https://example.com
        if "://" in referer:
            request_origin = referer.split("/", 3)[:3]
            request_origin = "/".join(request_origin)
        else:
            request_origin = referer
    
    # Check if same origin is allowed
    if allow_same_origin:
        # Get the host from the request
        request_host = request.get_host()
        request_scheme = request.scheme

        forwarded_proto = request.META.get("HTTP_X_FORWARDED_PROTO", "").split(",")[0].strip().lower()
        forwarded_host = request.META.get("HTTP_X_FORWARDED_HOST", "").split(",")[0].strip()

        candidates: set[str] = set()

        def _strip_port(host: str) -> str:
            if host.startswith("[") and "]" in host:
                return host.split("]")[0] + "]"
            if ":" in host:
                return host.split(":", 1)[0]
            return host

        def _add_candidate(scheme: str, host: str) -> None:
            if not scheme or not host:
                return
            candidates.add(f"{scheme}://{host}")
            candidates.add(f"{scheme}://{_strip_port(host)}")

        _add_candidate(request_scheme, request_host)
        _add_candidate(forwarded_proto, request_host)
        _add_candidate(request_scheme, forwarded_host)
        _add_candidate(forwarded_proto, forwarded_host)

        if request_origin in candidates:
            return True, ""
    
    # Check against allowed origins list
    if allowed_origins:
        for allowed in allowed_origins:
            # Exact match
            if request_origin == allowed:
                return True, ""
            
            # Wildcard match (e.g., https://*.example.com)
            if "*" in allowed:
                parts = allowed.split("*")
                if len(parts) == 2:
                    prefix, suffix = parts
                    if request_origin.startswith(prefix) and request_origin.endswith(suffix):
                        return True, ""
    
    # Origin not allowed
    return False, f"Origin '{request_origin}' not allowed"


"""
GOAL: Check if request method requires CSRF protection.

PARAMETERS:
  request: HttpRequest - Django request object - Not None

RETURNS:
  bool - True if method requires CSRF protection

RAARISES:
  None

GUARANTEES:
  - Returns True for POST, PUT, DELETE, PATCH methods
  - Returns False for GET, HEAD, OPTIONS methods
"""
def requires_csrf_protection(request: HttpRequest) -> bool:
    """
    Determine if request method needs CSRF validation.
    """
    method = request.method.upper() if request.method else ""
    return method in {"POST", "PUT", "DELETE", "PATCH"}


"""
GOAL: Middleware class that validates Origin/Referer headers for API endpoints.

PARAMETERS:
  get_response: Callable - Django's get_response callable - Not None

RETURNS:
  APICSRFProtectionMiddleware - Middleware instance

RAISES:
  None

GUARANTEES:
  - Validates Origin/Referer for state-changing requests
  - Only applies to views marked with @api_csrf_exempt
  - Logs all rejections with details
  - Returns HTTP 403 on validation failure
"""
class APICSRFProtectionMiddleware:
    """
    Middleware for API CSRF protection using Origin/Referer headers.
    """
    
    def __init__(self, get_response):
        """
        Initialize middleware with Django's get_response callable.
        """
        self.get_response = get_response
        
        # Load settings
        self.enabled = getattr(settings, "API_CSRF_ENABLED", True)
        self.allowed_origins = getattr(settings, "API_CSRF_ALLOWED_ORIGINS", [])
        self.allow_same_origin = getattr(settings, "API_CSRF_ALLOW_SAME_ORIGIN", True)
    
    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request and validate Origin/Referer if needed.
        """
        # Skip if protection is disabled
        if not self.enabled:
            return self.get_response(request)
        
        # Skip if request doesn't require CSRF protection
        if not requires_csrf_protection(request):
            return self.get_response(request)
        
        # Skip if view is not marked for API CSRF protection
        # This is set by the @api_csrf_exempt decorator
        if not getattr(request, "_api_csrf_exempt", False):
            return self.get_response(request)
        
        # Validate origin
        is_allowed, reason = validate_origin(
            request,
            self.allowed_origins,
            self.allow_same_origin
        )
        
        if not is_allowed:
            # Log the rejection
            logger.warning(
                "API CSRF protection blocked request - Path: %s - Method: %s - Origin: %s - Reason: %s - IP: %s",
                request.path,
                request.method,
                request.META.get("HTTP_ORIGIN", request.META.get("HTTP_REFERER", "")),
                reason,
                self._get_client_ip(request),
                extra={
                    "request": request,
                    "path": request.path,
                    "method": request.method,
                    "origin": request.META.get("HTTP_ORIGIN", request.META.get("HTTP_REFERER", "")),
                    "reason": reason,
                }
            )
             
            # Return 403 Forbidden
            return _json_response(
                {
                    "error": {
                        "code": "CSRF_VALIDATION_FAILED",
                        "message": "Request origin validation failed",
                        "details": reason,
                    }
                },
                status=403,
            )
        
        # Origin is valid, proceed with request
        return self.get_response(request)

    """
    GOAL: Apply API CSRF origin validation based on view decoration in real Django request flow.

    PARAMETERS:
      request: HttpRequest - Django request object - Not None
      view_func: Callable - Django view callable - Not None
      view_args: tuple[Any, ...] - Positional args for the view - Can be empty
      view_kwargs: dict[str, Any] - Keyword args for the view - Can be empty

    RETURNS:
      Optional[HttpResponse] - 403 JsonResponse when blocked, otherwise None to continue - Can be None

    RAISES:
      None

    GUARANTEES:
      - Only validates state-changing requests (POST/PUT/PATCH/DELETE)
      - Only applies to views marked with @api_csrf_exempt (via view_func._api_csrf_exempt)
      - Returns 403 with JSON error payload when origin is invalid
    """
    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable,
        view_args: tuple[Any, ...],
        view_kwargs: dict[str, Any],
    ) -> Optional[HttpResponse]:
        """
        Mirror the RequestFactory-based logic using Django's process_view hook to detect decorated views.
        """
        if not self.enabled:
            return None
        if not requires_csrf_protection(request):
            return None
        if not getattr(view_func, "_api_csrf_exempt", False):
            return None

        setattr(request, "_api_csrf_exempt", True)

        is_allowed, reason = validate_origin(request, self.allowed_origins, self.allow_same_origin)
        if is_allowed:
            return None

        logger.warning(
            "API CSRF protection blocked request - Path: %s - Method: %s - Origin: %s - Reason: %s - IP: %s",
            request.path,
            request.method,
            request.META.get("HTTP_ORIGIN", request.META.get("HTTP_REFERER", "")),
            reason,
            self._get_client_ip(request),
            extra={
                "request": request,
                "path": request.path,
                "method": request.method,
                "origin": request.META.get("HTTP_ORIGIN", request.META.get("HTTP_REFERER", "")),
                "reason": reason,
            },
        )

        return _json_response(
            {
                "error": {
                    "code": "CSRF_VALIDATION_FAILED",
                    "message": "Request origin validation failed",
                    "details": reason,
                }
            },
            status=403,
        )
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Extract client IP address from request.
        """
        # Check various headers for IP (supports proxies)
        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("HTTP_X_REAL_IP", "").strip()
            or request.META.get("REMOTE_ADDR", "").strip()
        )
        return ip or "unknown"
