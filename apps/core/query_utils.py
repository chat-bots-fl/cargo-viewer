"""
Optimized database query utilities to prevent N+1 queries.

This module provides helper functions for common query patterns with
proper select_related, prefetch_related, and select_for_update usage.
"""

from __future__ import annotations

from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.auth.models import DriverProfile, TelegramSession
from apps.subscriptions.models import Subscription

User = get_user_model()


"""
GOAL: Fetch user with driver_profile in a single query using select_related.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  User | None - User instance with driver_profile prefetched, or None if not found

RAISES:
  None

GUARANTEES:
  - Executes exactly 1 database query
  - Returns None if user does not exist
  - driver_profile is accessible without additional queries (may be None)
"""
def get_user_with_profile(user_id: int) -> Optional[User]:
    """
    Fetch user with OneToOne driver_profile relation using select_related.
    """
    if user_id <= 0:
        return None
    
    try:
        return User.objects.select_related("driver_profile").get(id=user_id)
    except User.DoesNotExist:
        return None


"""
GOAL: Fetch subscription with user in a single query using select_related.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  Subscription | None - Subscription instance with user prefetched, or None if not found

RAISES:
  None

GUARANTEES:
  - Executes exactly 1 database query
  - Returns None if subscription does not exist
  - user is accessible without additional queries
"""
def get_subscription_with_user(user_id: int) -> Optional[Subscription]:
    """
    Fetch subscription with ForeignKey user relation using select_related.
    """
    if user_id <= 0:
        return None
    
    try:
        return Subscription.objects.select_related("user").get(user_id=user_id)
    except Subscription.DoesNotExist:
        return None


"""
GOAL: Fetch driver profile for a user in a single query.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  DriverProfile | None - DriverProfile instance, or None if not found

RAISES:
  None

GUARANTEES:
  - Executes exactly 1 database query
  - Returns None if profile does not exist
"""
def get_driver_profile(user_id: int) -> Optional[DriverProfile]:
    """
    Fetch driver profile by user_id.
    """
    if user_id <= 0:
        return None
    
    try:
        return DriverProfile.objects.get(user_id=user_id)
    except DriverProfile.DoesNotExist:
        return None


"""
GOAL: Fetch user with all related objects for audit logging in a single query.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  tuple[User | None, str] - User instance with profile, and username string

RAISES:
  None

GUARANTEES:
  - Executes exactly 1 database query
  - Returns (None, "") if user not found
  - Username is extracted from user object or empty string
"""
def get_user_for_audit(user_id: int) -> tuple[Optional[User], str]:
    """
    Fetch user with profile for audit logging.
    Returns user instance and username string.
    """
    user = get_user_with_profile(user_id)
    username = getattr(user, "username", "") if user else ""
    return user, username


"""
GOAL: Fetch active session for a user with locking using select_for_update.

PARAMETERS:
  user: Any - Django user instance - Must be non-null

RETURNS:
  TelegramSession | None - Active session, or None if no active session exists

RAISES:
  None

GUARANTEES:
  - Executes exactly 1 database query
  - Returns None if no active (non-revoked) session exists
  - Session is locked for update to prevent race conditions
"""
def get_active_session_for_update(user: Any) -> Optional[TelegramSession]:
    """
    Fetch active session with row-level lock for atomic updates.
    """
    if not user or not hasattr(user, "id"):
        return None
    
    try:
        return TelegramSession.objects.select_for_update().filter(
            user=user, revoked_at__isnull=True
        ).first()
    except Exception:
        return None


"""
GOAL: Fetch telegram user ID from driver profile with caching.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  int | None - Telegram user ID, or None if not found

RAISES:
  None

GUARANTEES:
  - Uses cache to reduce database queries
  - Cache key: driver_profile:{user_id}:telegram_id
  - Cache TTL: 3600 seconds (1 hour)
"""
def get_telegram_user_id_cached(user_id: int) -> Optional[int]:
    """
    Fetch telegram user ID from driver profile with caching.
    """
    if user_id <= 0:
        return None
    
    cache_key = f"driver_profile:{user_id}:telegram_id"
    cached_value = cache.get(cache_key)
    
    if cached_value is not None:
        return int(cached_value) if cached_value else None
    
    profile = get_driver_profile(user_id)
    telegram_id = getattr(profile, "telegram_user_id", None) if profile else None
    
    cache.set(cache_key, telegram_id, timeout=3600)
    return telegram_id


"""
GOAL: Fetch subscription status with caching to avoid repeated database queries.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  dict[str, Any] - Dictionary with keys: has_subscription, is_active, is_expired, expires_at

RAISES:
  None

GUARANTEES:
  - Uses cache to reduce database queries
  - Cache key: subscription_status:{user_id}
  - Cache TTL: 300 seconds (5 minutes)
  - Returns default (inactive) status if subscription not found
"""
def get_subscription_status_cached(user_id: int) -> dict[str, Any]:
    """
    Fetch subscription status with caching.
    """
    if user_id <= 0:
        return {"has_subscription": False, "is_active": False, "is_expired": True, "expires_at": None}
    
    cache_key = f"subscription_status:{user_id}"
    cached_value = cache.get(cache_key)
    
    if cached_value is not None:
        return cached_value
    
    subscription = get_subscription_with_user(user_id)
    
    if not subscription:
        status = {"has_subscription": False, "is_active": False, "is_expired": True, "expires_at": None}
    else:
        status = {
            "has_subscription": True,
            "is_active": subscription.is_active,
            "is_expired": subscription.is_expired(),
            "expires_at": subscription.expires_at,
        }
    
    cache.set(cache_key, status, timeout=300)
    return status


"""
GOAL: Invalidate subscription status cache for a user.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Removes subscription status from cache
  - Safe to call even if cache entry does not exist
"""
def invalidate_subscription_cache(user_id: int) -> None:
    """
    Invalidate subscription status cache.
    """
    if user_id <= 0:
        return
    
    cache_key = f"subscription_status:{user_id}"
    cache.delete(cache_key)


"""
GOAL: Invalidate driver profile cache for a user.

PARAMETERS:
  user_id: int - User ID - Must be > 0

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Removes driver profile telegram ID from cache
  - Safe to call even if cache entry does not exist
"""
def invalidate_driver_profile_cache(user_id: int) -> None:
    """
    Invalidate driver profile cache.
    """
    if user_id <= 0:
        return
    
    cache_key = f"driver_profile:{user_id}:telegram_id"
    cache.delete(cache_key)
