"""
Circuit Breaker pattern implementation for external service resilience.

This module provides a circuit breaker that prevents cascading failures when
external services become unavailable. It uses Django cache backend for state
persistence across requests.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """
    Circuit breaker configuration parameters.

    PARAMETERS:
      failure_threshold: int - Failures before opening - Must be >= 1
      recovery_timeout: int - Seconds before HALF_OPEN - Must be >= 1
      success_threshold: int - Successes before closing - Must be >= 1
    """
    failure_threshold: int = 5
    recovery_timeout: int = 60
    success_threshold: int = 2


class CircuitBreakerOpenError(Exception):
    """
    Exception raised when circuit breaker is OPEN.

    Indicates that the external service is being blocked due to repeated failures.
    """

    def __init__(self, service_name: str, message: str = "Circuit breaker is OPEN"):
        """
        Initialize circuit breaker open error.

        PARAMETERS:
          service_name: str - Name of the service - Not empty
          message: str - Error message - Default "Circuit breaker is OPEN"

        GUARANTEES:
          - service_name is stored for logging
          - error message is user-friendly
        """
        super().__init__(message)
        self.service_name = service_name
        self.message = message


"""
GOAL: Initialize circuit breaker for a specific service with configuration.

PARAMETERS:
  service_name: str - Unique identifier for the service - Must be non-empty
  config: Optional[CircuitBreakerConfig] - Circuit breaker config - Uses defaults if None

RETURNS:
  CircuitBreaker - Initialized circuit breaker instance - Never None

RAISES:
  ValueError: If service_name is empty

GUARANTEES:
  - service_name is validated and stored
  - config is stored or defaults applied
  - Cache keys are generated for this service
"""
class CircuitBreaker:
    def __init__(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> None:
        """
        Initialize circuit breaker with service name and configuration.
        """
        if not service_name or not service_name.strip():
            raise ValueError("service_name must be non-empty")

        self.service_name = service_name.strip()
        self.config = config or CircuitBreakerConfig()

        # Cache keys for this service
        self._state_key = f"circuit_breaker:{self.service_name}:state"
        self._failure_count_key = f"circuit_breaker:{self.service_name}:failure_count"
        self._success_count_key = f"circuit_breaker:{self.service_name}:success_count"
        self._last_failure_time_key = f"circuit_breaker:{self.service_name}:last_failure_time"

    """
    GOAL: Get current circuit breaker state from cache.

PARAMETERS:
  None

RETURNS:
  CircuitState - Current state (CLOSED/OPEN/HALF_OPEN) - Never None

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - Returns CLOSED if cache unavailable (fail-open)
  - Returns cached state if available
  - Logs cache errors for debugging
"""
    def _get_state(self) -> CircuitState:
        """
        Retrieve state from cache, defaulting to CLOSED on failure.
        """
        try:
            state_str = cache.get(self._state_key)
            if state_str:
                return CircuitState(state_str)
        except Exception as exc:
            logger.error(
                "Failed to get circuit breaker state for %s: %s",
                self.service_name,
                exc
            )
        return CircuitState.CLOSED

    """
    GOAL: Set circuit breaker state in cache.

PARAMETERS:
  state: CircuitState - New state to set - Not None

RETURNS:
  None

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - State is persisted to cache if available
  - Logs cache errors for debugging
  - Continues operation even if cache fails
"""
    def _set_state(self, state: CircuitState) -> None:
        """
        Persist state to cache with appropriate timeout.
        """
        try:
            cache.set(self._state_key, state.value, timeout=86400)  # 24 hours
        except Exception as exc:
            logger.error(
                "Failed to set circuit breaker state for %s: %s",
                self.service_name,
                exc
            )

    """
    GOAL: Get current failure count from cache.

PARAMETERS:
  None

RETURNS:
  int - Number of consecutive failures - Always >= 0

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - Returns 0 if cache unavailable
  - Returns cached count if available
"""
    def _get_failure_count(self) -> int:
        """
        Retrieve failure count from cache, defaulting to 0 on failure.
        """
        try:
            count = cache.get(self._failure_count_key)
            if count is not None:
                return int(count)
        except Exception as exc:
            logger.error(
                "Failed to get failure count for %s: %s",
                self.service_name,
                exc
            )
        return 0

    """
    GOAL: Set failure count in cache.

