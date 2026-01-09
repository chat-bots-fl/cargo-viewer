from __future__ import annotations

import logging
import random
import time
from typing import Callable, Mapping, Protocol, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ResponseLike(Protocol):
    status_code: int
    headers: Mapping[str, str]


"""
GOAL: Sleep with exponential backoff and jitter between retry attempts.

PARAMETERS:
  attempt: int - Zero-based attempt number - Must be >= 0
  base_ms: int - Base delay in milliseconds - Must be > 0, default 500
  jitter_ms: int - Random jitter in ms - Must be >= 0, default 100

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Sleep time increases exponentially with attempt
"""
def _sleep_backoff(attempt: int, *, base_ms: int = 500, jitter_ms: int = 100) -> None:
    """500ms → 1500ms → 3000ms (+ jitter)."""
    wait_ms = base_ms * (2**attempt) + random.randint(0, jitter_ms)
    time.sleep(wait_ms / 1000.0)


"""
GOAL: Execute an HTTP request function with retries for retryable status codes.

PARAMETERS:
  request_fn: Callable[[], T] - Function that returns a response-like object - Must be callable
  max_attempts: int - Maximum number of attempts - Must be >= 1, default 4

RETURNS:
  T - The first non-retryable response - Never None

RAISES:
  RuntimeError: If max attempts are exceeded without a successful (non-retryable) response

GUARANTEES:
  - Retries on HTTP 429/503/504 with exponential backoff
"""
def fetch_with_retry(request_fn: Callable[[], T], *, max_attempts: int = 4) -> T:
    """
    Retry wrapper for HTTP requests (handles 429/503/504 with exponential backoff).
    """
    retryable = {429, 503, 504}
    last_response: ResponseLike | None = None
    for attempt in range(max_attempts):
        response = request_fn()
        last_response = response if hasattr(response, "status_code") else None

        if last_response is None or last_response.status_code not in retryable:
            return response

        logger.warning("Retryable HTTP status=%s attempt=%s", last_response.status_code, attempt + 1)
        if attempt >= max_attempts - 1:
            break
        _sleep_backoff(attempt)

    raise RuntimeError(
        f"Max retries exceeded after {max_attempts} attempts (last_status={getattr(last_response, 'status_code', None)})"
    )
