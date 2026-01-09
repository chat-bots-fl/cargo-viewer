from __future__ import annotations

import logging
from typing import Any

import requests

from apps.integrations.cargotech_auth import CargoTechAuthService

logger = logging.getLogger(__name__)


class CargoTechAuthMonitor:
    """
    Optional health checks for CargoTech auth token.
    """

    """
    GOAL: Verify that CargoTech token is valid by calling /v1/me.

    PARAMETERS:
      None

    RETURNS:
      dict[str, Any] - {"ok": bool, "status_code": int | None, "error": str | None} - Never None

    RAISES:
      None (errors are captured and returned)

    GUARANTEES:
      - Does not raise; safe for cron/health endpoints
    """
    @staticmethod
    def check_token_health() -> dict[str, Any]:
        """
        Call CargoTech /v1/me with current token and report HTTP status.
        """
        try:
            resp = requests.get(
                f"{CargoTechAuthService.BASE_URL}/v1/me",
                headers=CargoTechAuthService.auth_headers(),
                timeout=10,
            )
            ok = resp.status_code == 200
            return {"ok": ok, "status_code": resp.status_code, "error": None if ok else resp.text[:200]}
        except Exception as exc:
            logger.warning("CargoTech auth health check failed: %s", exc)
            return {"ok": False, "status_code": None, "error": str(exc)}

