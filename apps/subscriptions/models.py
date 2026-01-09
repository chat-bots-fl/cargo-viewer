from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    SOURCE_PAYMENT = "payment"
    SOURCE_PROMO = "promo"
    SOURCE_TRIAL = "trial"
    SOURCE_GIFT = "gift"

    SOURCE_CHOICES = [
        (SOURCE_PAYMENT, "payment"),
        (SOURCE_PROMO, "promo"),
        (SOURCE_TRIAL, "trial"),
        (SOURCE_GIFT, "gift"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    is_active = models.BooleanField(default=False, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    access_token = models.CharField(max_length=128, unique=True, blank=True, db_index=True)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default=SOURCE_TRIAL)

    payment = models.ForeignKey("payments.Payment", on_delete=models.SET_NULL, null=True, blank=True)
    promo_code = models.ForeignKey("promocodes.PromoCode", on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscriptions"
        indexes = [
            models.Index(fields=["user_id", "is_active", "expires_at"]),
            models.Index(fields=["access_token"]),
        ]

    def __str__(self) -> str:
        return f"Subscription(user_id={self.user_id}, active={self.is_active}, expires_at={self.expires_at})"

    """
    GOAL: Determine whether the subscription is expired at current time.

    PARAMETERS:
      None

    RETURNS:
      bool - True if expires_at is missing or <= now - Never None

    RAISES:
      None

    GUARANTEES:
      - Safe when expires_at is None
    """
    def is_expired(self) -> bool:
        if not self.expires_at:
            return True
        return timezone.now() >= self.expires_at

    """
    GOAL: Extend subscription by a number of days, starting from current expiry or now.

    PARAMETERS:
      days: int - Days to add - Must be > 0

    RETURNS:
      None

    RAISES:
      ValueError: If days <= 0

    GUARANTEES:
      - Sets activated_at to now
      - Sets expires_at to max(now, existing expires_at) + days
      - Ensures is_active=True and access_token is present
    """
    def extend(self, *, days: int) -> None:
        if days <= 0:
            raise ValueError("days must be > 0")
        base = self.expires_at if self.expires_at and not self.is_expired() else timezone.now()
        self.activated_at = timezone.now()
        self.expires_at = base + timedelta(days=days)
        self.is_active = True
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
