from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import JsonResponse

from apps.auth.models import DriverProfile
from apps.auth.services import SessionService, TelegramAuthService
from apps.core.decorators import api_csrf_exempt, rate_limit
from apps.core.exceptions import AuthenticationError, ValidationError as AppValidationError
from apps.core.schemas import TelegramAuthRequest
from apps.core.validation import validate_request_body

# Import for OpenAPI documentation (graceful degradation if not available)
try:
    from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
    from drf_spectacular.types import OpenApiTypes
    DRF_SPECTACULAR_AVAILABLE = True
except ImportError:
    DRF_SPECTACULAR_AVAILABLE = False
    # Fallback decorators that do nothing
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    class OpenApiExample:
        pass
    class OpenApiResponse:
        pass
    class OpenApiTypes:
        STR = str
        OBJECT = dict

User = get_user_model()


"""
GOAL: Authenticate driver using Telegram WebApp initData and return a JWT session token.

PARAMETERS:
  request: HttpRequest - Django request - Must be POST with JSON {"init_data": str}

RETURNS:
  JsonResponse - {"session_token": str, "driver": {...}} on success - HTTP 200

RAISES:
  None (errors are converted to JSON responses)

GUARANTEES:
  - initData is validated via HMAC + max_age
  - Driver user/profile is created or updated idempotently
  - Exactly one active session per user in Redis (previous revoked)
"""
@api_csrf_exempt
@rate_limit(requests_per_minute=10, endpoint_type="auth")
@extend_schema(
    tags=["auth"],
    summary="Аутентификация через Telegram WebApp",
    description=(
        "Аутентифицирует водителя используя Telegram WebApp initData. "
        "Валидирует HMAC и max_age, создаёт/обновляет пользователя и профиль, "
        "выдаёт JWT токен сессии."
    ),
    request=TelegramAuthRequest,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Успешная аутентификация",
            examples=[
                OpenApiExample(
                    name="Успешный ответ",
                    value={
                        "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "driver": {
                            "driver_id": 123456789,
                            "first_name": "Иван",
                            "username": "ivan_driver",
                        },
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка валидации",
            examples=[
                OpenApiExample(
                    name="Неверный JSON",
                    value={"error": "invalid_json"},
                ),
                OpenApiExample(
                    name="Ошибка валидации initData",
                    value={"error": "Invalid Telegram init_data"},
                ),
            ],
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка аутентификации",
            examples=[
                OpenApiExample(
                    name="Неверный initData",
                    value={"error": "Failed to validate Telegram data: HMAC mismatch"},
                ),
            ],
        ),
    },
)
def telegram_auth(request):
    """
    Validate initData, upsert Django user + DriverProfile, then issue a JWT token bound to Redis session id.
    """
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid_json"}, status=400)

    try:
        validated = validate_request_body(TelegramAuthRequest, payload)
        init_data = validated.init_data
    except AppValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        tg = TelegramAuthService.validate_init_data(init_data, max_age_seconds=300)
    except AuthenticationError as exc:
        raise exc
    except Exception as exc:
        raise AuthenticationError(f"Failed to validate Telegram data: {str(exc)}")

    telegram_user_id = int(tg["id"])
    first_name = str(tg.get("first_name") or "").strip()
    telegram_username = str(tg.get("username") or "").strip()

    username = f"tg_{telegram_user_id}"
    user, created = User.objects.get_or_create(username=username, defaults={"first_name": first_name})
    if created:
        user.set_unusable_password()
    if first_name and user.first_name != first_name:
        user.first_name = first_name
    user.is_active = True
    user.save(update_fields=["first_name", "is_active", "password"] if created else ["first_name", "is_active"])

    profile, _ = DriverProfile.objects.get_or_create(
        telegram_user_id=telegram_user_id,
        defaults={"user": user, "telegram_username": telegram_username},
    )
    if profile.user_id != user.id:
        profile.user = user
    if telegram_username and profile.telegram_username != telegram_username:
        profile.telegram_username = telegram_username
    profile.save(update_fields=["user", "telegram_username"])

    token = SessionService.create_session(
        user,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT"),
    )

    response = JsonResponse(
        {
            "session_token": token,
            "driver": {
                "driver_id": telegram_user_id,
                "first_name": first_name,
                "username": telegram_username,
            },
        }
    )
    response.set_cookie(
        "session_token",
        token,
        httponly=True,
        samesite="Lax",
        secure=not getattr(settings, "DEBUG", False),
        max_age=SessionService.DEFAULT_TTL_SECONDS,
    )
    return response
