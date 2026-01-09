"""
Validation helpers for request data using Pydantic schemas.

This module provides helper functions to validate request bodies and query parameters
using Pydantic v2 schemas, converting validation errors to Django ValidationError.
"""

from __future__ import annotations

from typing import Type, TypeVar, Any
from pydantic import ValidationError as PydanticValidationError
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.core.exceptions import ValidationError as AppValidationError

T = TypeVar("T", bound=object)


"""
GOAL: Validate JSON request body using a Pydantic schema and convert errors to app ValidationError.

PARAMETERS:
  schema_class: Type[T] - Pydantic model class for validation - Must be a BaseModel subclass
  request_body: dict[str, Any] - Raw JSON data from request.body - Can be empty dict

RETURNS:
  T - Validated and parsed data from schema - Never None

RAISES:
  AppValidationError: If validation fails with detailed error messages

GUARANTEES:
  - All validation errors from Pydantic are converted to AppValidationError
  - Error messages are user-friendly and field-specific
  - Original Pydantic error details are preserved in exception
"""
def validate_request_body(schema_class: Type[T], request_body: dict[str, Any]) -> T:
    """
    Parse and validate request body using Pydantic schema, converting validation errors.
    """
    try:
        return schema_class.model_validate(request_body)
    except PydanticValidationError as exc:
        # Convert Pydantic validation errors to user-friendly format
        errors = exc.errors()
        error_messages = []

        for error in errors:
            field = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            error_messages.append(f"{field}: {message}")

        raise AppValidationError(
            f"Validation failed: {'; '.join(error_messages)}",
            details={"validation_errors": errors}
        ) from exc


"""
GOAL: Validate query parameters using a Pydantic schema and convert errors to app ValidationError.

PARAMETERS:
  schema_class: Type[T] - Pydantic model class for validation - Must be a BaseModel subclass
  query_params: dict[str, Any] - Raw query params from request.GET - Can contain empty strings

RETURNS:
  T - Validated and parsed data from schema - Never None

RAISES:
  AppValidationError: If validation fails with detailed error messages

GUARANTEES:
  - All validation errors from Pydantic are converted to AppValidationError
  - Empty strings are treated as None for optional fields
  - Error messages are user-friendly and field-specific
"""
def validate_query_params(schema_class: Type[T], query_params: dict[str, Any]) -> T:
    """
    Parse and validate query parameters using Pydantic schema, converting validation errors.
    """
    # Clean up query params: convert empty strings to None for optional fields
    cleaned_params = {}
    for key, value in query_params.items():
        if value == "" or value is None:
            # Let Pydantic handle optional fields with None
            cleaned_params[key] = None
        else:
            cleaned_params[key] = value

    try:
        return schema_class.model_validate(cleaned_params)
    except PydanticValidationError as exc:
        # Convert Pydantic validation errors to user-friendly format
        errors = exc.errors()
        error_messages = []

        for error in errors:
            field = " -> ".join(str(loc) for loc in error["loc"])
            message = error["msg"]
            error_messages.append(f"{field}: {message}")

        raise AppValidationError(
            f"Validation failed: {'; '.join(error_messages)}",
            details={"validation_errors": errors}
        ) from exc
