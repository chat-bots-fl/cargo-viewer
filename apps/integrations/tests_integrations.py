"""
Unit tests for apps/integrations/.

This module contains tests for CargoTech authentication, API client,
rate limiting, and HTTP retry logic.
"""

from __future__ import annotations

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache
from requests.exceptions import HTTPError

from apps.integrations.cargotech_auth import CargoTechAuthService, CargoTechAuthError
from apps.integrations.cargotech_client import CargoAPIClient
from apps.integrations.rate_limiter import RateLimiter, RateLimitError
from apps.integrations.http_retry import fetch_with_retry, _sleep_backoff


class CargoTechAuthServiceTests(TestCase):
    """Test CargoTechAuthService for authentication."""
    
    def setUp(self):
        cache.clear()
    
    @patch('apps.integrations.cargotech_auth.requests.post')
    def test_login_success(self, mock_post):
        """Test that login returns token on successful authentication."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"token": "123|test_token"}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        token = CargoTechAuthService.login(
            phone="+79001234567",
            password="testpassword"
        )
        
        self.assertEqual(token, "123|test_token")
        mock_post.assert_called_once()
    
    @patch('apps.integrations.cargotech_auth.requests.post')
    def test_login_caches_token(self, mock_post):
        """Test that login caches the token."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"token": "123|test_token"}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        CargoTechAuthService.login(
            phone="+79001234567",
            password="testpassword"
        )
        
        cached_token = cache.get(CargoTechAuthService.CACHE_KEY)
        self.assertEqual(cached_token, "123|test_token")
    
    @patch('apps.integrations.cargotech_auth.requests.post')
    def test_login_http_error(self, mock_post):
        """Test that login raises CargoTechAuthError on HTTP error."""
        mock_post.side_effect = HTTPError("404 Not Found")
        
        with self.assertRaises(CargoTechAuthError):
            CargoTechAuthService.login(
                phone="+79001234567",
                password="testpassword"
            )
    
    @patch('apps.integrations.cargotech_auth.requests.post')
    def test_login_invalid_response(self, mock_post):
        """Test that login raises CargoTechAuthError on invalid response."""
        mock_response = Mock()
        mock_response.json.return_value = {"invalid": "response"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        with self.assertRaises(CargoTechAuthError):
            CargoTechAuthService.login(
                phone="+79001234567",
                password="testpassword"
            )
    
    def test_login_missing_credentials(self):
        """Test that login raises ValidationError for missing credentials."""
        from django.core.exceptions import ValidationError
        
        with self.assertRaises(ValidationError):
            CargoTechAuthService.login(phone="", password="testpassword")
        
        with self.assertRaises(ValidationError):
            CargoTechAuthService.login(phone="+79001234567", password="")
    
    @patch('apps.integrations.cargotech_auth.requests.post')
    def test_get_token_from_cache(self, mock_post):
        """Test that get_token returns cached token if available."""
        cache.set(CargoTechAuthService.CACHE_KEY, "cached_token", timeout=86400)
        
        token = CargoTechAuthService.get_token()
        
        self.assertEqual(token, "cached_token")
        mock_post.assert_not_called()
    
    @patch('apps.integrations.cargotech_auth.requests.post')
    @override_settings(CARGOTECH_PHONE="+79001234567", CARGOTECH_PASSWORD="testpass")
    def test_get_token_login_when_not_cached(self, mock_post):
        """Test that get_token performs login when token not cached."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"token": "123|new_token"}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        token = CargoTechAuthService.get_token()
        
        self.assertEqual(token, "123|new_token")
        mock_post.assert_called_once()
    
    def test_invalidate_cached_token(self):
        """Test that invalidate_cached_token removes token from cache."""
        cache.set(CargoTechAuthService.CACHE_KEY, "cached_token", timeout=86400)
        
        CargoTechAuthService.invalidate_cached_token()
        
        cached_token = cache.get(CargoTechAuthService.CACHE_KEY)
        self.assertIsNone(cached_token)
    
    @patch('apps.integrations.cargotech_auth.requests.post')
    @override_settings(CARGOTECH_PHONE="+79001234567", CARGOTECH_PASSWORD="testpass")
    def test_auth_headers(self, mock_post):
        """Test that auth_headers returns correct headers."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"token": "123|test_token"}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        headers = CargoTechAuthService.auth_headers()
        
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer 123|test_token")
        self.assertIn("Accept", headers)
        self.assertEqual(headers["Accept"], "application/json")


class CargoAPIClientTests(TestCase):
    """Test CargoAPIClient for API requests."""
    
    def setUp(self):
        cache.clear()
    
    @patch('apps.integrations.cargotech_client.fetch_with_retry')
    @patch('apps.integrations.cargotech_client.CargoTechAuthService.auth_headers')
    def test_request_success(self, mock_auth_headers, mock_fetch):
        """Test that request makes successful API call."""
        mock_auth_headers.return_value = {"Authorization": "Bearer test_token"}
        mock_response = Mock()
        mock_response.json.return_value = {"data": "test"}
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response
        
        result = CargoAPIClient.request("GET", "/test/path")
        
        self.assertEqual(result, {"data": "test"})
        mock_fetch.assert_called_once()
    
    def test_request_invalid_path(self):
        """Test that request raises ValueError for invalid path."""
        with self.assertRaises(ValueError):
            CargoAPIClient.request("GET", "invalid/path")
    
    def test_request_invalid_timeout(self):
        """Test that request raises ValueError for invalid timeout."""
        with self.assertRaises(ValueError):
            CargoAPIClient.request("GET", "/test/path", timeout=0)
    
    @patch('apps.integrations.cargotech_client.fetch_with_retry')
    @patch('apps.integrations.cargotech_client.CargoTechAuthService.auth_headers')
    @patch('apps.integrations.cargotech_client.CargoTechAuthService.invalidate_cached_token')
    def test_request_401_invalidates_token(self, mock_invalidate, mock_auth_headers, mock_fetch):
        """Test that request invalidates token on 401 response."""
        mock_auth_headers.return_value = {"Authorization": "Bearer test_token"}
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"data": "test"}
        mock_fetch.return_value = mock_response
        
        result = CargoAPIClient.request("GET", "/test/path")
        
        self.assertEqual(result, {"data": "test"})
        mock_invalidate.assert_called_once()
    
    @patch('apps.integrations.cargotech_client.fetch_with_retry')
    @patch('apps.integrations.cargotech_client.CargoTechAuthService.auth_headers')
    def test_fetch_cargos(self, mock_auth_headers, mock_fetch):
        """Test that fetch_cargos calls correct endpoint."""
        mock_auth_headers.return_value = {"Authorization": "Bearer test_token"}
        mock_response = Mock()
        mock_response.json.return_value = {"data": [], "meta": {}}
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response
        
        params = {"filter[mode]": "my", "limit": 20}
        result = CargoAPIClient.fetch_cargos(params)
        
        self.assertEqual(result, {"data": [], "meta": {}})
        mock_fetch.assert_called_once()
    
    @patch('apps.integrations.cargotech_client.fetch_with_retry')
    @patch('apps.integrations.cargotech_client.CargoTechAuthService.auth_headers')
    def test_fetch_cargo_detail(self, mock_auth_headers, mock_fetch):
        """Test that fetch_cargo_detail calls correct endpoint."""
        mock_auth_headers.return_value = {"Authorization": "Bearer test_token"}
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"id": "12345"}}
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response
        
        result = CargoAPIClient.fetch_cargo_detail("12345")
        
        self.assertEqual(result, {"data": {"id": "12345"}})
        mock_fetch.assert_called_once()
    
    def test_fetch_cargo_detail_empty_id(self):
        """Test that fetch_cargo_detail raises ValueError for empty cargo_id."""
        with self.assertRaises(ValueError):
            CargoAPIClient.fetch_cargo_detail("")
    
    @patch('apps.integrations.cargotech_client.fetch_with_retry')
    @patch('apps.integrations.cargotech_client.CargoTechAuthService.auth_headers')
    def test_search_cities(self, mock_auth_headers, mock_fetch):
        """Test that search_cities calls correct endpoint."""
        mock_auth_headers.return_value = {"Authorization": "Bearer test_token"}
        mock_response = Mock()
        mock_response.json.return_value = {"data": [], "meta": {}}
        mock_response.status_code = 200
        mock_fetch.return_value = mock_response
        
        result = CargoAPIClient.search_cities("Москва", limit=10, offset=0)
        
        self.assertEqual(result, {"data": [], "meta": {}})
        mock_fetch.assert_called_once()
    
    def test_search_cities_invalid_limit(self):
        """Test that search_cities raises ValueError for invalid limit."""
        with self.assertRaises(ValueError):
            CargoAPIClient.search_cities("Москва", limit=0)
        
        with self.assertRaises(ValueError):
            CargoAPIClient.search_cities("Москва", limit=51)
    
    def test_search_cities_invalid_offset(self):
        """Test that search_cities raises ValueError for invalid offset."""
        with self.assertRaises(ValueError):
            CargoAPIClient.search_cities("Москва", offset=-1)


