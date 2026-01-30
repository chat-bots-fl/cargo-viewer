"""
Custom exception classes for unified error handling across the application.

All exceptions follow a consistent structure with error codes and messages.
Integration with Sentry for error monitoring and tracking.
"""

import json
import logging
from typing import Optional, Dict, Any
from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)

"""
GOAL: Create a JsonResponse that also provides a .json() helper for tests.

PARAMETERS:
  payload: dict[str, Any] - JSON-serializable response payload - Must be a dict
  status: int - HTTP status code - Must be positive

RETURNS:
  JsonResponse - Django JsonResponse with added .json() method - Never None

RAISES:
  TypeError: If payload is not JSON serializable

GUARANTEES:
  - Returned response is a valid Django JsonResponse
  - Returned response supports response.json() in RequestFactory-based tests
"""
def _json_response(payload: dict[str, Any], status: int) -> JsonResponse:
    """
    Build JsonResponse and attach a small json() helper for parity with Django test client responses.
    """
    response = JsonResponse(payload, status=status)

    def _json() -> Any:
        return json.loads(response.content.decode(response.charset))

    setattr(response, "json", _json)
    return response

# Import Sentry monitoring functions (graceful degradation if not available)
try:
    from apps.core.monitoring import (
        capture_exception,
        add_breadcrumb,
        is_sentry_enabled,
    )
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("Sentry monitoring not available in exceptions")
    
    # Fallback functions
    def capture_exception(*args, **kwargs):
        return None
    def add_breadcrumb(*args, **kwargs):
        pass
    def is_sentry_enabled():
        return False


class BaseAPIError(Exception):
    """
    Base exception class for all API errors.

    Provides common structure for error responses including error code,
    human-readable message, and optional details.
    """

    def __init__(self, message: str, details: dict | None = None):
        """
        Initialize base API error.

        PARAMETERS:
          message: str - Human-readable error message - Not empty
          details: dict | None - Additional error details - Optional

        GUARANTEES:
          - error_code is set by subclass
          - message is stored and accessible
          - details dictionary is stored if provided
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    @property
    def error_code(self) -> str:
        """
        Return error code for this exception type.

        RETURNS:
          str - Error code identifier - Not empty
        """
        raise NotImplementedError("Subclasses must implement error_code")

    @property
    def http_status(self) -> int:
        """
        Return HTTP status code for this exception type.

        RETURNS:
          int - HTTP status code - Valid HTTP status (400-599)
        """
        raise NotImplementedError("Subclasses must implement http_status")
    
    """
    GOAL: Send exception to Sentry for monitoring and tracking.

    PARAMETERS:
      level: Optional[str] - Log level for Sentry - 'error', 'warning', 'info'
      extra: Optional[Dict[str, Any]] - Additional context data - May be None
      tags: Optional[Dict[str, str]] - Tags for grouping - May be None

    RETURNS:
      Optional[str] - Sentry event ID or None if disabled - May be None

    RAISES:
      None - Never raises exceptions (graceful degradation)

    GUARANTEES:
      - Returns None if Sentry is disabled
      - Adds breadcrumb with exception context
      - Sends exception to Sentry with provided context
      - Logs locally if Sentry is unavailable
    """
    def capture_to_sentry(
        self,
        level: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Send exception to Sentry with additional context.
        Automatically includes error_code and message in tags.
        """
        # Add breadcrumb for exception
        add_breadcrumb(
            message=f"Exception raised: {self.error_code}",
            category="exception",
            level=level or "error",
            data={
                "error_code": self.error_code,
                "message": self.message,
            }
        )
        
        # Prepare tags
        exception_tags = tags or {}
        exception_tags["error_code"] = self.error_code
        exception_tags["exception_type"] = self.__class__.__name__
        
        # Prepare extra context
        exception_extra = extra or {}
        exception_extra["error_code"] = self.error_code
        exception_extra["message"] = self.message
        if self.details:
            exception_extra["details"] = self.details
        
        # Send to Sentry
        return capture_exception(
            self,
            level=level or "error",
            extra=exception_extra,
            tags=exception_tags,
        )


class ValidationError(BaseAPIError):
    """
    Exception for validation errors (invalid input data).

    Used when request data fails validation rules.
    """

    def __init__(self, message: str = "Validation failed", details: dict | None = None):
        """
        Initialize validation error.

        PARAMETERS:
          message: str - Human-readable error message - Default "Validation failed"
          details: dict | None - Field-specific validation errors - Optional

        GUARANTEES:
          - error_code is "VALIDATION_ERROR"
          - http_status is 400
        """
        super().__init__(message, details)

    @property
    def error_code(self) -> str:
        """Return validation error code."""
        return "VALIDATION_ERROR"

    @property
    def http_status(self) -> int:
        """Return 400 Bad Request status."""
        return 400


class AuthenticationError(BaseAPIError):
    """
    Exception for authentication errors (invalid credentials, expired tokens).

    Used when user cannot be authenticated.
    """

    def __init__(self, message: str = "Authentication failed", details: dict | None = None):
        """
        Initialize authentication error.

        PARAMETERS:
          message: str - Human-readable error message - Default "Authentication failed"
          details: dict | None - Additional auth context - Optional

        GUARANTEES:
          - error_code is "AUTHENTICATION_ERROR"
          - http_status is 401
        """
        super().__init__(message, details)

    @property
    def error_code(self) -> str:
        """Return authentication error code."""
        return "AUTHENTICATION_ERROR"

    @property
    def http_status(self) -> int:
        """Return 401 Unauthorized status."""
        return 401


