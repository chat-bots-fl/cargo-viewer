"""
API Versioning Module

Provides middleware and helper functions for API versioning support.
Supports version extraction from URL path or HTTP headers with graceful degradation.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.core.cache import cache

logger = logging.getLogger("api_versioning")


# Default settings (can be overridden in config/settings.py)
API_VERSIONING_ENABLED = getattr(settings, "API_VERSIONING_ENABLED", True)
API_DEFAULT_VERSION = getattr(settings, "API_DEFAULT_VERSION", "v3")
API_SUPPORTED_VERSIONS = getattr(settings, "API_SUPPORTED_VERSIONS", ["v1", "v2", "v3"])
API_VERSION_HEADER = getattr(settings, "API_VERSION_HEADER", "X-API-Version")


"""
GOAL: Extract API version from request path or headers with fallback to default.

PARAMETERS:
  request: HttpRequest - Incoming HTTP request - Not None
  default: str - Default version if none found - Must be in supported versions

RETURNS:
  str - API version string (e.g., "v1", "v2", "v3") - Always in supported versions

RAISES:
  None (graceful degradation on errors)

GUARANTEES:
  - Always returns a valid version string
  - Version is always in supported versions list
  - Logs version extraction for debugging
  - Caches version in request.api_version attribute
"""
def get_api_version(request: HttpRequest, default: Optional[str] = None) -> str:
    """
    Check URL path first (/api/v1/...), then headers, then default.
    Validate version is supported, fallback to default if invalid.
    """
    if not API_VERSIONING_ENABLED:
        return API_DEFAULT_VERSION

    version = None
    default_version = default or API_DEFAULT_VERSION

    # Try extracting from URL path
    path = request.path
    if path.startswith("/api/"):
        parts = path.split("/")
        if len(parts) >= 3 and parts[2].startswith("v"):
            potential_version = parts[2]
            if potential_version in API_SUPPORTED_VERSIONS:
                version = potential_version

    # Try extracting from header
    if not version:
        header_version = request.headers.get(API_VERSION_HEADER, "")
        if header_version and header_version in API_SUPPORTED_VERSIONS:
            version = header_version

    # Fallback to default
    if not version:
        version = default_version

    # Validate version is supported
    if version not in API_SUPPORTED_VERSIONS:
        logger.warning(
            f"Invalid API version '{version}', using default '{default_version}'"
        )
        version = default_version

    # Cache in request for subsequent access
    request.api_version = version

    logger.debug(f"API version extracted: {version} from {path}")
    return version


"""
GOAL: Generate versioned URL path for a given endpoint and version.

PARAMETERS:
  endpoint: str - API endpoint path (e.g., "/auth/telegram") - Must start with /
  version: str - API version to use - Must be in supported versions

RETURNS:
  str - Full versioned URL path (e.g., "/api/v3/auth/telegram") - Always valid

RAISES:
  ValueError: If endpoint doesn't start with /
  ValueError: If version is not in supported versions

GUARANTEES:
  - Returned URL always starts with /api/
  - Version is always in supported versions list
  - Original endpoint path preserved after version prefix
"""
def versioned_url(endpoint: str, version: Optional[str] = None) -> str:
    """
    Prepend /api/{version}/ to endpoint path.
    Validate inputs and ensure proper formatting.
    """
    if not endpoint.startswith("/"):
        raise ValueError(f"Endpoint must start with '/', got: {endpoint}")

    api_version = version or API_DEFAULT_VERSION

    if api_version not in API_SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported API version '{api_version}'. "
            f"Supported: {API_SUPPORTED_VERSIONS}"
        )

    # Remove leading / from endpoint to avoid double slash
    clean_endpoint = endpoint.lstrip("/")

    return f"/api/{api_version}/{clean_endpoint}"


"""
GOAL: Middleware to add API version information to all requests.

PARAMETERS:
  get_response: Callable - Django middleware handler - Not None

RETURNS:
  Callable - Middleware function - Not None

RAISES:
  None

