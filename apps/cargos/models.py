from __future__ import annotations

from django.conf import settings
from django.db import models


class CargoCache(models.Model):
    """
    Optional DB-backed cache for cargos (Redis is the primary cache in this project).
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    cache_key = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "cargo_cache"
        indexes = [
            models.Index(fields=["user", "cache_key"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"CargoCache(user_id={self.user_id}, key={self.cache_key})"

