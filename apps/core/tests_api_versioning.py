"""
Tests for API Versioning Module

Tests cover middleware, helper functions, and URL routing with versioning.
"""

from __future__ import annotations

from django.test import RequestFactory, TestCase, override_settings
from django.contrib.auth.models import AnonymousUser

from apps.core.api_versioning import (
    get_api_version,
    versioned_url,
    is_version_supported,
    get_supported_versions,
    get_latest_version,
    is_version_outdated,
    build_version_headers,
    APIVersioningMiddleware,
)


class TestGetAPIVersion(TestCase):
    """
    Test cases for get_api_version function.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_extract_version_from_url_path(self):
        """
        GOAL: Verify version extraction from URL path.

        GUARANTEES:
          - Version extracted correctly from /api/v1/... pattern
          - request.api_version attribute is set
        """
        request = self.factory.get("/api/v1/auth/telegram")
        version = get_api_version(request)
        self.assertEqual(version, "v1")
        self.assertEqual(request.api_version, "v1")

    def test_extract_version_from_url_path_v2(self):
        """
        GOAL: Verify version extraction from URL path for v2.

        GUARANTEES:
          - Version extracted correctly from /api/v2/... pattern
        """
        request = self.factory.get("/api/v2/cargos/")
        version = get_api_version(request)
        self.assertEqual(version, "v2")

    def test_extract_version_from_url_path_v3(self):
        """
        GOAL: Verify version extraction from URL path for v3.

        GUARANTEES:
          - Version extracted correctly from /api/v3/... pattern
        """
        request = self.factory.get("/api/v3/cargos/123/")
        version = get_api_version(request)
        self.assertEqual(version, "v3")

    def test_extract_version_from_header(self):
        """
        GOAL: Verify version extraction from HTTP header.

        GUARANTEES:
          - Version extracted correctly from X-API-Version header
        """
        request = self.factory.get("/api/cargos/", HTTP_X_API_VERSION="v2")
        version = get_api_version(request)
        self.assertEqual(version, "v2")

    def test_header_takes_priority_over_path(self):
        """
        GOAL: Verify header takes priority over path when both present.

        GUARANTEES:
          - Header version used when both path and header have version
        """
        request = self.factory.get(
            "/api/v1/cargos/",
            HTTP_X_API_VERSION="v3"
        )
        version = get_api_version(request)
        self.assertEqual(version, "v3")

    def test_default_version_when_no_version(self):
        """
        GOAL: Verify default version used when none found.

        GUARANTEES:
          - Default version (v3) returned when no version in path or header
        """
        request = self.factory.get("/api/cargos/")
        version = get_api_version(request)
        self.assertEqual(version, "v3")

    def test_default_version_for_non_api_path(self):
        """
        GOAL: Verify default version for non-API paths.

        GUARANTEES:
          - Default version returned for paths not starting with /api/
        """
        request = self.factory.get("/webapp/")
        version = get_api_version(request)
        self.assertEqual(version, "v3")

    def test_invalid_version_fallback_to_default(self):
        """
        GOAL: Verify fallback to default for invalid version.

        GUARANTEES:
          - Default version used when version in path is invalid
        """
        request = self.factory.get("/api/v99/cargos/")
        version = get_api_version(request)
        self.assertEqual(version, "v3")

    def test_custom_default_version(self):
        """
        GOAL: Verify custom default version parameter works.

        GUARANTEES:
          - Custom default version used when specified
        """
        request = self.factory.get("/api/cargos/")
        version = get_api_version(request, default="v1")
        self.assertEqual(version, "v1")


class TestVersionedURL(TestCase):
    """
    Test cases for versioned_url function.
    """

    def test_versioned_url_with_v1(self):
        """
        GOAL: Verify versioned URL generation for v1.

        GUARANTEES:
          - URL correctly formatted with /api/v1/ prefix
        """
        url = versioned_url("/auth/telegram", version="v1")
        self.assertEqual(url, "/api/v1/auth/telegram")

    def test_versioned_url_with_v2(self):
        """
        GOAL: Verify versioned URL generation for v2.

        GUARANTEES:
          - URL correctly formatted with /api/v2/ prefix
        """
        url = versioned_url("/cargos/", version="v2")
        self.assertEqual(url, "/api/v2/cargos/")

    def test_versioned_url_with_v3(self):
        """
        GOAL: Verify versioned URL generation for v3.

        GUARANTEES:
          - URL correctly formatted with /api/v3/ prefix
        """
        url = versioned_url("/cargos/123/", version="v3")
        self.assertEqual(url, "/api/v3/cargos/123/")

    def test_versioned_url_default_version(self):
        """
        GOAL: Verify default version used when not specified.

        GUARANTEES:
          - Default version (v3) used when version parameter omitted
        """
        url = versioned_url("/auth/telegram")
        self.assertEqual(url, "/api/v3/auth/telegram")

    def test_versioned_url_leading_slash_normalization(self):
        """
        GOAL: Verify leading slash normalization.

        GUARANTEES:
          - Multiple leading slashes normalized to single slash
        """
        url = versioned_url("//auth/telegram", version="v1")
        self.assertEqual(url, "/api/v1/auth/telegram")

    def test_versioned_url_without_leading_slash_raises_error(self):
        """
        GOAL: Verify error when endpoint doesn't start with /.

        GUARANTEES:
          - ValueError raised for endpoint without leading slash
        """
        with self.assertRaises(ValueError) as context:
            versioned_url("auth/telegram", version="v1")
        self.assertIn("must start with '/'", str(context.exception))

    def test_versioned_url_unsupported_version_raises_error(self):
        """
        GOAL: Verify error for unsupported version.

        GUARANTEES:
          - ValueError raised for version not in supported list
        """
        with self.assertRaises(ValueError) as context:
            versioned_url("/auth/telegram", version="v99")
        self.assertIn("Unsupported API version", str(context.exception))


class TestIsVersionSupported(TestCase):
    """
    Test cases for is_version_supported function.
    """

    def test_supported_versions(self):
        """
        GOAL: Verify supported versions return True.

        GUARANTEES:
          - True returned for v1, v2, v3
        """
        self.assertTrue(is_version_supported("v1"))
        self.assertTrue(is_version_supported("v2"))
        self.assertTrue(is_version_supported("v3"))

    def test_unsupported_version(self):
        """
        GOAL: Verify unsupported versions return False.

        GUARANTEES:
          - False returned for versions not in supported list
        """
        self.assertFalse(is_version_supported("v4"))
        self.assertFalse(is_version_supported("v99"))
        self.assertFalse(is_version_supported("v0"))

    def test_case_sensitive(self):
        """
        GOAL: Verify version check is case-sensitive.

        GUARANTEES:
          - False returned for uppercase version names
        """
        self.assertFalse(is_version_supported("V1"))
        self.assertFalse(is_version_supported("V2"))


class TestGetSupportedVersions(TestCase):
    """
    Test cases for get_supported_versions function.
    """

    def test_returns_all_versions(self):
        """
        GOAL: Verify all supported versions returned.

        GUARANTEES:
          - List contains v1, v2, v3
        """
        versions = get_supported_versions()
        self.assertEqual(len(versions), 3)
        self.assertIn("v1", versions)
        self.assertIn("v2", versions)
        self.assertIn("v3", versions)

    def test_versions_sorted(self):
        """
        GOAL: Verify versions are sorted in ascending order.

        GUARANTEES:
          - Versions sorted numerically (v1, v2, v3)
        """
        versions = get_supported_versions()
        self.assertEqual(versions, ["v1", "v2", "v3"])

    def test_non_empty_list(self):
        """
        GOAL: Verify list is never empty.

        GUARANTEES:
          - At least one version always returned
        """
        versions = get_supported_versions()
        self.assertGreater(len(versions), 0)


class TestGetLatestVersion(TestCase):
    """
    Test cases for get_latest_version function.
    """

    def test_returns_latest_version(self):
        """
        GOAL: Verify latest version returned.

        GUARANTEES:
          - Highest version number returned (v3)
        """
        latest = get_latest_version()
        self.assertEqual(latest, "v3")

    def test_latest_is_in_supported(self):
        """
        GOAL: Verify latest version is in supported list.

        GUARANTEES:
          - Latest version is always supported
        """
        latest = get_latest_version()
        self.assertTrue(is_version_supported(latest))


class TestIsVersionOutdated(TestCase):
    """
    Test cases for is_version_outdated function.
    """

    def test_latest_version_not_outdated(self):
        """
        GOAL: Verify latest version is not outdated.

        GUARANTEES:
          - False returned for latest version (v3)
        """
        self.assertFalse(is_version_outdated("v3"))

    def test_older_versions_outdated(self):
        """
        GOAL: Verify older versions are outdated.

        GUARANTEES:
          - True returned for v1 and v2
        """
        self.assertTrue(is_version_outdated("v1"))
        self.assertTrue(is_version_outdated("v2"))

    def test_unsupported_version_not_outdated(self):
        """
        GOAL: Verify unsupported versions are not considered outdated.

        GUARANTEES:
          - False returned gracefully for unsupported versions
        """
        self.assertFalse(is_version_outdated("v4"))
        self.assertFalse(is_version_outdated("v99"))


class TestBuildVersionHeaders(TestCase):
    """
    Test cases for build_version_headers function.
    """

    def test_headers_include_version(self):
        """
        GOAL: Verify headers include API version.

        GUARANTEES:
          - X-API-Version header present with correct value
        """
        headers = build_version_headers("v1")
        self.assertIn("X-API-Version", headers)
        self.assertEqual(headers["X-API-Version"], "v1")

    def test_headers_include_latest_version(self):
        """
        GOAL: Verify headers include latest version.

        GUARANTEES:
          - X-API-Latest-Version header present
        """
        headers = build_version_headers("v1")
        self.assertIn("X-API-Latest-Version", headers)
        self.assertEqual(headers["X-API-Latest-Version"], "v3")

    def test_headers_include_supported_versions(self):
        """
        GOAL: Verify headers include supported versions list.

        GUARANTEES:
          - X-API-Supported-Versions header present
        """
        headers = build_version_headers("v1")
        self.assertIn("X-API-Supported-Versions", headers)
        self.assertIn("v1", headers["X-API-Supported-Versions"])
        self.assertIn("v2", headers["X-API-Supported-Versions"])
        self.assertIn("v3", headers["X-API-Supported-Versions"])

    def test_deprecation_header_for_outdated_version(self):
        """
        GOAL: Verify deprecation header for outdated versions.

        GUARANTEES:
          - X-API-Deprecation header present for v1 and v2
        """
        headers_v1 = build_version_headers("v1", include_deprecation=True)
        self.assertIn("X-API-Deprecation", headers_v1)
        self.assertIn("outdated", headers_v1["X-API-Deprecation"])

        headers_v2 = build_version_headers("v2", include_deprecation=True)
        self.assertIn("X-API-Deprecation", headers_v2)

    def test_no_deprecation_header_for_latest_version(self):
        """
        GOAL: Verify no deprecation header for latest version.

        GUARANTEES:
          - X-API-Deprecation header absent for v3
        """
        headers = build_version_headers("v3", include_deprecation=True)
        self.assertNotIn("X-API-Deprecation", headers)

    def test_deprecation_disabled(self):
        """
        GOAL: Verify deprecation can be disabled.

        GUARANTEES:
          - No deprecation header when include_deprecation=False
        """
        headers = build_version_headers("v1", include_deprecation=False)
        self.assertNotIn("X-API-Deprecation", headers)


class TestAPIVersioningMiddleware(TestCase):
    """
    Test cases for APIVersioningMiddleware.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = APIVersioningMiddleware(lambda r: r)

    def test_middleware_sets_api_version_attribute(self):
        """
        GOAL: Verify middleware sets request.api_version.

        GUARANTEES:
          - request.api_version attribute set after middleware
        """
        request = self.factory.get("/api/v1/cargos/")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(request.api_version, "v1")

    def test_middleware_adds_version_header_to_response(self):
        """
        GOAL: Verify middleware adds X-API-Version to response.

        GUARANTEES:
          - Response includes X-API-Version header
        """
        request = self.factory.get("/api/v2/auth/telegram")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(response["X-API-Version"], "v2")

    def test_middleware_with_version_header(self):
        """
        GOAL: Verify middleware respects version header.

        GUARANTEES:
          - Header version used when present
        """
        request = self.factory.get(
            "/api/cargos/",
            HTTP_X_API_VERSION="v2"
        )
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(request.api_version, "v2")
        self.assertEqual(response["X-API-Version"], "v2")

    def test_middleware_default_version(self):
        """
        GOAL: Verify middleware uses default version when none found.

        GUARANTEES:
          - Default version (v3) used for non-versioned URLs
        """
        request = self.factory.get("/api/cargos/")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(request.api_version, "v3")

    def test_middleware_graceful_degradation_on_error(self):
        """
        GOAL: Verify middleware handles errors gracefully.

        GUARANTEES:
          - Default version used on error
          - Response still returned
        """
        # Create a request that might cause issues
        request = self.factory.get("/api/v99/cargos/")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(request.api_version, "v3")
        self.assertIsNotNone(response)

    def test_middleware_with_non_api_path(self):
        """
        GOAL: Verify middleware works with non-API paths.

        GUARANTEES:
          - Default version set for non-API paths
        """
        request = self.factory.get("/webapp/")
        request.user = AnonymousUser()
        response = self.middleware(request)
        self.assertEqual(request.api_version, "v3")


