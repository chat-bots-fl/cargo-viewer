from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl

import jwt
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone as dj_timezone

from apps.auth.models import TelegramSession, User, DriverProfile
from apps.core.dtos import (
    UserDTO,
    DriverProfileDTO,
    TelegramSessionDTO,
    model_to_dto,
    dto_to_dict,
)
from apps.core.query_utils import get_telegram_user_id_cached
from apps.core.repositories import SubscriptionRepository, TelegramSessionRepository

logger = logging.getLogger("telegram_auth")

# Import Sentry monitoring functions (graceful degradation if not available)
try:
    from apps.core.monitoring import (
        capture_exception,
        add_breadcrumb,
        set_user_context,
    )
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("Sentry monitoring not available in auth")
    
    # Fallback functions
    def capture_exception(*args, **kwargs):
        return None
    def add_breadcrumb(*args, **kwargs):
        pass
    def set_user_context(*args, **kwargs):
        pass


@dataclass(frozen=True)
class SessionValidationResult:
    user_dto: Optional[UserDTO]
    driver_dto: Optional[DriverProfileDTO]
    session_dto: Optional[TelegramSessionDTO]
    refreshed_token: str | None = None


class TelegramAuthService:
    """
    Security-sensitive operations for Telegram WebApp authentication.
    """

    """
    GOAL: Validate Telegram WebApp initData and extract driver identity fields.

    PARAMETERS:
      init_data: str - Raw initData querystring from Telegram WebApp - Must include hash and auth_date
      max_age_seconds: int - Max allowed age for auth_date - Must be > 0, default 300

    RETURNS:
      dict[str, Any] - Driver identity data with keys {id, first_name, username, auth_date} - id is int

    RAISES:
      ValidationError: If TELEGRAM_BOT_TOKEN missing
      ValidationError: If hash missing/invalid or auth_date invalid/expired
      ValidationError: If user payload missing/invalid

    GUARANTEES:
      - Uses constant-time comparison for HMAC
      - Rejects replayed/expired initData older than max_age_seconds
      - Does not log secrets (logs only short prefix)
    """
    @staticmethod
    def validate_init_data(init_data: str, *, max_age_seconds: int = 300) -> dict[str, Any]:
        """
        Validate Telegram hash and auth_date, then parse user JSON and return identity fields.
        """
        if not init_data:
            raise ValidationError("init_data is required")
        if max_age_seconds <= 0:
            raise ValidationError(f"max_age_seconds must be > 0, got {max_age_seconds}")

        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token:
            raise ValidationError("TELEGRAM_BOT_TOKEN is not configured")

        pairs = parse_qsl(init_data, strict_parsing=False, keep_blank_values=True)
        data = dict(pairs)

        hash_value = data.pop("hash", None)
        if not hash_value:
            _record_auth_failure("missing_hash")
            raise ValidationError("Missing Telegram hash")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
        calculated_hash = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, hash_value):
            _record_auth_failure("invalid_hash")
            
            # Add breadcrumb for auth failure
            add_breadcrumb(
                message="Telegram auth failed: invalid hash",
                category="auth",
                level="warning",
                data={
                    "service": "telegram_auth",
                    "reason": "invalid_hash",
                }
            )
            
            logger.warning("Invalid Telegram hash (init_data_prefix=%r)", init_data[:64])
            raise ValidationError("Invalid Telegram hash")

        try:
            auth_date = int(data.get("auth_date", "0"))
        except ValueError:
            _record_auth_failure("invalid_auth_date")
            raise ValidationError("Invalid auth_date")

        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        age = now_ts - auth_date

        if age > max_age_seconds:
            _record_auth_failure("expired")
            logger.warning("Telegram auth too old: age=%ss max=%ss", age, max_age_seconds)
            raise ValidationError("Authentication expired")
        if age < -10:
            _record_auth_failure("future_auth_date")
            logger.warning("Telegram auth_date is in the future: age=%ss", age)
            raise ValidationError("Invalid auth_date")

        user_raw = data.get("user")
        if not user_raw:
            _record_auth_failure("missing_user")
            raise ValidationError("Missing user payload")

        try:
            user_obj = json.loads(user_raw)
        except json.JSONDecodeError:
            _record_auth_failure("invalid_user_json")
            raise ValidationError("Invalid user payload")

        try:
            driver_id = int(user_obj["id"])
        except Exception:
            _record_auth_failure("missing_user_id")
            
            # Add breadcrumb for auth failure
            add_breadcrumb(
                message="Telegram auth failed: missing user id",
                category="auth",
                level="warning",
                data={
                    "service": "telegram_auth",
                    "reason": "missing_user_id",
                }
            )
            
            raise ValidationError("User id is missing")

        return {
            "id": driver_id,
            "first_name": str(user_obj.get("first_name") or "").strip(),
            "username": str(user_obj.get("username") or "").strip(),
            "auth_date": auth_date,
        }


