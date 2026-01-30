from __future__ import annotations

import json
import logging
from typing import Any

from django.contrib.auth import get_user_model

from apps.audit.models import AuditLog
from apps.core.query_utils import get_user_for_audit
from apps.core.repositories import AuditLogRepository

logger = logging.getLogger(__name__)
User = get_user_model()


class AuditService:
    """
    DB-backed audit logger for payments, subscriptions, promos, and admin actions.
    """

    """
    GOAL: Make audit details JSON-serializable for safe storage in JSONField.

    PARAMETERS:
      details: dict[str, Any] | None - Audit details payload - Optional

    RETURNS:
      dict[str, Any] - JSON-safe details dictionary - Never None

    RAISES:
      None

    GUARANTEES:
      - Returns a dict (empty if input is None/empty)
      - Replaces non-serializable values with strings
      - Never raises
    """
    @staticmethod
    def _normalize_details(details: dict[str, Any] | None) -> dict[str, Any]:
        """
        Serialize+deserialize with a string fallback to coerce unknown values.
        """
        if not details:
            return {}

        try:
            return json.loads(json.dumps(details, ensure_ascii=False, default=str))
        except Exception:
            return {"_raw": str(details)}

    """
    GOAL: Record an auditable event in the database (best-effort).

    PARAMETERS:
      user_id: int | None - Actor user id - Optional
      action_type: str - Category - Must be non-empty
      action: str - Human-readable action - Must be non-empty
      target_id: str | None - Target identifier - Optional
      details: dict[str, Any] | None - Additional data - Optional
      ip_address: str | None - Remote IP - Optional
      user_agent: str | None - User-Agent - Optional
      audit_log_repo: AuditLogRepository | None - Repository for audit log operations - Optional

    RETURNS:
      None

    RAISES:
      None (errors are logged)

    GUARANTEES:
      - Never raises; failures are logged and ignored
      - Writes AuditLog row when DB is available
    """
    @staticmethod
    def log(
        *,
        user_id: int | None = None,
        action_type: str,
        action: str,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        audit_log_repo: AuditLogRepository | None = None,
    ) -> None:
        """
        Persist audit record; fall back to logging if DB write fails.
        Uses optimized query with select_related for driver_profile.
        """
        try:
            user, username = get_user_for_audit(int(user_id)) if user_id else (None, "")
            normalized_details = AuditService._normalize_details(details)

            # Use repository if provided, otherwise direct ORM access for backward compatibility
            if audit_log_repo is not None:
                from asgiref.sync import async_to_sync

                async_to_sync(audit_log_repo.create_log)(
                    user=user,
                    username=username,
                    action_type=str(action_type or "").strip(),
                    action=str(action or "").strip(),
                    target_id=str(target_id or ""),
                    details=normalized_details,
                    ip_address=ip_address,
                    user_agent=user_agent or "",
                )
            else:
                AuditLog.objects.create(
                    user=user,
                    username=username,
                    action_type=str(action_type or "").strip(),
                    action=str(action or "").strip(),
                    target_id=str(target_id or ""),
                    details=normalized_details,
                    ip_address=ip_address,
                    user_agent=user_agent or "",
                )
        except Exception as exc:
            logger.info(
                "AUDIT_FALLBACK action_type=%s action=%s user_id=%s target_id=%s details=%s err=%s",
                action_type,
                action,
                user_id,
                target_id,
                details,
                exc,
            )
