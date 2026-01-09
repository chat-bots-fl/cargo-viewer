"""
Repository Pattern implementation for Django ORM abstraction.

This module provides a base repository class and specific repositories
for each model in the application, following contract-based programming.
"""

from __future__ import annotations

from typing import Any, Generic, List, Optional, Type, TypeVar

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from django.db import models

# Import all models
from apps.audit.models import AuditLog
from apps.auth.models import DriverProfile, TelegramSession
from apps.feature_flags.models import FeatureFlag, SystemSetting
from apps.payments.models import Payment, PaymentHistory
from apps.promocodes.models import PromoCode, PromoCodeUsage
from apps.subscriptions.models import Subscription
from apps.telegram_bot.models import DriverCargoResponse

User = get_user_model()

# Type variable for generic repository
T = TypeVar("T", bound=models.Model)


class BaseRepository(Generic[T]):
    """
    Base repository with common CRUD operations.
    
    Provides abstraction over Django ORM with support for
    select_related and prefetch_related.
    """

    def __init__(self, model: Type[T]) -> None:
        """
        Initialize repository with model class.
        
        PARAMETERS:
          model: Type[T] - Django model class - Not None
        """
        self.model = model

    """
    GOAL: Retrieve a single instance by its primary key.

    PARAMETERS:
      pk: Any - Primary key value - Not None
      select_related: Optional[List[str]] - Fields to select - Default None
      prefetch_related: Optional[List[str]] - Fields to prefetch - Default None

    RETURNS:
      Optional[T] - Model instance or None if not found

    RAISES:
      None

    GUARANTEES:
      - Returns None instead of raising DoesNotExist
      - Applies select_related and prefetch_related if provided
    """
    async def get(
        self,
        pk: Any,
        select_related: Optional[List[str]] = None,
        prefetch_related: Optional[List[str]] = None,
    ) -> Optional[T]:
        """
        Fetch single record by PK with optional eager loading.
        """
        queryset = self.model.objects.all()
        
        if select_related:
            queryset = queryset.select_related(*select_related)
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)
        
        return await sync_to_async(queryset.filter(pk=pk).first)()

    """
    GOAL: Retrieve a single instance by filter criteria.

    PARAMETERS:
      **kwargs: Any - Filter criteria - Django ORM compatible

    RETURNS:
      Optional[T] - Model instance or None if not found

    RAISES:
      None

    GUARANTEES:
      - Returns None instead of raising DoesNotExist
      - Returns first matching record only
    """
    async def get_by(self, **kwargs: Any) -> Optional[T]:
        """
        Fetch single record matching filter criteria.
        """
        return await sync_to_async(self.model.objects.filter(**kwargs).first)()

    """
    GOAL: Retrieve multiple instances by filter criteria.

    PARAMETERS:
      **kwargs: Any - Filter criteria - Django ORM compatible

    RETURNS:
      List[T] - List of matching instances - Empty list if none found

    RAISES:
      None

    GUARANTEES:
      - Returns empty list instead of raising DoesNotExist
      - Results ordered by model's default ordering
    """
    async def filter(self, **kwargs: Any) -> List[T]:
        """
        Fetch all records matching filter criteria.
        """
        return list(await sync_to_async(list)(self.model.objects.filter(**kwargs)))

    """
    GOAL: Retrieve all instances from the model.

    PARAMETERS:
      select_related: Optional[List[str]] - Fields to select - Default None
      prefetch_related: Optional[List[str]] - Fields to prefetch - Default None

    RETURNS:
      List[T] - List of all instances - Empty list if none exist

    RAISES:
      None

    GUARANTEES:
      - Returns empty list instead of raising DoesNotExist
      - Applies eager loading if provided
    """
    async def all(
        self,
        select_related: Optional[List[str]] = None,
        prefetch_related: Optional[List[str]] = None,
    ) -> List[T]:
        """
        Fetch all records with optional eager loading.
        """
        queryset = self.model.objects.all()
        
        if select_related:
            queryset = queryset.select_related(*select_related)
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)
        
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Create a new instance with given attributes.

    PARAMETERS:
      **kwargs: Any - Field values for new instance - Must be valid for model

    RETURNS:
      T - Created instance - Saved to database

    RAISES:
      ValidationError: If field values are invalid
      IntegrityError: If unique constraint violated

    GUARANTEES:
      - Instance is saved to database
      - Returns instance with auto-generated fields populated
    """
    async def create(self, **kwargs: Any) -> T:
        """
        Create and save new record.
        """
        instance = self.model(**kwargs)
        await sync_to_async(instance.save)()
        return instance

    """
    GOAL: Update an existing instance with new values.

    PARAMETERS:
      instance: T - Instance to update - Must exist in database
      **kwargs: Any - Fields to update - Must be valid for model

    RETURNS:
      T - Updated instance - Saved to database

    RAISES:
      None

    GUARANTEES:
      - Only specified fields are updated
      - Changes are persisted to database
    """
    async def update(self, instance: T, **kwargs: Any) -> T:
        """
        Update specific fields of existing record.
        """
        for field, value in kwargs.items():
            setattr(instance, field, value)
        await sync_to_async(instance.save)()
        return instance

    """
    GOAL: Delete an instance from the database.

    PARAMETERS:
      instance: T - Instance to delete - Must exist in database

    RETURNS:
      None

    RAISES:
      None

    GUARANTEES:
      - Instance is removed from database
      - Cascade deletes are applied per model configuration
    """
    async def delete(self, instance: T) -> None:
        """
        Delete record from database.
        """
        await sync_to_async(instance.delete)()

    """
    GOAL: Count instances matching filter criteria.

    PARAMETERS:
      **kwargs: Any - Filter criteria - Django ORM compatible

    RETURNS:
      int - Count of matching instances - Never negative

    RAISES:
      None

    GUARANTEES:
      - Returns 0 if no matches found
    """
    async def count(self, **kwargs: Any) -> int:
        """
        Count records matching filter criteria.
        """
        return await sync_to_async(self.model.objects.filter(**kwargs).count)()

    """
    GOAL: Check if any instance matches filter criteria.

    PARAMETERS:
      **kwargs: Any - Filter criteria - Django ORM compatible

    RETURNS:
      bool - True if at least one match exists

    RAISES:
      None

    GUARANTEES:
      - More efficient than count() for existence checks
    """
    async def exists(self, **kwargs: Any) -> bool:
        """
        Check if any record matches filter criteria.
        """
        return await sync_to_async(self.model.objects.filter(**kwargs).exists)()


# ============================================================================
# Specific Repositories for Each Model
# ============================================================================


class UserRepository(BaseRepository[User]):
    """
    Repository for User model operations.
    """

    def __init__(self) -> None:
        super().__init__(User)

    """
    GOAL: Find user by username.

    PARAMETERS:
      username: str - Username to search - Not empty

    RETURNS:
      Optional[User] - User instance or None

    RAISES:
      None

    GUARANTEES:
      - Case-sensitive username match
    """
    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Fetch user by username field.
        """
        return await self.get_by(username=username)

    """
    GOAL: Find user by email.

    PARAMETERS:
      email: str - Email to search - Not empty

    RETURNS:
      Optional[User] - User instance or None

    RAISES:
      None

    GUARANTEES:
      - Case-insensitive email match
    """
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Fetch user by email field.
        """
        return await self.get_by(email__iexact=email)


class DriverProfileRepository(BaseRepository[DriverProfile]):
    """
    Repository for DriverProfile model operations.
    """

    def __init__(self) -> None:
        super().__init__(DriverProfile)

    """
    GOAL: Find driver profile by Telegram user ID.

    PARAMETERS:
      telegram_user_id: int - Telegram user ID - Must be > 0

    RETURNS:
      Optional[DriverProfile] - Driver profile or None

    RAISES:
      None

    GUARANTEES:
      - Exact match on telegram_user_id
    """
    async def get_by_telegram_user_id(
        self, telegram_user_id: int
    ) -> Optional[DriverProfile]:
        """
        Fetch driver profile by Telegram user ID.
        """
        return await self.get_by(telegram_user_id=telegram_user_id)

    """
    GOAL: Find driver profile by user ID with user data.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0

    RETURNS:
      Optional[DriverProfile] - Driver profile with user or None

    RAISES:
      None

    GUARANTEES:
      - Includes related user object
    """
    async def get_by_user_with_relations(
        self, user_id: int
    ) -> Optional[DriverProfile]:
        """
        Fetch driver profile with related user.
        """
        queryset = self.model.objects.select_related("user").filter(user_id=user_id)
        return await sync_to_async(queryset.first)()


class TelegramSessionRepository(BaseRepository[TelegramSession]):
    """
    Repository for TelegramSession model operations.
    """

    def __init__(self) -> None:
        super().__init__(TelegramSession)

    """
    GOAL: Find active (non-revoked) session for user.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0

    RETURNS:
      Optional[TelegramSession] - Active session or None

    RAISES:
      None

    GUARANTEES:
      - Returns only non-revoked sessions
      - Returns most recent session if multiple exist
    """
    async def get_active_session(
        self, user_id: int
    ) -> Optional[TelegramSession]:
        """
        Fetch active session for user.
        """
        queryset = self.model.objects.filter(
            user_id=user_id, revoked_at__isnull=True
        ).order_by("-created_at")
        return await sync_to_async(queryset.first)()

    """
    GOAL: Find session by session ID with user data.

    PARAMETERS:
      session_id: str - Session UUID - Must be valid UUID

    RETURNS:
      Optional[TelegramSession] - Session with user or None

    RAISES:
      None

    GUARANTEES:
      - Includes related user object
    """
    async def get_by_session_id_with_user(
        self, session_id: str
    ) -> Optional[TelegramSession]:
        """
        Fetch session by ID with related user.
        """
        queryset = self.model.objects.select_related("user").filter(
            session_id=session_id
        )
        return await sync_to_async(queryset.first)()

    """
    GOAL: Revoke all active sessions for user.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0

    RETURNS:
      int - Number of sessions revoked - Never negative

    RAISES:
      None

    GUARANTEES:
      - Only active sessions are affected
      - revoked_at set to current time
    """
    async def revoke_all_user_sessions(self, user_id: int) -> int:
        """
        Revoke all active sessions for user.
        """
        from django.utils import timezone
        
        count = await sync_to_async(
            self.model.objects.filter(user_id=user_id, revoked_at__isnull=True).update
        )(revoked_at=timezone.now())
        return count


class SubscriptionRepository(BaseRepository[Subscription]):
    """
    Repository for Subscription model operations.
    """

    def __init__(self) -> None:
        super().__init__(Subscription)

    """
    GOAL: Find subscription by user ID with related data.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0

    RETURNS:
      Optional[Subscription] - Subscription with relations or None

    RAISES:
      None

    GUARANTEES:
      - Includes payment and promo_code relations
    """
    async def get_by_user_with_relations(
        self, user_id: int
    ) -> Optional[Subscription]:
        """
        Fetch subscription with related payment and promo code.
        """
        queryset = self.model.objects.select_related(
            "user", "payment", "promo_code"
        ).filter(user_id=user_id)
        return await sync_to_async(queryset.first)()

    """
    GOAL: Find active (non-expired) subscriptions.

    PARAMETERS:
      None

    RETURNS:
      List[Subscription] - List of active subscriptions

    RAISES:
      None

    GUARANTEES:
      - Only returns is_active=True and not expired
    """
    async def get_active_subscriptions(self) -> List[Subscription]:
        """
        Fetch all active subscriptions.
        """
        from django.utils import timezone
        
        queryset = self.model.objects.filter(
            is_active=True, expires_at__gt=timezone.now()
        )
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Find subscription by access token.

    PARAMETERS:
      token: str - Access token - Not empty

    RETURNS:
      Optional[Subscription] - Subscription or None

    RAISES:
      None

    GUARANTEES:
      - Exact match on access_token
    """
    async def get_by_access_token(self, token: str) -> Optional[Subscription]:
        """
        Fetch subscription by access token.
        """
        return await self.get_by(access_token=token)