class SessionService:
    """
    Session lifecycle for drivers (Redis-backed, JWT for API).
    """

    CACHE_KEY_FMT = "driver:{user_id}:session"
    DEFAULT_TTL_SECONDS = 86400

    """
    GOAL: Create a single active driver session and return a signed JWT session token.

    PARAMETERS:
      user: Any - Django user instance - Must be authenticated/created
      ttl_seconds: int - Session TTL in seconds - Must be >= 60, default 86400
      ip_address: str | None - Client IP address - Optional
      user_agent: str | None - Client User-Agent - Optional
      session_repo: TelegramSessionRepository - Repository for session operations - Optional, uses default if None

    RETURNS:
      str - JWT token for Authorization header - Includes user_id, sid, exp

    RAISES:
      ValidationError: If ttl_seconds < 60

    GUARANTEES:
      - Exactly one active session per user (previous sessions revoked)
      - Session id stored in cache with TTL (sliding window via refresh)
      - TelegramSession DB record created for audit
    """
    @classmethod
    def create_session(
        cls,
        user: Any,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        ip_address: str | None = None,
        user_agent: str | None = None,
        session_repo: TelegramSessionRepository | None = None,
    ) -> str:
        """
        Generate a new session id, store it in cache, revoke previous DB sessions, and sign a JWT.
        Uses cached telegram_user_id to avoid additional database query.
        """
        if ttl_seconds < 60:
            raise ValidationError(f"ttl_seconds must be >= 60, got {ttl_seconds}")

        session_id = str(uuid.uuid4())
        cache_key = cls.CACHE_KEY_FMT.format(user_id=user.id)
        cache.set(cache_key, session_id, timeout=ttl_seconds)

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if session_repo is not None:
            from asgiref.sync import sync_to_async
            await session_repo.revoke_all_user_sessions(user.id)
            await session_repo.create(
                user=user,
                session_id=session_id,
                expires_at=dj_timezone.now() + timedelta(seconds=ttl_seconds),
                ip_address=ip_address,
                user_agent=user_agent or "",
            )
        else:
            TelegramSession.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=dj_timezone.now())
            TelegramSession.objects.create(
                user=user,
                session_id=session_id,
                expires_at=dj_timezone.now() + timedelta(seconds=ttl_seconds),
                ip_address=ip_address,
                user_agent=user_agent or "",
            )

        telegram_user_id = get_telegram_user_id_cached(int(getattr(user, "id", 0)))

        return cls._encode_jwt(
            user_id=int(user.id),
            session_id=session_id,
            ttl_seconds=ttl_seconds,
            telegram_user_id=telegram_user_id,
        )

    """
    GOAL: Encode a signed JWT for a user session id with optional telegram id.

    PARAMETERS:
      user_id: int - Django user id - Must be > 0
      session_id: str - Session UUID string - Must be non-empty
      ttl_seconds: int - Token TTL seconds - Must be >= 60
      telegram_user_id: int | None - Telegram user id - Optional

    RETURNS:
      str - JWT token string - Never empty

    RAISES:
      None

    GUARANTEES:
      - Includes exp claim for expiry validation
      - Uses HS256 with settings.SECRET_KEY
    """
    @classmethod
    def _encode_jwt(
        cls, *, user_id: int, session_id: str, ttl_seconds: int, telegram_user_id: int | None
    ) -> str:
        issued_at = int(datetime.now(tz=timezone.utc).timestamp())
        expires_at = issued_at + int(ttl_seconds)
        payload: dict[str, Any] = {"user_id": user_id, "sid": session_id, "iat": issued_at, "exp": expires_at}
        if telegram_user_id is not None:
            payload["tg_id"] = int(telegram_user_id)
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


