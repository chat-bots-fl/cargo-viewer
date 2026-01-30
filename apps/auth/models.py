from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="driver_profile")
    telegram_user_id = models.BigIntegerField(unique=True, db_index=True)
    telegram_username = models.CharField(max_length=255, blank=True)
    company_name = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "driver_profiles"

    def __str__(self) -> str:
        return f"DriverProfile(user_id={self.user_id}, telegram_user_id={self.telegram_user_id})"


class TelegramSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram_sessions")
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        db_table = "telegram_sessions"
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "revoked_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        return f"TelegramSession(user_id={self.user_id}, session_id={self.session_id})"
