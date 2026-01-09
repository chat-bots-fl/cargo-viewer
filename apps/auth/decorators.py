from __future__ import annotations

import logging
from functools import wraps
from typing import Callable, TypeVar

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpRequest, HttpResponse

from apps.auth.services import is_admin_user, has_admin_subscription

logger = logging.getLogger("admin_auth")

T = TypeVar("T", bound=Callable[..., HttpResponse])


"""
GOAL: Wrap a view to require a valid driver session (JWT + Redis binding).

PARAMETERS:
  view: Callable[..., HttpResponse] - Django view callable - Must accept (request, *args, **kwargs)

RETURNS:
  Callable[..., HttpResponse] - Wrapped view that returns 401 JSON when unauthenticated

RAISES:
  None

GUARANTEES:
  - Does not execute wrapped view when auth_context missing/invalid
  - Preserves wrapped view metadata via functools.wraps
"""
def require_driver(view: T) -> T:
    """
    Enforce that a valid driver session exists (JWT + Redis session binding).
    """

    @wraps(view)
    def _wrapped(request: HttpRequest, *args, **kwargs):
        ctx = getattr(request, "auth_context", None)
        if not ctx or not ctx.driver_data:
            return JsonResponse({"error": "unauthorized"}, status=401)
        return view(request, *args, **kwargs)

    return _wrapped  # type: ignore[return-value]


"""
GOAL: Wrap a view to require admin privileges (staff or superuser).

PARAMETERS:
  view: Callable[..., HttpResponse] - Django view callable - Must accept (request, *args, **kwargs)
  require_subscription: bool - Whether to check for admin subscription - Default from settings

RETURNS:
  Callable[..., HttpResponse] - Wrapped view that returns 403 when user lacks admin rights

RAISES:
  None

GUARANTEES:
  - Does not execute wrapped view when user is not authenticated
  - Does not execute wrapped view when user is not staff/superuser
  - Does not execute wrapped view when subscription check fails (if required)
  - Logs all access denials with user context
  - Preserves wrapped view metadata via functools.wraps
"""
def require_admin(view: T | None = None, *, require_subscription: bool | None = None) -> T | Callable[[T], T]:
    """
    Enforce that user is authenticated, staff/superuser, and optionally has admin subscription.
    Supports both @require_admin and @require_admin(require_subscription=True) syntax.
    """
    
    def decorator(view_func: T) -> T:
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args, **kwargs):
            user = getattr(request, "user", None)
            
            # Check authentication
            if not user or not user.is_authenticated:
                logger.warning(
                    "Admin access denied: unauthenticated attempt to %s from %s",
                    request.path,
                    _get_client_ip(request),
                )
                return JsonResponse({"error": "forbidden", "reason": "unauthenticated"}, status=403)
            
            # Check admin privileges
            if not is_admin_user(user):
                logger.warning(
                    "Admin access denied: user_id=%s username=%s lacks admin privileges for %s from %s",
                    user.id,
                    user.username,
                    request.path,
                    _get_client_ip(request),
                )
                return JsonResponse({"error": "forbidden", "reason": "not_admin"}, status=403)
            
            # Check subscription if required
            check_subscription = (
                require_subscription
                if require_subscription is not None
                else getattr(settings, "ADMIN_REQUIRE_SUBSCRIPTION", False)
            )
            
            if check_subscription:
                feature_key = getattr(settings, "ADMIN_SUBSCRIPTION_FEATURE", "admin_access")
                if not has_admin_subscription(user, feature_key=feature_key):
                    logger.warning(
                        "Admin access denied: user_id=%s username=%s lacks admin subscription for %s from %s",
                        user.id,
                        user.username,
                        request.path,
                        _get_client_ip(request),
                    )
                    return JsonResponse({"error": "forbidden", "reason": "no_admin_subscription"}, status=403)
            
            # All checks passed, log access and execute view
            logger.info(
                "Admin access granted: user_id=%s username=%s to %s from %s",
                user.id,
                user.username,
                request.path,
                _get_client_ip(request),
            )
            return view_func(request, *args, **kwargs)
        
        return _wrapped  # type: ignore[return-value]
    
    # Support both @require_admin and @require_admin(require_subscription=True) syntax
    if view is None:
        return decorator  # type: ignore[return-value]
    return decorator(view)


"""
GOAL: Extract client IP address from request.

PARAMETERS:
  request: HttpRequest - Django request object - Not None

RETURNS:
  str - Client IP address or "unknown" - Never None

RAISES:
  None

GUARANTEES:
  - Returns "unknown" if IP cannot be determined
  - Checks both REMOTE_ADDR and X-Forwarded-For headers
"""
def _get_client_ip(request: HttpRequest) -> str:
    """
    Get client IP from REMOTE_ADDR or X-Forwarded-For header.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return ip
