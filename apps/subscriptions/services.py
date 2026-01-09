from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.audit.services import AuditService
from apps.core.dtos import SubscriptionDTO, model_to_dto
from apps.core.query_utils import (
    get_subscription_status_cached,
    invalidate_subscription_cache,
)
from apps.core.repositories import FeatureFlagRepository, SubscriptionRepository
from apps.subscriptions.models import Subscription


class SubscriptionService:
    """
    Subscription lifecycle and access checks.
    """

    """
    GOAL: Activate or extend a subscription after a successful payment.

    PARAMETERS:
      user: Any - Django user instance - Must be non-null
      payment: Any - Payment instance - Must have status='succeeded'
      days: int - Subscription length in days - Must be > 0
      subscription_repo: SubscriptionRepository | None - Repository for subscription operations - Optional

    RETURNS:
      SubscriptionDTO - Created or updated subscription DTO - Never None

    RAISES:
      ValidationError: If payment not succeeded or days invalid
      IntegrityError: If access_token collisions persist after retries

    GUARANTEES:
      - Subscription created or extended atomically
      - Active subscription is extended, expired subscription restarts from now
      - access_token is regenerated on each activation
      - Audit log entry created
    """
    @staticmethod
    @transaction.atomic
    def activate_from_payment(
        *,
        user: Any,
        payment: Any,
        days: int,
        subscription_repo: SubscriptionRepository | None = None,
    ) -> SubscriptionDTO:
        """
        Extend subscription based on existing expiry and regenerate access token.
        Invalidates subscription cache after update.
        """
        if getattr(payment, "status", None) != "succeeded":
            raise ValidationError(f"Payment not succeeded: {getattr(payment, 'status', None)}")
        if days <= 0:
            raise ValidationError(f"Invalid days: {days}")

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if subscription_repo is not None:
            from asgiref.sync import sync_to_async
            existing_subscription = sync_to_async(subscription_repo.get_by_user_with_relations)(user.id)
            if existing_subscription:
                subscription = existing_subscription
                created = False
            else:
                subscription = Subscription(user=user, source=Subscription.SOURCE_PAYMENT, payment=payment)
                created = True
        else:
            subscription, created = Subscription.objects.select_for_update().get_or_create(
                user=user,
                defaults={"source": Subscription.SOURCE_PAYMENT, "payment": payment},
            )

        if subscription.is_expired() or not subscription.expires_at:
            subscription.activated_at = timezone.now()
            subscription.expires_at = timezone.now() + timedelta(days=days)
        else:
            subscription.expires_at = subscription.expires_at + timedelta(days=days)

        subscription.is_active = True
        subscription.source = Subscription.SOURCE_PAYMENT
        subscription.payment = payment
        subscription.promo_code = None

        for _ in range(3):
            subscription.access_token = secrets.token_urlsafe(32)
            try:
                subscription.save()
                break
            except IntegrityError:
                continue
        else:
            raise IntegrityError("Failed to generate unique access_token after 3 attempts")

        AuditService.log(
            user_id=getattr(user, "id", None),
            action_type="subscription",
            action="Created subscription" if created else f"Extended subscription by {days} days",
            target_id=str(subscription.id),
            details={"days": days, "expires_at": subscription.expires_at.isoformat(), "payment_id": str(payment.id)},
        )

        invalidate_subscription_cache(int(getattr(user, "id", 0)))
        return model_to_dto(subscription, SubscriptionDTO)

    """
    GOAL: Activate or extend a subscription using a validated promo code.

    PARAMETERS:
      user: Any - Django user instance - Must be non-null
      promo_code: Any - PromoCode instance - Must be usable (can_use() == True)
      subscription_repo: SubscriptionRepository | None - Repository for subscription operations - Optional

    RETURNS:
      SubscriptionDTO - Updated subscription DTO - Never None

    RAISES:
      ValidationError: If promo_code cannot be used

    GUARANTEES:
      - Subscription extended by promo_code.days_to_add
      - promo_code usage is recorded by caller (PromoCodeUsage)
      - Audit log entry created
    """
    @staticmethod
    @transaction.atomic
    def activate_from_promo(
        *,
        user: Any,
        promo_code: Any,
        subscription_repo: SubscriptionRepository | None = None,
    ) -> SubscriptionDTO:
        """
        Extend subscription and bind promo_code, regenerating access_token.
        Invalidates subscription cache after update.
        """
        if not promo_code or not getattr(promo_code, "can_use", None):
            raise ValidationError("Invalid promo_code")
        if not promo_code.can_use():
            raise ValidationError(f"Promo code cannot be used: {promo_code.code}")

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if subscription_repo is not None:
            from asgiref.sync import sync_to_async
            existing_subscription = sync_to_async(subscription_repo.get_by_user_with_relations)(user.id)
            if existing_subscription:
                subscription = existing_subscription
                created = False
            else:
                subscription = Subscription(user=user, source=Subscription.SOURCE_PROMO, promo_code=promo_code)
                created = True
        else:
            subscription, created = Subscription.objects.select_for_update().get_or_create(
                user=user,
                defaults={"source": Subscription.SOURCE_PROMO, "promo_code": promo_code},
            )

        days = int(getattr(promo_code, "days_to_add", 0) or 0)
        if days <= 0:
            raise ValidationError("Promo code days_to_add must be > 0")

        base = subscription.expires_at if subscription.expires_at and not subscription.is_expired() else timezone.now()
        subscription.activated_at = timezone.now()
        subscription.expires_at = base + timedelta(days=days)
        subscription.is_active = True
        subscription.source = Subscription.SOURCE_PROMO
        subscription.promo_code = promo_code
        subscription.payment = None
        subscription.access_token = secrets.token_urlsafe(32)
        subscription.save()

        AuditService.log(
            user_id=getattr(user, "id", None),
            action_type="subscription",
            action="Activated with promo code",
            target_id=str(subscription.id),
            details={"promo_code": promo_code.code, "days": days, "expires_at": subscription.expires_at.isoformat()},
        )

        invalidate_subscription_cache(int(getattr(user, "id", 0)))
        return model_to_dto(subscription, SubscriptionDTO)

    """
    GOAL: Decide whether a user is allowed to access a feature (paid/free) without deploys.

    PARAMETERS:
      user_id: int - Django user id - Must be > 0
      feature_key: str - Feature key - Must be non-empty
      feature_flag_repo: FeatureFlagRepository | None - Repository for feature flag operations - Optional

    RETURNS:
      bool - True if access is allowed - Never None

    RAISES:
      None (safe default is deny for paid features when data missing)

    GUARANTEES:
      - If feature flag 'payments_enabled' is disabled, paid features are denied
      - For respond_to_cargo, requires active non-expired subscription
    """
    @staticmethod
    def is_access_allowed(
        *,
        user_id: int,
        feature_key: str,
        feature_flag_repo: FeatureFlagRepository | None = None,
    ) -> bool:
        """
        Enforce paid feature gating via FeatureFlag + Subscription state.
        Uses cached subscription status to avoid repeated database queries.
        """
        feature_key = str(feature_key or "").strip()
        if not feature_key:
            return False

        if feature_key != "respond_to_cargo":
            return True

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if feature_flag_repo is not None:
            from asgiref.sync import sync_to_async
            payments_enabled = sync_to_async(feature_flag_repo.is_enabled)("payments_enabled")
        else:
            from apps.feature_flags.models import FeatureFlag
            payments_flag = FeatureFlag.objects.filter(key="payments_enabled").first()
            payments_enabled = payments_flag.enabled if payments_flag else False
        
        if not payments_enabled:
            return False

        status = get_subscription_status_cached(int(user_id))
        if not status["has_subscription"]:
            return False
        if not status["is_active"]:
            return False
        if status["is_expired"]:
            return False
        return True

