from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.dtos import PromoCodeDTO, SubscriptionDTO, model_to_dto
from apps.core.repositories import PromoCodeRepository, PromoCodeUsageRepository
from apps.promocodes.models import PromoCode, PromoCodeUsage
from apps.subscriptions.services import SubscriptionService


@dataclass(frozen=True)
class ApplyPromoResult:
    subscription_dto: SubscriptionDTO
    days_added: int


class PromoCodeService:
    ACTION_TO_DAYS = {
        "extend_30": 30,
        "extend_60": 60,
        "extend_90": 90,
        "activate_trial": 7,
    }

    """
    GOAL: Create a promo code in admin flow.

    PARAMETERS:
      action: str - One of extend_30/extend_60/extend_90/activate_trial - Required
      valid_from: datetime - Start time - Must be >= now
      valid_until: datetime - End time - Must be > valid_from
      max_uses: int - Max uses - Must be >= 1
      code: str | None - Optional custom code - If None, auto-generated
      created_by: Any | None - Admin user - Optional
      description: str - Optional description

    RETURNS:
      PromoCodeDTO - Created promo code DTO - Never None

    RAISES:
      ValidationError: If parameters invalid
      IntegrityError: If code is not unique

    GUARANTEES:
      - Auto-generates code when missing
      - Creates audit log entry when created_by provided
    """
    @staticmethod
    def create_promo_code(
        *,
        action: str,
        valid_from: datetime,
        valid_until: datetime,
        max_uses: int = 1,
        code: str | None = None,
        created_by: Any | None = None,
        description: str = "",
        promo_code_repo: PromoCodeRepository | None = None,
    ) -> PromoCodeDTO:
        """
        Validate inputs, derive days_to_add, create PromoCode row, and write audit log.
        """
        if valid_until <= valid_from:
            raise ValidationError("valid_until must be after valid_from")
        if valid_from < timezone.now():
            raise ValidationError("valid_from cannot be in the past")
        if max_uses < 1:
            raise ValidationError("max_uses must be >= 1")
        if action not in PromoCodeService.ACTION_TO_DAYS:
            raise ValidationError(f"Invalid action: {action}")

        days = PromoCodeService.ACTION_TO_DAYS[action]

        if not code:
            code = PromoCode.generate_code()

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if promo_code_repo is not None:
            from asgiref.sync import sync_to_async
            promo = sync_to_async(promo_code_repo.create)(
                code=str(code).upper(),
                action=action,
                days_to_add=days,
                valid_from=valid_from,
                valid_until=valid_until,
                max_uses=max_uses,
                created_by=created_by,
                description=description,
            )
        else:
            promo = PromoCode.objects.create(
                code=str(code).upper(),
                action=action,
                days_to_add=days,
                valid_from=valid_from,
                valid_until=valid_until,
                max_uses=max_uses,
                created_by=created_by,
                description=description,
            )

        if created_by:
            AuditService.log(
                user_id=getattr(created_by, "id", None),
                action_type="promo_code",
                action=f"Created promo code: {promo.code}",
                target_id=promo.code,
                details={"action": action, "days": days, "max_uses": max_uses},
            )

        return model_to_dto(promo, PromoCodeDTO)

    """
    GOAL: Apply a promo code for a user and extend subscription atomically.

    PARAMETERS:
      user: Any - Django user instance - Must be non-null
      code: str - Promo code string - Must be non-empty
      promo_code_repo: PromoCodeRepository | None - Repository for promo code operations - Optional
      promo_code_usage_repo: PromoCodeUsageRepository | None - Repository for promo code usage operations - Optional

    RETURNS:
      ApplyPromoResult - Contains subscription_dto and days_added - Never None

    RAISES:
      ValidationError: If code invalid/expired/exhausted

    GUARANTEES:
      - Records PromoCodeUsage (success or failure)
      - Extends subscription and increments promo usage exactly once
    """
    @staticmethod
    @transaction.atomic
    def apply_promo_code(
        *,
        user: Any,
        code: str,
        promo_code_repo: PromoCodeRepository | None = None,
        promo_code_usage_repo: PromoCodeUsageRepository | None = None,
    ) -> ApplyPromoResult:
        """
        Validate promo code, activate subscription, and record usage.
        """
        code = str(code or "").strip().upper()
        if not code:
            raise ValidationError("code is required")

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if promo_code_repo is not None:
            from asgiref.sync import sync_to_async
            promo = sync_to_async(promo_code_repo.get_by_code)(code)
        else:
            promo = PromoCode.objects.select_for_update().filter(code=code).first()
        
        if not promo:
            raise ValidationError("Promo code not found")

        if not promo.can_use():
            # Use repository if provided, otherwise direct ORM access for backward compatibility
            if promo_code_usage_repo is not None:
                from asgiref.sync import sync_to_async
                sync_to_async(promo_code_usage_repo.create)(
                    promo_code=promo, user=user, success=False, reason="cannot_use", days_added=0
                )
            else:
                PromoCodeUsage.objects.create(promo_code=promo, user=user, success=False, reason="cannot_use")
            raise ValidationError("Promo code cannot be used")

        subscription = SubscriptionService.activate_from_promo(user=user, promo_code=promo)
        promo.use()
        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if promo_code_usage_repo is not None:
            from asgiref.sync import sync_to_async
            sync_to_async(promo_code_usage_repo.create)(
                promo_code=promo, user=user, success=True, days_added=promo.days_to_add
            )
        else:
            PromoCodeUsage.objects.create(promo_code=promo, user=user, success=True, days_added=promo.days_to_add)

        return ApplyPromoResult(subscription_dto=subscription, days_added=promo.days_to_add)
