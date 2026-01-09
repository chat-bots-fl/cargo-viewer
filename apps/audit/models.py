from __future__ import annotations

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField(max_length=255, blank=True)

    action_type = models.CharField(max_length=64, db_index=True)
    action = models.TextField()
    target_id = models.CharField(max_length=128, blank=True)
    details = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "action_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"[{self.created_at}] {self.username or self.user_id}: {self.action_type}"

