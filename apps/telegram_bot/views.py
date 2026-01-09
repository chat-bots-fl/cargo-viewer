from __future__ import annotations

import json

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.auth.decorators import require_driver
from apps.auth.models import DriverProfile
from apps.core.decorators import api_csrf_exempt, rate_limit
from apps.core.exceptions import ValidationError as AppValidationError
from apps.core.schemas import TelegramResponseRequest
from apps.core.validation import validate_request_body
from apps.telegram_bot.handlers import TelegramUpdateHandler
from apps.telegram_bot.services import TelegramBotService

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


"""
GOAL: Receive Telegram Bot webhook updates and handle minimal commands (e.g., /start).

PARAMETERS:
  request: HttpRequest - POST from Telegram - Body must be JSON update

RETURNS:
  JsonResponse - {"ok": True} - HTTP 200

RAISES:
  None (errors are logged and returned as ok=false)

GUARANTEES:
  - Does not raise on malformed updates
"""
@csrf_exempt
@extend_schema(
    tags=["telegram"],
    summary="Telegram Bot Webhook",
    description=(
        "Принимает обновления от Telegram Bot API и обрабатывает команды. "
        "Не возвращает ошибки при некорректных обновлениях."
    ),
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Обновление обработано",
            examples=[
                OpenApiExample(
                    name="Успешная обработка",
                    value={"ok": True, "handled": True},
                ),
            ],
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка запроса",
            examples=[
                OpenApiExample(
                    name="Метод не разрешён",
                    value={"ok": False, "error": "method_not_allowed"},
                ),
                OpenApiExample(
                    name="Неверный JSON",
                    value={"ok": False, "error": "invalid_json"},
                ),
            ],
        ),
        500: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Внутренняя ошибка сервера",
        ),
    },
)
def telegram_webhook(request):
    """
    Parse Telegram update payload and route to TelegramUpdateHandler.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method_not_allowed"}, status=405)
    try:
        update = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    try:
        handled = TelegramUpdateHandler.handle_update(update)
        return JsonResponse({"ok": True, "handled": handled})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)


"""
GOAL: Handle driver cargo response coming from WebApp and forward it via Telegram bot.

PARAMETERS:
  request: HttpRequest - Authenticated driver request - POST form/JSON with cargo_id, phone, name

RETURNS:
  HttpResponse - Small HTML snippet for modal UI - HTTP 200/400

RAISES:
  None (returns error messages)

GUARANTEES:
  - Enforces idempotency per (user, cargo_id)
  - Enforces subscription access control (payment_required)
"""
@api_csrf_exempt
@require_driver
@rate_limit(requests_per_minute=20, endpoint_type="telegram")
@extend_schema(
    tags=["telegram"],
    summary="Отправить отклик на груз",
    description=(
        "Принимает отклик водителя на груз из WebApp и пересылает его через Telegram бот. "
        "Проверяет наличие активной подписки и обеспечивает идемпотентность."
    ),
    request=TelegramResponseRequest,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-фрагмент с результатом",
            examples=[
                OpenApiExample(
                    name="Успешная отправка",
                    value='<div class="muted">✅ Отправлено (id: 123).</div>',
                ),
            ],
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="Ошибка валидации или отправки",
            examples=[
                OpenApiExample(
                    name="Ошибка валидации",
                    value='<div class="muted">Ошибка валидации: cargo_id is required</div>',
                ),
                OpenApiExample(
                    name="Ошибка отправки",
                    value='<div class="muted">Ошибка отправки: Telegram API error</div>',
                ),
            ],
        ),
        402: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="Требуется подписка",
            examples=[
                OpenApiExample(
                    name="Нет подписки",
                    value='<div class="muted">Нужна подписка. Перейдите в раздел "Подписка".</div>',
                ),
            ],
        ),
        405: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Метод не разрешён",
        ),
    },
)
def handle_response(request):
    """
    Validate inputs, enforce subscription, then create-or-reuse response record and send Telegram message.
    """
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    try:
        validated = validate_request_body(TelegramResponseRequest, dict(request.POST))
        cargo_id = validated.cargo_id
        phone = validated.phone
        name = validated.name
    except AppValidationError as exc:
        return HttpResponse(f'<div class="muted">Ошибка валидации: {exc}</div>', status=400)

    if not name:
        name = str(getattr(request.user, "first_name", "") or "").strip()

    try:
        profile = DriverProfile.objects.get(user=request.user)
        telegram_user_id = int(profile.telegram_user_id)
    except DriverProfile.DoesNotExist:
        telegram_user_id = 0

    try:
        result = TelegramBotService.handle_response(
            user_id=int(request.user.id),
            telegram_user_id=telegram_user_id,
            cargo_id=cargo_id,
            phone=phone,
            name=name,
        )
    except ValidationError as exc:
        if getattr(exc, "messages", None) and "payment_required" in exc.messages:
            return HttpResponse('<div class="muted">Нужна подписка. Перейдите в раздел "Подписка".</div>', status=402)
        return HttpResponse(f'<div class="muted">Ошибка: {exc}</div>', status=400)
    except Exception as exc:
        return HttpResponse(f'<div class="muted">Ошибка отправки: {exc}</div>', status=502)

    return HttpResponse(f'<div class="muted">✅ Отправлено (id: {result["response_id"]}).</div>')
