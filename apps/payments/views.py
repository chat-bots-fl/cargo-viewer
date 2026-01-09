from __future__ import annotations

import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from apps.auth.decorators import require_driver
from apps.core.decorators import api_csrf_exempt, rate_limit
from apps.core.exceptions import BusinessLogicError, ValidationError as AppValidationError
from apps.core.schemas import PaymentCreateRequest
from apps.core.validation import validate_request_body
from apps.feature_flags.models import SystemSetting
from apps.payments.services import PaymentService
from apps.payments.webhooks import WebhookHandler
from apps.subscriptions.models import Subscription

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
GOAL: Render paywall/subscription status page for the driver.

PARAMETERS:
  request: HttpRequest - Can be anonymous (shows message) - Recommended with driver session cookie

RETURNS:
  HttpResponse - Rendered paywall template - HTTP 200

RAISES:
  None

GUARANTEES:
  - Tariffs are loaded from SystemSetting['tariffs'] with defaults fallback
"""
def paywall(request):
    """
    Render tariffs and current subscription status.
    """
    tariffs = SystemSetting.get_setting("tariffs", None) or PaymentService.DEFAULT_TARIFFS

    subscription = None
    if getattr(request, "user", None) and getattr(request.user, "is_authenticated", False):
        subscription = Subscription.objects.filter(user=request.user).first()

    return render(
        request,
        "paywall.html",
        {
            "tariffs": tariffs,
            "subscription": subscription,
            "return_url": getattr(settings, "WEBAPP_URL", "") or request.build_absolute_uri("/"),
        },
    )


"""
GOAL: Create a payment for selected tariff and return a confirmation URL to the client.

PARAMETERS:
  request: HttpRequest - Authenticated driver request - POST with tariff_name and return_url

RETURNS:
  HttpResponse - HTML snippet containing payment link - HTTP 200/400

RAISES:
  None (errors are converted to HTML)

GUARANTEES:
  - Requires driver session (JWT)
  - Idempotent within 5 minutes for same user+tariff
"""
@api_csrf_exempt
@require_driver
@rate_limit(requests_per_minute=5, endpoint_type="payment")
@extend_schema(
    tags=["payments"],
    summary="Создать платёж",
    description=(
        "Создаёт платёж в YuKassa для выбранного тарифа и возвращает "
        "URL подтверждения для перенаправления пользователя."
    ),
    request=PaymentCreateRequest,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="HTML-фрагмент со ссылкой на оплату",
            examples=[
                OpenApiExample(
                    name="Успешное создание",
                    value='<div><a class="btn" href="https://yoomoney.ru/checkout/..." target="_blank" rel="noopener">Перейти к оплате</a></div>',
                ),
            ],
        ),
        202: OpenApiResponse(
            response=OpenApiTypes.STR,
            description="Платёж создан, но ссылка не получена",
            examples=[
                OpenApiExample(
                    name="Ссылка недоступна",
                    value='<div class="muted">Платёж создан, но ссылка не получена. Попробуйте позже.</div>',
                ),
            ],
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка валидации",
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Требуется аутентификация",
        ),
        422: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка бизнес-логики",
        ),
    },
)
def create_payment(request):
    """
    Validate tariff name and create a YuKassa payment, returning confirmation link for redirect.
    """
    if request.method != "POST":
        raise AppValidationError("Method not allowed")

    try:
        validated = validate_request_body(PaymentCreateRequest, dict(request.POST))
        tariff_name = validated.tariff_name
        return_url = validated.return_url or getattr(settings, "WEBAPP_URL", "") or ""
    except AppValidationError as exc:
        raise exc

    try:
        payment = PaymentService.create_payment(user=request.user, tariff_name=tariff_name, return_url=return_url)
    except AppValidationError as exc:
        raise exc
    except BusinessLogicError as exc:
        raise exc
    except Exception as exc:
        raise BusinessLogicError(f"Failed to create payment: {str(exc)}")

    if payment.confirmation_url:
        return HttpResponse(
            f'<div><a class="btn" href="{payment.confirmation_url}" target="_blank" rel="noopener">Перейти к оплате</a></div>'
        )

    return HttpResponse('<div class="muted">Платёж создан, но ссылка не получена. Попробуйте позже.</div>', status=202)


"""
GOAL: Receive YuKassa webhook and update payment/subscription status.

PARAMETERS:
  request: HttpRequest - POST from YuKassa - JSON body

RETURNS:
  JsonResponse - {"ok": True} - HTTP 200

RAISES:
  None (errors converted to JSON)

GUARANTEES:
  - Optional shared-secret validation via YOOKASSA_WEBHOOK_SECRET
  - Webhook processing is idempotent by payment status
"""
@csrf_exempt
@extend_schema(
    tags=["payments"],
    summary="Webhook YuKassa",
    description=(
        "Принимает webhook от YuKassa и обновляет статус платежа/подписки. "
        "Поддерживает валидацию подписи через YOOKASSA_WEBHOOK_SECRET."
    ),
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Webhook обработан успешно",
            examples=[
                OpenApiExample(
                    name="Успешная обработка",
                    value={
                        "ok": True,
                        "payment_id": "123e4567-e89b-12d3-a456-426614174000",
                        "status": "succeeded",
                        "subscription": "987e6543-e21b-43d2-a876-543219876543",
                    },
                ),
            ],
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка валидации",
            examples=[
                OpenApiExample(
                    name="Неверная подпись",
                    value={"error": "Invalid webhook signature"},
                ),
                OpenApiExample(
                    name="Неверный JSON",
                    value={"error": "Invalid JSON payload"},
                ),
            ],
        ),
        422: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Ошибка бизнес-логики",
        ),
    },
)
def yookassa_webhook(request):
    """
    Validate webhook secret (if configured) and process the webhook payload atomically.
    """
    if request.method != "POST":
        raise ValidationError("Method not allowed")

    secret = str(getattr(settings, "YOOKASSA_WEBHOOK_SECRET", "") or "").strip()
    if secret:
        token = str(request.META.get("HTTP_X_WEBHOOK_TOKEN") or "").strip()
        if token != secret:
            raise ValidationError("Invalid webhook signature")

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON payload")

    try:
        payment, subscription = WebhookHandler.process_webhook(payload)
        return JsonResponse(
            {
                "ok": True,
                "payment_id": str(payment.id),
                "status": payment.status,
                "subscription": str(getattr(subscription, "id", "")) if subscription else None,
            }
        )
    except BusinessLogicError as exc:
        raise exc
    except Exception as exc:
        raise BusinessLogicError(f"Failed to process webhook: {str(exc)}")

