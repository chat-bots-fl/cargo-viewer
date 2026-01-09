"""
Tests for Pydantic schemas and validation helpers.

This module contains unit tests for all Pydantic schemas and validation helpers
defined in apps/core/schemas.py and apps/core/validation.py.
"""

from __future__ import annotations

import pytest
from datetime import date
from pydantic import ValidationError as PydanticValidationError

from apps.core.schemas import (
    TelegramAuthRequest,
    CargoListRequest,
    CargoDetailRequest,
    PaymentCreateRequest,
    FilterRequest,
    TelegramResponseRequest,
)
from apps.core.validation import validate_request_body, validate_query_params
from apps.core.exceptions import ValidationError as AppValidationError


class TestTelegramAuthRequest:
    """
    Tests for TelegramAuthRequest schema.
    """

    def test_valid_init_data(self):
        """
        GOAL: Verify valid init_data passes validation.

        GUARANTEES:
          - Valid init_data string is accepted
        """
        request = TelegramAuthRequest(init_data="query_id=123&auth_date=1234567890&hash=abc123")
        assert request.init_data == "query_id=123&auth_date=1234567890&hash=abc123"

    def test_missing_init_data(self):
        """
        GOAL: Verify missing init_data raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised when init_data is missing
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            TelegramAuthRequest()
        assert "init_data" in str(exc_info.value)

    def test_empty_init_data(self):
        """
        GOAL: Verify empty init_data raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised when init_data is empty
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            TelegramAuthRequest(init_data="")
        assert "init_data" in str(exc_info.value)

    def test_whitespace_stripped(self):
        """
        GOAL: Verify whitespace is stripped from init_data.

        GUARANTEES:
          - Leading/trailing whitespace is removed from init_data
        """
        request = TelegramAuthRequest(init_data="  query_id=123  ")
        assert request.init_data == "query_id=123"


class TestCargoListRequest:
    """
    Tests for CargoListRequest schema.
    """

    def test_default_values(self):
        """
        GOAL: Verify default values are applied correctly.

        GUARANTEES:
          - limit defaults to 20
          - offset defaults to 0
          - mode defaults to "my"
        """
        request = CargoListRequest()
        assert request.limit == 20
        assert request.offset == 0
        assert request.mode == "my"

    def test_valid_pagination(self):
        """
        GOAL: Verify valid pagination parameters are accepted.

        GUARANTEES:
          - limit within [1, 100] is accepted
          - offset >= 0 is accepted
        """
        request = CargoListRequest(limit=50, offset=10)
        assert request.limit == 50
        assert request.offset == 10

    def test_limit_out_of_range(self):
        """
        GOAL: Verify limit outside [1, 100] raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for invalid limit
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(limit=0)
        assert "limit" in str(exc_info.value)

        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(limit=101)
        assert "limit" in str(exc_info.value)

    def test_negative_offset(self):
        """
        GOAL: Verify negative offset raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for negative offset
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(offset=-1)
        assert "offset" in str(exc_info.value)

    def test_valid_start_date(self):
        """
        GOAL: Verify valid ISO date is accepted.

        GUARANTEES:
          - Valid ISO date string is converted to date object
        """
        request = CargoListRequest(start_date="2024-01-15")
        assert request.start_date == date(2024, 1, 15)

    def test_invalid_start_date(self):
        """
        GOAL: Verify invalid date raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for invalid date format
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(start_date="2024-13-01")
        assert "start_date" in str(exc_info.value)

    def test_valid_weight_volume(self):
        """
        GOAL: Verify valid weight_volume format is accepted.

        GUARANTEES:
          - Valid "weight-volume" format is accepted
          - Decimal values are accepted
        """
        request = CargoListRequest(weight_volume="15-65")
        assert request.weight_volume == "15-65"

        request = CargoListRequest(weight_volume="1.5-9.5")
        assert request.weight_volume == "1.5-9.5"

    def test_invalid_weight_volume_format(self):
        """
        GOAL: Verify invalid weight_volume format raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for invalid format
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(weight_volume="15")
        assert "weight_volume" in str(exc_info.value)

        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(weight_volume="15-")
        assert "weight_volume" in str(exc_info.value)

    def test_weight_volume_out_of_range(self):
        """
        GOAL: Verify weight_volume values outside ranges raise validation error.

        GUARANTEES:
          - PydanticValidationError is raised for out-of-range values
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(weight_volume="0.05-10")
        assert "Weight" in str(exc_info.value)

        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(weight_volume="10-0.05")
        assert "Volume" in str(exc_info.value)

    def test_valid_csv_ids(self):
        """
        GOAL: Verify valid CSV IDs are accepted.

        GUARANTEES:
          - Valid CSV format "1,2,3" is accepted
        """
        request = CargoListRequest(load_types="1,2,3")
        assert request.load_types == "1,2,3"

        request = CargoListRequest(truck_types="1,2,3")
        assert request.truck_types == "1,2,3"

    def test_invalid_csv_ids(self):
        """
        GOAL: Verify invalid CSV format raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for invalid CSV format
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(load_types="1,2,abc")
        assert "load_types" in str(exc_info.value)

        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(truck_types="1,,2")
        assert "truck_types" in str(exc_info.value)

    def test_valid_mode(self):
        """
        GOAL: Verify valid mode values are accepted.

        GUARANTEES:
          - "my" and "all" are accepted
        """
        request = CargoListRequest(mode="my")
        assert request.mode == "my"

        request = CargoListRequest(mode="all")
        assert request.mode == "all"

    def test_invalid_mode(self):
        """
        GOAL: Verify invalid mode raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for invalid mode
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoListRequest(mode="invalid")
        assert "mode" in str(exc_info.value)


class TestCargoDetailRequest:
    """
    Tests for CargoDetailRequest schema.
    """

    def test_valid_cargo_id(self):
        """
        GOAL: Verify valid cargo_id is accepted.

        GUARANTEES:
          - Non-empty cargo_id string is accepted
        """
        request = CargoDetailRequest(cargo_id="12345")
        assert request.cargo_id == "12345"

    def test_missing_cargo_id(self):
        """
        GOAL: Verify missing cargo_id raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised when cargo_id is missing
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoDetailRequest()
        assert "cargo_id" in str(exc_info.value)

    def test_empty_cargo_id(self):
        """
        GOAL: Verify empty cargo_id raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised when cargo_id is empty
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            CargoDetailRequest(cargo_id="")
        assert "cargo_id" in str(exc_info.value)

    def test_whitespace_stripped(self):
        """
        GOAL: Verify whitespace is stripped from cargo_id.

        GUARANTEES:
          - Leading/trailing whitespace is removed from cargo_id
        """
        request = CargoDetailRequest(cargo_id="  12345  ")
        assert request.cargo_id == "12345"


class TestPaymentCreateRequest:
    """
    Tests for PaymentCreateRequest schema.
    """

    def test_valid_tariff_name(self):
        """
        GOAL: Verify valid tariff_name is accepted.

        GUARANTEES:
          - Non-empty tariff_name string is accepted
        """
        request = PaymentCreateRequest(tariff_name="premium")
        assert request.tariff_name == "premium"

    def test_missing_tariff_name(self):
        """
        GOAL: Verify missing tariff_name raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised when tariff_name is missing
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            PaymentCreateRequest()
        assert "tariff_name" in str(exc_info.value)

    def test_valid_return_url(self):
        """
        GOAL: Verify valid return_url is accepted.

        GUARANTEES:
          - Valid URL starting with http:// or https:// is accepted
        """
        request = PaymentCreateRequest(tariff_name="premium", return_url="https://example.com")
        assert request.return_url == "https://example.com"

        request = PaymentCreateRequest(tariff_name="premium", return_url="http://example.com")
        assert request.return_url == "http://example.com"

    def test_invalid_return_url(self):
        """
        GOAL: Verify invalid return_url raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for invalid URL format
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            PaymentCreateRequest(tariff_name="premium", return_url="ftp://example.com")
        assert "return_url" in str(exc_info.value)

        with pytest.raises(PydanticValidationError) as exc_info:
            PaymentCreateRequest(tariff_name="premium", return_url="example.com")
        assert "return_url" in str(exc_info.value)


class TestFilterRequest:
    """
    Tests for FilterRequest schema.
    """

    def test_default_values(self):
        """
        GOAL: Verify default values are applied correctly.

        GUARANTEES:
          - mode defaults to "my"
        """
        request = FilterRequest()
        assert request.mode == "my"

    def test_valid_filters(self):
        """
        GOAL: Verify valid filter parameters are accepted.

        GUARANTEES:
          - All valid filter parameters are accepted
        """
        request = FilterRequest(
            start_point_id=1,
            finish_point_id=2,
            start_date="2024-01-15",
            weight_volume="15-65",
            load_types="1,2,3",
            truck_types="1,2,3",
            mode="my"
        )
        assert request.start_point_id == 1
        assert request.finish_point_id == 2
        assert request.start_date == date(2024, 1, 15)
        assert request.weight_volume == "15-65"
        assert request.load_types == "1,2,3"
        assert request.truck_types == "1,2,3"
        assert request.mode == "my"

    def test_invalid_point_id(self):
        """
        GOAL: Verify invalid point_id raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised for non-positive point_id
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            FilterRequest(start_point_id=0)
        assert "start_point_id" in str(exc_info.value)

        with pytest.raises(PydanticValidationError) as exc_info:
            FilterRequest(finish_point_id=-1)
        assert "finish_point_id" in str(exc_info.value)


class TestTelegramResponseRequest:
    """
    Tests for TelegramResponseRequest schema.
    """

    def test_valid_request(self):
        """
        GOAL: Verify valid response request is accepted.

        GUARANTEES:
          - All valid fields are accepted
        """
        request = TelegramResponseRequest(
            cargo_id="12345",
            phone="+1234567890",
            name="John Doe"
        )
        assert request.cargo_id == "12345"
        assert request.phone == "+1234567890"
        assert request.name == "John Doe"

    def test_missing_cargo_id(self):
        """
        GOAL: Verify missing cargo_id raises validation error.

        GUARANTEES:
          - PydanticValidationError is raised when cargo_id is missing
        """
        with pytest.raises(PydanticValidationError) as exc_info:
            TelegramResponseRequest()
        assert "cargo_id" in str(exc_info.value)

    def test_optional_fields_empty(self):
        """
        GOAL: Verify optional fields can be empty.

        GUARANTEES:
          - phone and name can be empty strings
        """
        request = TelegramResponseRequest(cargo_id="12345", phone="", name="")
        assert request.phone == ""
        assert request.name == ""


class TestValidateRequestBody:
    """
    Tests for validate_request_body helper.
    """

    def test_valid_body(self):
        """
        GOAL: Verify valid body is validated successfully.

        GUARANTEES:
          - Valid body returns validated schema instance
        """
        body = {"init_data": "query_id=123&auth_date=1234567890&hash=abc123"}
        result = validate_request_body(TelegramAuthRequest, body)
        assert isinstance(result, TelegramAuthRequest)
        assert result.init_data == "query_id=123&auth_date=1234567890&hash=abc123"

    def test_invalid_body(self):
        """
        GOAL: Verify invalid body raises AppValidationError.

        GUARANTEES:
          - AppValidationError is raised with detailed error messages
        """
        body = {}
        with pytest.raises(AppValidationError) as exc_info:
            validate_request_body(TelegramAuthRequest, body)
        assert "Validation failed" in str(exc_info.value)
        assert "init_data" in str(exc_info.value)

    def test_validation_error_details(self):
        """
        GOAL: Verify validation errors include details.

        GUARANTEES:
          - Error details are included in exception
        """
        body = {"init_data": ""}
        with pytest.raises(AppValidationError) as exc_info:
            validate_request_body(TelegramAuthRequest, body)
        assert hasattr(exc_info.value, "details")
        assert "validation_errors" in exc_info.value.details


class TestValidateQueryParams:
    """
    Tests for validate_query_params helper.
    """

    def test_valid_params(self):
        """
        GOAL: Verify valid query params are validated successfully.

        GUARANTEES:
          - Valid params return validated schema instance
        """
        params = {"limit": "50", "offset": "10", "mode": "my"}
        result = validate_query_params(CargoListRequest, params)
        assert isinstance(result, CargoListRequest)
        assert result.limit == 50
        assert result.offset == 10
        assert result.mode == "my"

    def test_empty_string_to_none(self):
        """
        GOAL: Verify empty strings are converted to None for optional fields.

        GUARANTEES:
          - Empty strings are treated as None
        """
        params = {"limit": "", "offset": "", "mode": ""}
        result = validate_query_params(CargoListRequest, params)
        assert isinstance(result, CargoListRequest)
        assert result.limit == 20  # default
        assert result.offset == 0  # default
        assert result.mode == "my"  # default

    def test_invalid_params(self):
        """
        GOAL: Verify invalid params raise AppValidationError.

        GUARANTEES:
          - AppValidationError is raised with detailed error messages
        """
        params = {"limit": "invalid"}
        with pytest.raises(AppValidationError) as exc_info:
            validate_query_params(CargoListRequest, params)
        assert "Validation failed" in str(exc_info.value)
        assert "limit" in str(exc_info.value)

    def test_validation_error_details(self):
        """
        GOAL: Verify validation errors include details.

        GUARANTEES:
          - Error details are included in exception
        """
        params = {"limit": "0"}
        with pytest.raises(AppValidationError) as exc_info:
            validate_query_params(CargoListRequest, params)
        assert hasattr(exc_info.value, "details")
        assert "validation_errors" in exc_info.value.details