class TokenService:
    """
    JWT verification + Redis session binding.
    """

    REFRESH_THRESHOLD_SECONDS = 60 * 60 * 4  # 4 hours

    """
    GOAL: Validate a driver JWT session token and refresh Redis TTL (sliding window).

    PARAMETERS:
      session_token: str - JWT from Authorization header - Must be non-empty

    RETURNS:
      SessionValidationResult - Contains driver_data and optional refreshed_token - Never None

    RAISES:
      ValidationError: If token invalid/expired or session revoked

    GUARANTEES:
      - JWT signature and exp are verified
      - Session id is matched against Redis cache for idempotent revocation
      - Redis TTL is refreshed on successful validation
    """
    @staticmethod
    def validate_session(session_token: str) -> SessionValidationResult:
        """
        Decode JWT and ensure it matches the current Redis session id; optionally refresh JWT near expiry.
        """
        if not session_token:
            raise ValidationError("session_token is required")

        try:
            payload = jwt.decode(session_token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ValidationError("Session token expired")
        except jwt.PyJWTError as exc:
            raise ValidationError(f"Invalid session token: {exc}") from exc

        user_id = payload.get("user_id")
        session_id = payload.get("sid")
        if not user_id or not session_id:
            raise ValidationError("Invalid session token payload")

        cache_key = SessionService.CACHE_KEY_FMT.format(user_id=user_id)
        cached_sid = cache.get(cache_key)
        if not cached_sid or str(cached_sid) != str(session_id):
            raise ValidationError("Session revoked")

        cache.set(cache_key, str(session_id), timeout=SessionService.DEFAULT_TTL_SECONDS)

        refreshed_token: str | None = None
        exp = payload.get("exp")
        if isinstance(exp, int):
            now_ts = int(datetime.now(tz=timezone.utc).timestamp())
            if exp - now_ts < TokenService.REFRESH_THRESHOLD_SECONDS:
                refreshed_token = SessionService._encode_jwt(
                    user_id=int(user_id),
                    session_id=str(session_id),
                    ttl_seconds=SessionService.DEFAULT_TTL_SECONDS,
                    telegram_user_id=int(payload["tg_id"]) if "tg_id" in payload else None,
                )

        user_id_int = int(user_id)
        
        # Try to get user model
        user_dto: Optional[UserDTO] = None
        driver_dto: Optional[DriverProfileDTO] = None
        session_dto: Optional[TelegramSessionDTO] = None
        
        try:
            user = User.objects.get(id=user_id_int)
            user_dto = model_to_dto(user, UserDTO)
            
            # Try to get driver profile
            if hasattr(user, 'driverprofile'):
                driver_dto = model_to_dto(user.driverprofile, DriverProfileDTO)
            
            # Try to get active session
            session = TelegramSession.objects.filter(
                user=user,
                session_id=str(session_id),
                revoked_at__isnull=True
            ).first()
            if session:
                session_dto = model_to_dto(session, TelegramSessionDTO)
                
        except User.DoesNotExist:
            pass
        
        return SessionValidationResult(
            user_dto=user_dto,
            driver_dto=driver_dto,
            session_dto=session_dto,
            refreshed_token=refreshed_token,
        )


"""
GOAL: Track suspicious Telegram initData failures via per-minute counters.

PARAMETERS:
  reason: str - Failure reason slug - Must be non-empty

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Increments a short-lived cache counter
  - Emits a warning log when failures exceed a threshold
"""
def _record_auth_failure(reason: str) -> None:
    """
    Increment per-minute auth failure counter; warn if the rate is suspiciously high.
    """
    now = datetime.now(tz=timezone.utc)
    bucket = now.strftime("%Y%m%d%H%M")
    key = f"telegram_auth:failures:{bucket}:{reason}"
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=120)
        count = 1
    if count >= 10:
        # Add breadcrumb for high failure rate
        add_breadcrumb(
            message=f"High Telegram auth failure rate: {reason}",
            category="auth",
            level="warning",
            data={
                "service": "telegram_auth",
                "reason": reason,
                "count": count,
            }
        )
        
        logger.warning("High Telegram auth failure rate: reason=%s count=%s", reason, count)
        
        # Send to Sentry for alerting
        capture_exception(
            Exception(f"High Telegram auth failure rate: {reason}"),
            level="warning",
            extra={
                "service": "telegram_auth",
                "reason": reason,
                "count": count,
                "bucket": bucket,
            },
            tags={
                "service": "telegram_auth",
                "reason": reason,
            }
        )