class TestIntegration(TestCase):
    """
    Integration tests for API versioning with Django URL routing.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_versioned_url_accessible(self):
        """
        GOAL: Verify versioned URLs are accessible.

        GUARANTEES:
          - /api/v1/, /api/v2/, /api/v3/ URLs work
        """
        # Test v1
        response_v1 = self.client.get("/api/v1/cargos/")
        self.assertIn(response_v1.status_code, [200, 302, 401, 403])

        # Test v2
        response_v2 = self.client.get("/api/v2/cargos/")
        self.assertIn(response_v2.status_code, [200, 302, 401, 403])

        # Test v3
        response_v3 = self.client.get("/api/v3/cargos/")
        self.assertIn(response_v3.status_code, [200, 302, 401, 403])

    def test_legacy_urls_accessible(self):
        """
        GOAL: Verify legacy URLs still work for backward compatibility.

        GUARANTEES:
          - Old /api/... URLs without version prefix work
        """
        response = self.client.get("/api/cargos/")
        self.assertIn(response.status_code, [200, 302, 401, 403])

    def test_version_header_in_response(self):
        """
        GOAL: Verify version header present in responses.

        GUARANTEES:
          - X-API-Version header in API responses
        """
        response = self.client.get("/api/v1/cargos/")
        self.assertIn("X-API-Version", response)

    def test_version_header_in_legacy_response(self):
        """
        GOAL: Verify version header in legacy endpoint responses.

        GUARANTEES:
          - X-API-Version header in legacy endpoint responses
        """
        response = self.client.get("/api/cargos/")
        self.assertIn("X-API-Version", response)


class TestVersioningDisabled(TestCase):
    """
    Test cases for when API versioning is disabled.
    """

    @override_settings(API_VERSIONING_ENABLED=False)
    def test_versioning_disabled_returns_default(self):
        """
        GOAL: Verify default version returned when versioning disabled.

        GUARANTEES:
          - Default version always returned when disabled
        """
        factory = RequestFactory()
        request = self.factory.get("/api/v1/cargos/")
        version = get_api_version(request)
        self.assertEqual(version, "v3")