class PaymentRepository(BaseRepository[Payment]):
    """
    Repository for Payment model operations.
    """

    def __init__(self) -> None:
        super().__init__(Payment)

    """
    GOAL: Find payment by user ID with history.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0

    RETURNS:
      List[Payment] - List of payments with history

    RAISES:
      None

    GUARANTEES:
      - Includes history records for each payment
      - Ordered by created_at descending
    """
    async def get_by_user_with_history(self, user_id: int) -> List[Payment]:
        """
        Fetch payments with related history.
        """
        queryset = self.model.objects.filter(user_id=user_id).prefetch_related(
            "history"
        ).order_by("-created_at")
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Find payment by Yukassa payment ID.

    PARAMETERS:
      yukassa_id: str - Yukassa payment ID - Not empty

    RETURNS:
      Optional[Payment] - Payment or None

    RAISES:
      None

    GUARANTEES:
      - Exact match on yukassa_payment_id
    """
    async def get_by_yukassa_id(self, yukassa_id: str) -> Optional[Payment]:
        """
        Fetch payment by Yukassa payment ID.
        """
        return await self.get_by(yukassa_payment_id=yukassa_id)

    """
    GOAL: Find payments by status.

    PARAMETERS:
      status: str - Payment status - Must be valid STATUS_CHOICES

    RETURNS:
      List[Payment] - List of payments with given status

    RAISES:
      None

    GUARANTEES:
      - Ordered by created_at descending
    """
    async def get_by_status(self, status: str) -> List[Payment]:
        """
        Fetch payments by status.
        """
        queryset = self.model.objects.filter(status=status).order_by("-created_at")
        return list(await sync_to_async(list)(queryset))


class PaymentHistoryRepository(BaseRepository[PaymentHistory]):
    """
    Repository for PaymentHistory model operations.
    """

    def __init__(self) -> None:
        super().__init__(PaymentHistory)

    """
    GOAL: Find history records for a payment.

    PARAMETERS:
      payment_id: str - Payment UUID - Must be valid UUID

    RETURNS:
      List[PaymentHistory] - List of history records

    RAISES:
      None

    GUARANTEES:
      - Ordered by created_at descending
    """
    async def get_by_payment(self, payment_id: str) -> List[PaymentHistory]:
        """
        Fetch history records for payment.
        """
        queryset = self.model.objects.filter(payment_id=payment_id).order_by(
            "-created_at"
        )
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Create a history record for payment status change.

    PARAMETERS:
      payment: Payment - Payment instance - Not None
      event_type: str - Type of event - Not empty
      old_status: Optional[str] - Previous status - Can be None
      new_status: Optional[str] - New status - Can be None
      raw_payload: Optional[dict] - Raw data - Default empty dict

    RETURNS:
      PaymentHistory - Created history record

    RAISES:
      None

    GUARANTEES:
      - Record is saved to database
      - created_at set to current time
    """
    async def create_history_event(
        self,
        payment: Payment,
        event_type: str,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        raw_payload: Optional[dict] = None,
    ) -> PaymentHistory:
        """
        Create payment history event.
        """
        return await self.create(
            payment=payment,
            event_type=event_type,
            old_status=old_status or "",
            new_status=new_status or "",
            raw_payload=raw_payload or {},
        )