"""
GOAL: Check if a user has admin privileges (staff or superuser).

PARAMETERS:
  user: Any - Django user instance - Not None

RETURNS:
  bool - True if user is staff or superuser - Never None

RAISES:
  None

GUARANTEES:
  - Returns False if user is None or not authenticated
  - Returns True if user.is_staff or user.is_superuser
  - Safe to call with AnonymousUser
"""
def is_admin_user(user: Any) -> bool:
    """
    Check user.is_staff or user.is_superuser with graceful handling of None/AnonymousUser.
    """
    if user is None or not hasattr(user, "is_authenticated"):
        return False
    if not user.is_authenticated:
        return False
    return bool(user.is_staff or user.is_superuser)


"""
GOAL: Check if a user has staff privileges.

PARAMETERS:
  user: Any - Django user instance - Not None

RETURNS:
  bool - True if user is staff - Never None

RAISES:
  None

GUARANTEES:
  - Returns False if user is None or not authenticated
  - Returns True if user.is_staff
  - Safe to call with AnonymousUser
"""
def is_staff_user(user: Any) -> bool:
    """
    Check user.is_staff with graceful handling of None/AnonymousUser.
    """
    if user is None or not hasattr(user, "is_authenticated"):
        return False
    if not user.is_authenticated:
        return False
    return bool(user.is_staff)


"""
GOAL: Check if a user has an active admin subscription.

PARAMETERS:
  user: Any - Django user instance - Not None
  feature_key: str - Feature key to check - Default "admin_access"
  subscription_repo: SubscriptionRepository | None - Repository for subscription operations - Optional

RETURNS:
  bool - True if user has active admin subscription - Never None

RAISES:
  None

GUARANTEES:
  - Returns False if user is None or not authenticated
  - Returns False if subscription is missing, inactive, or expired
  - Logs warnings for subscription access failures
  - Graceful degradation on database errors
"""
def has_admin_subscription(
    user: Any,
    *,
    feature_key: str = "admin_access",
    subscription_repo: SubscriptionRepository | None = None,
) -> bool:
    """
    Check if user has an active subscription that grants admin access.
    Gracefully handles missing subscriptions and database errors.
    """
    if user is None or not hasattr(user, "is_authenticated"):
        return False
    if not user.is_authenticated:
        return False
    
    try:
        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if subscription_repo is not None:
            from asgiref.sync import sync_to_async
            subscription = sync_to_async(subscription_repo.get_by_user_with_relations)(user.id)
        else:
            from apps.subscriptions.models import Subscription
            subscription = Subscription.objects.select_related("user").filter(user=user).first()
        
        if not subscription:
            logger.warning(
                "Admin subscription check failed: user_id=%s username=%s has no subscription",
                user.id,
                user.username,
            )
            return False
        
        if not subscription.is_active:
            logger.warning(
                "Admin subscription check failed: user_id=%s username=%s subscription is inactive",
                user.id,
                user.username,
            )
            return False
        
        if subscription.is_expired():
            logger.warning(
                "Admin subscription check failed: user_id=%s username=%s subscription expired at %s",
                user.id,
                user.username,
                subscription.expires_at,
            )
            return False
        
        logger.info(
            "Admin subscription check passed: user_id=%s username=%s expires_at=%s",
            user.id,
            user.username,
            subscription.expires_at,
        )
        return True
        
    except Exception as exc:
        logger.error(
            "Admin subscription check error: user_id=%s username=%s error=%s",
            user.id,
            user.username,
            exc,
            exc_info=True,
        )
        # Graceful degradation: return False on error
        return False
