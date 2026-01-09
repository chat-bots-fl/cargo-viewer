from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.payments.models import Payment, PaymentHistory
from apps.subscriptions.services import SubscriptionService


class WebhookHandler:
    """
    Webhook processing for YuKassa payment status updates.
    """

    """
    GOAL: Process YuKassa webhook payload and update payment/subscription atomically.

    PARAMETERS:
      webhook_data: dict[str, Any] - JSON from YuKassa - Must contain keys event and object

    RETURNS:
      tuple[Payment, Any | None] - Updated payment and optional subscription - Never None

    RAISES:
      ValidationError: If webhook structure invalid
      ObjectDoesNotExist: If payment not found

    GUARANTEES:
      - Idempotent: same status does not create side effects
      - payment.succeeded activates subscription
      - PaymentHistory record is created on status change
    """
    @staticmethod
    @transaction.atomic
    def process_webhook(webhook_data: dict[str, Any]) -> tuple[Payment, Any | None]:
        """
        Validate structure, find payment by yukassa id, update status, and activate subscription when succeeded.
        """
        if "event" not in webhook_data or "object" not in webhook_data:
            raise ValidationError("Invalid webhook structure")

        event = str(webhook_data["event"])
        payment_data = webhook_data["object"] or {}
        yukassa_id = str(payment_data.get("id") or "").strip()
        if not yukassa_id:
            raise ValidationError("Missing payment id in webhook")

        try:
            payment = Payment.objects.select_for_update().get(yukassa_payment_id=yukassa_id)
        except Payment.DoesNotExist as exc:
            raise ObjectDoesNotExist(f"Payment not found: {yukassa_id}") from exc

        old_status = payment.status
        new_status = str(payment_data.get("status") or "").strip()
        if not new_status:
            raise ValidationError("Missing status in webhook")

        if old_status == new_status:
            return payment, None

        payment.status = new_status
        if event == "payment.succeeded":
            payment.paid_at = timezone.now()
        payment.raw_yukassa_response = webhook_data
        payment.save(update_fields=["status", "paid_at", "raw_yukassa_response", "updated_at"])

        PaymentHistory.objects.create(
            payment=payment,
            event_type="webhook",
            old_status=old_status,
            new_status=new_status,
            raw_payload=webhook_data,
        )

        subscription = None
        if event == "payment.succeeded":
            subscription = SubscriptionService.activate_from_payment(user=payment.user, payment=payment, days=payment.subscription_days)

        AuditService.log(
            user_id=payment.user_id,
            action_type="payment",
            action=f"Payment {new_status}",
            target_id=str(payment.id),
            details={"old_status": old_status, "new_status": new_status, "event": event},
        )

        return payment, subscription

