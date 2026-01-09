"""
Exception handling middleware for unified API error responses.

This middleware catches all exceptions and returns standardized JSON responses.
Also integrates with Sentry for monitoring and error tracking.
"""

import logging
import traceback
from typing import Any, Optional

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.core.exceptions import (
    AuthenticationError,
    BaseAPIError,
    BusinessLogicError,
    ExternalServiceError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Import Sentry monitoring functions (graceful degradation if not available)
try:
    from apps.core.monitoring import (
        add_breadcrumb,
        set_user_context,
        set_transaction,
        capture_exception,
        is_sentry_enabled,
    )
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("Sentry monitoring not available")
    
    # Fallback functions
    def add_breadcrumb(*args, **kwargs):
        pass
    def set_user_context(*args, **kwargs):
        pass
    def set_transaction(*args, **kwargs):
        return None
    def capture_exception(*args, **kwargs):
        return None
    def is_sentry_enabled():
        return False


"""
GOAL: Catch all exceptions and return standardized JSON error responses.

PARAMETERS:
  get_response: Callable - Django middleware get_response callable - Not None

RETURNS:
  Callable - Middleware function - Not None

RAISES:
  None

GUARANTEES:
  - All exceptions are caught and logged
  - Responses follow unified JSON format
  - Production mode hides exception details
  - Debug mode includes full error information
"""
def ExceptionHandlingMiddleware(get_response: Any) -> Any:
    """
    Create middleware that wraps request processing with exception handling.
    """

    """
    GOAL: Process request and handle any exceptions that occur.

    PARAMETERS:
      request: HttpRequest - Incoming HTTP request - Not None

    RETURNS:
      HttpResponse - Either successful response or error response - Not None

    RAISES:
      None (all exceptions are caught)

    GUARANTEES:
      - BaseAPIError exceptions return formatted JSON with error code
      - Django ValidationError is converted to ValidationError
      - Other exceptions return generic error response
      - All exceptions are logged with stack trace in debug mode
      - Sentry breadcrumbs and user context are added for monitoring
      - Transactions are tracked for performance monitoring
    """
    def middleware(request: HttpRequest) -> HttpResponse:
        """
        Wrap request processing in try-except for unified error handling.
        Add Sentry breadcrumbs and user context for monitoring.
        """
        # Add breadcrumb for request start
        add_breadcrumb(
            message=f"Request: {request.method} {request.path}",
            category="http",
            level="info",
            data={
                "method": request.method,
                "path": request.path,
                "user_agent": request.META.get("HTTP_USER_AGENT", ""),
                "ip": _get_client_ip(request),
            }
        )
        
        # Set user context if authenticated
        _set_user_context_from_request(request)
        
        # Start transaction for performance monitoring
        transaction = set_transaction(
            name=f"{request.method} {request.path}",
            op="http.request",
            tags={
                "method": request.method,
                "path": request.path,
            }
        )
        
        try:
            if transaction:
                with transaction:
                    response = get_response(request)
            else:
                response = get_response(request)
            
            # Add breadcrumb for successful response
            add_breadcrumb(
                message=f"Response: {response.status_code}",
                category="http",
                level="info",
                data={
                    "status_code": response.status_code,
                }
            )
            
            return response
        except BaseAPIError as exc:
            # Handle our custom API exceptions
            return _handle_api_error(exc, request)
        except DjangoValidationError as exc:
            # Convert Django ValidationError to our ValidationError
            validation_error = ValidationError(
                message=str(exc),
                details={"django_validation": str(exc.message_dict) if hasattr(exc, "message_dict") else str(exc)},
            )
            return _handle_api_error(validation_error, request)
        except Exception as exc:
            # Handle unexpected exceptions
            return _handle_unexpected_error(exc, request)

    return middleware


"""
GOAL: Generate standardized JSON response for custom API exceptions.

PARAMETERS:
  exc: BaseAPIError - Custom API exception - Not None
  request: HttpRequest - Current request for logging - Not None

RETURNS:
  JsonResponse - JSON error response with status code - Not None

RAISES:
  None

GUARANTEES:
  - Response format includes error code, message, and optional details
  - Details only included in DEBUG mode
  - Exception is logged with appropriate level
  - Exception is sent to Sentry if monitoring is enabled
  - Breadcrumb is added for error context
"""
def _handle_api_error(exc: BaseAPIError, request: HttpRequest) -> JsonResponse:
    """
    Build JSON response from custom exception and log the error.
    Send exception to Sentry for monitoring.
    """
    # Add breadcrumb for API error
    add_breadcrumb(
        message=f"API Error: {exc.error_code}",
        category="error",
        level="warning",
        data={
            "error_code": exc.error_code,
            "path": request.path,
            "method": request.method,
        }
    )
    
    # Send exception to Sentry
    capture_exception(
        exc,
        level="warning",
        extra={
            "path": request.path,
            "method": request.method,
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "ip": _get_client_ip(request),
        },
        tags={
            "error_code": exc.error_code,
            "path": request.path,
        }
    )
    
    # Log the error
    logger.warning(
        "API Error: %s - %s - Path: %s",
        exc.error_code,
        exc.message,
        request.path,
        extra={"request": request, "exception": exc},
    )

    # Build response data
    response_data: dict[str, Any] = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
        }
    }

    # Add details in debug mode or if explicitly provided
    if settings.DEBUG and exc.details:
        response_data["error"]["details"] = exc.details

    return JsonResponse(response_data, status=exc.http_status)


