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

        # Логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"JWTMiddleware - path: {request.path}, header: {header[:50] if header else 'none'}, cookie_token: {bool(request.COOKIES.get('session_token'))}, token: {token[:20] if token else 'none'}...")

        if not token:
            logger.warning(f"JWTMiddleware - no token found, setting AnonymousUser")
            request.user = getattr(request, "user", AnonymousUser())
            return

        try:
            logger.info(f"JWTMiddleware - calling TokenService.validate_session with token: {token[:20]}...")
            result = TokenService.validate_session(token)
            logger.info(f"JWTMiddleware - token validated, user_dto: {result.user_dto}, driver_dto: {result.driver_dto}")
        except Exception as e:
            logger.error(f"JWTMiddleware - token validation failed: {e}", exc_info=True)
            request.user = AnonymousUser()
            return

        logger.info(f"JWTMiddleware - setting auth_context.driver_data: {result.driver_dto}")
        request.auth_context.driver_data = result.driver_dto  # type: ignore[attr-defined]
        request.auth_context.refreshed_token = result.refreshed_token  # type: ignore[attr-defined]
        
        if result.user_dto:
            try:
                logger.info(f"JWTMiddleware - getting user with id: {result.user_dto.id}")
                request.user = User.objects.get(id=int(result.user_dto.id))
                logger.info(f"JWTMiddleware - user set: {request.user.username}, user.id: {request.user.id}")
                
                # Проверяем наличие driverprofile
                if hasattr(request.user, 'driverprofile'):
                    logger.info(f"JWTMiddleware - user has driverprofile attribute")
                else:
                    logger.warning(f"JWTMiddleware - user does NOT have driverprofile attribute")
                    
            except Exception as e:
                logger.error(f"JWTMiddleware - failed to get user: {e}", exc_info=True)
                request.user = AnonymousUser()
        else:
            logger.warning(f"JWTMiddleware - user_dto is None, setting AnonymousUser")
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