class AuditLogRepository(BaseRepository[AuditLog]):
    """
    Repository for AuditLog model operations.
    """

    def __init__(self) -> None:
        super().__init__(AuditLog)

    """
    GOAL: Find audit logs for a user.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0
      limit: Optional[int] - Max records to return - Default None (all)

    RETURNS:
      List[AuditLog] - List of audit logs

    RAISES:
      None

    GUARANTEES:
      - Ordered by created_at descending
      - Respects limit parameter
    """
    async def get_by_user(self, user_id: int, limit: Optional[int] = None) -> List[AuditLog]:
        """
        Fetch audit logs for user.
        """
        queryset = self.model.objects.filter(user_id=user_id).order_by("-created_at")
        if limit:
            queryset = queryset[:limit]
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Find audit logs by action type.

    PARAMETERS:
      action_type: str - Type of action - Not empty
      limit: Optional[int] - Max records to return - Default None (all)

    RETURNS:
      List[AuditLog] - List of audit logs

    RAISES:
      None

    GUARANTEES:
      - Ordered by created_at descending
      - Respects limit parameter
    """
    async def get_by_action_type(
        self, action_type: str, limit: Optional[int] = None
    ) -> List[AuditLog]:
        """
        Fetch audit logs by action type.
        """
        queryset = self.model.objects.filter(action_type=action_type).order_by(
            "-created_at"
        )
        if limit:
            queryset = queryset[:limit]
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Create an audit log entry.

    PARAMETERS:
      user: Optional[User] - User who performed action - Can be None
      username: str - Username string - Not empty
      action_type: str - Type of action - Not empty
      action: str - Description of action - Not empty
      target_id: Optional[str] - ID of target object - Default empty
      details: Optional[dict] - Additional details - Default empty dict
      ip_address: Optional[str] - IP address - Default None
      user_agent: Optional[str] - User agent string - Default empty

    RETURNS:
      AuditLog - Created audit log entry

    RAISES:
      None

    GUARANTEES:
      - Record is saved to database
      - created_at set to current time
    """
    async def create_log(
        self,
        user: Optional[User],
        username: str,
        action_type: str,
        action: str,
        target_id: str = "",
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: str = "",
    ) -> AuditLog:
        """
        Create audit log entry.
        """
        return await self.create(
            user=user,
            username=username,
            action_type=action_type,
            action=action,
            target_id=target_id,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )


