from __future__ import annotations

import random
import string

from django.conf import settings
from django.db import models
from django.utils import timezone


class PromoCode(models.Model):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    action = models.CharField(max_length=32, db_index=True)
    days_to_add = models.IntegerField(default=0)

    valid_from = models.DateTimeField(db_index=True)
    valid_until = models.DateTimeField(db_index=True)

    max_uses = models.IntegerField(default=1)
    current_uses = models.IntegerField(default=0)
    disabled = models.BooleanField(default=False, db_index=True)
    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_promocodes",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "promo_codes"
        indexes = [
            models.Index(fields=["action", "valid_until"]),
            models.Index(fields=["disabled", "valid_until"]),
        ]

    def __str__(self) -> str:
        return f"PromoCode(code={self.code}, action={self.action}, uses={self.current_uses}/{self.max_uses})"

    """
    GOAL: Check whether the promo code is currently usable.

    PARAMETERS:
      None

    RETURNS:
      bool - True if active within time window and under usage limit - Never None

    RAISES:
      None

    GUARANTEES:
      - Uses timezone-aware now()
    """
    def can_use(self) -> bool:
        if self.disabled:
            return False
        now = timezone.now()
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.current_uses >= self.max_uses:
            return False
        return True

    """
    GOAL: Consume one usage of the promo code.

    PARAMETERS:
      None

    RETURNS:
      None

    RAISES:
      None

    GUARANTEES:
      - Increments current_uses by 1 and persists to DB
    """
    def use(self) -> None:
        self.current_uses += 1
        self.save(update_fields=["current_uses", "updated_at"])

    """
    GOAL: Generate a random promo code string.

    PARAMETERS:
      length: int - Length of code - Must be >= 6, default 12

    RETURNS:
      str - Uppercase alphanumeric code - Never empty

    RAISES:
      ValueError: If length < 6

    GUARANTEES:
      - Uses A-Z and 0-9 only
    """
    @staticmethod
    def generate_code(length: int = 12) -> str:
        if length < 6:
            raise ValueError("length must be >= 6")
        alphabet = string.ascii_uppercase + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))


class PromoCodeUsage(models.Model):
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="usages")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True, db_index=True)
    success = models.BooleanField(default=True, db_index=True)
    reason = models.TextField(blank=True)
    days_added = models.IntegerField(default=0)

    class Meta:
        db_table = "promo_code_usage"
        indexes = [
            models.Index(fields=["promo_code", "used_at"]),
            models.Index(fields=["user", "used_at"]),
            models.Index(fields=["success", "used_at"]),
        ]

    def __str__(self) -> str:
        return f"PromoCodeUsage(code={self.promo_code.code}, user_id={self.user_id}, success={self.success})"
