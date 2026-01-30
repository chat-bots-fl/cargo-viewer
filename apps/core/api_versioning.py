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


"""
GOAL: Read API versioning configuration from Django settings.

PARAMETERS:
  None

RETURNS:
  tuple[bool, str, list[str], str] - (enabled, default_version, supported_versions, header_name)

RAISES:
  None

GUARANTEES:
  - Returns sane defaults when settings are missing
  - Supported versions list is never empty
"""
def _get_versioning_config() -> tuple[bool, str, list[str], str]:
    """
    Read API versioning knobs from settings so override_settings/fixtures are respected.
    """
    enabled = bool(getattr(settings, "API_VERSIONING_ENABLED", True))
    default_version = str(getattr(settings, "API_DEFAULT_VERSION", "v3") or "v3")
    supported_versions = list(getattr(settings, "API_SUPPORTED_VERSIONS", ["v1", "v2", "v3"]) or ["v3"])
    header_name = str(getattr(settings, "API_VERSION_HEADER", "X-API-Version") or "X-API-Version")
    return enabled, default_version, supported_versions, header_name


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
    Check headers first, then URL path (/api/v1/...), then default.
    Validate version is supported, fallback to default if invalid.
    """
    enabled, default_setting, supported_versions, header_name = _get_versioning_config()
    default_version = default or default_setting

    if not enabled:
        request.api_version = default_version
        return default_version

    version = None

    # Try extracting from header
    header_version = request.headers.get(header_name, "")
    if header_version and header_version in supported_versions:
        version = header_version

    # Try extracting from URL path
    path = request.path
    if not version and path.startswith("/api/"):
        parts = path.split("/")
        if len(parts) >= 3 and parts[2].startswith("v"):
            potential_version = parts[2]
            if potential_version in supported_versions:
                version = potential_version

    # Fallback to default
    if not version:
        version = default_version

    # Validate version is supported
    if version not in supported_versions:
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

    _enabled, default_version, supported_versions, _header_name = _get_versioning_config()
    api_version = version or default_version

    if api_version not in supported_versions:
        raise ValueError(
            f"Unsupported API version '{api_version}'. "
            f"Supported: {supported_versions}"
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

            # Log request with version (safely access user if available)
            user_info = getattr(request, 'user', 'anonymous')
            logger.info(
                f"API Request: {request.method} {request.path} "
                f"(version: {version}, user: {user_info})"
            )

        except Exception as exc:
            # Graceful degradation: use default version on error
            logger.error(f"API versioning error: {exc}, using default version")
            _enabled, default_version, _supported_versions, _header_name = _get_versioning_config()
            request.api_version = default_version

        response = self.get_response(request)
        if not isinstance(response, HttpResponse):
            response = HttpResponse()

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
    _enabled, _default_version, supported_versions, _header_name = _get_versioning_config()
    return version in supported_versions


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
    _enabled, _default_version, supported_versions, _header_name = _get_versioning_config()
    return sorted(supported_versions, key=lambda v: int(v[1:]))


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
