from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


"""
GOAL: Build a Fernet instance from SETTINGS_ENCRYPTION_KEY if configured.

PARAMETERS:
  None

RETURNS:
  Fernet | None - Fernet instance when key exists, else None

RAISES:
  None

GUARANTEES:
  - Does not validate key format beyond Fernet constructor
"""
def _get_fernet() -> Fernet | None:
    key = str(getattr(settings, "SETTINGS_ENCRYPTION_KEY", "") or "").strip()
    if not key:
        return None
    return Fernet(key.encode("utf-8"))


class SystemSetting(models.Model):
    key = models.CharField(max_length=128, unique=True, db_index=True)
    value = models.JSONField(default=dict, blank=True)
    encrypted_value = models.TextField(blank=True)
    is_secret = models.BooleanField(default=False, db_index=True)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "system_settings"
        indexes = [
            models.Index(fields=["is_secret", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"SystemSetting(key={self.key}, secret={self.is_secret})"

    """
    GOAL: Read a system setting value by key with optional default fallback.

    PARAMETERS:
      key: str - Setting key - Must be non-empty
      default: Any - Default value when not found - Optional

    RETURNS:
      Any - Stored value (JSON) or decrypted secret - Never raises on missing key

    RAISES:
      ValueError: If key is empty

    GUARANTEES:
      - Returns default when setting absent
      - Secret values are decrypted when encryption key is configured
    """
    @staticmethod
    def get_setting(key: str, default: Any = None) -> Any:
        """
        Fetch from DB; decrypt when necessary; return default on missing key.
        """
        key = str(key or "").strip()
        if not key:
            raise ValueError("key is required")
        try:
            setting = SystemSetting.objects.get(key=key)
        except SystemSetting.DoesNotExist:
            return default

        if not setting.is_secret:
            return setting.value

        f = _get_fernet()
        if not f:
            return setting.encrypted_value or default
        try:
            raw = f.decrypt(setting.encrypted_value.encode("utf-8"))
        except InvalidToken:
            return default
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return raw.decode("utf-8")

    """
    GOAL: Store or update a system setting value by key.

    PARAMETERS:
      key: str - Setting key - Must be non-empty
      value: Any - JSON-serializable value (or secret string) - Not None
      is_secret: bool - Whether to encrypt at rest - Default False

    RETURNS:
      SystemSetting - Saved instance - Never None

    RAISES:
      ValueError: If key is empty
      ValueError: If is_secret=True but SETTINGS_ENCRYPTION_KEY not configured

    GUARANTEES:
      - Upserts by key
      - When is_secret=True, stores encrypted_value and clears value field
    """
    @staticmethod
    def set_setting(key: str, value: Any, *, is_secret: bool = False) -> "SystemSetting":
        """
        Upsert setting, encrypting secrets using Fernet when enabled.
        """
        key = str(key or "").strip()
        if not key:
            raise ValueError("key is required")

        setting, _ = SystemSetting.objects.get_or_create(key=key)
        setting.is_secret = bool(is_secret)

        if not setting.is_secret:
            setting.value = value
            setting.encrypted_value = ""
            setting.save(update_fields=["is_secret", "value", "encrypted_value", "updated_at"])
            return setting

        f = _get_fernet()
        if not f:
            raise ValueError("SETTINGS_ENCRYPTION_KEY is required to store secret settings")

        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        setting.encrypted_value = f.encrypt(raw).decode("utf-8")
        setting.value = {}
        setting.save(update_fields=["is_secret", "value", "encrypted_value", "updated_at"])
        return setting


class FeatureFlag(models.Model):
    key = models.CharField(max_length=128, unique=True, db_index=True)
    enabled = models.BooleanField(default=False, db_index=True)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "feature_flags"
        indexes = [
            models.Index(fields=["enabled", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"FeatureFlag(key={self.key}, enabled={self.enabled})"
