from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CargoTechAuthError(RuntimeError):
    pass


class CargoTechAuthService:
    """
    CargoTech API auth (Laravel Sanctum).

    Login response shape:
        {"data": {"token": "12345|<opaque_token>"}}
    """

    BASE_URL = "https://api.cargotech.pro"
    CACHE_KEY = "cargotech:api:token"

    """
    GOAL: Login to CargoTech API and cache Bearer token.

    PARAMETERS:
      phone: str - CargoTech phone - Must be non-empty (E.164 recommended)
      password: str - CargoTech password - Must be non-empty
      remember: bool - CargoTech remember flag - Default True

    RETURNS:
      str - Bearer token string "{id}|{hash}" - Never empty

    RAISES:
      CargoTechAuthError: If request fails or response shape unexpected
      ValidationError: If credentials missing

    GUARANTEES:
      - Token is cached in Redis (or default cache) under key cargotech:api:token
      - Cache TTL is settings.CARGOTECH_TOKEN_CACHE_TTL (default 86400)
    """
    @classmethod
    def login(cls, *, phone: str, password: str, remember: bool = True) -> str:
        """
        Call CargoTech /v1/auth/login and store returned token in cache.
        """
        if not phone or not password:
            raise ValidationError("CargoTech credentials are required")

        response = requests.post(
            f"{cls.BASE_URL}/v1/auth/login",
            json={"phone": phone, "password": password, "remember": remember},
            timeout=10,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise CargoTechAuthError(f"CargoTech login failed: {exc}") from exc

        payload: dict[str, Any] = response.json()
        try:
            token = str(payload["data"]["token"])
        except Exception as exc:
            raise CargoTechAuthError("CargoTech login response missing data.token") from exc

        try:
            cache.set(cls.CACHE_KEY, token, timeout=int(getattr(settings, "CARGOTECH_TOKEN_CACHE_TTL", 86400)))
        except Exception as exc:
            logger.warning("CargoTech token cache set failed: %s", exc)
        logger.info("CargoTech token cached")
        return token

    """
    GOAL: Get cached CargoTech token or perform login using configured credentials.

    PARAMETERS:
      None

    RETURNS:
      str - Bearer token string - Never empty

    RAISES:
      CargoTechAuthError: If credentials missing or login fails

    GUARANTEES:
      - Returns a token that was cached or freshly obtained
    """
    @classmethod
    def get_token(cls) -> str:
        """
        Prefer cached token; fallback to login with env credentials.
        """
        try:
            cached = cache.get(cls.CACHE_KEY)
        except Exception as exc:
            logger.warning("CargoTech token cache get failed: %s", exc)
            cached = None
        if cached:
            return str(cached)

        phone = settings.CARGOTECH_PHONE
        password = settings.CARGOTECH_PASSWORD
        if not phone or not password:
            raise CargoTechAuthError("CARGOTECH_PHONE/CARGOTECH_PASSWORD are not configured")

        return cls.login(phone=phone, password=password, remember=True)

    """
    GOAL: Invalidate cached CargoTech token.

    PARAMETERS:
      None

    RETURNS:
      None

    RAISES:
      None

    GUARANTEES:
      - Next request will force re-login
    """
    @classmethod
    def invalidate_cached_token(cls) -> None:
        """
        Delete cached token key.
        """
        try:
            cache.delete(cls.CACHE_KEY)
        except Exception as exc:
            logger.warning("CargoTech token cache delete failed: %s", exc)

    """
    GOAL: Build Authorization headers for CargoTech API requests.

    PARAMETERS:
      None

    RETURNS:
      dict[str, str] - HTTP headers including Authorization - Never empty

    RAISES:
      CargoTechAuthError: If token cannot be obtained

    GUARANTEES:
      - Authorization header uses "Bearer <token>"
    """
    @classmethod
    def auth_headers(cls) -> dict[str, str]:
        """
        Fetch token and build standard JSON headers.
        """
        return {"Authorization": f"Bearer {cls.get_token()}", "Accept": "application/json"}
