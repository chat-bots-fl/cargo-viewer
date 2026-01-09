from __future__ import annotations

import os

"""
GOAL: Automatically determine the current environment and load appropriate Django settings.

PARAMETERS:
  None

RETURNS:
  None - Module-level configuration import

RAISES:
  ImportError: If environment-specific settings module cannot be imported
  ValueError: If DJANGO_ENV has invalid value

GUARANTEES:
  - Always imports a settings module
  - Falls back to development if DJANGO_ENV is not set
  - Validates environment name before import
"""

# Valid environment names
VALID_ENVIRONMENTS = {"development", "staging", "production"}


"""
GOAL: Get the current environment name from DJANGO_ENV environment variable.

PARAMETERS:
  None

RETURNS:
  str - Environment name (development, staging, or production) - Always valid

RAISES:
  ValueError: If DJANGO_ENV is set but not in VALID_ENVIRONMENTS

GUARANTEES:
  - Returns a valid environment name
  - Defaults to 'development' if DJANGO_ENV is not set
  - Raises ValueError for invalid environment names
"""
def get_environment() -> str:
    """
    Read DJANGO_ENV from environment, validate against allowed values,
    and return the environment name with fallback to 'development'.
    """
    env = os.getenv("DJANGO_ENV", "development").lower().strip()
    
    if env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"Invalid DJANGO_ENV value: '{env}'. "
            f"Must be one of: {', '.join(sorted(VALID_ENVIRONMENTS))}"
        )
    
    return env


# Get the current environment
environment = get_environment()

# Import the appropriate settings module
try:
    if environment == "development":
        from .development import *  # noqa: F401, F403
    elif environment == "staging":
        from .staging import *  # noqa: F401, F403
    elif environment == "production":
        from .production import *  # noqa: F401, F403
except ImportError as e:
    raise ImportError(
        f"Failed to import settings for environment '{environment}': {e}"
    )

# Export environment name for use in other parts of the application
DJANGO_ENV = environment
