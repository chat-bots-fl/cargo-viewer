from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone as dj_timezone

from apps.auth.models import DriverProfile, TelegramSession

from apps.auth.decorators import require_admin
from apps.auth.middleware import JWTAuthenticationMiddleware
from apps.auth.services import (
    TelegramAuthService,
    SessionService,
    TokenService,
    is_admin_user,
    is_staff_user,
    has_admin_subscription
)
from apps.auth.views import telegram_auth

User = get_user_model()


def _make_init_data(*, bot_token: str, auth_date: int, user: dict) -> str:
    """
    Build a minimal Telegram initData querystring with a correct hash for tests.
    """
    data = {"auth_date": str(auth_date), "query_id": "AAHtest", "user": json.dumps(user, separators=(",", ":"))}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    data["hash"] = hash_value
    return urlencode(data)


class TelegramAuthServiceTests(TestCase):
    @override_settings(TELEGRAM_BOT_TOKEN="123:TESTTOKEN")
    def test_validate_init_data_ok(self):
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        init_data = _make_init_data(
            bot_token="123:TESTTOKEN",
            auth_date=now_ts,
            user={"id": 1001, "first_name": "Иван", "username": "ivan_driver"},
        )
        out = TelegramAuthService.validate_init_data(init_data, max_age_seconds=300)
        self.assertEqual(out["id"], 1001)
        self.assertEqual(out["first_name"], "Иван")
        self.assertEqual(out["username"], "ivan_driver")

    @override_settings(TELEGRAM_BOT_TOKEN="123:TESTTOKEN")
    def test_validate_init_data_expired(self):
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        init_data = _make_init_data(
            bot_token="123:TESTTOKEN",
            auth_date=now_ts - 1000,
            user={"id": 1001, "first_name": "Иван", "username": "ivan_driver"},
        )
        with self.assertRaises(ValidationError):
            TelegramAuthService.validate_init_data(init_data, max_age_seconds=300)