PARAMETERS:
  count: int - New failure count - Must be >= 0

RETURNS:
  None

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - Count is persisted to cache if available
"""
    def _set_failure_count(self, count: int) -> None:
        """
        Persist failure count to cache.
        """
        try:
            cache.set(self._failure_count_key, count, timeout=86400)
        except Exception as exc:
            logger.error(
                "Failed to set failure count for %s: %s",
                self.service_name,
                exc
            )

    """
    GOAL: Get current success count from cache (for HALF_OPEN state).

PARAMETERS:
  None

RETURNS:
  int - Number of consecutive successes - Always >= 0

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - Returns 0 if cache unavailable
  - Returns cached count if available
"""
    def _get_success_count(self) -> int:
        """
        Retrieve success count from cache, defaulting to 0 on failure.
        """
        try:
            count = cache.get(self._success_count_key)
            if count is not None:
                return int(count)
        except Exception as exc:
            logger.error(
                "Failed to get success count for %s: %s",
                self.service_name,
                exc
            )
        return 0

    """
    GOAL: Set success count in cache.

PARAMETERS:
  count: int - New success count - Must be >= 0

RETURNS:
  None

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - Count is persisted to cache if available
"""
    def _set_success_count(self, count: int) -> None:
        """
        Persist success count to cache.
        """
        try:
            cache.set(self._success_count_key, count, timeout=86400)
        except Exception as exc:
            logger.error(
                "Failed to set success count for %s: %s",
                self.service_name,
                exc
            )

    """
    GOAL: Get last failure timestamp from cache.

PARAMETERS:
  None

RETURNS:
  float - Unix timestamp of last failure - 0 if not set

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - Returns 0 if cache unavailable or no failure recorded
"""
    def _get_last_failure_time(self) -> float:
        """
        Retrieve last failure time from cache.
        """
        try:
            timestamp = cache.get(self._last_failure_time_key)
            if timestamp is not None:
                return float(timestamp)
        except Exception as exc:
            logger.error(
                "Failed to get last failure time for %s: %s",
                self.service_name,
                exc
            )
        return 0.0

    """
    GOAL: Set last failure timestamp in cache.

PARAMETERS:
  timestamp: float - Unix timestamp - Must be > 0

RETURNS:
  None

RAISES:
  None (graceful degradation on cache failure)

GUARANTEES:
  - Timestamp is persisted to cache if available
"""
    def _set_last_failure_time(self, timestamp: float) -> None:
        """
        Persist last failure time to cache.
        """
        try:
            cache.set(self._last_failure_time_key, timestamp, timeout=86400)
        except Exception as exc:
            logger.error(
                "Failed to set last failure time for %s: %s",
                self.service_name,
                exc
            )

    """
    GOAL: Check if circuit breaker allows request execution.

PARAMETERS:
  None

RETURNS:
  bool - True if request allowed, False if blocked - Never None

RAISES:
  CircuitBreakerOpenError: If circuit is OPEN

GUARANTEES:
  - Returns True if CLOSED or HALF_OPEN
  - Raises CircuitBreakerOpenError if OPEN
  - Transitions from OPEN to HALF_OPEN if recovery timeout elapsed
"""
    def allow_request(self) -> bool:
        """
        Check if request should be allowed based on current state.
        """
        state = self._get_state()

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            last_failure = self._get_last_failure_time()
            now = time.time()

            if now - last_failure >= self.config.recovery_timeout:
                # Transition to HALF_OPEN for testing
                logger.info(
                    "Circuit breaker for %s transitioning from OPEN to HALF_OPEN",
                    self.service_name
                )
                self._set_state(CircuitState.HALF_OPEN)
                self._set_success_count(0)
                return True

            # Circuit still open, block request
            raise CircuitBreakerOpenError(
                service_name=self.service_name,
                message=f"Circuit breaker for {self.service_name} is OPEN. "
                       f"Recovery timeout: {self.config.recovery_timeout}s"
            )

        # HALF_OPEN state - allow requests to test recovery
        return True

    """
    GOAL: Record a successful request to circuit breaker.

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Resets failure count to 0
  - If in HALF_OPEN, increments success count
  - If success count reaches threshold, transitions to CLOSED
  - Logs all state transitions
