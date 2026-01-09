from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from apps.auth.services import TokenService

User = get_user_model()


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
    def process_request(self, request: HttpRequest) -> None:
        request.auth_context = RequestAuthContext()  # type: ignore[attr-defined]

        header = request.META.get("HTTP_AUTHORIZATION", "")
        token = ""
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ").strip()
        else:
            token = str(request.COOKIES.get("session_token") or "").strip()

        if not token:
            request.user = getattr(request, "user", AnonymousUser())
            return

        try:
            result = TokenService.validate_session(token)
        except Exception:
            request.user = AnonymousUser()
            return

        request.auth_context.driver_data = result.driver_data  # type: ignore[attr-defined]
        request.auth_context.refreshed_token = result.refreshed_token  # type: ignore[attr-defined]
        try:
            request.user = User.objects.get(id=int(result.driver_data["user_id"]))
        except Exception:
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
