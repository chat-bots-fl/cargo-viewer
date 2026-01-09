from __future__ import annotations

import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimitError(RuntimeError):
    pass


class RateLimiter:
    """
    Token Bucket limiter (in-memory).

    capacity = requests_per_minute
    refill_rate = capacity / 60 tokens per second
    """

    """
    GOAL: Initialize a token-bucket rate limiter.

    PARAMETERS:
      requests_per_minute: int - Allowed requests per minute - Must be > 0, default 600

    RETURNS:
      None

    RAISES:
      ValueError: If requests_per_minute <= 0

    GUARANTEES:
      - Starts with a full bucket (burst up to requests_per_minute)
    """
    def __init__(self, requests_per_minute: int = 600):
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be > 0")
        self.capacity = float(requests_per_minute)
        self.tokens = float(requests_per_minute)
        self.last_update = time.monotonic()
        self.lock = Lock()

    """
    GOAL: Check if an HTTP request is allowed and consume one token.

    PARAMETERS:
      None

    RETURNS:
      bool - True if request allowed (token consumed), False otherwise

    RAISES:
      None

    GUARANTEES:
      - Thread-safe token accounting
      - Replenishes tokens proportional to elapsed time
    """
    def can_request(self) -> bool:
        """Return True if request is allowed (consumes 1 token)."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            new_tokens = elapsed * (self.capacity / 60.0)
            self.tokens = min(self.capacity, self.tokens + new_tokens)
            self.last_update = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

    """
    GOAL: Block until a token becomes available or fail fast after a timeout.

    PARAMETERS:
      max_wait_seconds: float - Max time to wait - Must be > 0, default 5.0

    RETURNS:
      None

    RAISES:
      RateLimitError: If token not available within max_wait_seconds

    GUARANTEES:
      - Uses short sleeps to avoid busy-waiting
    """
    def wait_for_token(self, *, max_wait_seconds: float = 5.0) -> None:
        """
        Block until a token is available or raise RateLimitError after max_wait_seconds.
        """
        start = time.monotonic()
        while True:
            if self.can_request():
                return
            if time.monotonic() - start > max_wait_seconds:
                raise RateLimitError("Rate limiter timeout")
            time.sleep(0.05)