class PromoCodeRepository(BaseRepository[PromoCode]):
    """
    Repository for PromoCode model operations.
    """

    def __init__(self) -> None:
        super().__init__(PromoCode)

    """
    GOAL: Find promo code by code string.

    PARAMETERS:
      code: str - Promo code string - Not empty

    RETURNS:
      Optional[PromoCode] - Promo code or None

    RAISES:
      None

    GUARANTEES:
      - Case-sensitive exact match
    """
    async def get_by_code(self, code: str) -> Optional[PromoCode]:
        """
        Fetch promo code by code string.
        """
        return await self.get_by(code=code)

    """
    GOAL: Find active (usable) promo codes.

    PARAMETERS:
      action: Optional[str] - Filter by action type - Default None

    RETURNS:
      List[PromoCode] - List of active promo codes

    RAISES:
      None

    GUARANTEES:
      - Only returns codes where can_use() is True
      - Filters by action if provided
    """
    async def get_active_promo_codes(
        self, action: Optional[str] = None
    ) -> List[PromoCode]:
        """
        Fetch active promo codes.
        """
        from django.utils import timezone
        
        queryset = self.model.objects.filter(
            disabled=False,
            valid_from__lte=timezone.now(),
            valid_until__gte=timezone.now(),
        )
        if action:
            queryset = queryset.filter(action=action)
        return list(await sync_to_async(list)(queryset))