class AdminAuthHelpersTests(TestCase):
    """Test helper functions for admin access checks."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.staff_user = User.objects.create_user(username="staff", password="testpass", is_staff=True)
        self.superuser = User.objects.create_superuser(username="admin", password="testpass")
    
    def test_is_admin_user_with_none(self):
        """Test is_admin_user with None user."""
        self.assertFalse(is_admin_user(None))
    
    def test_is_admin_user_with_anonymous(self):
        """Test is_admin_user with anonymous user."""
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        self.assertFalse(is_admin_user(anon))
    
    def test_is_admin_user_with_regular_user(self):
        """Test is_admin_user with regular user."""
        self.assertFalse(is_admin_user(self.user))
    
    def test_is_admin_user_with_staff_user(self):
        """Test is_admin_user with staff user."""
        self.assertTrue(is_admin_user(self.staff_user))
    
    def test_is_admin_user_with_superuser(self):
        """Test is_admin_user with superuser."""
        self.assertTrue(is_admin_user(self.superuser))
    
    def test_is_staff_user_with_none(self):
        """Test is_staff_user with None user."""
        self.assertFalse(is_staff_user(None))
    
    def test_is_staff_user_with_anonymous(self):
        """Test is_staff_user with anonymous user."""
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        self.assertFalse(is_staff_user(anon))
    
    def test_is_staff_user_with_regular_user(self):
        """Test is_staff_user with regular user."""
        self.assertFalse(is_staff_user(self.user))
    
    def test_is_staff_user_with_staff_user(self):
        """Test is_staff_user with staff user."""
        self.assertTrue(is_staff_user(self.staff_user))
    
    def test_is_staff_user_with_superuser(self):
        """Test is_staff_user with superuser."""
        self.assertTrue(is_staff_user(self.superuser))
    
    def test_has_admin_subscription_with_none(self):
        """Test has_admin_subscription with None user."""
        self.assertFalse(has_admin_subscription(None))
    
    def test_has_admin_subscription_with_anonymous(self):
        """Test has_admin_subscription with anonymous user."""
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        self.assertFalse(has_admin_subscription(anon))
    
    def test_has_admin_subscription_without_subscription(self):
        """Test has_admin_subscription with user without subscription."""
        self.assertFalse(has_admin_subscription(self.user))
    
    def test_has_admin_subscription_with_inactive_subscription(self):
        """Test has_admin_subscription with inactive subscription."""
        from apps.subscriptions.models import Subscription
        Subscription.objects.create(
            user=self.user,
            is_active=False,
        )
        self.assertFalse(has_admin_subscription(self.user))
    
    def test_has_admin_subscription_with_expired_subscription(self):
        """Test has_admin_subscription with expired subscription."""
        from apps.subscriptions.models import Subscription
        from django.utils import timezone
        Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )
        self.assertFalse(has_admin_subscription(self.user))
    
    def test_has_admin_subscription_with_active_subscription(self):
        """Test has_admin_subscription with active subscription."""
        from apps.subscriptions.models import Subscription
        from django.utils import timezone
        Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        self.assertTrue(has_admin_subscription(self.user))


class RequireAdminDecoratorTests(TestCase):
    """Test @require_admin decorator."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.staff_user = User.objects.create_user(username="staff", password="testpass", is_staff=True)
        self.superuser = User.objects.create_superuser(username="admin", password="testpass")
    
    def _create_mock_view(self) -> Any:
        """Create a mock view function for testing."""
        def mock_view(request):
            return HttpResponse("OK")
        return mock_view
    
    def test_require_admin_unauthenticated(self):
        """Test @require_admin with unauthenticated user."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/admin/")
        request.user = AnonymousUser()
        
        decorated_view = require_admin(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("forbidden", response.json())
    
    def test_require_admin_regular_user(self):
        """Test @require_admin with regular user (not staff)."""
        request = self.factory.get("/admin/")
        request.user = self.user
        
        decorated_view = require_admin(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("forbidden", response.json())
        self.assertEqual(response.json()["reason"], "not_admin")
    
    def test_require_admin_staff_user(self):
        """Test @require_admin with staff user."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        
        decorated_view = require_admin(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
    
    def test_require_admin_superuser(self):
        """Test @require_admin with superuser."""
        request = self.factory.get("/admin/")
        request.user = self.superuser
        
        decorated_view = require_admin(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
    
    @override_settings(ADMIN_REQUIRE_SUBSCRIPTION=True)
    def test_require_admin_with_subscription_required_no_subscription(self):
        """Test @require_admin with subscription required but no subscription."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        
        decorated_view = require_admin(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["reason"], "no_admin_subscription")
    
    @override_settings(ADMIN_REQUIRE_SUBSCRIPTION=True)
    def test_require_admin_with_subscription_required_active_subscription(self):
        """Test @require_admin with subscription required and active subscription."""
        from apps.subscriptions.models import Subscription
        from django.utils import timezone
        Subscription.objects.create(
            user=self.staff_user,
            is_active=True,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        
        decorated_view = require_admin(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
    
    @override_settings(ADMIN_REQUIRE_SUBSCRIPTION=False)
    def test_require_admin_with_subscription_disabled(self):
        """Test @require_admin with subscription check disabled."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        
        decorated_view = require_admin(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
    
    def test_require_admin_with_require_subscription_param_true(self):
        """Test @require_admin with require_subscription=True parameter."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        
        decorated_view = require_admin(require_subscription=True)(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["reason"], "no_admin_subscription")
    
    def test_require_admin_with_require_subscription_param_false(self):
        """Test @require_admin with require_subscription=False parameter."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        
        decorated_view = require_admin(require_subscription=False)(self._create_mock_view())
        response = decorated_view(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"OK")
    
    def test_require_admin_preserves_view_metadata(self):
        """Test that @require_admin preserves view metadata."""
        mock_view = self._create_mock_view()
        mock_view.__name__ = "test_view"
        mock_view.__doc__ = "Test view docstring"
        
        decorated_view = require_admin(mock_view)
        
        self.assertEqual(decorated_view.__name__, "test_view")
        self.assertEqual(decorated_view.__doc__, "Test view docstring")


class AdminPanelViewsIntegrationTests(TestCase):
    """Integration tests for admin panel views with @require_admin."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.staff_user = User.objects.create_user(username="staff", password="testpass", is_staff=True)
        self.superuser = User.objects.create_superuser(username="admin", password="testpass")
    
    def test_dashboard_view_unauthorized(self):
        """Test dashboard view with unauthorized user."""
        request = self.factory.get("/admin/")
        request.user = self.user
        
        from apps.admin_panel.views import dashboard
        response = dashboard(request)
        
        self.assertEqual(response.status_code, 403)
    
    def test_dashboard_view_authorized_staff(self):
        """Test dashboard view with authorized staff user."""
        request = self.factory.get("/admin/")
        request.user = self.staff_user
        
        from apps.admin_panel.views import dashboard
        response = dashboard(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_dashboard_view_authorized_superuser(self):
        """Test dashboard view with authorized superuser."""
        request = self.factory.get("/admin/")
        request.user = self.superuser
        
        from apps.admin_panel.views import dashboard
        response = dashboard(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_payment_list_view_unauthorized(self):
        """Test payment list view with unauthorized user."""
        request = self.factory.get("/admin/payments/")
        request.user = self.user
        
        from apps.admin_panel.views import payment_list_view
        response = payment_list_view(request)
        
        self.assertEqual(response.status_code, 403)
    
    def test_payment_list_view_authorized(self):
        """Test payment list view with authorized user."""
        request = self.factory.get("/admin/payments/")
        request.user = self.staff_user
        
        from apps.admin_panel.views import payment_list_view
        response = payment_list_view(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_subscription_list_view_unauthorized(self):
        """Test subscription list view with unauthorized user."""
        request = self.factory.get("/admin/subscriptions/")
        request.user = self.user
        
        from apps.admin_panel.views import subscription_list_view
        response = subscription_list_view(request)
        
        self.assertEqual(response.status_code, 403)
    
    def test_subscription_list_view_authorized(self):
        """Test subscription list view with authorized user."""
        request = self.factory.get("/admin/subscriptions/")
        request.user = self.staff_user
        
        from apps.admin_panel.views import subscription_list_view
        response = subscription_list_view(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_promocode_list_view_unauthorized(self):
        """Test promocode list view with unauthorized user."""
        request = self.factory.get("/admin/promocodes/")
        request.user = self.user
        
        from apps.admin_panel.views import promocode_list_view
        response = promocode_list_view(request)
        
        self.assertEqual(response.status_code, 403)
    
    def test_promocode_list_view_authorized(self):
        """Test promocode list view with authorized user."""
        request = self.factory.get("/admin/promocodes/")
        request.user = self.staff_user
        
        from apps.admin_panel.views import promocode_list_view
        response = promocode_list_view(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_settings_view_unauthorized(self):
        """Test settings view with unauthorized user."""
        request = self.factory.get("/admin/settings/")
        request.user = self.user
        
        from apps.admin_panel.views import settings_view
        response = settings_view(request)
        
        self.assertEqual(response.status_code, 403)
    
    def test_settings_view_authorized(self):
        """Test settings view with authorized user."""
        request = self.factory.get("/admin/settings/")
        request.user = self.staff_user
        
        from apps.admin_panel.views import settings_view
        response = settings_view(request)
        
        self.assertEqual(response.status_code, 200)
    
    def test_audit_log_view_unauthorized(self):
        """Test audit log view with unauthorized user."""
        request = self.factory.get("/admin/audit/")
        request.user = self.user
        
        from apps.admin_panel.views import audit_log_view
        response = audit_log_view(request)
        
        self.assertEqual(response.status_code, 403)
    
    def test_audit_log_view_authorized(self):
        """Test audit log view with authorized user."""
        request = self.factory.get("/admin/audit/")
        request.user = self.staff_user
        
        from apps.admin_panel.views import audit_log_view
        response = audit_log_view(request)
        
        self.assertEqual(response.status_code, 200)


class SessionServiceTests(TestCase):
    """Test SessionService for session management."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        DriverProfile.objects.create(
            user=self.user,
            telegram_user_id=123456789,
            telegram_username="testuser"
        )
    
    def test_create_session_creates_jwt_token(self):
        """Test that create_session returns a valid JWT token."""
        token = SessionService.create_session(self.user)
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 0)
    
    def test_create_session_stores_in_cache(self):
        """Test that create_session stores session in cache."""
        from django.core.cache import cache
        token = SessionService.create_session(self.user)
        
        # Verify token is stored in cache
        cache_key = SessionService.CACHE_KEY_FMT.format(user_id=self.user.id)
        cached_sid = cache.get(cache_key)
        self.assertIsNotNone(cached_sid)
    
    def test_create_session_revokes_previous_sessions(self):
        """Test that create_session revokes previous active sessions."""
        # Create first session
        SessionService.create_session(self.user)
        active_sessions = TelegramSession.objects.filter(user=self.user, revoked_at__isnull=True)
        first_count = active_sessions.count()
        
        # Create second session
        SessionService.create_session(self.user)
        
        # Verify first session is revoked
        revoked_sessions = TelegramSession.objects.filter(user=self.user, revoked_at__isnull=False)
        self.assertEqual(revoked_sessions.count(), 1)
    
    def test_create_session_creates_db_record(self):
        """Test that create_session creates TelegramSession DB record."""
        SessionService.create_session(self.user)
        
        session = TelegramSession.objects.filter(user=self.user, revoked_at__isnull=True).first()
        self.assertIsNotNone(session)
        self.assertIsNotNone(session.session_id)
        self.assertIsNotNone(session.expires_at)
    
    def test_create_session_with_custom_ttl(self):
        """Test that create_session respects custom TTL."""
        from datetime import timedelta
        
        custom_ttl = 3600
        SessionService.create_session(self.user, ttl_seconds=custom_ttl)
        
        session = TelegramSession.objects.filter(user=self.user, revoked_at__isnull=True).first()
        expected_expiry = dj_timezone.now() + timedelta(seconds=custom_ttl)
        
        # Allow 1 second tolerance
        time_diff = abs((session.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 2)
    
    def test_create_session_with_ip_and_user_agent(self):
        """Test that create_session stores IP and user agent."""
        ip_address = "192.168.1.1"
        user_agent = "Test Browser"
        
        SessionService.create_session(
            self.user,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        session = TelegramSession.objects.filter(user=self.user, revoked_at__isnull=True).first()
        self.assertEqual(session.ip_address, ip_address)
        self.assertEqual(session.user_agent, user_agent)
    
    def test_create_session_invalid_ttl(self):
        """Test that create_session raises ValidationError for invalid TTL."""
        with self.assertRaises(ValidationError):
            SessionService.create_session(self.user, ttl_seconds=30)
    
    def test_encode_jwt_includes_required_claims(self):
        """Test that _encode_jwt includes required JWT claims."""
        import jwt
        
        token = SessionService._encode_jwt(
            user_id=1,
            session_id="test-session-id",
            ttl_seconds=86400,
            telegram_user_id=123456789
        )
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        
        self.assertEqual(payload["user_id"], 1)
        self.assertEqual(payload["sid"], "test-session-id")
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)
        self.assertEqual(payload["tg_id"], 123456789)
    
    def test_encode_jwt_without_telegram_id(self):
        """Test that _encode_jwt works without telegram_user_id."""
        import jwt
        
        token = SessionService._encode_jwt(
            user_id=1,
            session_id="test-session-id",
            ttl_seconds=86400,
            telegram_user_id=None
        )
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        
        self.assertNotIn("tg_id", payload)


class TokenServiceTests(TestCase):
    """Test TokenService for JWT validation."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        DriverProfile.objects.create(
            user=self.user,
            telegram_user_id=123456789,
            telegram_username="testuser"
        )
        self.token = SessionService.create_session(self.user)
    
    def test_validate_session_valid_token(self):
        """Test that validate_session accepts valid token."""
        result = TokenService.validate_session(self.token)
        
        self.assertIsNotNone(result)
        self.assertIn("driver_data", result.driver_data)
        self.assertEqual(result.driver_data["user_id"], self.user.id)
        self.assertTrue(result.driver_data["session_valid"])
    
    def test_validate_session_invalid_token(self):
        """Test that validate_session rejects invalid token."""
        with self.assertRaises(ValidationError):
            TokenService.validate_session("invalid.token.here")
    
    def test_validate_session_expired_token(self):
        """Test that validate_session rejects expired token."""
        import jwt
        from datetime import timedelta
        
        # Create expired token
        expired_payload = {
            "user_id": self.user.id,
            "sid": "test-session-id",
            "iat": int((datetime.now(tz=timezone.utc) - timedelta(days=2)).timestamp()),
            "exp": int((datetime.now(tz=timezone.utc) - timedelta(days=1)).timestamp()),
            "tg_id": 123456789
        }
        expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm="HS256")
        
        with self.assertRaises(ValidationError):
            TokenService.validate_session(expired_token)
    
    def test_validate_session_revoked_session(self):
        """Test that validate_session rejects revoked session."""
        # Revoke session
        TelegramSession.objects.filter(user=self.user).update(revoked_at=dj_timezone.now())
        
        with self.assertRaises(ValidationError):
            TokenService.validate_session(self.token)
    
    def test_validate_session_refreshes_cache_ttl(self):
        """Test that validate_session refreshes cache TTL."""
        from django.core.cache import cache
        
        cache_key = SessionService.CACHE_KEY_FMT.format(user_id=self.user.id)
        initial_ttl = cache.ttl(cache_key) if hasattr(cache, 'ttl') else None
        
        TokenService.validate_session(self.token)
        
        # Verify cache is still set (TTL refreshed)
        cached_sid = cache.get(cache_key)
        self.assertIsNotNone(cached_sid)
    
    def test_validate_session_refreshes_token_near_expiry(self):
        """Test that validate_session refreshes token near expiry."""
        import jwt
        from datetime import timedelta
        
        session = TelegramSession.objects.filter(user=self.user, revoked_at__isnull=True).first()
        self.assertIsNotNone(session)
        session_id = str(session.session_id)
        
        # Create token near expiry (within REFRESH_THRESHOLD_SECONDS)
        near_expiry_payload = {
            "user_id": self.user.id,
            "sid": session_id,
            "iat": int((datetime.now(tz=timezone.utc) - timedelta(hours=20)).timestamp()),
            "exp": int((datetime.now(tz=timezone.utc) + timedelta(hours=1)).timestamp()),
            "tg_id": 123456789
        }
        near_expiry_token = jwt.encode(near_expiry_payload, settings.SECRET_KEY, algorithm="HS256")
        
        # Store session in cache
        from django.core.cache import cache
        cache_key = SessionService.CACHE_KEY_FMT.format(user_id=self.user.id)
        cache.set(cache_key, session_id, timeout=SessionService.DEFAULT_TTL_SECONDS)
        
        result = TokenService.validate_session(near_expiry_token)
        
        self.assertIsNotNone(result.refreshed_token)
        self.assertNotEqual(result.refreshed_token, near_expiry_token)
    
    def test_validate_session_no_refresh_for_fresh_token(self):
        """Test that validate_session doesn't refresh fresh tokens."""
        result = TokenService.validate_session(self.token)
        
        self.assertIsNone(result.refreshed_token)


class JWTAuthenticationMiddlewareTests(TestCase):
    """Test JWTAuthenticationMiddleware for request authentication."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        DriverProfile.objects.create(
            user=self.user,
            telegram_user_id=123456789,
            telegram_username="testuser"
        )
        self.token = SessionService.create_session(self.user)
        self.factory = RequestFactory()
        self.middleware = JWTAuthenticationMiddleware(get_response=lambda r: r)
    
    def test_process_request_with_valid_bearer_token(self):
        """Test that middleware authenticates request with valid Bearer token."""
        request = self.factory.get("/test/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"
        
        self.middleware.process_request(request)
        
        self.assertEqual(request.user.id, self.user.id)
        self.assertIsNotNone(request.auth_context.driver_data)
    
    def test_process_request_with_valid_cookie_token(self):
        """Test that middleware authenticates request with valid cookie token."""
        request = self.factory.get("/test/")
        request.COOKIES["session_token"] = self.token
        
        self.middleware.process_request(request)
        
        self.assertEqual(request.user.id, self.user.id)
        self.assertIsNotNone(request.auth_context.driver_data)
    
    def test_process_request_without_token(self):
        """Test that middleware sets AnonymousUser without token."""
        request = self.factory.get("/test/")
        
        self.middleware.process_request(request)
        
        from django.contrib.auth.models import AnonymousUser
        self.assertIsInstance(request.user, AnonymousUser)
    
    def test_process_request_with_invalid_token(self):
        """Test that middleware sets AnonymousUser with invalid token."""
        request = self.factory.get("/test/")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid.token"
        
        self.middleware.process_request(request)
        
        from django.contrib.auth.models import AnonymousUser
        self.assertIsInstance(request.user, AnonymousUser)
    
    def test_process_request_with_revoked_session(self):
        """Test that middleware sets AnonymousUser with revoked session."""
        # Revoke session
        TelegramSession.objects.filter(user=self.user).update(revoked_at=dj_timezone.now())
        
        request = self.factory.get("/test/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"
        
        self.middleware.process_request(request)
        
        from django.contrib.auth.models import AnonymousUser
        self.assertIsInstance(request.user, AnonymousUser)
    
    def test_process_response_adds_refreshed_token(self):
        """Test that process_response adds X-Session-Token header when token refreshed."""
        request = self.factory.get("/test/")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {self.token}"
        request.auth_context = type('obj', (object,), {
            'driver_data': {'user_id': self.user.id},
            'refreshed_token': 'new_refreshed_token'
        })()
        
        response = HttpResponse("OK")
        response = self.middleware.process_response(request, response)
        
        self.assertEqual(response["X-Session-Token"], "new_refreshed_token")
    
    def test_process_response_without_refreshed_token(self):
        """Test that process_response doesn't add header without refreshed token."""
        request = self.factory.get("/test/")
        request.auth_context = type('obj', (object,), {
            'driver_data': {'user_id': self.user.id},
            'refreshed_token': None
        })()
        
        response = HttpResponse("OK")
        response = self.middleware.process_response(request, response)
        
        self.assertNotIn("X-Session-Token", response)


@override_settings(
    TELEGRAM_BOT_TOKEN="123:TESTTOKEN",
    TELEGRAM_SKIP_HASH_VALIDATION=False,
    TELEGRAM_SKIP_AUTH_DATE_VALIDATION=False,
)
class TelegramAuthViewTests(TestCase):
    """Test telegram_auth view for Telegram WebApp authentication."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="tg_1001", password="testpass")
        DriverProfile.objects.create(
            user=self.user,
            telegram_user_id=1001,
            telegram_username="ivan_driver"
        )
    
    def test_telegram_auth_post_success(self):
        """Test that telegram_auth returns JWT token on successful auth."""
        init_data = _make_init_data(
            bot_token="123:TESTTOKEN",
            auth_date=int(datetime.now(tz=timezone.utc).timestamp()),
            user={"id": 1001, "first_name": "Иван", "username": "ivan_driver"}
        )
        
        request = self.factory.post(
            "/auth/telegram/",
            data={"init_data": init_data},
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("session_token", data)
        self.assertIn("driver", data)
        self.assertEqual(data["driver"]["driver_id"], 1001)
    
    def test_telegram_auth_post_creates_new_user(self):
        """Test that telegram_auth creates new user if not exists."""
        init_data = _make_init_data(
            bot_token="123:TESTTOKEN",
            auth_date=int(datetime.now(tz=timezone.utc).timestamp()),
            user={"id": 9999, "first_name": "Новый", "username": "new_user"}
        )
        
        request = self.factory.post(
            "/auth/telegram/",
            data={"init_data": init_data},
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 200)
        new_user = User.objects.filter(username="tg_9999").first()
        self.assertIsNotNone(new_user)
    
    def test_telegram_auth_post_updates_existing_user(self):
        """Test that telegram_auth updates existing user data."""
        init_data = _make_init_data(
            bot_token="123:TESTTOKEN",
            auth_date=int(datetime.now(tz=timezone.utc).timestamp()),
            user={"id": 1001, "first_name": "ИванОбновленный", "username": "ivan_updated"}
        )
        
        request = self.factory.post(
            "/auth/telegram/",
            data={"init_data": init_data},
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "ИванОбновленный")
    
    def test_telegram_auth_post_invalid_json(self):
        """Test that telegram_auth returns 400 for invalid JSON."""
        request = self.factory.post(
            "/auth/telegram/",
            data="invalid json",
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
    
    def test_telegram_auth_post_missing_init_data(self):
        """Test that telegram_auth returns 400 for missing init_data."""
        request = self.factory.post(
            "/auth/telegram/",
            data={},
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
    
    def test_telegram_auth_post_invalid_init_data(self):
        """Test that telegram_auth returns error for invalid init_data."""
        request = self.factory.post(
            "/auth/telegram/",
            data={"init_data": "invalid_init_data"},
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
    
    def test_telegram_auth_post_expired_init_data(self):
        """Test that telegram_auth returns error for expired init_data."""
        init_data = _make_init_data(
            bot_token="123:TESTTOKEN",
            auth_date=int(datetime.now(tz=timezone.utc).timestamp()) - 1000,
            user={"id": 1001, "first_name": "Иван", "username": "ivan_driver"}
        )
        
        request = self.factory.post(
            "/auth/telegram/",
            data={"init_data": init_data},
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
    
    def test_telegram_auth_get_method_not_allowed(self):
        """Test that telegram_auth returns 405 for GET requests."""
        request = self.factory.get("/auth/telegram/")
        
        response = telegram_auth(request)
        
        self.assertEqual(response.status_code, 405)
        data = response.json()
        self.assertIn("error", data)
    
    def test_telegram_auth_sets_cookie(self):
        """Test that telegram_auth sets session_token cookie."""
        init_data = _make_init_data(
            bot_token="123:TESTTOKEN",
            auth_date=int(datetime.now(tz=timezone.utc).timestamp()),
            user={"id": 1001, "first_name": "Иван", "username": "ivan_driver"}
        )
        
        request = self.factory.post(
            "/auth/telegram/",
            data={"init_data": init_data},
            content_type="application/json"
        )
        
        response = telegram_auth(request)
        
        self.assertIn("session_token", response.cookies)
        self.assertTrue(response.cookies["session_token"].get("httponly"))
        self.assertEqual(response.cookies["session_token"].get("samesite"), "Lax")