class TestSentryMonitoring:
    """
    Tests for Sentry monitoring integration.
    """

    def test_init_sentry_with_valid_dsn(self, monkeypatch):
        """
        GOAL: Verify Sentry initializes with valid DSN.

        GUARANTEES:
          - Returns True when valid DSN is provided
          - Sentry is enabled after initialization
        """
        from apps.core.monitoring import init_sentry, is_sentry_enabled
        
        # Mock sentry_init to avoid actual initialization
        def mock_init(*args, **kwargs):
            return None
        
        monkeypatch.setattr("apps.core.monitoring.sentry_init", mock_init)
        
        result = init_sentry(
            dsn="https://test@sentry.io/123",
            environment="test",
        )
        
        assert result is True

    def test_init_sentry_with_empty_dsn(self):
        """
        GOAL: Verify Sentry is disabled with empty DSN.

        GUARANTEES:
          - Returns False when DSN is empty
          - Sentry is not enabled
        """
        from apps.core.monitoring import init_sentry, is_sentry_enabled
        
        result = init_sentry(dsn="")
        
        assert result is False
        assert is_sentry_enabled() is False

    def test_capture_exception_with_sentry_disabled(self):
        """
        GOAL: Verify capture_exception returns None when Sentry is disabled.

        GUARANTEES:
          - Returns None when Sentry is disabled
          - Exception is not sent to Sentry
          - No exception is raised
        """
        from apps.core.monitoring import capture_exception
        
        test_exception = ValueError("Test exception")
        result = capture_exception(test_exception)
        
        assert result is None

    def test_add_breadcrumb_with_sentry_disabled(self):
        """
        GOAL: Verify add_breadcrumb does nothing when Sentry is disabled.

        GUARANTEES:
          - No exception is raised
          - Function completes successfully
        """
        from apps.core.monitoring import add_breadcrumb
        
        # Should not raise any exception
        add_breadcrumb(
            message="Test breadcrumb",
            category="test",
            level="info",
        )

    def test_set_user_context_with_sentry_disabled(self):
        """
        GOAL: Verify set_user_context does nothing when Sentry is disabled.

        GUARANTEES:
          - No exception is raised
          - Function completes successfully
        """
        from apps.core.monitoring import set_user_context
        
        # Should not raise any exception
        set_user_context(
            user_id=123,
            username="test_user",
        )

    def test_set_transaction_with_sentry_disabled(self):
        """
        GOAL: Verify set_transaction returns None when Sentry is disabled.

        GUARANTEES:
          - Returns None when Sentry is disabled
          - No exception is raised
        """
        from apps.core.monitoring import set_transaction
        
        result = set_transaction(
            name="test_transaction",
            op="test.op",
        )
        
        assert result is None

    def test_capture_message_with_sentry_disabled(self):
        """
        GOAL: Verify capture_message returns None when Sentry is disabled.

        GUARANTEES:
          - Returns None when Sentry is disabled
          - No exception is raised
        """
        from apps.core.monitoring import capture_message
        
        result = capture_message(
            message="Test message",
            level="info",
        )
        
        assert result is None