class PromoCodeUsageRepository(BaseRepository[PromoCodeUsage]):
    """
    Repository for PromoCodeUsage model operations.
    """

    def __init__(self) -> None:
        super().__init__(PromoCodeUsage)

    """
    GOAL: Find usage records for a promo code.

    PARAMETERS:
      promo_code_id: int - Promo code primary key - Must be > 0

    RETURNS:
      List[PromoCodeUsage] - List of usage records

    RAISES:
      None

    GUARANTEES:
      - Ordered by used_at descending
    """
    async def get_by_promo_code(self, promo_code_id: int) -> List[PromoCodeUsage]:
        """
        Fetch usage records for promo code.
        """
        queryset = self.model.objects.filter(promo_code_id=promo_code_id).order_by(
            "-used_at"
        )
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Find usage records for a user.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0

    RETURNS:
      List[PromoCodeUsage] - List of usage records

    RAISES:
      None

    GUARANTEES:
      - Ordered by used_at descending
    """
    async def get_by_user(self, user_id: int) -> List[PromoCodeUsage]:
        """
        Fetch usage records for user.
        """
        queryset = self.model.objects.filter(user_id=user_id).order_by("-used_at")
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Check if user has already used a promo code.

    PARAMETERS:
      promo_code_id: int - Promo code primary key - Must be > 0
      user_id: int - User primary key - Must be > 0

    RETURNS:
      bool - True if user has used the code

    RAISES:
      None

    GUARANTEES:
      - Only checks successful usages (success=True)
    """
    async def user_has_used_code(
        self, promo_code_id: int, user_id: int
    ) -> bool:
        """
        Check if user has used promo code.
        """
        return await self.exists(
            promo_code_id=promo_code_id, user_id=user_id, success=True
        )