"""
GOAL: Generate standardized JSON response for unexpected exceptions.

PARAMETERS:
  exc: Exception - Unexpected exception - Not None
  request: HttpRequest - Current request for logging - Not None

RETURNS:
  JsonResponse - JSON error response with 500 status - Not None

RAISES:
  None

GUARANTEES:
  - Response format includes generic error message
  - Stack trace included in DEBUG mode
  - Exception is logged as error with full traceback
  - Exception is sent to Sentry for monitoring
  - Breadcrumb is added for error context
"""
def _handle_unexpected_error(exc: Exception, request: HttpRequest) -> JsonResponse:
    """
    Build JSON response from unexpected exception and log with traceback.
    Send exception to Sentry for monitoring.
    """
    # Add breadcrumb for unexpected error
    add_breadcrumb(
        message=f"Unexpected error: {type(exc).__name__}",
        category="error",
        level="error",
        data={
            "exception_type": type(exc).__name__,
            "path": request.path,
            "method": request.method,
        }
    )
    
    # Send exception to Sentry
    capture_exception(
        exc,
        level="error",
        extra={
            "path": request.path,
            "method": request.method,
            "user_agent": request.META.get("HTTP_USER_AGENT", ""),
            "ip": _get_client_ip(request),
        },
        tags={
            "exception_type": type(exc).__name__,
            "path": request.path,
        }
    )
    
    # Log the error with full traceback
    logger.error(
        "Unexpected error: %s - Path: %s",
        str(exc),
        request.path,
        exc_info=True,
        extra={"request": request},
    )

    # Build response data
    response_data: dict[str, Any] = {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
        }
    }

    # Add details only in debug mode
    if settings.DEBUG:
        response_data["error"]["details"] = {
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc(),
        }

    return JsonResponse(response_data, status=500)


"""
GOAL: Extract client IP address from request.

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None

RETURNS:
  str - Client IP address - Never None

RAISES:
  None

GUARANTEES:
  - Returns IP address from X-Forwarded-For header if present
  - Falls back to REMOTE_ADDR
  - Returns "unknown" if no IP found
"""
def _get_client_ip(request: HttpRequest) -> str:
    """
    Extract client IP from request headers or connection info.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return ip


"""
GOAL: Set user context in Sentry from authenticated request.

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - User context is set if user is authenticated
  - No-op if user is not authenticated
  - Graceful degradation if Sentry is disabled
"""
def _set_user_context_from_request(request: HttpRequest) -> None:
    """
    Extract user information from request and set Sentry context.
    """
    if not hasattr(request, "user") or not request.user.is_authenticated:
        return
    
    try:
        user = request.user
        set_user_context(
            user_id=getattr(user, "id", None),
            username=getattr(user, "username", None),
            email=getattr(user, "email", None),
            ip_address=_get_client_ip(request),
        )
    except Exception as e:
        logger.warning(f"Failed to set user context: {e}")
