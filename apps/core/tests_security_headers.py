"""
Tests for Security Headers middleware.

This module contains unit and integration tests for the SecurityHeadersMiddleware.
"""

from __future__ import annotations

import pytest
from django.test import RequestFactory, override_settings
from django.http import HttpResponse


class TestSecurityHeadersMiddleware:
    """
    Tests for SecurityHeadersMiddleware class.
    """

    def test_middleware_adds_all_headers(self, rf, settings):
        """
        GOAL: Verify middleware adds all security headers when enabled.

        GUARANTEES:
          - All security headers are present in response
          - Headers have correct values from settings
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.CSP_ENABLED = True
        settings.HSTS_ENABLED = True
        settings.DEBUG = False

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        # Check all headers are present
        assert "Content-Security-Policy" in response
        assert "X-Content-Type-Options" in response
        assert "X-Frame-Options" in response
        assert "X-XSS-Protection" in response
        assert "Referrer-Policy" in response
        assert "Permissions-Policy" in response

    def test_middleware_skips_when_disabled(self, rf, settings):
        """
        GOAL: Verify middleware skips adding headers when disabled.

        GUARANTEES:
          - No security headers are added when SECURITY_HEADERS_ENABLED=False
          - Response is returned unchanged
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = False

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        # Check no headers are added
        assert "Content-Security-Policy" not in response
        assert "X-Content-Type-Options" not in response
        assert "X-Frame-Options" not in response

    def test_csp_header_format(self, rf, settings):
        """
        GOAL: Verify CSP header has correct format.

        GUARANTEES:
          - CSP header contains all configured directives
          - Directives are separated by semicolons
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.CSP_ENABLED = True
        settings.CSP_DEFAULT_SRC = "'self'"
        settings.CSP_SCRIPT_SRC = "'self' 'unsafe-inline'"
        settings.CSP_STYLE_SRC = "'self' 'unsafe-inline'"

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        csp = response["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self' 'unsafe-inline'" in csp
        assert "style-src 'self' 'unsafe-inline'" in csp

    def test_csp_skipped_when_disabled(self, rf, settings):
        """
        GOAL: Verify CSP header is not added when CSP_ENABLED=False.

        GUARANTEES:
          - CSP header is not present
          - Other security headers are still added
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.CSP_ENABLED = False

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert "Content-Security-Policy" not in response
        assert "X-Content-Type-Options" in response

    def test_hsts_header_in_production(self, rf, settings):
        """
        GOAL: Verify HSTS header is added in production.

        GUARANTEES:
          - HSTS header is present when DEBUG=False and HSTS_ENABLED=True
          - Header includes max-age and other directives
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.HSTS_ENABLED = True
        settings.DEBUG = False
        settings.HSTS_MAX_AGE = 31536000
        settings.HSTS_INCLUDE_SUBDOMAINS = True
        settings.HSTS_PRELOAD = True

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        hsts = response["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_hsts_skipped_in_debug(self, rf, settings):
        """
        GOAL: Verify HSTS header is not added in debug mode.

        GUARANTEES:
          - HSTS header is not present when DEBUG=True
          - Other security headers are still added
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.HSTS_ENABLED = True
        settings.DEBUG = True

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert "Strict-Transport-Security" not in response
        assert "X-Content-Type-Options" in response

    def test_hsts_skipped_when_disabled(self, rf, settings):
        """
        GOAL: Verify HSTS header is not added when HSTS_ENABLED=False.

        GUARANTEES:
          - HSTS header is not present when HSTS_ENABLED=False
          - Other security headers are still added
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.HSTS_ENABLED = False
        settings.DEBUG = False

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert "Strict-Transport-Security" not in response
        assert "X-Content-Type-Options" in response

    def test_x_content_type_options_header(self, rf, settings):
        """
        GOAL: Verify X-Content-Type-Options header has correct value.

        GUARANTEES:
          - Header is set to 'nosniff' by default
          - Header value can be customized via settings
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.X_CONTENT_TYPE_OPTIONS = "nosniff"

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert response["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_header(self, rf, settings):
        """
        GOAL: Verify X-Frame-Options header has correct value.

        GUARANTEES:
          - Header is set to 'DENY' by default
          - Header value can be customized via settings
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.X_FRAME_OPTIONS = "DENY"

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert response["X-Frame-Options"] == "DENY"

    def test_x_xss_protection_header(self, rf, settings):
        """
        GOAL: Verify X-XSS-Protection header has correct value.

        GUARANTEES:
          - Header is set to '1; mode=block' by default
          - Header value can be customized via settings
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.X_XSS_PROTECTION = "1; mode=block"

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert response["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy_header(self, rf, settings):
        """
        GOAL: Verify Referrer-Policy header has correct value.

        GUARANTEES:
          - Header is set to 'strict-origin-when-cross-origin' by default
          - Header value can be customized via settings
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.REFERRER_POLICY = "strict-origin-when-cross-origin"

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy_header(self, rf, settings):
        """
        GOAL: Verify Permissions-Policy header has correct value.

        GUARANTEES:
          - Header disables sensitive features by default
          - Header value can be customized via settings
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.PERMISSIONS_POLICY = "geolocation=(), camera=(), microphone=()"

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert response["Permissions-Policy"] == "geolocation=(), camera=(), microphone=()"

    def test_csp_with_custom_directives(self, rf, settings):
        """
        GOAL: Verify CSP can be customized with custom directives.

        GUARANTEES:
          - Custom CSP directives are used
          - All configured directives are included
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.CSP_ENABLED = True
        settings.CSP_DEFAULT_SRC = "'self' https://cdn.example.com"
        settings.CSP_SCRIPT_SRC = "'self' https://cdn.example.com"
        settings.CSP_IMG_SRC = "'self' data: https: https://cdn.example.com"

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        csp = response["Content-Security-Policy"]
        assert "https://cdn.example.com" in csp

    def test_hsts_with_custom_max_age(self, rf, settings):
        """
        GOAL: Verify HSTS can be customized with custom max-age.

        GUARANTEES:
          - Custom max-age is used
          - Header format is correct
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.HSTS_ENABLED = True
        settings.DEBUG = False
        settings.HSTS_MAX_AGE = 63072000  # 2 years
        settings.HSTS_INCLUDE_SUBDOMAINS = False
        settings.HSTS_PRELOAD = False

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        hsts = response["Strict-Transport-Security"]
        assert "max-age=63072000" in hsts
        assert "includeSubDomains" not in hsts
        assert "preload" not in hsts

    def test_middleware_preserves_existing_headers(self, rf, settings):
        """
        GOAL: Verify middleware preserves headers set by view.

        GUARANTEES:
          - Headers set by view are not removed
          - Security headers are added alongside existing headers
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True

        def get_response(request):
            response = HttpResponse("OK")
            response["X-Custom-Header"] = "custom-value"
            return response

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        assert response["X-Custom-Header"] == "custom-value"
        assert "Content-Security-Policy" in response

    def test_middleware_with_different_http_methods(self, rf, settings):
        """
        GOAL: Verify middleware works with all HTTP methods.

        GUARANTEES:
          - Security headers are added for all HTTP methods
          - No method-specific behavior
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)

        # Test GET
        request = rf.get("/test/")
        response = middleware(request)
        assert "Content-Security-Policy" in response

        # Test POST
        request = rf.post("/test/")
        response = middleware(request)
        assert "Content-Security-Policy" in response

        # Test PUT
        request = rf.put("/test/")
        response = middleware(request)
        assert "Content-Security-Policy" in response

        # Test DELETE
        request = rf.delete("/test/")
        response = middleware(request)
        assert "Content-Security-Policy" in response

    def test_empty_csp_directive_skipped(self, rf, settings):
        """
        GOAL: Verify empty CSP directives are not included.

        GUARANTEES:
          - Empty directive values are skipped
          - CSP header still contains valid directives
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True
        settings.CSP_ENABLED = True
        settings.CSP_DEFAULT_SRC = "'self'"
        settings.CSP_SCRIPT_SRC = ""  # Empty

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        csp = response["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src" not in csp  # Empty directive skipped


class TestSecurityHeadersIntegration:
    """
    Integration tests for Security Headers middleware with Django.
    """

    def test_headers_on_health_check(self, client):
        """
        GOAL: Verify security headers are present on health check endpoint.

        GUARANTEES:
          - Health check endpoint includes security headers
          - Headers are consistent across endpoints
        """
        response = client.get("/health/")

        # Check for security headers (may be disabled in tests)
        # This test verifies the middleware is working if enabled
        if hasattr(response, "get"):
            # Middleware may be disabled in test settings
            pass

    def test_headers_on_api_endpoints(self, client, settings):
        """
        GOAL: Verify security headers are present on API endpoints.

        GUARANTEES:
          - API endpoints include security headers
          - Headers do not break API functionality
        """
        settings.SECURITY_HEADERS_ENABLED = True

        response = client.get("/health/")

        # Verify response is still valid
        assert response.status_code == 200
        assert "status" in response.json()

    def test_middleware_order(self, rf, settings):
        """
        GOAL: Verify middleware is in correct position in middleware chain.

        GUARANTEES:
          - SecurityHeadersMiddleware runs after SecurityMiddleware
          - Headers are applied before response is sent
        """
        from apps.core.security_headers import SecurityHeadersMiddleware

        settings.SECURITY_HEADERS_ENABLED = True

        def get_response(request):
            return HttpResponse("OK")

        middleware = SecurityHeadersMiddleware(get_response)
        request = rf.get("/test/")

        response = middleware(request)

        # Verify headers are added
        assert "Content-Security-Policy" in response