class RateLimiterTests(TestCase):
    """Test RateLimiter for rate limiting."""
    
    def test_init_with_valid_requests_per_minute(self):
        """Test that RateLimiter initializes with valid requests_per_minute."""
        limiter = RateLimiter(requests_per_minute=600)
        self.assertEqual(limiter.capacity, 600.0)
        self.assertEqual(limiter.tokens, 600.0)
    
    def test_init_with_invalid_requests_per_minute(self):
        """Test that RateLimiter raises ValueError for invalid requests_per_minute."""
        with self.assertRaises(ValueError):
            RateLimiter(requests_per_minute=0)
        
        with self.assertRaises(ValueError):
            RateLimiter(requests_per_minute=-10)
    
    def test_can_request_consumes_token(self):
        """Test that can_request consumes a token."""
        limiter = RateLimiter(requests_per_minute=10)
        
        self.assertTrue(limiter.can_request())
        self.assertEqual(limiter.tokens, 9.0)
    
    def test_can_request_depletes_tokens(self):
        """Test that can_request returns False when tokens depleted."""
        limiter = RateLimiter(requests_per_minute=1)
        
        self.assertTrue(limiter.can_request())
        self.assertFalse(limiter.can_request())
    
    def test_can_request_replenishes_tokens(self):
        """Test that can_request replenishes tokens over time."""
        import time
        
        limiter = RateLimiter(requests_per_minute=60)
        
        # Consume all tokens
        for _ in range(60):
            limiter.can_request()
        
        self.assertFalse(limiter.can_request())
        
        # Wait for tokens to replenish (1 second = 1 token)
        time.sleep(1.1)
        
        self.assertTrue(limiter.can_request())
    
    def test_can_request_thread_safe(self):
        """Test that can_request is thread-safe."""
        import threading
        
        limiter = RateLimiter(requests_per_minute=100)
        results = []
        
        def make_request():
            results.append(limiter.can_request())
        
        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have exactly 10 successful requests
        self.assertEqual(sum(results), 10)
    
    def test_wait_for_token_success(self):
        """Test that wait_for_token returns when token available."""
        limiter = RateLimiter(requests_per_minute=60)
        
        # Should not raise, token is available
        limiter.wait_for_token(max_wait_seconds=1.0)
    
    def test_wait_for_token_timeout(self):
        """Test that wait_for_token raises RateLimitError on timeout."""
        limiter = RateLimiter(requests_per_minute=1)
        
        # Consume the only token
        limiter.can_request()
        
        # Should raise RateLimitError
        with self.assertRaises(RateLimitError):
            limiter.wait_for_token(max_wait_seconds=0.1)


