"""
API CSRF Protection Middleware

This module provides Origin/Referer header validation for API endpoints
that use @api_csrf_exempt decorator, providing an additional layer of security
beyond Django's built-in CSRF protection.
"""

import logging
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)


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
        
        # Build the expected origin for same-origin requests
        same_origin = f"{request_scheme}://{request_host}"
        
        # Check if request_origin matches same_origin
        if request_origin == same_origin:
            return True, ""
        
        # Also check without port (some browsers omit default ports)
        same_origin_no_port = f"{request_scheme}://{request_host.split(':')[0]}"
        if request_origin == same_origin_no_port:
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
            return JsonResponse(
                {
                    "error": {
                        "code": "CSRF_VALIDATION_FAILED",
                        "message": "Request origin validation failed",
                        "details": reason,
                    }
                },
                status=403
            )
        
        # Origin is valid, proceed with request
        return self.get_response(request)
    
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
