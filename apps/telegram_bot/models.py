from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class DriverCargoResponse(models.Model):
    """
    A driver's response to a cargo, used for idempotency and status tracking.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cargo_id = models.CharField(max_length=64, db_index=True)

    phone = models.CharField(max_length=64, blank=True)
    name = models.CharField(max_length=255, blank=True)

    status = models.CharField(max_length=32, default="pending", db_index=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "driver_cargo_responses"
        constraints = [
            models.UniqueConstraint(fields=["user", "cargo_id"], name="uniq_driver_cargo_response"),
        ]
        indexes = [
            models.Index(fields=["cargo_id", "created_at"], name="dcr_cargo_id_created_at"),
            models.Index(fields=["user", "created_at"], name="dcr_user_created_at"),
            models.Index(fields=["status", "created_at"], name="dcr_status_created_at"),
        ]

    def __str__(self) -> str:
        return f"DriverCargoResponse(user_id={self.user_id}, cargo_id={self.cargo_id}, status={self.status})"