class HttpRetryTests(TestCase):
    """Test HTTP retry logic."""
    
    def test_sleep_backoff_increases_exponentially(self):
        """Test that _sleep_backoff increases delay exponentially."""
        import time
        from unittest.mock import patch
        
        with patch('time.sleep') as mock_sleep:
            _sleep_backoff(attempt=0)
            mock_sleep.assert_called_once()
            first_delay = mock_sleep.call_args[0][0]
            
            mock_sleep.reset_mock()
            _sleep_backoff(attempt=1)
            second_delay = mock_sleep.call_args[0][0]
            
            # Second delay should be roughly 2x first delay
            self.assertGreater(second_delay, first_delay * 1.5)
            self.assertLess(second_delay, first_delay * 2.5)
    
    def test_fetch_with_retry_success_on_first_attempt(self):
        """Test that fetch_with_retry returns on first successful attempt."""
        mock_response = Mock()
        mock_response.status_code = 200
        
        request_fn = Mock(return_value=mock_response)
        result = fetch_with_retry(request_fn, max_attempts=4)
        
        self.assertEqual(result, mock_response)
        self.assertEqual(request_fn.call_count, 1)
    
    def test_fetch_with_retry_retries_on_429(self):
        """Test that fetch_with_retry retries on 429 status."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        
        request_fn = Mock(side_effect=[mock_response_429, mock_response_200])
        result = fetch_with_retry(request_fn, max_attempts=4)
        
        self.assertEqual(result, mock_response_200)
        self.assertEqual(request_fn.call_count, 2)
    
    def test_fetch_with_retry_retries_on_503(self):
        """Test that fetch_with_retry retries on 503 status."""
        mock_response_503 = Mock()
        mock_response_503.status_code = 503
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        
        request_fn = Mock(side_effect=[mock_response_503, mock_response_200])
        result = fetch_with_retry(request_fn, max_attempts=4)
        
        self.assertEqual(result, mock_response_200)
        self.assertEqual(request_fn.call_count, 2)
    
    def test_fetch_with_retry_retries_on_504(self):
        """Test that fetch_with_retry retries on 504 status."""
        mock_response_504 = Mock()
        mock_response_504.status_code = 504
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        
        request_fn = Mock(side_effect=[mock_response_504, mock_response_200])
        result = fetch_with_retry(request_fn, max_attempts=4)
        
        self.assertEqual(result, mock_response_200)
        self.assertEqual(request_fn.call_count, 2)
    
    def test_fetch_with_retry_no_retry_on_200(self):
        """Test that fetch_with_retry doesn't retry on 200 status."""
        mock_response = Mock()
        mock_response.status_code = 200
        
        request_fn = Mock(return_value=mock_response)
        result = fetch_with_retry(request_fn, max_attempts=4)
        
        self.assertEqual(result, mock_response)
        self.assertEqual(request_fn.call_count, 1)
    
    def test_fetch_with_retry_no_retry_on_404(self):
        """Test that fetch_with_retry doesn't retry on 404 status."""
        mock_response = Mock()
        mock_response.status_code = 404
        
        request_fn = Mock(return_value=mock_response)
        result = fetch_with_retry(request_fn, max_attempts=4)
        
        self.assertEqual(result, mock_response)
        self.assertEqual(request_fn.call_count, 1)
    
    def test_fetch_with_retry_max_attempts_exceeded(self):
        """Test that fetch_with_retry raises RuntimeError after max attempts."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        
        request_fn = Mock(return_value=mock_response_429)
        
        with self.assertRaises(RuntimeError):
            fetch_with_retry(request_fn, max_attempts=4)
        
        self.assertEqual(request_fn.call_count, 4)
    
    def test_fetch_with_retry_custom_max_attempts(self):
        """Test that fetch_with_retry respects custom max_attempts."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        
        request_fn = Mock(return_value=mock_response_429)
        
        with self.assertRaises(RuntimeError):
            fetch_with_retry(request_fn, max_attempts=2)
        
        self.assertEqual(request_fn.call_count, 2)