class DriverCargoResponseRepository(BaseRepository[DriverCargoResponse]):
    """
    Repository for DriverCargoResponse model operations.
    """

    def __init__(self) -> None:
        super().__init__(DriverCargoResponse)

    """
    GOAL: Find response by user and cargo ID.

    PARAMETERS:
      user_id: int - User primary key - Must be > 0
      cargo_id: str - Cargo ID - Not empty

    RETURNS:
      Optional[DriverCargoResponse] - Response or None

    RAISES:
      None

    GUARANTEES:
      - Unique constraint ensures at most one result
    """
    async def get_by_user_and_cargo(
        self, user_id: int, cargo_id: str
    ) -> Optional[DriverCargoResponse]:
        """
        Fetch response by user and cargo ID.
        """
        return await self.get_by(user_id=user_id, cargo_id=cargo_id)

    """
    GOAL: Find all responses for a cargo.

    PARAMETERS:
      cargo_id: str - Cargo ID - Not empty

    RETURNS:
      List[DriverCargoResponse] - List of responses

    RAISES:
      None

    GUARANTEES:
      - Ordered by created_at descending
    """
    async def get_by_cargo(self, cargo_id: str) -> List[DriverCargoResponse]:
        """
        Fetch all responses for cargo.
        """
        queryset = self.model.objects.filter(cargo_id=cargo_id).order_by("-created_at")
        return list(await sync_to_async(list)(queryset))

    """
    GOAL: Find responses by status.

    PARAMETERS:
      status: str - Response status - Not empty

    RETURNS:
      List[DriverCargoResponse] - List of responses

    RAISES:
      None

    GUARANTEES:
      - Ordered by created_at descending
    """
    async def get_by_status(self, status: str) -> List[DriverCargoResponse]:
        """
        Fetch responses by status.
        """
        queryset = self.model.objects.filter(status=status).order_by("-created_at")
        return list(await sync_to_async(list)(queryset))


class SystemSettingRepository(BaseRepository[SystemSetting]):
    """
    Repository for SystemSetting model operations.
    """

    def __init__(self) -> None:
        super().__init__(SystemSetting)

    """
    GOAL: Find setting by key.

    PARAMETERS:
      key: str - Setting key - Not empty

    RETURNS:
      Optional[SystemSetting] - Setting or None

    RAISES:
      None

    GUARANTEES:
      - Case-sensitive exact match
    """
    async def get_by_key(self, key: str) -> Optional[SystemSetting]:
        """
        Fetch setting by key.
        """
        return await self.get_by(key=key)

    """
    GOAL: Find secret settings.

    PARAMETERS:
      None

    RETURNS:
      List[SystemSetting] - List of secret settings

    RAISES:
      None

    GUARANTEES:
      - Only returns settings where is_secret=True
    """
    async def get_secret_settings(self) -> List[SystemSetting]:
        """
        Fetch all secret settings.
        """
        return await self.filter(is_secret=True)


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    """
    Repository for FeatureFlag model operations.
    """

    def __init__(self) -> None:
        super().__init__(FeatureFlag)

    """
    GOAL: Find feature flag by key.

    PARAMETERS:
      key: str - Feature flag key - Not empty

    RETURNS:
      Optional[FeatureFlag] - Feature flag or None

    RAISES:
      None

    GUARANTEES:
      - Case-sensitive exact match
    """
    async def get_by_key(self, key: str) -> Optional[FeatureFlag]:
        """
        Fetch feature flag by key.
        """
        return await self.get_by(key=key)

    """
    GOAL: Find enabled feature flags.

    PARAMETERS:
      None

    RETURNS:
      List[FeatureFlag] - List of enabled flags

    RAISES:
      None

    GUARANTEES:
      - Only returns flags where enabled=True
    """
    async def get_enabled_flags(self) -> List[FeatureFlag]:
        """
        Fetch all enabled feature flags.
        """
        return await self.filter(enabled=True)

    """
    GOAL: Check if feature flag is enabled.

    PARAMETERS:
      key: str - Feature flag key - Not empty

    RETURNS:
      bool - True if flag exists and is enabled

    RAISES:
      None

    GUARANTEES:
      - Returns False if flag doesn't exist
    """
    async def is_enabled(self, key: str) -> bool:
        """
        Check if feature flag is enabled.
        """
        flag = await self.get_by_key(key)
        return flag.enabled if flag else False