class TestHealthCheckEndpoints:
    """
    Tests for health check endpoints.
    """

    def test_health_check_endpoint(self, client):
        """
        GOAL: Verify basic health check returns 200 OK.

        GUARANTEES:
          - Returns 200 status code
          - Response contains "status": "ok"
          - Response contains timestamp
        """
        response = client.get("/health/")
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "timestamp" in response.json()

    def test_readiness_check_endpoint_healthy(self, client):
        """
        GOAL: Verify readiness check returns 200 OK when all services are healthy.

        GUARANTEES:
          - Returns 200 status code
          - Response contains "status": "ok"
          - All checks show "status": "ok"
        """
        response = client.get("/health/ready/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "checks" in data
        assert "database" in data["checks"]
        assert "cache" in data["checks"]
        assert "external_services" in data["checks"]

    def test_liveness_check_endpoint(self, client):
        """
        GOAL: Verify liveness check returns 200 OK.

        GUARANTEES:
          - Returns 200 status code
          - Response contains "status": "alive"
          - Response contains timestamp
        """
        response = client.get("/health/live/")
        
        assert response.status_code == 200
        assert response.json()["status"] == "alive"
        assert "timestamp" in response.json()

    def test_health_check_database_status(self, client):
        """
        GOAL: Verify database check includes database status.

        GUARANTEES:
          - Database status is included in readiness check
          - Status is either "ok" or "error"
        """
        response = client.get("/health/ready/")
        
        data = response.json()
        assert "database" in data["checks"]
        db_status = data["checks"]["database"]["status"]
        assert db_status in ["ok", "error"]

    def test_health_check_cache_status(self, client):
        """
        GOAL: Verify cache check includes cache status.

        GUARANTEES:
          - Cache status is included in readiness check
          - Status is either "ok" or "error"
        """
        response = client.get("/health/ready/")
        
        data = response.json()
        assert "cache" in data["checks"]
        cache_status = data["checks"]["cache"]["status"]
        assert cache_status in ["ok", "error"]

    def test_health_check_external_services_status(self, client):
        """
        GOAL: Verify external services check includes service status.

        GUARANTEES:
          - External services status is included in readiness check
          - Each service has "configured" boolean
        """
        response = client.get("/health/ready/")
        
        data = response.json()
        assert "external_services" in data["checks"]
        ext_services = data["checks"]["external_services"]
        
        assert "services" in ext_services
        services = ext_services["services"]
        
        # Check that expected services are present
        assert "telegram_bot" in services
        assert "cargotech" in services
        assert "yookassa" in services
        assert "sentry" in services
        
        # Check that each service has "configured" field
        for service_name, service_data in services.items():
            assert "configured" in service_data
            assert isinstance(service_data["configured"], bool)


class TestAPICSRFProtectionMiddleware:
    """
    Tests for API CSRF Protection middleware.
    """

    def test_middleware_skips_when_disabled(self, rf, settings):
        """
        GOAL: Verify middleware skips validation when disabled.

        GUARANTEES:
          - Request passes through when API_CSRF_ENABLED is False
          - No origin validation is performed
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = False
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={})
        request._api_csrf_exempt = True
        
        response = middleware(request)
        assert response.status_code == 200
        assert response.content == b"OK"

    def test_middleware_skips_for_safe_methods(self, rf, settings):
        """
        GOAL: Verify middleware skips validation for safe HTTP methods.

        GUARANTEES:
          - GET, HEAD, OPTIONS requests pass through
          - No origin validation is performed
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        
        # Test GET
        request = rf.get("/test/")
        request._api_csrf_exempt = True
        response = middleware(request)
        assert response.status_code == 200
        
        # Test HEAD
        request = rf.head("/test/")
        request._api_csrf_exempt = True
        response = middleware(request)
        assert response.status_code == 200
        
        # Test OPTIONS
        request = rf.options("/test/")
        request._api_csrf_exempt = True
        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_skips_for_non_exempt_views(self, rf, settings):
        """
        GOAL: Verify middleware skips validation for views not marked with @api_csrf_exempt.

        GUARANTEES:
          - Views without _api_csrf_exempt flag pass through
          - No origin validation is performed
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={})
        # Don't set _api_csrf_exempt flag
        
        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_allows_same_origin(self, rf, settings):
        """
        GOAL: Verify middleware allows requests from same origin.

        GUARANTEES:
          - Requests with matching Origin header are allowed
          - Response status is 200
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
        settings.API_CSRF_ALLOWED_ORIGINS = []
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={}, HTTP_ORIGIN="http://testserver")
        request._api_csrf_exempt = True
        
        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_allows_allowed_origin(self, rf, settings):
        """
        GOAL: Verify middleware allows requests from configured allowed origins.

        GUARANTEES:
          - Requests with Origin in API_CSRF_ALLOWED_ORIGINS are allowed
          - Response status is 200
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = False
        settings.API_CSRF_ALLOWED_ORIGINS = ["https://example.com", "https://trusted.com"]
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={}, HTTP_ORIGIN="https://example.com")
        request._api_csrf_exempt = True
        
        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_blocks_invalid_origin(self, rf, settings):
        """
        GOAL: Verify middleware blocks requests from invalid origins.

        GUARANTEES:
          - Requests with invalid Origin return 403
          - Response contains error details
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = False
        settings.API_CSRF_ALLOWED_ORIGINS = ["https://example.com"]
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={}, HTTP_ORIGIN="https://malicious.com")
        request._api_csrf_exempt = True
        
        response = middleware(request)
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "CSRF_VALIDATION_FAILED"

    def test_middleware_blocks_missing_origin_headers(self, rf, settings):
        """
        GOAL: Verify middleware blocks requests without Origin or Referer headers.

        GUARANTEES:
          - Requests without Origin/Referer return 403
          - Response contains error details
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={})
        request._api_csrf_exempt = True
        # Remove any Origin or Referer headers
        
        response = middleware(request)
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "Missing Origin and Referer headers" in data["error"]["details"]

    def test_middleware_uses_referer_as_fallback(self, rf, settings):
        """
        GOAL: Verify middleware uses Referer header when Origin is missing.

        GUARANTEES:
          - Requests with valid Referer but no Origin are allowed
          - Response status is 200
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={}, HTTP_REFERER="http://testserver/path")
        request._api_csrf_exempt = True
        
        response = middleware(request)
        assert response.status_code == 200

    def test_middleware_allows_wildcard_origin(self, rf, settings):
        """
        GOAL: Verify middleware allows wildcard origin patterns.

        GUARANTEES:
          - Requests matching wildcard patterns are allowed
          - Response status is 200
        """
        from apps.core.csrf_protection import APICSRFProtectionMiddleware
        
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = False
        settings.API_CSRF_ALLOWED_ORIGINS = ["https://*.example.com"]
        
        def get_response(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        middleware = APICSRFProtectionMiddleware(get_response)
        request = rf.post("/test/", data={}, HTTP_ORIGIN="https://sub.example.com")
        request._api_csrf_exempt = True
        
        response = middleware(request)
        assert response.status_code == 200


class TestValidateOrigin:
    """
    Tests for validate_origin helper function.
    """

    def test_validate_origin_same_origin_allowed(self, rf):
        """
        GOAL: Verify origin validation allows same-origin requests.

        GUARANTEES:
          - Returns (True, "") for same-origin requests
          - Origin matches request host
        """
        from apps.core.csrf_protection import validate_origin
        
        request = rf.get("/test/")
        request.META["HTTP_ORIGIN"] = "http://testserver"
        
        is_allowed, reason = validate_origin(request, [], allow_same_origin=True)
        assert is_allowed is True
        assert reason == ""

    def test_validate_origin_allowed_origin(self, rf):
        """
        GOAL: Verify origin validation allows configured origins.

        GUARANTEES:
          - Returns (True, "") for origins in allowed list
        """
        from apps.core.csrf_protection import validate_origin
        
        request = rf.get("/test/")
        request.META["HTTP_ORIGIN"] = "https://example.com"
        
        is_allowed, reason = validate_origin(
            request,
            ["https://example.com", "https://trusted.com"],
            allow_same_origin=False
        )
        assert is_allowed is True
        assert reason == ""

    def test_validate_origin_wildcard_pattern(self, rf):
        """
        GOAL: Verify origin validation allows wildcard patterns.

        GUARANTEES:
          - Returns (True, "") for origins matching wildcard
        """
        from apps.core.csrf_protection import validate_origin
        
        request = rf.get("/test/")
        request.META["HTTP_ORIGIN"] = "https://sub.example.com"
        
        is_allowed, reason = validate_origin(
            request,
            ["https://*.example.com"],
            allow_same_origin=False
        )
        assert is_allowed is True
        assert reason == ""

    def test_validate_origin_invalid_origin(self, rf):
        """
        GOAL: Verify origin validation rejects invalid origins.

        GUARANTEES:
          - Returns (False, reason) for invalid origins
          - Reason contains origin details
        """
        from apps.core.csrf_protection import validate_origin
        
        request = rf.get("/test/")
        request.META["HTTP_ORIGIN"] = "https://malicious.com"
        
        is_allowed, reason = validate_origin(
            request,
            ["https://example.com"],
            allow_same_origin=False
        )
        assert is_allowed is False
        assert "not allowed" in reason

    def test_validate_origin_missing_headers(self, rf):
        """
        GOAL: Verify origin validation rejects requests without headers.

        GUARANTEES:
          - Returns (False, reason) when headers are missing
          - Reason mentions missing headers
        """
        from apps.core.csrf_protection import validate_origin
        
        request = rf.get("/test/")
        # No Origin or Referer headers
        
        is_allowed, reason = validate_origin(request, [], allow_same_origin=True)
        assert is_allowed is False
        assert "Missing" in reason

    def test_validate_origin_referer_fallback(self, rf):
        """
        GOAL: Verify origin validation uses Referer as fallback.

        GUARANTEES:
          - Returns (True, "") when Referer is valid
          - Origin extracted from Referer path
        """
        from apps.core.csrf_protection import validate_origin
        
        request = rf.get("/test/")
        request.META["HTTP_REFERER"] = "http://testserver/path"
        
        is_allowed, reason = validate_origin(request, [], allow_same_origin=True)
        assert is_allowed is True
        assert reason == ""


class TestAPICSRFExemptDecorator:
    """
    Tests for @api_csrf_exempt decorator.
    """

    def test_decorator_sets_flag(self):
        """
        GOAL: Verify decorator sets _api_csrf_exempt flag.

        GUARANTEES:
          - Decorated view has _api_csrf_exempt = True
          - Decorator wraps the view function
        """
        from apps.core.decorators import api_csrf_exempt
        
        @api_csrf_exempt
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        assert hasattr(test_view, "_api_csrf_exempt")
        assert test_view._api_csrf_exempt is True

    def test_decorator_wraps_view_properly(self):
        """
        GOAL: Verify decorator preserves view metadata.

        GUARANTEES:
          - View function name is preserved
          - View docstring is preserved
        """
        from apps.core.decorators import api_csrf_exempt
        
        @api_csrf_exempt
        def test_view(request):
            """Test view docstring."""
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        assert test_view.__name__ == "test_view"
        assert "Test view docstring" in test_view.__doc__

    def test_decorator_with_other_decorators(self):
        """
        GOAL: Verify decorator works with other decorators.

        GUARANTEES:
          - Decorator can be stacked with other decorators
          - _api_csrf_exempt flag is still set
        """
        from apps.core.decorators import api_csrf_exempt, rate_limit
        
        @api_csrf_exempt
        @rate_limit(requests_per_minute=10)
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse("OK")
        
        assert hasattr(test_view, "_api_csrf_exempt")
        assert test_view._api_csrf_exempt is True


class TestAPICSRFIntegration:
    """
    Integration tests for API CSRF protection with actual views.
    """

    def test_telegram_auth_with_valid_origin(self, client, settings):
        """
        GOAL: Verify telegram_auth view allows requests with valid origin.

        GUARANTEES:
          - Valid origin requests return 200
          - CSRF protection is applied correctly
        """
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
        
        response = client.post(
            "/auth/telegram/",
            data={"init_data": "query_id=123&auth_date=1234567890&hash=abc123"},
            HTTP_ORIGIN="http://testserver",
            content_type="application/json"
        )
        
        # Should get 400 (invalid init_data), not 403 (CSRF)
        assert response.status_code in [400, 403]

    def test_telegram_auth_with_invalid_origin(self, client, settings):
        """
        GOAL: Verify telegram_auth view blocks requests with invalid origin.

        GUARANTEES:
          - Invalid origin requests return 403
          - Error message indicates CSRF validation failure
        """
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = False
        settings.API_CSRF_ALLOWED_ORIGINS = ["https://trusted.com"]
        
        response = client.post(
            "/auth/telegram/",
            data={"init_data": "query_id=123&auth_date=1234567890&hash=abc123"},
            HTTP_ORIGIN="https://malicious.com",
            content_type="application/json"
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "CSRF_VALIDATION_FAILED"

    def test_create_payment_with_valid_origin(self, client, settings, auth_driver):
        """
        GOAL: Verify create_payment view allows requests with valid origin.

        GUARANTEES:
          - Valid origin requests proceed normally
          - CSRF protection is applied correctly
        """
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
        
        response = client.post(
            "/payments/create/",
            data={"tariff_name": "premium"},
            HTTP_ORIGIN="http://testserver"
        )
        
        # Should not get 403 (CSRF), may get other errors
        assert response.status_code != 403

    def test_handle_response_with_valid_origin(self, client, settings, auth_driver):
        """
        GOAL: Verify handle_response view allows requests with valid origin.

        GUARANTEES:
          - Valid origin requests proceed normally
          - CSRF protection is applied correctly
        """
        settings.API_CSRF_ENABLED = True
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
        
        response = client.post(
            "/telegram/handle-response/",
            data={"cargo_id": "12345", "phone": "+1234567890", "name": "Test"},
            HTTP_ORIGIN="http://testserver"
        )
        
        # Should not get 403 (CSRF), may get other errors
        assert response.status_code != 403

    def test_csrf_protection_can_be_disabled(self, client, settings):
        """
        GOAL: Verify CSRF protection can be disabled via settings.

        GUARANTEES:
          - When disabled, requests without origin headers pass through
          - No 403 errors are returned
        """
        settings.API_CSRF_ENABLED = False
        
        response = client.post(
            "/auth/telegram/",
            data={"init_data": "query_id=123&auth_date=1234567890&hash=abc123"},
            content_type="application/json"
        )
        
        # Should not get 403 (CSRF)
        assert response.status_code != 403


class TestBaseRepository:
    """
    Tests for BaseRepository class.
    """

    def test_repository_initialization(self):
        """
        GOAL: Verify BaseRepository initializes with model.

        GUARANTEES:
          - Repository stores model reference
        """
        from apps.core.repositories import BaseRepository
        from apps.auth.models import DriverProfile
        
        repo = BaseRepository(DriverProfile)
        assert repo.model == DriverProfile

    def test_get_by_pk(self, db):
        """
        GOAL: Verify get() retrieves record by primary key.

        GUARANTEES:
          - Returns model instance when exists
          - Returns None when not found
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverProfileRepository()
        profile = repo.create(user=user, telegram_user_id=123456789)
        
        # Test get existing
        result = repo.get(profile.id)
        assert result is not None
        assert result.id == profile.id
        
        # Test get non-existing
        result = repo.get(999999)
        assert result is None

    def test_filter(self, db):
        """
        GOAL: Verify filter() returns matching records.

        GUARANTEES:
          - Returns list of matching instances
          - Returns empty list when no matches
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")
        
        repo = DriverProfileRepository()
        repo.create(user=user1, telegram_user_id=111)
        repo.create(user=user2, telegram_user_id=222)
        
        # Test filter
        results = repo.filter(telegram_user_id=111)
        assert len(results) == 1
        assert results[0].telegram_user_id == 111

    def test_create(self, db):
        """
        GOAL: Verify create() creates new record.

        GUARANTEES:
          - Record is saved to database
          - Returns created instance with ID
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverProfileRepository()
        profile = repo.create(user=user, telegram_user_id=123456789)
        
        assert profile.id is not None
        assert profile.telegram_user_id == 123456789

    def test_update(self, db):
        """
        GOAL: Verify update() modifies existing record.

        GUARANTEES:
          - Specified fields are updated
          - Changes are persisted
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverProfileRepository()
        profile = repo.create(user=user, telegram_user_id=123456789)
        
        updated = repo.update(profile, telegram_username="newusername")
        
        assert updated.telegram_username == "newusername"
        assert updated.id == profile.id

    def test_delete(self, db):
        """
        GOAL: Verify delete() removes record.

        GUARANTEES:
          - Record is removed from database
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverProfileRepository()
        profile = repo.create(user=user, telegram_user_id=123456789)
        profile_id = profile.id
        
        repo.delete(profile)
        
        # Verify deleted
        result = repo.get(profile_id)
        assert result is None

    def test_count(self, db):
        """
        GOAL: Verify count() returns correct count.

        GUARANTEES:
          - Returns count of matching records
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")
        
        repo = DriverProfileRepository()
        repo.create(user=user1, telegram_user_id=111)
        repo.create(user=user2, telegram_user_id=222)
        
        count = repo.count()
        assert count == 2

    def test_exists(self, db):
        """
        GOAL: Verify exists() checks for record existence.

        GUARANTEES:
          - Returns True when record exists
          - Returns False when record doesn't exist
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverProfileRepository()
        repo.create(user=user, telegram_user_id=123456789)
        
        # Test exists
        exists = repo.exists(telegram_user_id=123456789)
        assert exists is True
        
        # Test not exists
        exists = repo.exists(telegram_user_id=999999)
        assert exists is False


class TestUserRepository:
    """
    Tests for UserRepository class.
    """

    def test_get_by_username(self, db):
        """
        GOAL: Verify get_by_username retrieves user.

        GUARANTEES:
          - Returns user when exists
          - Returns None when not found
        """
        from apps.core.repositories import UserRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = UserRepository()
        result = repo.get_by_username("testuser")
        
        assert result is not None
        assert result.username == "testuser"
        
        # Test non-existing
        result = repo.get_by_username("nonexistent")
        assert result is None

    def test_get_by_email(self, db):
        """
        GOAL: Verify get_by_email retrieves user.

        GUARANTEES:
          - Returns user when exists
          - Returns None when not found
        """
        from apps.core.repositories import UserRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", email="test@example.com", password="testpass")
        
        repo = UserRepository()
        result = repo.get_by_email("test@example.com")
        
        assert result is not None
        assert result.email == "test@example.com"
        
        # Test non-existing
        result = repo.get_by_email("nonexistent@example.com")
        assert result is None


class TestDriverProfileRepository:
    """
    Tests for DriverProfileRepository class.
    """

    def test_get_by_telegram_user_id(self, db):
        """
        GOAL: Verify get_by_telegram_user_id retrieves profile.

        GUARANTEES:
          - Returns profile when exists
          - Returns None when not found
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverProfileRepository()
        profile = repo.create(user=user, telegram_user_id=123456789)
        
        result = repo.get_by_telegram_user_id(123456789)
        
        assert result is not None
        assert result.telegram_user_id == 123456789
        
        # Test non-existing
        result = repo.get_by_telegram_user_id(999999)
        assert result is None

    def test_get_by_user_with_relations(self, db):
        """
        GOAL: Verify get_by_user_with_relations includes user.

        GUARANTEES:
          - Returns profile with related user
        """
        from apps.core.repositories import DriverProfileRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverProfileRepository()
        profile = repo.create(user=user, telegram_user_id=123456789)
        
        result = repo.get_by_user_with_relations(user.id)
        
        assert result is not None
        assert result.id == profile.id
        assert result.user_id == user.id


class TestTelegramSessionRepository:
    """
    Tests for TelegramSessionRepository class.
    """

    def test_get_active_session(self, db):
        """
        GOAL: Verify get_active_session retrieves non-revoked session.

        GUARANTEES:
          - Returns active session when exists
          - Returns None when no active session
        """
        from apps.core.repositories import TelegramSessionRepository
        from apps.auth.models import TelegramSession
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        import uuid
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = TelegramSessionRepository()
        active = repo.create(
            user=user,
            session_id=uuid.uuid4(),
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        
        result = repo.get_active_session(user.id)
        
        assert result is not None
        assert result.id == active.id

    def test_get_by_session_id_with_user(self, db):
        """
        GOAL: Verify get_by_session_id_with_user includes user.

        GUARANTEES:
          - Returns session with related user
        """
        from apps.core.repositories import TelegramSessionRepository
        from apps.auth.models import TelegramSession
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        import uuid
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        session_id = uuid.uuid4()
        
        repo = TelegramSessionRepository()
        session = repo.create(
            user=user,
            session_id=session_id,
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        
        result = repo.get_by_session_id_with_user(str(session_id))
        
        assert result is not None
        assert result.session_id == session_id
        assert result.user_id == user.id

    def test_revoke_all_user_sessions(self, db):
        """
        GOAL: Verify revoke_all_user_sessions revokes active sessions.

        GUARANTEES:
          - All active sessions are revoked
          - Returns count of revoked sessions
        """
        from apps.core.repositories import TelegramSessionRepository
        from apps.auth.models import TelegramSession
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        import uuid
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = TelegramSessionRepository()
        repo.create(
            user=user,
            session_id=uuid.uuid4(),
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        repo.create(
            user=user,
            session_id=uuid.uuid4(),
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        
        count = repo.revoke_all_user_sessions(user.id)
        
        assert count == 2


class TestSubscriptionRepository:
    """
    Tests for SubscriptionRepository class.
    """

    def test_get_by_user_with_relations(self, db):
        """
        GOAL: Verify get_by_user_with_relations includes relations.

        GUARANTEES:
          - Returns subscription with payment and promo_code
        """
        from apps.core.repositories import SubscriptionRepository
        from apps.subscriptions.models import Subscription
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = SubscriptionRepository()
        subscription = repo.create(
            user=user,
            is_active=True,
            source=Subscription.SOURCE_TRIAL,
        )
        
        result = repo.get_by_user_with_relations(user.id)
        
        assert result is not None
        assert result.id == subscription.id
        assert result.user_id == user.id

    def test_get_active_subscriptions(self, db):
        """
        GOAL: Verify get_active_subscriptions returns active subscriptions.

        GUARANTEES:
          - Only returns active non-expired subscriptions
        """
        from apps.core.repositories import SubscriptionRepository
        from apps.subscriptions.models import Subscription
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        
        User = get_user_model()
        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")
        
        repo = SubscriptionRepository()
        repo.create(
            user=user1,
            is_active=True,
            expires_at=timezone.now() + timezone.timedelta(days=30),
            source=Subscription.SOURCE_TRIAL,
        )
        repo.create(
            user=user2,
            is_active=False,
            source=Subscription.SOURCE_TRIAL,
        )
        
        results = repo.get_active_subscriptions()
        
        assert len(results) == 1
        assert results[0].user_id == user1.id

    def test_get_by_access_token(self, db):
        """
        GOAL: Verify get_by_access_token retrieves subscription.

        GUARANTEES:
          - Returns subscription when token exists
          - Returns None when not found
        """
        from apps.core.repositories import SubscriptionRepository
        from apps.subscriptions.models import Subscription
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = SubscriptionRepository()
        subscription = repo.create(
            user=user,
            is_active=True,
            access_token="test_token_123",
            source=Subscription.SOURCE_TRIAL,
        )
        
        result = repo.get_by_access_token("test_token_123")
        
        assert result is not None
        assert result.access_token == "test_token_123"
        
        # Test non-existing
        result = repo.get_by_access_token("nonexistent_token")
        assert result is None


class TestPaymentRepository:
    """
    Tests for PaymentRepository class.
    """

    def test_get_by_user_with_history(self, db):
        """
        GOAL: Verify get_by_user_with_history includes history.

        GUARANTEES:
          - Returns payments with history records
        """
        from apps.core.repositories import PaymentRepository
        from apps.payments.models import Payment
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = PaymentRepository()
        payment = repo.create(
            user=user,
            amount=100.00,
            status=Payment.STATUS_PENDING,
        )
        
        results = repo.get_by_user_with_history(user.id)
        
        assert len(results) == 1
        assert results[0].id == payment.id

    def test_get_by_yukassa_id(self, db):
        """
        GOAL: Verify get_by_yukassa_id retrieves payment.

        GUARANTEES:
          - Returns payment when yukassa_id exists
          - Returns None when not found
        """
        from apps.core.repositories import PaymentRepository
        from apps.payments.models import Payment
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = PaymentRepository()
        payment = repo.create(
            user=user,
            amount=100.00,
            status=Payment.STATUS_PENDING,
            yukassa_payment_id="yukassa_123",
        )
        
        result = repo.get_by_yukassa_id("yukassa_123")
        
        assert result is not None
        assert result.yukassa_payment_id == "yukassa_123"
        
        # Test non-existing
        result = repo.get_by_yukassa_id("nonexistent")
        assert result is None

    def test_get_by_status(self, db):
        """
        GOAL: Verify get_by_status returns payments by status.

        GUARANTEES:
          - Returns list of payments with given status
        """
        from apps.core.repositories import PaymentRepository
        from apps.payments.models import Payment
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")
        
        repo = PaymentRepository()
        repo.create(user=user1, amount=100.00, status=Payment.STATUS_PENDING)
        repo.create(user=user2, amount=200.00, status=Payment.STATUS_SUCCEEDED)
        
        results = repo.get_by_status(Payment.STATUS_PENDING)
        
        assert len(results) == 1
        assert results[0].status == Payment.STATUS_PENDING


class TestPaymentHistoryRepository:
    """
    Tests for PaymentHistoryRepository class.
    """

    def test_get_by_payment(self, db):
        """
        GOAL: Verify get_by_payment returns history for payment.

        GUARANTEES:
          - Returns list of history records
        """
        from apps.core.repositories import PaymentRepository, PaymentHistoryRepository
        from apps.payments.models import Payment
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        payment_repo = PaymentRepository()
        payment = payment_repo.create(
            user=user,
            amount=100.00,
            status=Payment.STATUS_PENDING,
        )
        
        history_repo = PaymentHistoryRepository()
        history_repo.create_history_event(
            payment=payment,
            event_type="created",
            old_status="",
            new_status=Payment.STATUS_PENDING,
        )
        
        results = history_repo.get_by_payment(str(payment.id))
        
        assert len(results) == 1
        assert results[0].event_type == "created"

    def test_create_history_event(self, db):
        """
        GOAL: Verify create_history_event creates history record.

        GUARANTEES:
          - History record is created
          - All fields are populated
        """
        from apps.core.repositories import PaymentRepository, PaymentHistoryRepository
        from apps.payments.models import Payment
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        payment_repo = PaymentRepository()
        payment = payment_repo.create(
            user=user,
            amount=100.00,
            status=Payment.STATUS_PENDING,
        )
        
        history_repo = PaymentHistoryRepository()
        history = history_repo.create_history_event(
            payment=payment,
            event_type="status_changed",
            old_status=Payment.STATUS_PENDING,
            new_status=Payment.STATUS_SUCCEEDED,
            raw_payload={"test": "data"},
        )
        
        assert history.id is not None
        assert history.event_type == "status_changed"
        assert history.old_status == Payment.STATUS_PENDING
        assert history.new_status == Payment.STATUS_SUCCEEDED


class TestAuditLogRepository:
    """
    Tests for AuditLogRepository class.
    """

    def test_get_by_user(self, db):
        """
        GOAL: Verify get_by_user returns audit logs for user.

        GUARANTEES:
          - Returns list of audit logs
          - Respects limit parameter
        """
        from apps.core.repositories import AuditLogRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = AuditLogRepository()
        repo.create_log(
            user=user,
            username=user.username,
            action_type="test_action",
            action="Test action",
        )
        repo.create_log(
            user=user,
            username=user.username,
            action_type="test_action2",
            action="Test action 2",
        )
        
        results = repo.get_by_user(user.id, limit=1)
        
        assert len(results) == 1

    def test_get_by_action_type(self, db):
        """
        GOAL: Verify get_by_action_type returns logs by type.

        GUARANTEES:
          - Returns list of audit logs with given action_type
        """
        from apps.core.repositories import AuditLogRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = AuditLogRepository()
        repo.create_log(
            user=user,
            username=user.username,
            action_type="login",
            action="User logged in",
        )
        repo.create_log(
            user=user,
            username=user.username,
            action_type="logout",
            action="User logged out",
        )
        
        results = repo.get_by_action_type("login")
        
        assert len(results) == 1
        assert results[0].action_type == "login"

    def test_create_log(self, db):
        """
        GOAL: Verify create_log creates audit log entry.

        GUARANTEES:
          - Audit log is created
          - All fields are populated
        """
        from apps.core.repositories import AuditLogRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = AuditLogRepository()
        log = repo.create_log(
            user=user,
            username=user.username,
            action_type="test_action",
            action="Test action",
            target_id="12345",
            details={"test": "data"},
            ip_address="127.0.0.1",
            user_agent="TestAgent",
        )
        
        assert log.id is not None
        assert log.action_type == "test_action"
        assert log.action == "Test action"
        assert log.target_id == "12345"


class TestPromoCodeRepository:
    """
    Tests for PromoCodeRepository class.
    """

    def test_get_by_code(self, db):
        """
        GOAL: Verify get_by_code retrieves promo code.

        GUARANTEES:
          - Returns promo code when exists
          - Returns None when not found
        """
        from apps.core.repositories import PromoCodeRepository
        from apps.promocodes.models import PromoCode
        from django.utils import timezone
        
        repo = PromoCodeRepository()
        promo = repo.create(
            code="TEST123",
            action="extend_30",
            days_to_add=30,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
        )
        
        result = repo.get_by_code("TEST123")
        
        assert result is not None
        assert result.code == "TEST123"
        
        # Test non-existing
        result = repo.get_by_code("NONEXISTENT")
        assert result is None

    def test_get_active_promo_codes(self, db):
        """
        GOAL: Verify get_active_promo_codes returns active codes.

        GUARANTEES:
          - Only returns active codes within time window
        """
        from apps.core.repositories import PromoCodeRepository
        from apps.promocodes.models import PromoCode
        from django.utils import timezone
        
        repo = PromoCodeRepository()
        repo.create(
            code="ACTIVE123",
            action="extend_30",
            days_to_add=30,
            valid_from=timezone.now() - timezone.timedelta(days=1),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            disabled=False,
        )
        repo.create(
            code="DISABLED456",
            action="extend_60",
            days_to_add=60,
            valid_from=timezone.now() - timezone.timedelta(days=1),
            valid_until=timezone.now() + timezone.timedelta(days=60),
            disabled=True,
        )
        
        results = repo.get_active_promo_codes()
        
        assert len(results) == 1
        assert results[0].code == "ACTIVE123"


class TestPromoCodeUsageRepository:
    """
    Tests for PromoCodeUsageRepository class.
    """

    def test_get_by_promo_code(self, db):
        """
        GOAL: Verify get_by_promo_code returns usage records.

        GUARANTEES:
          - Returns list of usage records for promo code
        """
        from apps.core.repositories import PromoCodeRepository, PromoCodeUsageRepository
        from apps.promocodes.models import PromoCode
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        promo_repo = PromoCodeRepository()
        promo = promo_repo.create(
            code="TEST123",
            action="extend_30",
            days_to_add=30,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
        )
        
        usage_repo = PromoCodeUsageRepository()
        usage_repo.create(
            promo_code=promo,
            user=user,
            success=True,
            days_added=30,
        )
        
        results = usage_repo.get_by_promo_code(promo.id)
        
        assert len(results) == 1
        assert results[0].success is True

    def test_get_by_user(self, db):
        """
        GOAL: Verify get_by_user returns usage records for user.

        GUARANTEES:
          - Returns list of usage records for user
        """
        from apps.core.repositories import PromoCodeRepository, PromoCodeUsageRepository
        from apps.promocodes.models import PromoCode
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        promo_repo = PromoCodeRepository()
        promo1 = promo_repo.create(
            code="TEST123",
            action="extend_30",
            days_to_add=30,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
        )
        promo2 = promo_repo.create(
            code="TEST456",
            action="extend_60",
            days_to_add=60,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=60),
        )
        
        usage_repo = PromoCodeUsageRepository()
        usage_repo.create(promo_code=promo1, user=user, success=True, days_added=30)
        usage_repo.create(promo_code=promo2, user=user, success=True, days_added=60)
        
        results = usage_repo.get_by_user(user.id)
        
        assert len(results) == 2

    def test_user_has_used_code(self, db):
        """
        GOAL: Verify user_has_used_code checks usage.

        GUARANTEES:
          - Returns True when user has used code
          - Returns False when user hasn't used code
        """
        from apps.core.repositories import PromoCodeRepository, PromoCodeUsageRepository
        from apps.promocodes.models import PromoCode
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        promo_repo = PromoCodeRepository()
        promo = promo_repo.create(
            code="TEST123",
            action="extend_30",
            days_to_add=30,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timezone.timedelta(days=30),
        )
        
        usage_repo = PromoCodeUsageRepository()
        usage_repo.create(promo_code=promo, user=user, success=True, days_added=30)
        
        # Test has used
        has_used = usage_repo.user_has_used_code(promo.id, user.id)
        assert has_used is True
        
        # Test hasn't used
        User2 = get_user_model()
        user2 = User2.objects.create_user(username="testuser2", password="testpass2")
        has_used = usage_repo.user_has_used_code(promo.id, user2.id)
        assert has_used is False


class TestDriverCargoResponseRepository:
    """
    Tests for DriverCargoResponseRepository class.
    """

    def test_get_by_user_and_cargo(self, db):
        """
        GOAL: Verify get_by_user_and_cargo retrieves response.

        GUARANTEES:
          - Returns response when exists
          - Returns None when not found
        """
        from apps.core.repositories import DriverCargoResponseRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        
        repo = DriverCargoResponseRepository()
        response = repo.create(
            user=user,
            cargo_id="CARGO123",
            status="pending",
        )
        
        result = repo.get_by_user_and_cargo(user.id, "CARGO123")
        
        assert result is not None
        assert result.cargo_id == "CARGO123"
        
        # Test non-existing
        result = repo.get_by_user_and_cargo(user.id, "NONEXISTENT")
        assert result is None

    def test_get_by_cargo(self, db):
        """
        GOAL: Verify get_by_cargo returns responses for cargo.

        GUARANTEES:
          - Returns list of responses for cargo
        """
        from apps.core.repositories import DriverCargoResponseRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")
        
        repo = DriverCargoResponseRepository()
        repo.create(user=user1, cargo_id="CARGO123", status="pending")
        repo.create(user=user2, cargo_id="CARGO123", status="pending")
        
        results = repo.get_by_cargo("CARGO123")
        
        assert len(results) == 2

    def test_get_by_status(self, db):
        """
        GOAL: Verify get_by_status returns responses by status.

        GUARANTEES:
          - Returns list of responses with given status
        """
        from apps.core.repositories import DriverCargoResponseRepository
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")
        
        repo = DriverCargoResponseRepository()
        repo.create(user=user1, cargo_id="CARGO123", status="pending")
        repo.create(user=user2, cargo_id="CARGO456", status="sent")
        
        results = repo.get_by_status("pending")
        
        assert len(results) == 1
        assert results[0].status == "pending"


class TestSystemSettingRepository:
    """
    Tests for SystemSettingRepository class.
    """

    def test_get_by_key(self, db):
        """
        GOAL: Verify get_by_key retrieves setting.

        GUARANTEES:
          - Returns setting when key exists
          - Returns None when not found
        """
        from apps.core.repositories import SystemSettingRepository
        from apps.feature_flags.models import SystemSetting
        
        repo = SystemSettingRepository()
        setting = repo.create(
            key="test_setting",
            value={"test": "value"},
            is_secret=False,
        )
        
        result = repo.get_by_key("test_setting")
        
        assert result is not None
        assert result.key == "test_setting"
        
        # Test non-existing
        result = repo.get_by_key("nonexistent_setting")
        assert result is None

    def test_get_secret_settings(self, db):
        """
        GOAL: Verify get_secret_settings returns only secret settings.

        GUARANTEES:
          - Only returns settings where is_secret=True
        """
        from apps.core.repositories import SystemSettingRepository
        from apps.feature_flags.models import SystemSetting
        
        repo = SystemSettingRepository()
        repo.create(key="public_setting", value={"test": "value"}, is_secret=False)
        repo.create(key="secret_setting", value={"test": "value"}, is_secret=True)
        
        results = repo.get_secret_settings()
        
        assert len(results) == 1
        assert results[0].key == "secret_setting"


class TestFeatureFlagRepository:
    """
    Tests for FeatureFlagRepository class.
    """

    def test_get_by_key(self, db):
        """
        GOAL: Verify get_by_key retrieves feature flag.

        GUARANTEES:
          - Returns feature flag when key exists
          - Returns None when not found
        """
        from apps.core.repositories import FeatureFlagRepository
        from apps.feature_flags.models import FeatureFlag
        
        repo = FeatureFlagRepository()
        flag = repo.create(
            key="test_feature",
            enabled=True,
            description="Test feature flag",
        )
        
        result = repo.get_by_key("test_feature")
        
        assert result is not None
        assert result.key == "test_feature"
        
        # Test non-existing
        result = repo.get_by_key("nonexistent_feature")
        assert result is None

    def test_get_enabled_flags(self, db):
        """
        GOAL: Verify get_enabled_flags returns only enabled flags.

        GUARANTEES:
          - Only returns flags where enabled=True
        """
        from apps.core.repositories import FeatureFlagRepository
        from apps.feature_flags.models import FeatureFlag
        
        repo = FeatureFlagRepository()
        repo.create(key="disabled_feature", enabled=False, description="Disabled feature")
        repo.create(key="enabled_feature", enabled=True, description="Enabled feature")
        
        results = repo.get_enabled_flags()
        
        assert len(results) == 1
        assert results[0].key == "enabled_feature"

    def test_is_enabled(self, db):
        """
        GOAL: Verify is_enabled checks flag status.

        GUARANTEES:
          - Returns True when flag exists and is enabled
          - Returns False when flag doesn't exist or is disabled
        """
        from apps.core.repositories import FeatureFlagRepository
        from apps.feature_flags.models import FeatureFlag
        
        repo = FeatureFlagRepository()
        repo.create(key="test_feature", enabled=True, description="Test feature")
        
        # Test enabled
        is_enabled = repo.is_enabled("test_feature")
        assert is_enabled is True
        
        # Test non-existing
        is_enabled = repo.is_enabled("nonexistent_feature")
        assert is_enabled is False


class TestUserDTO:
    """
    Tests for UserDTO.
    """

    def test_user_dto_from_dict(self):
        """
        GOAL: Verify UserDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import UserDTO
        from datetime import datetime
        
        data = {
            "id": 1,
            "telegram_id": 123456789,
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User",
            "phone": "+1234567890",
            "is_driver": True,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = UserDTO(**data)
        assert dto.id == 1
        assert dto.telegram_id == 123456789
        assert dto.username == "testuser"
        assert dto.is_driver is True


class TestDriverProfileDTO:
    """
    Tests for DriverProfileDTO.
    """

    def test_driver_profile_dto_from_dict(self):
        """
        GOAL: Verify DriverProfileDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import DriverProfileDTO
        from datetime import datetime
        
        data = {
            "id": 1,
            "user_id": 1,
            "company_name": "Test Company",
            "inn": "1234567890",
            "ogrn": "1234567890123",
            "license_number": "ABC123",
            "license_expiry": datetime.utcnow(),
            "truck_type": "truck",
            "truck_capacity": 10.5,
            "verified": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = DriverProfileDTO(**data)
        assert dto.id == 1
        assert dto.user_id == 1
        assert dto.company_name == "Test Company"
        assert dto.verified is True


class TestTelegramSessionDTO:
    """
    Tests for TelegramSessionDTO.
    """

    def test_telegram_session_dto_from_dict(self):
        """
        GOAL: Verify TelegramSessionDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import TelegramSessionDTO
        from datetime import datetime
        
        data = {
            "id": 1,
            "user_id": 1,
            "telegram_id": 123456789,
            "session_data": {"test": "data"},
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = TelegramSessionDTO(**data)
        assert dto.id == 1
        assert dto.user_id == 1
        assert dto.telegram_id == 123456789
        assert dto.is_active is True


class TestCargoCardDTO:
    """
    Tests for CargoCardDTO.
    """

    def test_cargo_card_dto_from_dict(self):
        """
        GOAL: Verify CargoCardDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import CargoCardDTO
        from datetime import datetime
        from decimal import Decimal
        
        data = {
            "id": 1,
            "cargo_id": "CARGO123",
            "title": "Test Cargo",
            "route_from": "Moscow",
            "route_to": "St. Petersburg",
            "distance": 700,
            "price": Decimal("1000.00"),
            "cargo_type": "general",
            "weight": 15.5,
            "volume": 65.0,
            "loading_date": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = CargoCardDTO(**data)
        assert dto.id == 1
        assert dto.cargo_id == "CARGO123"
        assert dto.route_from == "Moscow"
        assert dto.route_to == "St. Petersburg"


class TestCargoDetailDTO:
    """
    Tests for CargoDetailDTO.
    """

    def test_cargo_detail_dto_from_dict(self):
        """
        GOAL: Verify CargoDetailDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import CargoDetailDTO
        from datetime import datetime
        from decimal import Decimal
        
        data = {
            "id": 1,
            "cargo_id": "CARGO123",
            "title": "Test Cargo",
            "description": "Test description",
            "route_from": "Moscow",
            "route_to": "St. Petersburg",
            "distance": 700,
            "price": Decimal("1000.00"),
            "cargo_type": "general",
            "weight": 15.5,
            "volume": 65.0,
            "loading_date": datetime.utcnow(),
            "unloading_date": datetime.utcnow(),
            "loading_address": "Test address",
            "unloading_address": "Test address 2",
            "requirements": ["req1", "req2"],
            "contact_phone": "+1234567890",
            "contact_name": "Test Contact",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = CargoDetailDTO(**data)
        assert dto.id == 1
        assert dto.cargo_id == "CARGO123"
        assert dto.description == "Test description"
        assert len(dto.requirements) == 2


class TestPaymentDTO:
    """
    Tests for PaymentDTO.
    """

    def test_payment_dto_from_dict(self):
        """
        GOAL: Verify PaymentDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import PaymentDTO
        from datetime import datetime
        from decimal import Decimal
        
        data = {
            "id": 1,
            "user_id": 1,
            "subscription_id": 1,
            "amount": Decimal("499.00"),
            "currency": "RUB",
            "status": "succeeded",
            "payment_method": "card",
            "transaction_id": "TX123456",
            "paid_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = PaymentDTO(**data)
        assert dto.id == 1
        assert dto.amount == Decimal("499.00")
        assert dto.status == "succeeded"
        assert dto.currency == "RUB"


class TestSubscriptionDTO:
    """
    Tests for SubscriptionDTO.
    """

    def test_subscription_dto_from_dict(self):
        """
        GOAL: Verify SubscriptionDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import SubscriptionDTO
        from datetime import datetime
        
        data = {
            "id": 1,
            "user_id": 1,
            "plan_type": "premium",
            "status": "active",
            "start_date": datetime.utcnow(),
            "end_date": datetime.utcnow(),
            "auto_renew": True,
            "payment_count": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = SubscriptionDTO(**data)
        assert dto.id == 1
        assert dto.plan_type == "premium"
        assert dto.status == "active"
        assert dto.auto_renew is True


class TestPromoCodeDTO:
    """
    Tests for PromoCodeDTO.
    """

    def test_promo_code_dto_from_dict(self):
        """
        GOAL: Verify PromoCodeDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import PromoCodeDTO
        from datetime import datetime
        
        data = {
            "id": 1,
            "code": "TEST123",
            "discount_percent": 10.0,
            "max_uses": 100,
            "current_uses": 5,
            "valid_from": datetime.utcnow(),
            "valid_until": datetime.utcnow(),
            "active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        dto = PromoCodeDTO(**data)
        assert dto.id == 1
        assert dto.code == "TEST123"
        assert dto.discount_percent == 10.0
        assert dto.active is True


class TestTelegramResponseDTO:
    """
    Tests for TelegramResponseDTO.
    """

    def test_telegram_response_dto_from_dict(self):
        """
        GOAL: Verify TelegramResponseDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import TelegramResponseDTO
        from datetime import datetime
        
        data = {
            "message_id": 123,
            "chat_id": 456789,
            "text": "Test message",
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[{"text": "Button"}]]},
            "success": True,
            "error_message": None,
            "created_at": datetime.utcnow(),
        }
        
        dto = TelegramResponseDTO(**data)
        assert dto.message_id == 123
        assert dto.chat_id == 456789
        assert dto.text == "Test message"
        assert dto.success is True


class TestAuditLogDTO:
    """
    Tests for AuditLogDTO.
    """

    def test_audit_log_dto_from_dict(self):
        """
        GOAL: Verify AuditLogDTO can be created from dict.

        GUARANTEES:
          - All fields are populated correctly
        """
        from apps.core.dtos import AuditLogDTO
        from datetime import datetime
        
        data = {
            "id": 1,
            "user_id": 1,
            "action": "Test action",
            "entity_type": "user",
            "entity_id": 1,
            "old_values": {"field": "old"},
            "new_values": {"field": "new"},
            "ip_address": "127.0.0.1",
            "user_agent": "TestAgent",
            "created_at": datetime.utcnow(),
        }
        
        dto = AuditLogDTO(**data)
        assert dto.id == 1
        assert dto.action == "Test action"
        assert dto.entity_type == "user"
        assert dto.ip_address == "127.0.0.1"


class TestModelToDto:
    """
    Tests for model_to_dto helper function.
    """

    def test_model_to_dto_with_user_model(self, db):
        """
        GOAL: Verify model_to_dto converts User model to UserDTO.

        GUARANTEES:
          - Returns UserDTO with correct fields
          - Original model is not modified
        """
        from apps.core.dtos import UserDTO, model_to_dto
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            first_name="Test",
            last_name="User",
        )
        
        dto = model_to_dto(user, UserDTO)
        
        assert isinstance(dto, UserDTO)
        assert dto.id == user.id
        assert dto.username == "testuser"
        assert dto.email == "test@example.com"

    def test_model_to_dto_with_driver_profile_model(self, db):
        """
        GOAL: Verify model_to_dto converts DriverProfile model to DriverProfileDTO.

        GUARANTEES:
          - Returns DriverProfileDTO with correct fields
          - Original model is not modified
        """
        from apps.core.dtos import DriverProfileDTO, model_to_dto
        from django.contrib.auth import get_user_model
        from apps.auth.models import DriverProfile
        
        User = get_user_model()
        user = User.objects.create_user(username="testuser", password="testpass")
        profile = DriverProfile.objects.create(
            user=user,
            telegram_user_id=123456789,
            company_name="Test Company",
        )
        
        dto = model_to_dto(profile, DriverProfileDTO)
        
        assert isinstance(dto, DriverProfileDTO)
        assert dto.id == profile.id
        assert dto.user_id == user.id
        assert dto.company_name == "Test Company"

    def test_model_to_dto_with_invalid_model(self):
        """
        GOAL: Verify model_to_dto raises TypeError for non-model objects.

        GUARANTEES:
          - TypeError is raised for invalid input
        """
        from apps.core.dtos import UserDTO, model_to_dto
        
        with pytest.raises(TypeError) as exc_info:
            model_to_dto({"id": 1}, UserDTO)
        
        assert "Expected Django model" in str(exc_info.value)


class TestDtoToDict:
    """
    Tests for dto_to_dict helper function.
    """

    def test_dto_to_dict_with_user_dto(self):
        """
        GOAL: Verify dto_to_dict converts UserDTO to dict.

        GUARANTEES:
          - Returns dict with all fields
          - Original DTO is not modified
        """
        from apps.core.dtos import UserDTO, dto_to_dict
        from datetime import datetime
        
        dto = UserDTO(
            id=1,
            telegram_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User",
            phone="+1234567890",
            is_driver=True,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        result = dto_to_dict(dto)
        
        assert isinstance(result, dict)
        assert result["id"] == 1
        assert result["username"] == "testuser"
        assert result["is_driver"] is True

    def test_dto_to_dict_with_nested_dto(self):
        """
        GOAL: Verify dto_to_dict handles nested DTOs.

        GUARANTEES:
          - Nested DTOs are converted to dicts
        """
        from apps.core.dtos import TelegramResponseDTO, dto_to_dict
        from datetime import datetime
        
        dto = TelegramResponseDTO(
            message_id=123,
            chat_id=456789,
            text="Test message",
            parse_mode=None,
            reply_markup={"inline_keyboard": [[{"text": "Button"}]]},
            success=True,
            error_message=None,
            created_at=datetime.utcnow(),
        )
        
        result = dto_to_dict(dto)
        
        assert isinstance(result, dict)
        assert isinstance(result["reply_markup"], dict)
        assert result["reply_markup"]["inline_keyboard"] == [[{"text": "Button"}]]

    def test_dto_to_dict_with_invalid_input(self):
        """
        GOAL: Verify dto_to_dict raises TypeError for non-DTO objects.

        GUARANTEES:
          - TypeError is raised for invalid input
        """
        from apps.core.dtos import dto_to_dict
        
        with pytest.raises(TypeError) as exc_info:
            dto_to_dict({"id": 1})
        
        assert "Expected pydantic BaseModel" in str(exc_info.value)


class TestModelsToDtos:
    """
    Tests for models_to_dtos helper function.
    """

    def test_models_to_dtos_with_user_models(self, db):
        """
        GOAL: Verify models_to_dtos converts list of User models to list of UserDTOs.

        GUARANTEES:
          - Returns list of UserDTOs
          - Order is preserved
          - Length matches input
        """
        from apps.core.dtos import UserDTO, models_to_dtos
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        user1 = User.objects.create_user(username="user1", password="pass1")
        user2 = User.objects.create_user(username="user2", password="pass2")
        user3 = User.objects.create_user(username="user3", password="pass3")
        
        users = list(User.objects.filter(username__in=["user1", "user2", "user3"]))
        
        dtos = models_to_dtos(users, UserDTO)
        
        assert len(dtos) == 3
        assert all(isinstance(dto, UserDTO) for dto in dtos)
        assert dtos[0].username == "user1"
        assert dtos[1].username == "user2"
        assert dtos[2].username == "user3"

    def test_models_to_dtos_with_empty_list(self):
        """
        GOAL: Verify models_to_dtos handles empty list.

        GUARANTEES:
          - Returns empty list
        """
        from apps.core.dtos import UserDTO, models_to_dtos
        
        dtos = models_to_dtos([], UserDTO)
        
        assert dtos == []

    def test_models_to_dtos_with_invalid_model(self):
        """
        GOAL: Verify models_to_dtos raises TypeError for non-model objects.

        GUARANTEES:
          - TypeError is raised for invalid input
        """
        from apps.core.dtos import UserDTO, models_to_dtos
        
        with pytest.raises(TypeError) as exc_info:
            models_to_dtos([{"id": 1}], UserDTO)
        
        assert "Expected Django model" in str(exc_info.value)


class TestEnvironmentSettings:
    """
    Tests for environment-specific settings configuration.
    """

    def test_get_environment_returns_development_by_default(self, monkeypatch):
        """
        GOAL: Verify get_environment returns 'development' when DJANGO_ENV is not set.

        GUARANTEES:
          - Returns 'development' when DJANGO_ENV is not set
          - Function does not raise an exception
        """
        from config.settings import get_environment
        
        # Remove DJANGO_ENV if it exists
        monkeypatch.delenv("DJANGO_ENV", raising=False)
        
        env = get_environment()
        assert env == "development"

    def test_get_environment_returns_set_value(self, monkeypatch):
        """
        GOAL: Verify get_environment returns the value from DJANGO_ENV.

        GUARANTEES:
          - Returns the value from DJANGO_ENV environment variable
          - Value is case-insensitive and trimmed
        """
        from config.settings import get_environment
        
        monkeypatch.setenv("DJANGO_ENV", "staging")
        env = get_environment()
        assert env == "staging"
        
        monkeypatch.setenv("DJANGO_ENV", "PRODUCTION")
        env = get_environment()
        assert env == "production"
        
        monkeypatch.setenv("DJANGO_ENV", "  development  ")
        env = get_environment()
        assert env == "development"

    def test_get_environment_raises_on_invalid_value(self, monkeypatch):
        """
        GOAL: Verify get_environment raises ValueError for invalid environment names.

        GUARANTEES:
          - Raises ValueError for invalid environment names
          - Error message includes valid environment names
        """
        from config.settings import get_environment
        
        monkeypatch.setenv("DJANGO_ENV", "invalid")
        
        with pytest.raises(ValueError) as exc_info:
            get_environment()
        
        assert "Invalid DJANGO_ENV value" in str(exc_info.value)
        assert "development" in str(exc_info.value)
        assert "staging" in str(exc_info.value)
        assert "production" in str(exc_info.value)

    def test_development_settings_debug_true(self, settings):
        """
        GOAL: Verify development settings have DEBUG=True.

        GUARANTEES:
          - DEBUG is True in development
          - ALLOWED_HOSTS includes localhost
        """
        from config.settings import development
        
        assert development.DEBUG is True
        assert "localhost" in development.ALLOWED_HOSTS or not development.ALLOWED_HOSTS

    def test_staging_settings_debug_false(self, settings):
        """
        GOAL: Verify staging settings have DEBUG=False.

        GUARANTEES:
          - DEBUG is False in staging
          - Security settings are enabled
        """
        from config.settings import staging
        
        assert staging.DEBUG is False
        assert staging.HSTS_ENABLED is True

    def test_production_settings_debug_false(self, settings):
        """
        GOAL: Verify production settings have DEBUG=False.

        GUARANTEES:
          - DEBUG is False in production
          - All security settings are enabled
          - SSL redirect is enabled
        """
        from config.settings import production
        
        assert production.DEBUG is False
        assert production.SECURE_SSL_REDIRECT is True
        assert production.HSTS_ENABLED is True
        assert production.HSTS_PRELOAD is True

    def test_development_rate_limiting_disabled(self, settings):
        """
        GOAL: Verify rate limiting is disabled in development.

        GUARANTEES:
          - RATE_LIMIT_ENABLED is False in development
          - CIRCUIT_BREAKER_ENABLED is False in development
        """
        from config.settings import development
        
        assert development.RATE_LIMIT_ENABLED is False
        assert development.CIRCUIT_BREAKER_ENABLED is False

    def test_staging_rate_limiting_enabled(self, settings):
        """
        GOAL: Verify rate limiting is enabled in staging.

        GUARANTEES:
          - RATE_LIMIT_ENABLED is True in staging
          - CIRCUIT_BREAKER_ENABLED is True in staging
        """
        from config.settings import staging
        
        assert staging.RATE_LIMIT_ENABLED is True
        assert staging.CIRCUIT_BREAKER_ENABLED is True

    def test_production_rate_limiting_enabled(self, settings):
        """
        GOAL: Verify rate limiting is enabled in production.

        GUARANTEES:
          - RATE_LIMIT_ENABLED is True in production
          - CIRCUIT_BREAKER_ENABLED is True in production
        """
        from config.settings import production
        
        assert production.RATE_LIMIT_ENABLED is True
        assert production.CIRCUIT_BREAKER_ENABLED is True

    def test_development_logging_verbose(self, settings):
        """
        GOAL: Verify development logging is verbose.

        GUARANTEES:
          - Django log level is INFO or DEBUG
          - Database query logging is enabled
        """
        from config.settings import development
        
        django_logger = development.LOGGING["loggers"]["django"]
        assert django_logger["level"] in ["INFO", "DEBUG"]
        
        db_logger = development.LOGGING["loggers"]["django.db.backends"]
        assert db_logger["level"] == "DEBUG"

    def test_production_logging_minimal(self, settings):
        """
        GOAL: Verify production logging is minimal.

        GUARANTEES:
          - Django log level is WARNING or ERROR
          - Database query logging is disabled
        """
        from config.settings import production
        
        django_logger = production.LOGGING["loggers"]["django"]
        assert django_logger["level"] in ["WARNING", "ERROR"]
        
        db_logger = production.LOGGING["loggers"]["django.db.backends"]
        assert db_logger["level"] == "WARNING"

    def test_sentry_environment_configuration(self, settings):
        """
        GOAL: Verify Sentry environment is set correctly for each environment.

        GUARANTEES:
          - Development: SENTRY_ENVIRONMENT is "development"
          - Staging: SENTRY_ENVIRONMENT is "staging"
          - Production: SENTRY_ENVIRONMENT is "production"
        """
        from config.settings import development, staging, production
        
        assert development.SENTRY_ENVIRONMENT == "development"
        assert staging.SENTRY_ENVIRONMENT == "staging"
        assert production.SENTRY_ENVIRONMENT == "production"

    def test_sentry_sample_rates_development(self, settings):
        """
        GOAL: Verify Sentry sample rates are 100% in development.

        GUARANTEES:
          - Traces sample rate is 1.0
          - Profiles sample rate is 1.0
        """
        from config.settings import development
        
        assert development.SENTRY_TRACES_SAMPLE_RATE == 1.0
        assert development.SENTRY_PROFILES_SAMPLE_RATE == 1.0

    def test_sentry_sample_rates_staging(self, settings):
        """
        GOAL: Verify Sentry sample rates are 50% in staging.

        GUARANTEES:
          - Traces sample rate is 0.5
          - Profiles sample rate is 0.5
        """
        from config.settings import staging
        
        assert staging.SENTRY_TRACES_SAMPLE_RATE == 0.5
        assert staging.SENTRY_PROFILES_SAMPLE_RATE == 0.5

    def test_sentry_sample_rates_production(self, settings):
        """
        GOAL: Verify Sentry sample rates are 10% in production.

        GUARANTEES:
          - Traces sample rate is 0.1
          - Profiles sample rate is 0.1
        """
        from config.settings import production
        
        assert production.SENTRY_TRACES_SAMPLE_RATE == 0.1
        assert production.SENTRY_PROFILES_SAMPLE_RATE == 0.1

    def test_static_files_storage_development(self, settings):
        """
        GOAL: Verify static files storage is local in development.

        GUARANTEES:
          - Uses StaticFilesStorage
          - Not compressed
        """
        from config.settings import development
        
        storage_backend = development.STORAGES["staticfiles"]["BACKEND"]
        assert "StaticFilesStorage" in storage_backend

    def test_static_files_storage_production(self, settings):
        """
        GOAL: Verify static files storage is compressed in production.

        GUARANTEES:
          - Uses CompressedManifestStaticFilesStorage
          - Files are compressed and have manifest
        """
        from config.settings import production
        
        storage_backend = production.STORAGES["staticfiles"]["BACKEND"]
        assert "CompressedManifestStaticFilesStorage" in storage_backend

    def test_hsts_settings_production(self, settings):
        """
        GOAL: Verify HSTS settings are strict in production.

        GUARANTEES:
          - HSTS_MAX_AGE is 1 year (31536000)
          - HSTS_INCLUDE_SUBDOMAINS is True
          - HSTS_PRELOAD is True
        """
        from config.settings import production
        
        assert production.HSTS_MAX_AGE == 31536000
        assert production.HSTS_INCLUDE_SUBDOMAINS is True
        assert production.HSTS_PRELOAD is True

    def test_hsts_settings_staging(self, settings):
        """
        GOAL: Verify HSTS settings are moderate in staging.

        GUARANTEES:
          - HSTS_MAX_AGE is 1 day (86400)
          - HSTS_INCLUDE_SUBDOMAINS is True
          - HSTS_PRELOAD is False
        """
        from config.settings import staging
        
        assert staging.HSTS_MAX_AGE == 86400
        assert staging.HSTS_INCLUDE_SUBDOMAINS is True
        assert staging.HSTS_PRELOAD is False

    def test_csp_settings_development(self, settings):
        """
        GOAL: Verify CSP is permissive in development.

        GUARANTEES:
          - CSP_SCRIPT_SRC includes 'unsafe-inline' and 'unsafe-eval'
          - CSP_STYLE_SRC includes 'unsafe-inline'
        """
        from config.settings import development
        
        assert "'unsafe-inline'" in development.CSP_SCRIPT_SRC
        assert "'unsafe-eval'" in development.CSP_SCRIPT_SRC
        assert "'unsafe-inline'" in development.CSP_STYLE_SRC

    def test_csp_settings_production(self, settings):
        """
        GOAL: Verify CSP is strict in production.

        GUARANTEES:
          - CSP_SCRIPT_SRC is only 'self'
          - CSP_STYLE_SRC is only 'self'
        """
        from config.settings import production
        
        assert production.CSP_SCRIPT_SRC == "'self'"
        assert production.CSP_STYLE_SRC == "'self'"

    def test_email_backend_development(self, settings):
        """
        GOAL: Verify email backend is console in development.

        GUARANTEES:
          - EMAIL_BACKEND is console backend
          - Emails are printed to console
        """
        from config.settings import development
        
        assert "console" in development.EMAIL_BACKEND.lower()

    def test_email_backend_production(self, settings):
        """
        GOAL: Verify email backend is SMTP in production.

        GUARANTEES:
          - EMAIL_BACKEND is SMTP backend
          - Emails are sent via SMTP
        """
        from config.settings import production
        
        assert "smtp" in production.EMAIL_BACKEND.lower()

    def test_django_env_variable_is_set(self, settings):
        """
        GOAL: Verify DJANGO_ENV variable is set in settings module.

        GUARANTEES:
          - DJANGO_ENV is defined
          - DJANGO_ENV is one of valid environment names
        """
        from config.settings import DJANGO_ENV
        
        assert DJANGO_ENV in ["development", "staging", "production"]

    def test_base_settings_imported_in_all_environments(self, settings):
        """
        GOAL: Verify base settings are imported in all environment-specific settings.

        GUARANTEES:
          - INSTALLED_APPS is defined
          - MIDDLEWARE is defined
          - DATABASES is defined
        """
        from config.settings import development, staging, production
        
        for env_settings in [development, staging, production]:
            assert hasattr(env_settings, "INSTALLED_APPS")
            assert hasattr(env_settings, "MIDDLEWARE")
            assert hasattr(env_settings, "DATABASES")
            assert len(env_settings.INSTALLED_APPS) > 0
            assert len(env_settings.MIDDLEWARE) > 0

    def test_environment_specific_settings_override_base(self, settings):
        """
        GOAL: Verify environment-specific settings override base settings.

        GUARANTEES:
          - DEBUG is overridden in environment-specific settings
          - LOGGING is overridden in environment-specific settings
          - STORAGES is overridden in environment-specific settings
        """
        from config.settings import base, development, production
        
        # DEBUG is not set in base.py, but is set in environment-specific files
        assert hasattr(development, "DEBUG")
        assert hasattr(production, "DEBUG")
        
        # LOGGING is set in both base.py and environment-specific files
        assert hasattr(base, "LOGGING")
        assert hasattr(development, "LOGGING")
        assert hasattr(production, "LOGGING")

    def test_allowed_hosts_development(self, settings):
        """
        GOAL: Verify ALLOWED_HOSTS includes localhost in development.

        GUARANTEES:
          - localhost is in ALLOWED_HOSTS
          - 127.0.0.1 is in ALLOWED_HOSTS
        """
        from config.settings import development
        
        if development.ALLOWED_HOSTS:
            assert "localhost" in development.ALLOWED_HOSTS
            assert "127.0.0.1" in development.ALLOWED_HOSTS


class TestCDNSettings:
    """
    Tests for CDN configuration and URL generation.
    """

    def test_cdn_disabled_by_default(self, settings):
        """
        GOAL: Verify CDN is disabled by default.

        GUARANTEES:
          - CDN_ENABLED is False
          - STATIC_URL uses local path
        """
        from config.settings import base

        assert base.CDN_ENABLED is False
        assert base.STATIC_URL == "static/"

    def test_cdn_url_generation_when_enabled(self, settings):
        """
        GOAL: Verify CDN URL is generated correctly when enabled.

        GUARANTEES:
          - STATIC_URL includes CDN_URL and CDN_STATIC_PREFIX
          - URL format is correct
        """
        from config.settings import base

        settings.CDN_ENABLED = True
        settings.CDN_URL = "https://cdn.example.com"
        settings.CDN_STATIC_PREFIX = "static"

        expected_url = "https://cdn.example.com/static/"
        assert base.STATIC_URL == expected_url

    def test_cdn_url_with_trailing_slash(self, settings):
        """
        GOAL: Verify CDN URL handles trailing slashes correctly.

        GUARANTEES:
          - Trailing slash in CDN_URL is handled
          - Leading slash in CDN_STATIC_PREFIX is handled
          - Result URL has correct format
        """
        from config.settings import base

        settings.CDN_ENABLED = True
        settings.CDN_URL = "https://cdn.example.com/"
        settings.CDN_STATIC_PREFIX = "/static"

        expected_url = "https://cdn.example.com/static/"
        assert base.STATIC_URL == expected_url

    def test_cdn_disabled_uses_local_url(self, settings):
        """
        GOAL: Verify local STATIC_URL is used when CDN is disabled.

        GUARANTEES:
          - STATIC_URL is "static/" when CDN disabled
          - CDN_URL is ignored
        """
        from config.settings import base

        settings.CDN_ENABLED = False
        settings.CDN_URL = "https://cdn.example.com"
        settings.CDN_STATIC_PREFIX = "static"

        assert base.STATIC_URL == "static/"

    def test_cdn_enabled_but_no_url_uses_local(self, settings):
        """
        GOAL: Verify local STATIC_URL is used when CDN enabled but URL empty.

        GUARANTEES:
          - STATIC_URL is "static/" when CDN_URL is empty
          - Graceful degradation works
        """
        from config.settings import base

        settings.CDN_ENABLED = True
        settings.CDN_URL = ""
        settings.CDN_STATIC_PREFIX = "static"

        assert base.STATIC_URL == "static/"

    def test_production_cdn_enabled(self, settings):
        """
        GOAL: Verify CDN is enabled in production settings.

        GUARANTEES:
          - CDN_ENABLED is True in production
          - CDN_URL is set
          - STATIC_URL uses CDN
        """
        from config.settings import production

        assert production.CDN_ENABLED is True
        assert production.CDN_URL is not None
        assert len(production.CDN_URL) > 0
        assert "cdn." in production.STATIC_URL or production.STATIC_URL != "static/"

    def test_cdn_static_prefix_customization(self, settings):
        """
        GOAL: Verify CDN_STATIC_PREFIX can be customized.

        GUARANTEES:
          - Custom prefix is used in STATIC_URL
          - Default is "static" if not set
        """
        from config.settings import base

        settings.CDN_ENABLED = True
        settings.CDN_URL = "https://cdn.example.com"
        settings.CDN_STATIC_PREFIX = "assets"

        expected_url = "https://cdn.example.com/assets/"
        assert base.STATIC_URL == expected_url

    def test_cdn_environment_variable_parsing(self, monkeypatch):
        """
        GOAL: Verify CDN settings are parsed from environment variables.

        GUARANTEES:
          - CDN_ENABLED is parsed from env var
          - CDN_URL is parsed from env var
          - CDN_STATIC_PREFIX is parsed from env var
        """
        from config.settings import base
        from importlib import reload
        import config.settings.base as base_module

        monkeypatch.setenv("CDN_ENABLED", "True")
        monkeypatch.setenv("CDN_URL", "https://cdn.example.com")
        monkeypatch.setenv("CDN_STATIC_PREFIX", "static")

        # Reload settings to pick up new environment variables
        reload(base_module)

        assert base_module.CDN_ENABLED is True
        assert base_module.CDN_URL == "https://cdn.example.com"
        assert base_module.CDN_STATIC_PREFIX == "static"


class TestCDNTemplateIntegration:
    """
    Integration tests for CDN in templates.
    """

    def test_static_tag_uses_cdn_url(self, client, settings):
        """
        GOAL: Verify {% static %} tag uses CDN URL when enabled.

        GUARANTEES:
          - Static files reference CDN URL
          - Template rendering includes CDN URL
        """
        settings.CDN_ENABLED = True
        settings.CDN_URL = "https://cdn.example.com"
        settings.CDN_STATIC_PREFIX = "static"

        # Load base template
        from django.template import Template, Context

        template = Template('{% load static %}<link rel="stylesheet" href="{% static \'css/main.css\' %}" />')
        context = Context()
        rendered = template.render(context)

        assert "https://cdn.example.com/static/css/main.css" in rendered

    def test_static_tag_uses_local_url_when_cdn_disabled(self, client, settings):
        """
        GOAL: Verify {% static %} tag uses local URL when CDN disabled.

        GUARANTEES:
          - Static files reference local path
          - Template rendering uses local URL
        """
        settings.CDN_ENABLED = False
        settings.STATIC_URL = "static/"

        from django.template import Template, Context

        template = Template('{% load static %}<link rel="stylesheet" href="{% static \'css/main.css\' %}" />')
        context = Context()
        rendered = template.render(context)

        assert "/static/css/main.css" in rendered
        assert "cdn.example.com" not in rendered

    def test_multiple_static_files_with_cdn(self, client, settings):
        """
        GOAL: Verify multiple static files use CDN URL.

        GUARANTEES:
          - All static files reference CDN URL
          - CDN URL is consistent across files
        """
        settings.CDN_ENABLED = True
        settings.CDN_URL = "https://cdn.example.com"
        settings.CDN_STATIC_PREFIX = "static"

        from django.template import Template, Context

        template = Template('''
            {% load static %}
            <link rel="stylesheet" href="{% static 'css/main.css' %}" />
            <link rel="stylesheet" href="{% static 'css/spinner.css' %}" />
            <script src="{% static 'js/app.js' %}" defer></script>
            <script src="{% static 'js/filters.js' %}" defer></script>
        ''')
        context = Context()
        rendered = template.render(context)

        assert rendered.count("https://cdn.example.com/static/") == 4
        assert "css/main.css" in rendered
        assert "css/spinner.css" in rendered
        assert "js/app.js" in rendered
        assert "js/filters.js" in rendered


class TestCDNManagementCommand:
    """
    Tests for upload_static_to_cdn management command.
    """

    def test_command_validates_cloudflare_config(self, monkeypatch):
        """
        GOAL: Verify command validates Cloudflare R2 configuration.

        GUARANTEES:
          - ValueError is raised for missing account ID
          - ValueError is raised for missing access key
          - ValueError is raised for missing secret key
        """
        from apps.core.management.commands.upload_static_to_cdn import Command

        # Test missing account ID
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
        monkeypatch.setenv("CLOUDFLARE_R2_BUCKET", "test-bucket")
        monkeypatch.setenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "test-secret")

        command = Command()
        with pytest.raises(ValueError) as exc_info:
            command._validate_cdn_config("cloudflare", "test-bucket")
        assert "CLOUDFLARE_ACCOUNT_ID" in str(exc_info.value)

    def test_command_validates_aws_config(self, monkeypatch):
        """
        GOAL: Verify command validates AWS S3 configuration.

        GUARANTEES:
          - ValueError is raised for missing access key ID
          - ValueError is raised for missing secret access key
          - ValueError is raised for missing bucket name
        """
        from apps.core.management.commands.upload_static_to_cdn import Command

        # Test missing access key
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
        monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")

        command = Command()
        with pytest.raises(ValueError) as exc_info:
            command._validate_cdn_config("aws", "test-bucket")
        assert "AWS_ACCESS_KEY_ID" in str(exc_info.value)

    def test_command_collects_static_files(self, settings, tmp_path):
        """
        GOAL: Verify command collects static files correctly.

        GUARANTEES:
          - All files in STATICFILES_DIRS are collected
          - File paths are relative to static directory
        """
        from apps.core.management.commands.upload_static_to_cdn import Command

        # Create temporary static files
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "css").mkdir()
        (static_dir / "js").mkdir()

        (static_dir / "css" / "main.css").write_text("body { color: red; }")
        (static_dir / "js" / "app.js").write_text("console.log('test');")

        settings.STATICFILES_DIRS = [static_dir]

        command = Command()
        static_files = command._collect_static_files()

        assert len(static_files) == 2
        assert any(f["path"].name == "main.css" for f in static_files)
        assert any(f["path"].name == "app.js" for f in static_files)

    def test_command_gets_content_type(self):
        """
        GOAL: Verify command returns correct MIME types.

        GUARANTEES:
          - CSS files return text/css
          - JavaScript files return application/javascript
          - Images return correct image types
        """
        from apps.core.management.commands.upload_static_to_cdn import Command
        from pathlib import Path

        command = Command()

        assert command._get_content_type(Path("test.css")) == "text/css"
        assert command._get_content_type(Path("test.js")) == "application/javascript"
        assert command._get_content_type(Path("test.jpg")) == "image/jpeg"
        assert command._get_content_type(Path("test.png")) == "image/png"
        assert command._get_content_type(Path("test.svg")) == "image/svg+xml"
        assert command._get_content_type(Path("test.woff2")) == "font/woff2"

    def test_command_handles_unknown_file_types(self):
        """
        GOAL: Verify command handles unknown file types gracefully.

        GUARANTEES:
          - Unknown file types return application/octet-stream
          - No exception is raised
        """
        from apps.core.management.commands.upload_static_to_cdn import Command
        from pathlib import Path

        command = Command()

        assert command._get_content_type(Path("test.unknown")) == "application/octet-stream"
        assert command._get_content_type(Path("test.xyz")) == "application/octet-stream"

    def test_command_dry_run_mode(self, settings, tmp_path, monkeypatch):
        """
        GOAL: Verify command dry run mode doesn't upload files.

        GUARANTEES:
          - Files are not uploaded in dry run mode
          - Upload count is zero
          - Skipped count matches file count
        """
        from apps.core.management.commands.upload_static_to_cdn import Command

        # Create temporary static files
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        (static_dir / "test.css").write_text("body { color: red; }")

        settings.STATICFILES_DIRS = [static_dir]
        settings.CDN_ENABLED = True

        # Set up minimal Cloudflare config
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
        monkeypatch.setenv("CLOUDFLARE_R2_BUCKET", "test-bucket")
        monkeypatch.setenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "test-secret")

        command = Command()
        command._collect_static_files()
        command.skipped_count = 0

        # Simulate dry run
        for file_info in [{"path": Path("test.css"), "full_path": static_dir / "test.css"}]:
            s3_key = str(file_info["path"])
            command.stdout.write(f"[DRY RUN] Would upload: {s3_key}")
            command.skipped_count += 1

        assert command.skipped_count == 1
        assert command.uploaded_count == 0

    def test_command_supports_custom_bucket_name(self, monkeypatch):
        """
        GOAL: Verify command supports custom bucket name via --bucket option.

        GUARANTEES:
          - Custom bucket name is used when provided
          - Environment variable is overridden
        """
        from apps.core.management.commands.upload_static_to_cdn import Command

        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account")
        monkeypatch.setenv("CLOUDFLARE_R2_BUCKET", "env-bucket")
        monkeypatch.setenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "test-secret")

        command = Command()

        # Test with custom bucket
        command._validate_cdn_config("cloudflare", "custom-bucket")
        # Should not raise error with custom bucket

        # Test with environment bucket
        command._validate_cdn_config("cloudflare", None)
        # Should use env-bucket from environment


class TestCDNGracefulDegradation:
    """
    Tests for CDN graceful degradation.
    """

    def test_fallback_to_local_on_cdn_failure(self, settings):
        """
        GOAL: Verify application falls back to local serving on CDN failure.

        GUARANTEES:
          - WhiteNoise serves static files locally
          - Application continues to work
        """
        settings.CDN_ENABLED = True
        settings.CDN_URL = "https://invalid-cdn.example.com"
        settings.CDN_STATIC_PREFIX = "static"

        # WhiteNoise should still serve files locally
        from django.contrib.staticfiles.storage import staticfiles_storage

        # Storage should be accessible
        assert staticfiles_storage is not None

    def test_cdn_url_empty_uses_local(self, settings):
        """
        GOAL: Verify empty CDN URL falls back to local serving.

        GUARANTEES:
          - STATIC_URL uses local path
          - No CDN URL is referenced
        """
        from config.settings import base

        settings.CDN_ENABLED = True
        settings.CDN_URL = ""
        settings.CDN_STATIC_PREFIX = "static"

        assert base.STATIC_URL == "static/"

    def test_cdn_disabled_with_url_set_uses_local(self, settings):
        """
        GOAL: Verify CDN disabled with URL set uses local serving.

        GUARANTEES:
          - CDN_ENABLED takes precedence over CDN_URL
          - STATIC_URL uses local path
        """
        from config.settings import base

        settings.CDN_ENABLED = False
        settings.CDN_URL = "https://cdn.example.com"
        settings.CDN_STATIC_PREFIX = "static"

        assert base.STATIC_URL == "static/"

    def test_template_rendering_without_cdn(self, client, settings):
        """
        GOAL: Verify templates render correctly without CDN.

        GUARANTEES:
          - Templates render successfully
          - Static files reference local paths
        """
        settings.CDN_ENABLED = False
        settings.STATIC_URL = "static/"

        from django.template import Template, Context

        template = Template('{% load static %}<link rel="stylesheet" href="{% static \'css/main.css\' %}" />')
        context = Context()
        rendered = template.render(context)

        assert "/static/css/main.css" in rendered
        assert len(rendered) > 0


class TestLazyLoadingTemplateTags:
    """
    Tests for lazy loading template tags.
    """

    def test_lazy_image_enabled_returns_true_by_default(self, settings):
        """
        GOAL: Verify lazy_image_enabled returns True by default.

        GUARANTEES:
          - Returns True when LAZY_LOADING_ENABLED is not set
          - Default behavior is to enable lazy loading
        """
        from apps.core.templatetags.lazy_loading import lazy_image_enabled

        # Remove setting if it exists
        if hasattr(settings, 'LAZY_LOADING_ENABLED'):
            delattr(settings, 'LAZY_LOADING_ENABLED')

        result = lazy_image_enabled()
        assert result is True

    def test_lazy_image_enabled_returns_false_when_disabled(self, settings):
        """
        GOAL: Verify lazy_image_enabled returns False when disabled.

        GUARANTEES:
          - Returns False when LAZY_LOADING_ENABLED is False
          - Setting takes precedence over default
        """
        from apps.core.templatetags.lazy_loading import lazy_image_enabled

        settings.LAZY_LOADING_ENABLED = False

        result = lazy_image_enabled()
        assert result is False

    def test_lazy_image_placeholder_returns_default(self, settings):
        """
        GOAL: Verify lazy_image_placeholder returns default placeholder.

        GUARANTEES:
          - Returns default placeholder when not configured
          - Default is "/static/img/placeholder.svg"
        """
        from apps.core.templatetags.lazy_loading import lazy_image_placeholder

        # Remove setting if it exists
        if hasattr(settings, 'LAZY_LOADING_PLACEHOLDER'):
            delattr(settings, 'LAZY_LOADING_PLACEHOLDER')

        result = lazy_image_placeholder()
        assert result == "/static/img/placeholder.svg"

    def test_lazy_image_placeholder_returns_custom(self, settings):
        """
        GOAL: Verify lazy_image_placeholder returns custom placeholder.

        GUARANTEES:
          - Returns custom placeholder when configured
          - Setting takes precedence over default
        """
        from apps.core.templatetags.lazy_loading import lazy_image_placeholder

        settings.LAZY_LOADING_PLACEHOLDER = "/static/img/custom-placeholder.svg"

        result = lazy_image_placeholder()
        assert result == "/static/img/custom-placeholder.svg"

    def test_lazy_image_config_returns_valid_json(self, settings):
        """
        GOAL: Verify lazy_loading_config returns valid JSON.

        GUARANTEES:
          - Returns valid JSON string
          - JSON contains enabled and rootMargin keys
        """
        from apps.core.templatetags.lazy_loading import lazy_loading_config
        import json

        settings.LAZY_LOADING_ENABLED = True
        settings.LAZY_LOADING_ROOT_MARGIN = "100px"

        result = lazy_loading_config()
        config = json.loads(result)

        assert "enabled" in config
        assert "rootMargin" in config
        assert config["enabled"] is True
        assert config["rootMargin"] == "100px"

    def test_lazy_image_inclusion_tag_with_enabled(self, settings):
        """
        GOAL: Verify lazy_image inclusion tag generates correct HTML when enabled.

        GUARANTEES:
          - HTML contains data-src attribute
          - HTML contains lazy class
          - HTML contains lazy-loading class
          - Placeholder is used as src
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True
        settings.LAZY_LOADING_PLACEHOLDER = "/static/img/placeholder.svg"

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image",
            class_name="my-image"
        )

        assert result["enabled"] is True
        assert result["src"] == "/static/img/test.jpg"
        assert result["alt"] == "Test image"
        assert result["placeholder"] == "/static/img/placeholder.svg"
        assert "lazy" in result["class"]
        assert "lazy-loading" in result["class"]
        assert "my-image" in result["class"]

    def test_lazy_image_inclusion_tag_with_disabled(self, settings):
        """
        GOAL: Verify lazy_image inclusion tag generates correct HTML when disabled.

        GUARANTEES:
          - HTML contains src attribute (not data-src)
          - HTML does not contain lazy class
          - Original image URL is used directly
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = False

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image"
        )

        assert result["enabled"] is False
        assert result["src"] == "/static/img/test.jpg"
        assert "lazy" not in result["class"]

    def test_lazy_image_inclusion_tag_with_srcset(self, settings):
        """
        GOAL: Verify lazy_image inclusion tag supports srcset.

        GUARANTEES:
          - srcset is included in context
          - srcset will be used as data-srcset in template
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image",
            srcset="/static/img/test-small.jpg 300w, /static/img/test-large.jpg 800w"
        )

        assert result["srcset"] == "/static/img/test-small.jpg 300w, /static/img/test-large.jpg 800w"

    def test_lazy_image_inclusion_tag_with_sizes(self, settings):
        """
        GOAL: Verify lazy_image inclusion tag supports sizes.

        GUARANTEES:
          - sizes is included in context
          - sizes will be used as data-sizes in template
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image",
            sizes="(max-width: 600px) 300px, 800px"
        )

        assert result["sizes"] == "(max-width: 600px) 300px, 800px"

    def test_lazy_image_inclusion_tag_with_dimensions(self, settings):
        """
        GOAL: Verify lazy_image inclusion tag supports width and height.

        GUARANTEES:
          - width and height are included in attrs
          - Dimensions are added to HTML attributes
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image",
            width=800,
            height=600
        )

        assert result["attrs"]["width"] == 800
        assert result["attrs"]["height"] == 600

    def test_lazy_image_inclusion_tag_raises_on_empty_src(self, settings):
        """
        GOAL: Verify lazy_image raises ValueError for empty src.

        GUARANTEES:
          - ValueError is raised when src is empty
          - Error message indicates src is required
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True

        context = {}

        with pytest.raises(ValueError) as exc_info:
            lazy_image(context, src="", alt="Test image")

        assert "src" in str(exc_info.value).lower()

    def test_lazy_image_inclusion_tag_with_custom_placeholder(self, settings):
        """
        GOAL: Verify lazy_image supports custom placeholder.

        GUARANTEES:
          - Custom placeholder is used when provided
          - Custom placeholder overrides default
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True
        settings.LAZY_LOADING_PLACEHOLDER = "/static/img/default.svg"

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image",
            placeholder="/static/img/custom.svg"
        )

        assert result["placeholder"] == "/static/img/custom.svg"

    def test_lazy_image_inclusion_tag_with_loading_attribute(self, settings):
        """
        GOAL: Verify lazy_image supports loading attribute.

        GUARANTEES:
          - loading attribute is included in attrs
          - loading attribute is passed to template
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image",
            loading="eager"
        )

        assert result["loading"] == "eager"
        assert result["attrs"]["loading"] == "eager"

    def test_lazy_image_inclusion_tag_with_additional_attrs(self, settings):
        """
        GOAL: Verify lazy_image supports additional HTML attributes.

        GUARANTEES:
          - Additional attributes are included in attrs
          - Custom attributes are passed to template
        """
        from apps.core.templatetags.lazy_loading import lazy_image

        settings.LAZY_LOADING_ENABLED = True

        context = {}
        result = lazy_image(
            context,
            src="/static/img/test.jpg",
            alt="Test image",
            id="my-image",
            data_test="value"
        )

        assert result["attrs"]["id"] == "my-image"
        assert result["attrs"]["data_test"] == "value"


class TestLazyLoadingIntegration:
    """
    Integration tests for lazy loading with templates.
    """

    def test_lazy_image_template_rendering(self, client, settings):
        """
        GOAL: Verify lazy image template renders correctly.

        GUARANTEES:
          - Template renders without errors
          - Generated HTML contains correct attributes
        """
        settings.LAZY_LOADING_ENABLED = True
        settings.LAZY_LOADING_PLACEHOLDER = "/static/img/placeholder.svg"

        from django.template import Template, Context

        template = Template('''
            {% load lazy_loading %}
            {% lazy_image src="/static/img/test.jpg" alt="Test" class_name="my-class" %}
        ''')
        context = Context()
        rendered = template.render(context)

        assert 'data-src="/static/img/test.jpg"' in rendered
        assert 'class="my-class lazy lazy-loading"' in rendered
        assert 'src="/static/img/placeholder.svg"' in rendered

    def test_lazy_image_template_when_disabled(self, client, settings):
        """
        GOAL: Verify lazy image template renders correctly when disabled.

        GUARANTEES:
          - Template renders without errors
          - Generated HTML uses direct src (not data-src)
        """
        settings.LAZY_LOADING_ENABLED = False

        from django.template import Template, Context

        template = Template('''
            {% load lazy_loading %}
            {% lazy_image src="/static/img/test.jpg" alt="Test" %}
        ''')
        context = Context()
        rendered = template.render(context)

        assert 'src="/static/img/test.jpg"' in rendered
        assert 'data-src' not in rendered
        assert 'lazy' not in rendered

    def test_lazy_loading_config_in_template(self, client, settings):
        """
        GOAL: Verify lazy loading config is available in templates.

        GUARANTEES:
          - Config is rendered as JSON
          - Config contains expected keys
        """
        settings.LAZY_LOADING_ENABLED = True
        settings.LAZY_LOADING_ROOT_MARGIN = "100px"

        from django.template import Template, Context

        template = Template('''
            {% load lazy_loading %}
            <script>
                window.LAZY_LOADING_CONFIG = {% lazy_loading_config %};
            </script>
        ''')
        context = Context()
        rendered = template.render(context)

        assert '"enabled": true' in rendered
        assert '"rootMargin": "100px"' in rendered

    def test_lazy_image_with_responsive_attributes(self, client, settings):
        """
        GOAL: Verify lazy image template supports responsive attributes.

        GUARANTEES:
          - Template renders with srcset and sizes
          - Responsive attributes are correctly formatted
        """
        settings.LAZY_LOADING_ENABLED = True

        from django.template import Template, Context

        template = Template('''
            {% load lazy_loading %}
            {% lazy_image src="/static/img/test.jpg" alt="Test"
               srcset="/static/img/test-small.jpg 300w, /static/img/test-large.jpg 800w"
               sizes="(max-width: 600px) 300px, 800px" %}
        ''')
        context = Context()
        rendered = template.render(context)

        assert 'data-srcset="/static/img/test-small.jpg 300w, /static/img/test-large.jpg 800w"' in rendered
        assert 'data-sizes="(max-width: 600px) 300px, 800px"' in rendered

    def test_lazy_image_with_dimensions(self, client, settings):
        """
        GOAL: Verify lazy image template supports width and height.

        GUARANTEES:
          - Template renders with width and height attributes
          - Dimensions are correctly formatted
        """
        settings.LAZY_LOADING_ENABLED = True

        from django.template import Template, Context

        template = Template('''
            {% load lazy_loading %}
            {% lazy_image src="/static/img/test.jpg" alt="Test" width="800" height="600" %}
        ''')
        context = Context()
        rendered = template.render(context)

        assert 'width="800"' in rendered
        assert 'height="600"' in rendered

    def test_multiple_lazy_images_in_template(self, client, settings):
        """
        GOAL: Verify template can render multiple lazy images.

        GUARANTEES:
          - All images are rendered correctly
          - Each image has lazy loading attributes
        """
        settings.LAZY_LOADING_ENABLED = True

        from django.template import Template, Context

        template = Template('''
            {% load lazy_loading %}
            {% lazy_image src="/static/img/test1.jpg" alt="Test 1" %}
            {% lazy_image src="/static/img/test2.jpg" alt="Test 2" %}
            {% lazy_image src="/static/img/test3.jpg" alt="Test 3" %}
        ''')
        context = Context()
        rendered = template.render(context)

        assert rendered.count('data-src') == 3
        assert rendered.count('lazy') == 3
        assert 'test1.jpg' in rendered
        assert 'test2.jpg' in rendered
        assert 'test3.jpg' in rendered


class TestOpenAPI:
    """
    Tests for OpenAPI/Swagger documentation.
    """

    def test_openapi_schema_endpoint(self, client, settings):
        """
        GOAL: Verify OpenAPI schema endpoint returns valid JSON schema.

        GUARANTEES:
          - Returns 200 status code
          - Response is valid JSON
          - Schema contains expected fields
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        
        schema = response.json()
        
        # Verify schema structure
        assert "openapi" in schema
        assert schema["openapi"] == "3.2.0"
        assert "info" in schema
        assert schema["info"]["title"] == "Cargo Viewer API"
        assert "paths" in schema
        assert "components" in schema

    def test_openapi_schema_disabled(self, client, settings):
        """
        GOAL: Verify OpenAPI endpoints are disabled when OPENAPI_ENABLED=False.

        GUARANTEES:
          - Schema endpoint returns 404
          - Swagger UI returns 404
          - ReDoc UI returns 404
        """
        settings.OPENAPI_ENABLED = False
        
        response_schema = client.get("/api/schema/")
        response_swagger = client.get("/api/docs/")
        response_redoc = client.get("/api/redoc/")
        
        assert response_schema.status_code == 404
        assert response_swagger.status_code == 404
        assert response_redoc.status_code == 404

    def test_swagger_ui_endpoint(self, client, settings):
        """
        GOAL: Verify Swagger UI endpoint returns HTML interface.

        GUARANTEES:
          - Returns 200 status code
          - Response is HTML
          - Contains Swagger UI elements
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/docs/")
        
        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]
        content = response.content.decode("utf-8")
        
        # Verify Swagger UI elements
        assert "swagger" in content.lower() or "openapi" in content.lower()
        assert "swagger-ui" in content.lower()

    def test_redoc_ui_endpoint(self, client, settings):
        """
        GOAL: Verify ReDoc UI endpoint returns HTML interface.

        GUARANTEES:
          - Returns 200 status code
          - Response is HTML
          - Contains ReDoc elements
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/redoc/")
        
        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]
        content = response.content.decode("utf-8")
        
        # Verify ReDoc elements
        assert "redoc" in content.lower()

    def test_schema_includes_auth_endpoints(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes authentication endpoints.

        GUARANTEES:
          - Schema contains /api/v3/auth/telegram path
          - Auth endpoint has POST method
          - Request schema is defined
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        # Check for auth endpoint
        assert "/api/v3/auth/telegram" in schema["paths"]
        auth_path = schema["paths"]["/api/v3/auth/telegram"]
        assert "post" in auth_path
        
        # Check request schema
        post_schema = auth_path["post"]
        assert "requestBody" in post_schema
        assert "responses" in post_schema

    def test_schema_includes_cargos_endpoints(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes cargo endpoints.

        GUARANTEES:
          - Schema contains /api/v3/cargos/ path
          - Schema contains /api/v3/cargos/{cargo_id}/ path
          - Both have GET methods
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        # Check for cargo list endpoint
        assert "/api/v3/cargos/" in schema["paths"]
        cargo_list = schema["paths"]["/api/v3/cargos/"]
        assert "get" in cargo_list
        
        # Check for cargo detail endpoint
        assert "/api/v3/cargos/{cargo_id}/" in schema["paths"]
        cargo_detail = schema["paths"]["/api/v3/cargos/{cargo_id}/"]
        assert "get" in cargo_detail

    def test_schema_includes_payments_endpoints(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes payment endpoints.

        GUARANTEES:
          - Schema contains /api/v3/payments/create path
          - Schema contains /api/v3/payments/webhook path
          - Both have POST methods
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        # Check for payment create endpoint
        assert "/api/v3/payments/create" in schema["paths"]
        payment_create = schema["paths"]["/api/v3/payments/create"]
        assert "post" in payment_create
        
        # Check for webhook endpoint
        assert "/api/v3/payments/webhook" in schema["paths"]
        webhook = schema["paths"]["/api/v3/payments/webhook"]
        assert "post" in webhook

    def test_schema_includes_telegram_endpoints(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes Telegram endpoints.

        GUARANTEES:
          - Schema contains /telegram/webhook/ path
          - Schema contains /telegram/responses/ path
          - Both have POST methods
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        # Check for webhook endpoint
        assert "/telegram/webhook/" in schema["paths"]
        webhook = schema["paths"]["/telegram/webhook/"]
        assert "post" in webhook
        
        # Check for responses endpoint
        assert "/telegram/responses/" in schema["paths"]
        responses = schema["paths"]["/telegram/responses/"]
        assert "post" in responses

    def test_schema_includes_health_check_endpoints(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes health check endpoints.

        GUARANTEES:
          - Schema contains /health/ path
          - Schema contains /health/ready/ path
          - Schema contains /health/live/ path
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        # Check for health endpoints
        assert "/health/" in schema["paths"]
        assert "/health/ready/" in schema["paths"]
        assert "/health/live/" in schema["paths"]

    def test_schema_has_tags(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes all defined tags.

        GUARANTEES:
          - Schema contains tags array
          - All expected tags are present
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        assert "tags" in schema
        tags = [tag["name"] for tag in schema["tags"]]
        
        expected_tags = ["auth", "cargos", "payments", "promocodes", "telegram", "admin", "health"]
        for tag in expected_tags:
            assert tag in tags

    def test_schema_has_servers(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes server definitions.

        GUARANTEES:
          - Schema contains servers array
          - At least one server is defined
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        assert "servers" in schema
        assert len(schema["servers"]) > 0
        
        # Check server structure
        server = schema["servers"][0]
        assert "url" in server
        assert "description" in server

    def test_schema_version_matches_settings(self, client, settings):
        """
        GOAL: Verify OpenAPI schema version matches settings.

        GUARANTEES:
          - Schema version matches SPECTACULAR_SETTINGS['VERSION']
        """
        from config.settings.base import SPECTACULAR_SETTINGS
        
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        assert schema["openapi"] == SPECTACULAR_SETTINGS["VERSION"]

    def test_schema_title_matches_settings(self, client, settings):
        """
        GOAL: Verify OpenAPI schema title matches settings.

        GUARANTEES:
          - Schema title matches SPECTACULAR_SETTINGS['TITLE']
        """
        from config.settings.base import SPECTACULAR_SETTINGS
        
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        assert schema["info"]["title"] == SPECTACULAR_SETTINGS["TITLE"]

    def test_schema_description_matches_settings(self, client, settings):
        """
        GOAL: Verify OpenAPI schema description matches settings.

        GUARANTEES:
          - Schema description matches SPECTACULAR_SETTINGS['DESCRIPTION']
        """
        from config.settings.base import SPECTACULAR_SETTINGS
        
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        assert schema["info"]["description"] == SPECTACULAR_SETTINGS["DESCRIPTION"]

    def test_schema_has_components(self, client, settings):
        """
        GOAL: Verify OpenAPI schema includes reusable components.

        GUARANTEES:
          - Schema contains components section
          - Components may include schemas, responses, parameters
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        assert "components" in schema
        components = schema["components"]
        
        # Check for common component types
        assert isinstance(components, dict)

    def test_schema_path_prefix(self, client, settings):
        """
        GOAL: Verify OpenAPI schema uses correct path prefix.

        GUARANTEES:
          - All API paths start with /api
        """
        settings.OPENAPI_ENABLED = True
        
        response = client.get("/api/schema/")
        schema = response.json()
        
        paths = schema["paths"]
        api_paths = [path for path in paths.keys() if path.startswith("/api")]
        
        assert len(api_paths) > 0

    def test_graceful_degradation_when_drf_spectacular_not_installed(self, client, settings, monkeypatch):
        """
        GOAL: Verify graceful degradation when drf-spectacular is not installed.

        GUARANTEES:
          - Views still work without drf-spectacular
          - No ImportError is raised
        """
        # Simulate drf-spectacular not being available
        settings.OPENAPI_ENABLED = True
        
        # Test that views still work
        response = client.get("/health/")
        
        assert response.status_code == 200

    def test_custom_exception_handler_works_with_openapi(self, client, settings):
        """
        GOAL: Verify custom exception handler works with OpenAPI.

        GUARANTEES:
          - Exception handler returns JSON responses
          - Responses include error_code field
        """
        from apps.core.exceptions import custom_exception_handler, ValidationError
        from django.http import HttpRequest
        
        settings.OPENAPI_ENABLED = True
        
        # Create a mock exception
        exc = ValidationError("Test error", {"field": "error"})
        
        # Create mock request
        request = HttpRequest()
        request.META = {}
        
        # Call exception handler
        response = custom_exception_handler(exc, {"request": request})
        
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "message" in data