class PermissionError(BaseAPIError):
    """
    Exception for permission errors (insufficient rights).

    Used when user is authenticated but lacks required permissions.
    """

    def __init__(self, message: str = "Permission denied", details: dict | None = None):
        """
        Initialize permission error.

        PARAMETERS:
          message: str - Human-readable error message - Default "Permission denied"
          details: dict | None - Required permissions context - Optional

        GUARANTEES:
          - error_code is "PERMISSION_ERROR"
          - http_status is 403
        """
        super().__init__(message, details)

    @property
    def error_code(self) -> str:
        """Return permission error code."""
        return "PERMISSION_ERROR"

    @property
    def http_status(self) -> int:
        """Return 403 Forbidden status."""
        return 403


class NotFoundError(BaseAPIError):
    """
    Exception for resource not found errors.

    Used when requested resource does not exist.
    """

    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        """
        Initialize not found error.

        PARAMETERS:
          message: str - Human-readable error message - Default "Resource not found"
          details: dict | None - Resource identifier context - Optional

        GUARANTEES:
          - error_code is "NOT_FOUND"
          - http_status is 404
        """
        super().__init__(message, details)

    @property
    def error_code(self) -> str:
        """Return not found error code."""
        return "NOT_FOUND"

    @property
    def http_status(self) -> int:
        """Return 404 Not Found status."""
        return 404


class RateLimitError(BaseAPIError):
    """
    Exception for rate limit exceeded errors.

    Used when request rate limits are exceeded.
    """

    def __init__(self, message: str = "Rate limit exceeded", details: dict | None = None):
        """
        Initialize rate limit error.

        PARAMETERS:
          message: str - Human-readable error message - Default "Rate limit exceeded"
          details: dict | None - Rate limit context (retry_after, etc.) - Optional

        GUARANTEES:
          - error_code is "RATE_LIMIT_ERROR"
          - http_status is 429
        """
        super().__init__(message, details)

    @property
    def error_code(self) -> str:
        """Return rate limit error code."""
        return "RATE_LIMIT_ERROR"

    @property
    def http_status(self) -> int:
        """Return 429 Too Many Requests status."""
        return 429


class ExternalServiceError(BaseAPIError):
    """
    Exception for external service errors (third-party API failures).

    Used when external services (CargoTech, YuKassa, etc.) are unavailable or return errors.
    """

    def __init__(self, message: str = "External service error", details: dict | None = None):
        """
        Initialize external service error.

        PARAMETERS:
          message: str - Human-readable error message - Default "External service error"
          details: dict | None - Service name and error context - Optional

        GUARANTEES:
          - error_code is "EXTERNAL_SERVICE_ERROR"
          - http_status is 502
        """
        super().__init__(message, details)

    @property
    def error_code(self) -> str:
        """Return external service error code."""
        return "EXTERNAL_SERVICE_ERROR"

    @property
    def http_status(self) -> int:
        """Return 502 Bad Gateway status."""
        return 502


class BusinessLogicError(BaseAPIError):
    """
    Exception for business logic errors.

    Used when request is valid but violates business rules.
    """

    def __init__(self, message: str = "Business logic error", details: dict | None = None):
        """
        Initialize business logic error.

        PARAMETERS:
          message: str - Human-readable error message - Default "Business logic error"
          details: dict | None - Business rule context - Optional

        GUARANTEES:
          - error_code is "BUSINESS_LOGIC_ERROR"
          - http_status is 422
        """
        super().__init__(message, details)

    @property
    def error_code(self) -> str:
        """Return business logic error code."""
        return "BUSINESS_LOGIC_ERROR"

    @property
    def http_status(self) -> int:
        """Return 422 Unprocessable Entity status."""
        return 422


"""
GOAL: Convert custom exceptions to DRF-compatible JSON responses.

PARAMETERS:
  exc: Exception - Any exception raised during request handling - Can be BaseAPIError or other
  context: Dict[str, Any] - DRF exception context - Contains 'request' and 'view'

RETURNS:
  JsonResponse - JSON error response with error_code, message, details - HTTP status from exception

RAISES:
  None - Always returns a valid response

GUARANTEES:
  - BaseAPIError exceptions return structured error responses
  - Non-API exceptions return generic 500 error
  - All responses include error_code field for frontend handling
"""
def custom_exception_handler(exc: Exception, context: Dict[str, Any]) -> JsonResponse:
    """
    Map exceptions to JSON responses with proper HTTP status codes.
    Supports both BaseAPIError subclasses and Django exceptions.
    """
    request: HttpRequest = context.get("request")
    
    # Handle our custom API errors
    if isinstance(exc, BaseAPIError):
        response_data = {
            "error_code": exc.error_code,
            "message": exc.message,
        }
        if exc.details:
            response_data["details"] = exc.details
        
        # Capture to Sentry if enabled
        if hasattr(exc, "capture_to_sentry"):
            try:
                exc.capture_to_sentry()
            except Exception:
                logger.exception("Failed to capture exception to Sentry")
        
        return _json_response(response_data, status=exc.http_status)
    
    # Handle Django ValidationError
    if hasattr(exc, "messages") and isinstance(exc.messages, list):
        response_data = {
            "error_code": "VALIDATION_ERROR",
            "message": "Validation failed",
            "details": {"errors": exc.messages}
        }
        return _json_response(response_data, status=400)
    
    # Generic fallback for unexpected exceptions
    logger.exception("Unhandled exception in custom_exception_handler")
    response_data = {
        "error_code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred",
    }
    return _json_response(response_data, status=500)