GUARANTEES:
  - request.api_version always set after middleware runs
  - Version is always in supported versions list
  - Logs all requests with version information
  - Gracefully handles versioning errors
"""
class APIVersioningMiddleware:
    """
    Extract API version from path/header, set in request.api_version.
    Support graceful degradation on errors.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Process request: extract version, set attribute, call next middleware.
        """
        try:
            # Extract and cache API version
            version = get_api_version(request)
            request.api_version = version

            # Log request with version
            logger.info(
                f"API Request: {request.method} {request.path} "
                f"(version: {version}, user: {request.user})"
            )

        except Exception as exc:
            # Graceful degradation: use default version on error
            logger.error(f"API versioning error: {exc}, using default version")
            request.api_version = API_DEFAULT_VERSION

        response = self.get_response(request)

        # Add version to response headers
        response["X-API-Version"] = request.api_version

        return response


"""
GOAL: Check if a specific API version is supported.

PARAMETERS:
  version: str - API version to check - Not None

RETURNS:
  bool - True if version is supported, False otherwise - Never None

RAISES:
  None

GUARANTEES:
  - Returns True for all versions in supported versions list
  - Returns False for any other version string
"""
def is_version_supported(version: str) -> bool:
    """
    Check if version is in API_SUPPORTED_VERSIONS list.
    Case-sensitive comparison.
    """
    return version in API_SUPPORTED_VERSIONS


"""
GOAL: Get list of all supported API versions.

PARAMETERS:
  None

RETURNS:
  List[str] - List of supported version strings - Never empty

RAISES:
  None

GUARANTEES:
  - Always returns at least one version
  - Versions are sorted in ascending order
  - List contains only strings starting with 'v'
"""
def get_supported_versions() -> list[str]:
    """
    Return sorted list of supported API versions.
    Ensures consistent ordering across application.
    """
    return sorted(API_SUPPORTED_VERSIONS, key=lambda v: int(v[1:]))


"""
GOAL: Get the latest supported API version.

PARAMETERS:
  None

RETURNS:
  str - Latest version string - Always in supported versions

RAISES:
  None

GUARANTEES:
  - Returned version is always in supported versions list
  - Version is numerically highest among supported versions
"""
def get_latest_version() -> str:
    """
    Return highest version number from supported versions list.
    Used for version upgrade recommendations.
    """
    return get_supported_versions()[-1]


"""
GOAL: Check if client is using outdated API version.

PARAMETERS:
  version: str - Client's API version - Not None

RETURNS:
  bool - True if version is not latest, False otherwise - Never None

RAISES:
  None

GUARANTEES:
  - Returns True for any version older than latest
  - Returns False for latest version
  - Returns False if version not supported (graceful)
"""
def is_version_outdated(version: str) -> bool:
    """
    Compare version against latest supported version.
    Returns False if version not supported (graceful degradation).
    """
    if not is_version_supported(version):
        return False
    return version != get_latest_version()


"""
GOAL: Build version-aware response headers.

PARAMETERS:
  version: str - Current API version - Not None
  include_deprecation: bool - Include deprecation warning if outdated - Default True

RETURNS:
  Dict[str, str] - Response headers dictionary - Not None

RAISES:
  None

GUARANTEES:
  - Always includes X-API-Version header
  - Includes X-API-Latest-Version header
  - Includes deprecation warning if version outdated and requested
  - All header values are non-empty strings
"""
def build_version_headers(version: str, include_deprecation: bool = True) -> dict[str, str]:
    """
    Build headers with version information and deprecation warnings.
    Used for API responses to inform clients about version status.
    """
    headers = {
        "X-API-Version": version,
        "X-API-Latest-Version": get_latest_version(),
        "X-API-Supported-Versions": ", ".join(get_supported_versions()),
    }

    if include_deprecation and is_version_outdated(version):
        headers["X-API-Deprecation"] = (
            f"Version {version} is outdated. "
            f"Please upgrade to {get_latest_version()}"
        )

    return headers