"""
    def record_success(self) -> None:
        """
        Record successful request and update circuit breaker state.
        """
        state = self._get_state()

        # Reset failure count on success
        self._set_failure_count(0)

        if state == CircuitState.HALF_OPEN:
            success_count = self._get_success_count() + 1
            self._set_success_count(success_count)

            if success_count >= self.config.success_threshold:
                # Close circuit after threshold successes
                logger.info(
                    "Circuit breaker for %s transitioning from HALF_OPEN to CLOSED "
                    "(successes: %d/%d)",
                    self.service_name,
                    success_count,
                    self.config.success_threshold
                )
                self._set_state(CircuitState.CLOSED)
                self._set_success_count(0)

    """
    GOAL: Record a failed request to circuit breaker.

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - Increments failure count
  - If failure count reaches threshold, transitions to OPEN
  - Resets success count in HALF_OPEN
  - Logs all state transitions
"""
    def record_failure(self) -> None:
        """
        Record failed request and update circuit breaker state.
        """
        state = self._get_state()
        failure_count = self._get_failure_count() + 1
        self._set_failure_count(failure_count)
        self._set_last_failure_time(time.time())

        if state == CircuitState.HALF_OPEN:
            # Immediate reopen on failure in HALF_OPEN
            logger.warning(
                "Circuit breaker for %s transitioning from HALF_OPEN to OPEN "
                "(failure in test mode)",
                self.service_name
            )
            self._set_state(CircuitState.OPEN)
            self._set_success_count(0)
        elif failure_count >= self.config.failure_threshold:
            # Open circuit after threshold failures
            logger.warning(
                "Circuit breaker for %s transitioning from CLOSED to OPEN "
                "(failures: %d/%d)",
                self.service_name,
                failure_count,
                self.config.failure_threshold
            )
            self._set_state(CircuitState.OPEN)
            self._set_success_count(0)

    """
    GOAL: Reset circuit breaker to initial CLOSED state.

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - State set to CLOSED
  - Failure count reset to 0
  - Success count reset to 0
  - Logs reset operation
"""
    def reset(self) -> None:
        """
        Reset circuit breaker to initial state.
        """
        logger.info("Resetting circuit breaker for %s", self.service_name)
        self._set_state(CircuitState.CLOSED)
        self._set_failure_count(0)
        self._set_success_count(0)


"""
GOAL: Get circuit breaker instance for a service with configuration from settings.

PARAMETERS:
  service_name: str - Service identifier (e.g., "cargotech", "yukassa") - Must be non-empty

RETURNS:
  CircuitBreaker - Configured circuit breaker instance - Never None

RAISES:
  ValueError: If service_name is empty

GUARANTEES:
  - Returns existing instance if already created
  - Creates new instance with settings-based config if needed
  - Uses default config if settings not defined
"""
def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """
    Get or create circuit breaker for service with settings-based configuration.
    """
    if not service_name or not service_name.strip():
        raise ValueError("service_name must be non-empty")

    service_name = service_name.strip()

    # Check if circuit breaker is globally disabled
    if not getattr(settings, "CIRCUIT_BREAKER_ENABLED", True):
        # Return circuit breaker with very high thresholds (effectively disabled)
        return CircuitBreaker(
            service_name=service_name,
            config=CircuitBreakerConfig(
                failure_threshold=1000000,
                recovery_timeout=1,
                success_threshold=1
            )
        )

    # Get service-specific configuration from settings
    failure_threshold = getattr(
        settings,
        f"CIRCUIT_BREAKER_{service_name.upper()}_FAILURE_THRESHOLD",
        getattr(settings, "CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5)
    )

    recovery_timeout = getattr(
        settings,
        f"CIRCUIT_BREAKER_{service_name.upper()}_RECOVERY_TIMEOUT",
        getattr(settings, "CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 60)
    )

    success_threshold = getattr(
        settings,
        f"CIRCUIT_BREAKER_{service_name.upper()}_SUCCESS_THRESHOLD",
        getattr(settings, "CIRCUIT_BREAKER_SUCCESS_THRESHOLD", 2)
    )

    config = CircuitBreakerConfig(
        failure_threshold=int(failure_threshold),
        recovery_timeout=int(recovery_timeout),
        success_threshold=int(success_threshold)
    )

    return CircuitBreaker(service_name=service_name, config=config)
