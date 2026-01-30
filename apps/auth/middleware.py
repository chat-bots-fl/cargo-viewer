from __future__ import annotations

import logging

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from apps.auth.services import TokenService

User = get_user_model()

logger = logging.getLogger(__name__)


@dataclass
class RequestAuthContext:
    driver_data: dict[str, Any] | None = None
    refreshed_token: str | None = None


class JWTAuthenticationMiddleware(MiddlewareMixin):
    """
    GOAL: Attach driver authentication context to request using JWT from Authorization header or cookie.

    PARAMETERS:
      request: HttpRequest - Django request - Any path - Reads Authorization/cookies

    RETURNS:
      None

    RAISES:
      None (invalid tokens result in AnonymousUser)

    GUARANTEES:
      - Sets request.auth_context with driver_data when token valid
      - Sets request.user to the authenticated Django user when possible
      - Does not block request handling (views enforce auth via decorators)
    """
    """
    GOAL: Attach auth context from JWT without leaking secrets into logs.

    PARAMETERS:
      request: HttpRequest - Django request - Reads Authorization/cookies

    RETURNS:
      None

    RAISES:
      None (invalid tokens result in AnonymousUser)

    GUARANTEES:
      - Never logs raw JWT/session_token/Authorization header values
      - On invalid token, request.user is AnonymousUser
      - On valid token, request.auth_context is populated
    """
    def process_request(self, request: HttpRequest) -> None:
        request.auth_context = RequestAuthContext()  # type: ignore[attr-defined]

        header = request.META.get("HTTP_AUTHORIZATION", "")
        token = ""
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ").strip()
        else:
            token = str(request.COOKIES.get("session_token") or "").strip()

        # Логирование для отладки
        logger.debug(
            "JWT auth: token present (path=%s source=%s)",
            request.path,
            "header" if header.startswith("Bearer ") else "cookie",
        )

        if not token:
            logger.debug("JWT auth: no token (path=%s)", request.path)
            request.user = getattr(request, "user", AnonymousUser())
            return

        try:
            result = TokenService.validate_session(token)
        except Exception:
            logger.info(
                "JWT auth: token validation failed (path=%s)",
                request.path,
                exc_info=getattr(settings, "DEBUG", False),
            )
            request.user = AnonymousUser()
            return

        request.auth_context.driver_data = result.driver_data  # type: ignore[attr-defined]
        request.auth_context.refreshed_token = result.refreshed_token  # type: ignore[attr-defined]
        
        if result.driver_data.get("user_id"):
            try:
                request.user = User.objects.get(id=int(result.driver_data["user_id"]))
                
                # Проверяем наличие driverprofile
                if hasattr(request.user, "driver_profile"):
                    pass
                else:
                    pass
                    
            except Exception:
                logger.warning(
                    "JWT auth: failed to load Django user (path=%s user_id=%s)",
                    request.path,
                    result.driver_data.get("user_id"),
                    exc_info=getattr(settings, "DEBUG", False),
                )
                request.user = AnonymousUser()
        else:
            logger.debug("JWT auth: user_id missing in token (path=%s)", request.path)
            request.user = AnonymousUser()

    """
    GOAL: Add refreshed session token to response headers when sliding-window refresh occurs.

    PARAMETERS:
      request: HttpRequest - Django request - Must have auth_context
      response: HttpResponse - Django response

    RETURNS:
      HttpResponse - Same response with optional X-Session-Token header

    RAISES:
      None

    GUARANTEES:
      - If auth_context.refreshed_token present, sets X-Session-Token header
    """
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        ctx = getattr(request, "auth_context", None)
        if ctx and getattr(ctx, "refreshed_token", None):
            response["X-Session-Token"] = ctx.refreshed_token
        return response
