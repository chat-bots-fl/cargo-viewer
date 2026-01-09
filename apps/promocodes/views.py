from __future__ import annotations

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from apps.auth.decorators import require_driver
from apps.promocodes.services import PromoCodeService


"""
GOAL: Apply a promo code for the current driver and extend subscription.

PARAMETERS:
  request: HttpRequest - Authenticated driver request - POST with code

RETURNS:
  HttpResponse - HTML snippet with result message - HTTP 200/400

RAISES:
  None (errors converted to HTML)

GUARANTEES:
  - Requires driver session (JWT)
  - On success, subscription is extended and usage is recorded
"""
@csrf_exempt
@require_driver
def apply_promocode(request):
    """
    Validate and apply promo code using PromoCodeService.
    """
    if request.method != "POST":
        return HttpResponse("method_not_allowed", status=405)

    code = str(request.POST.get("code") or "").strip()
    try:
        result = PromoCodeService.apply_promo_code(user=request.user, code=code)
        return HttpResponse(f"<div>✅ Промокод применён: +{result.days_added} дней (до {result.subscription_expires_at}).</div>")
    except ValidationError as exc:
        return HttpResponse(f'<div class="muted">Ошибка: {exc}</div>', status=400)
    except Exception as exc:
        return HttpResponse(f'<div class="muted">Ошибка: {exc}</div>', status=502)

