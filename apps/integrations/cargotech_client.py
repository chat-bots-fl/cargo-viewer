from __future__ import annotations

import logging
from typing import Any, Mapping

import requests

from apps.core.decorators import circuit_breaker
from apps.integrations.cargotech_auth import CargoTechAuthService
from apps.integrations.http_retry import fetch_with_retry
from apps.integrations.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# Import Sentry monitoring functions (graceful degradation if not available)
try:
    from apps.core.monitoring import (
        capture_exception,
        add_breadcrumb,
        set_transaction,
    )
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("Sentry monitoring not available in cargotech_client")
    
    # Fallback functions
    def capture_exception(*args, **kwargs):
        return None
    def add_breadcrumb(*args, **kwargs):
        pass
    def set_transaction(*args, **kwargs):
        return None


class CargoAPIClient:
    BASE_URL = "https://api.cargotech.pro"
    _limiter = RateLimiter(requests_per_minute=600)

    """
    GOAL: Perform a CargoTech API request with Bearer auth, rate limiting, circuit breaker, and a single 401 re-login retry.

    PARAMETERS:
      method: str - HTTP method - One of GET/POST/PUT/PATCH/DELETE
      path: str - API path starting with "/" - Must be non-empty
      params: Mapping[str, Any] | None - Query params - Optional
      json: Any | None - JSON body - Optional
      timeout: int - Request timeout seconds - Must be > 0, default 15

    RETURNS:
      dict[str, Any] - Parsed JSON response - Never None

    RAISES:
      requests.HTTPError: If non-retryable HTTP error occurs
      RuntimeError: If retries exceed max attempts
      ExternalServiceError: If circuit breaker is OPEN

    GUARANTEES:
      - Applies in-memory rate limiting (token bucket)
      - Applies circuit breaker protection
      - Retries 429/503/504 with exponential backoff
      - On 401: invalidates token and retries once
    """
    @classmethod
    @circuit_breaker(service_name="cargotech")
    def request(
        cls,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        """
        Use requests with retry wrapper and token invalidation on 401, returning JSON payload.
        """
        if not path.startswith("/"):
            raise ValueError("path must start with '/'")
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {timeout}")

        url = f"{cls.BASE_URL}{path}"

        def _do() -> requests.Response:
            cls._limiter.wait_for_token(max_wait_seconds=5.0)
            return requests.request(
                method,
                url,
                headers=CargoTechAuthService.auth_headers(),
                params=params,
                json=json,
                timeout=timeout,
            )

        # Add breadcrumb for API request start
        add_breadcrumb(
            message=f"CargoTech API request: {method} {path}",
            category="api",
            level="info",
            data={
                "service": "cargotech",
                "method": method,
                "path": path,
            }
        )
        
        # Start transaction for performance monitoring
        transaction = set_transaction(
            name=f"CargoTech {method} {path}",
            op="http.client",
            tags={
                "service": "cargotech",
                "method": method,
                "path": path,
            }
        )

        try:
            if transaction:
                with transaction:
                    response = fetch_with_retry(_do, max_attempts=4)
            else:
                response = fetch_with_retry(_do, max_attempts=4)

            if response.status_code == 401:
                logger.warning("CargoTech 401, invalidating token and retrying once")
                add_breadcrumb(
                    message="CargoTech 401 response, invalidating token",
                    category="api",
                    level="warning",
                    data={"service": "cargotech", "status_code": 401}
                )
                CargoTechAuthService.invalidate_cached_token()
                response = fetch_with_retry(_do, max_attempts=2)

            response.raise_for_status()
            
            # Add breadcrumb for successful response
            add_breadcrumb(
                message=f"CargoTech API success: {method} {path}",
                category="api",
                level="info",
                data={
                    "service": "cargotech",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                }
            )
            
            return response.json()
        except Exception as exc:
            # Add breadcrumb for error
            add_breadcrumb(
                message=f"CargoTech API error: {method} {path}",
                category="api",
                level="error",
                data={
                    "service": "cargotech",
                    "method": method,
                    "path": path,
                    "error_type": type(exc).__name__,
                }
            )
            
            # Send exception to Sentry
            capture_exception(
                exc,
                level="error",
                extra={
                    "service": "cargotech",
                    "method": method,
                    "path": path,
                    "params": params,
                },
                tags={
                    "service": "cargotech",
                    "method": method,
                    "path": path,
                }
            )
            
            raise

    """
    GOAL: Fetch cargo cards list from CargoTech /v2/cargos/views endpoint.

    PARAMETERS:
      params: Mapping[str, Any] - Query params for CargoTech endpoint - Must include include/limit/offset

    RETURNS:
      dict[str, Any] - Response payload with {data, meta} - Never None

    RAISES:
      requests.HTTPError: For HTTP errors

    GUARANTEES:
      - Uses authenticated request with retry policies from request()
    """
    @classmethod
    def fetch_cargos(cls, params: Mapping[str, Any]) -> dict[str, Any]:
        """
        GET /v2/cargos/views with provided params.
        """
        return cls.request("GET", "/v2/cargos/views", params=params)

    """
    GOAL: Fetch cargo detail from CargoTech detail endpoint (includes comment in data.extra.note).

    PARAMETERS:
      cargo_id: str - CargoTech cargo id - Must be non-empty

    RETURNS:
      dict[str, Any] - Response payload with {data} - Never None

    RAISES:
      requests.HTTPError: For HTTP errors

    GUARANTEES:
      - Calls /v1/carrier/cargos/{id} with include=contacts
    """
    @classmethod
    def fetch_cargo_detail(cls, cargo_id: str) -> dict[str, Any]:
        """
        GET /v1/carrier/cargos/{id}?source=1&include=contacts
        """
        cargo_id = str(cargo_id).strip()
        if not cargo_id:
            raise ValueError("cargo_id is required")
        return cls.request(
            "GET",
            f"/v1/carrier/cargos/{cargo_id}",
            params={"source": 1, "include": "contacts"},
        )

    """
    GOAL: Search city points by name using CargoTech dictionaries endpoint.

    PARAMETERS:
      query: str - Search prefix - Can be empty but UI should debounce and require min length
      limit: int - Max items - Must be between 1 and 50, default 10
      offset: int - Pagination offset - Must be >= 0, default 0

    RETURNS:
      dict[str, Any] - Response payload with {data, meta} - Never None

    RAISES:
      ValueError: If limit/offset invalid

    GUARANTEES:
      - Calls /v1/dictionaries/points?filter[name]={query}
    """
    @classmethod
    def search_cities(cls, query: str, *, limit: int = 10, offset: int = 0) -> dict[str, Any]:
        """
        GET /v1/dictionaries/points with filter[name]=query.
        """
        if limit < 1 or limit > 50:
            raise ValueError("limit must be within [1, 50]")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        return cls.request(
            "GET",
            "/v1/dictionaries/points",
            params={"filter[name]": str(query or ""), "limit": int(limit), "offset": int(offset)},
        )

    """
    GOAL: Fetch truck types dictionary for filters from CargoTech.

    PARAMETERS:
      None

    RETURNS:
      dict[str, Any] - Response payload with {data, meta} - Never None

    RAISES:
      requests.HTTPError: For HTTP errors

    GUARANTEES:
      - Calls /v1/dictionaries/truck_types
    """
    @classmethod
    def fetch_truck_types(cls) -> dict[str, Any]:
        """
        GET /v1/dictionaries/truck_types.
        """
        return cls.request("GET", "/v1/dictionaries/truck_types")

    """
    GOAL: Fetch load types dictionary for filters from CargoTech.

    PARAMETERS:
      None

    RETURNS:
      dict[str, Any] - Response payload with {data, meta} - Never None

    RAISES:
      requests.HTTPError: For HTTP errors

    GUARANTEES:
      - Calls /v1/dictionaries/load_types
    """
    @classmethod
    def fetch_load_types(cls) -> dict[str, Any]:
        """
        GET /v1/dictionaries/load_types.
        """
        return cls.request("GET", "/v1/dictionaries/load_types")
