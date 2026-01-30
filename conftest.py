"""
Pytest configuration and fixtures for Django tests.

This module provides common fixtures used across all test modules.
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, MagicMock

from django.contrib.auth import get_user_model
from django.test import RequestFactory as DjangoRequestFactory
from django.utils import timezone as dj_timezone

from apps.auth.models import DriverProfile, TelegramSession
from apps.subscriptions.models import Subscription
from apps.payments.models import Payment
from apps.audit.models import AuditLog

User = get_user_model()

"""
GOAL: Sync CDN-related runtime settings back to config.settings.base for tests that inspect the base module.

PARAMETERS:
  django_settings: Any - django.conf.settings (or compatible) object - Must provide CDN_* attributes

RETURNS:
  None - Updates config.settings.base module attributes in-place

RAISES:
  None

GUARANTEES:
  - base.CDN_ENABLED, base.CDN_URL, base.CDN_STATIC_PREFIX are updated from django_settings
  - base.STATIC_URL matches the CDN configuration when enabled, otherwise equals "static/"
"""
def _sync_cdn_settings_to_base(django_settings: Any) -> None:
    """
    Keep config.settings.base in sync with overridden settings used during tests.
    """
    from config.settings import base

    base.CDN_ENABLED = bool(getattr(django_settings, "CDN_ENABLED", False))
    base.CDN_URL = str(getattr(django_settings, "CDN_URL", "") or "")
    base.CDN_STATIC_PREFIX = str(getattr(django_settings, "CDN_STATIC_PREFIX", "static") or "static")

    if base.CDN_ENABLED and base.CDN_URL:
        static_url = f"{base.CDN_URL.rstrip('/')}/{base.CDN_STATIC_PREFIX.lstrip('/')}/"
    else:
        static_url = "static/"

    base.STATIC_URL = static_url
    setattr(django_settings, "STATIC_URL", static_url)

    try:
        from django.contrib.staticfiles.storage import staticfiles_storage
        from django.utils.functional import empty

        staticfiles_storage._wrapped = empty
    except Exception:
        pass


class _SettingsProxy:
    def __init__(self, settings_obj: Any) -> None:
        object.__setattr__(self, "_settings", settings_obj)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_settings"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        settings_obj = object.__getattribute__(self, "_settings")
        setattr(settings_obj, name, value)
        if name in {"CDN_ENABLED", "CDN_URL", "CDN_STATIC_PREFIX"}:
            _sync_cdn_settings_to_base(settings_obj)

    def __delattr__(self, name: str) -> None:
        settings_obj = object.__getattribute__(self, "_settings")
        delattr(settings_obj, name)
        if name in {"CDN_ENABLED", "CDN_URL", "CDN_STATIC_PREFIX"}:
            _sync_cdn_settings_to_base(settings_obj)


@pytest.fixture
def rf():
    """
    GOAL: Provide a Django RequestFactory for creating test requests.

    RETURNS:
      RequestFactory - Django request factory instance

    GUARANTEES:
      - Can create mock requests for testing
      - Supports all HTTP methods
    """
    return DjangoRequestFactory()


@pytest.fixture
def settings(settings):
    """
    GOAL: Provide Django settings object for test configuration.

    RETURNS:
      Settings - Django settings object

    GUARANTEES:
      - Settings can be modified for individual tests
      - Changes are isolated per test
    """
    # Ensure API CSRF settings are available
    if not hasattr(settings, "API_CSRF_ENABLED"):
        settings.API_CSRF_ENABLED = True
    if not hasattr(settings, "API_CSRF_ALLOWED_ORIGINS"):
        settings.API_CSRF_ALLOWED_ORIGINS = []
    if not hasattr(settings, "API_CSRF_ALLOW_SAME_ORIGIN"):
        settings.API_CSRF_ALLOW_SAME_ORIGIN = True
    
    # Ensure Telegram settings are available
    if not hasattr(settings, "TELEGRAM_BOT_TOKEN"):
        settings.TELEGRAM_BOT_TOKEN = "123:TESTTOKEN"
    
    # Ensure CargoTech settings are available
    if not hasattr(settings, "CARGOTECH_PHONE"):
        settings.CARGOTECH_PHONE = "+79001234567"
    if not hasattr(settings, "CARGOTECH_PASSWORD"):
        settings.CARGOTECH_PASSWORD = "testpassword"
    if not hasattr(settings, "CARGOTECH_TOKEN_CACHE_TTL"):
        settings.CARGOTECH_TOKEN_CACHE_TTL = 86400
    
    # Ensure YuKassa settings are available
    if not hasattr(settings, "YOOKASSA_SHOP_ID"):
        settings.YOOKASSA_SHOP_ID = "test_shop_id"
    if not hasattr(settings, "YOOKASSA_SECRET_KEY"):
        settings.YOOKASSA_SECRET_KEY = "test_secret_key"

    if not hasattr(settings, "CDN_ENABLED"):
        settings.CDN_ENABLED = False
    if not hasattr(settings, "CDN_URL"):
        settings.CDN_URL = ""
    if not hasattr(settings, "CDN_STATIC_PREFIX"):
        settings.CDN_STATIC_PREFIX = "static"

    _sync_cdn_settings_to_base(settings)
     
    return _SettingsProxy(settings)


@pytest.fixture
def client():
    """
    GOAL: Provide a Django test client for making HTTP requests.

    RETURNS:
      Client - Django test client instance

    GUARANTEES:
      - Can make requests to views
      - Supports all HTTP methods
    """
    from django.test import Client
    return Client()


@pytest.fixture
def auth_driver(db, client):
    """
    GOAL: Create and authenticate a driver user for testing.

    RETURNS:
      User - Authenticated driver user

    GUARANTEES:
      - User has DriverProfile
      - User is authenticated in the client
    """
    # Create user
    user = User.objects.create_user(
        username="test_driver",
        first_name="Test",
        password="testpass123"
    )
    
    # Create driver profile
    DriverProfile.objects.create(
        user=user,
        telegram_user_id=123456789,
        telegram_username="test_driver"
    )
    
    # Force authentication
    client.force_login(user)
    
    return user


@pytest.fixture
def user(db):
    """
    GOAL: Create a regular user for testing.

    RETURNS:
      User - Regular user instance

    GUARANTEES:
      - User is created in database
      - User has no special permissions
    """
    return User.objects.create_user(
        username="testuser",
        first_name="Test",
        last_name="User",
        password="testpass123"
    )


@pytest.fixture
def staff_user(db):
    """
    GOAL: Create a staff user for testing.

    RETURNS:
      User - Staff user instance

    GUARANTEES:
      - User has is_staff=True
      - User can access admin panel
    """
    return User.objects.create_user(
        username="staffuser",
        first_name="Staff",
        last_name="User",
        password="testpass123",
        is_staff=True
    )


@pytest.fixture
def superuser(db):
    """
    GOAL: Create a superuser for testing.

    RETURNS:
      User - Superuser instance

    GUARANTEES:
      - User has is_staff=True and is_superuser=True
      - User has all permissions
    """
    return User.objects.create_superuser(
        username="admin",
        first_name="Admin",
        last_name="User",
        password="testpass123"
    )


@pytest.fixture
def driver_profile(user):
    """
    GOAL: Create a driver profile for a user.

    PARAMETERS:
      user: User - User to create profile for

    RETURNS:
      DriverProfile - Driver profile instance

    GUARANTEES:
      - DriverProfile is linked to user
      - Telegram user ID is set
    """
    return DriverProfile.objects.create(
        user=user,
        telegram_user_id=123456789,
        telegram_username="test_driver"
    )


@pytest.fixture
def telegram_session(user):
    """
    GOAL: Create a Telegram session for a user.

    PARAMETERS:
      user: User - User to create session for

    RETURNS:
      TelegramSession - Telegram session instance

    GUARANTEES:
      - Session is active (not revoked)
      - Session has expiration date
    """
    return TelegramSession.objects.create(
        user=user,
        expires_at=dj_timezone.now() + timedelta(days=1),
        ip_address="127.0.0.1",
        user_agent="Test Agent"
    )


@pytest.fixture
def active_subscription(user):
    """
    GOAL: Create an active subscription for a user.

    PARAMETERS:
      user: User - User to create subscription for

    RETURNS:
      Subscription - Active subscription instance

    GUARANTEES:
      - Subscription is active
      - Subscription is not expired
    """
    return Subscription.objects.create(
        user=user,
        is_active=True,
        expires_at=dj_timezone.now() + timedelta(days=30)
    )


@pytest.fixture
def expired_subscription(user):
    """
    GOAL: Create an expired subscription for a user.

    PARAMETERS:
      user: User - User to create subscription for

    RETURNS:
      Subscription - Expired subscription instance

    GUARANTEES:
      - Subscription is inactive
      - Subscription is expired
    """
    return Subscription.objects.create(
        user=user,
        is_active=False,
        expires_at=dj_timezone.now() - timedelta(days=1)
    )


@pytest.fixture
def payment(user):
    """
    GOAL: Create a payment for a user.

    PARAMETERS:
      user: User - User to create payment for

    RETURNS:
      Payment - Payment instance

    GUARANTEES:
      - Payment is in pending state
      - Payment has amount and tariff
    """
    return Payment.objects.create(
        user=user,
        amount=Decimal("499.00"),
        currency="RUB",
        subscription_days=30,
        tariff_name="1_month",
        description="Подписка на 30 дней",
        status=Payment.STATUS_PENDING
    )


@pytest.fixture
def audit_log(user):
    """
    GOAL: Create an audit log entry for a user.

    PARAMETERS:
      user: User - User to create audit log for

    RETURNS:
      AuditLog - Audit log instance

    GUARANTEES:
      - Audit log has action type and action
      - Audit log is linked to user
    """
    return AuditLog.objects.create(
        user_id=user.id,
        action_type="test",
        action="Test action",
        target_id="test_target"
    )


@pytest.fixture
def mock_requests():
    """
    GOAL: Provide a mock for requests library.

    RETURNS:
      Mock - Mocked requests module

    GUARANTEES:
      - Can mock HTTP requests
      - Can control response behavior
    """
    return MagicMock()


@pytest.fixture
def mock_cache():
    """
    GOAL: Provide a mock for Django cache.

    RETURNS:
      Mock - Mocked cache instance

    GUARANTEES:
      - Can mock cache operations
      - Can control cache behavior
    """
    return MagicMock()


@pytest.fixture
def sample_cargo_data():
    """
    GOAL: Provide sample cargo data for testing.

    RETURNS:
      dict - Sample cargo data from CargoTech API

    GUARANTEES:
      - Data matches CargoTech API structure
      - All required fields are present
    """
    return {
        "id": "12345",
        "weight": 15000,
        "volume": 65,
        "price": 352500,
        "points": {
            "start": {
                "city": {"name": "Москва"},
                "address": "ул. Тестовая, 1",
                "first_date": "2024-01-15"
            },
            "finish": {
                "city": {"name": "Санкт-Петербург"},
                "address": "ул. Тестовая, 2",
                "first_date": "2024-01-16"
            }
        },
        "load_types": [{"short_name": "Задняя"}],
        "truck_types": [{"short_name": "Тент"}]
    }


@pytest.fixture
def sample_cargo_detail_data():
    """
    GOAL: Provide sample cargo detail data for testing.

    RETURNS:
      dict - Sample cargo detail data from CargoTech API

    GUARANTEES:
      - Data matches CargoTech API structure
      - Includes contact information
    """
    return {
        "id": "12345",
        "weight": 15000,
        "volume": 65,
        "price": 352500,
        "distance": 700,
        "points": {
            "start": {
                "city": {"name": "Москва"},
                "address": "ул. Тестовая, 1",
                "first_date": "2024-01-15"
            },
            "finish": {
                "city": {"name": "Санкт-Петербург"},
                "address": "ул. Тестовая, 2",
                "first_date": "2024-01-16"
            }
        },
        "shipper": {
            "name": "ООО Тестовая Компания",
            "inn": "1234567890"
        },
        "extra": {
            "note": "Тестовый комментарий"
        }
    }


@pytest.fixture
def sample_city_data():
    """
    GOAL: Provide sample city data for testing.

    RETURNS:
      dict - Sample city data from CargoTech API

    GUARANTEES:
      - Data matches CargoTech API structure
      - Includes city name and ID
    """
    return {
        "id": 1,
        "name": "Москва",
        "type": "city"
    }


@pytest.fixture
def sample_yukassa_payment_response():
    """
    GOAL: Provide sample YuKassa payment response for testing.

    RETURNS:
      dict - Sample YuKassa payment response

    GUARANTEES:
      - Data matches YuKassa API structure
      - Includes payment ID and confirmation URL
    """
    return {
        "id": "test_payment_id",
        "status": "pending",
        "amount": {
            "value": "499.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "confirmation_url": "https://test.example.com/confirm"
        },
        "metadata": {
            "payment_id": "1",
            "user_id": "1",
            "tariff": "1_month"
        }
    }


@pytest.fixture
def monkeypatch():
    """
    GOAL: Provide monkeypatch fixture for mocking.

    RETURNS:
      MonkeyPatch - Pytest monkeypatch fixture

    GUARANTEES:
      - Can mock any object during tests
      - Changes are reverted after test
    """
    return pytest.MonkeyPatch()


@pytest.fixture
def freeze_time(monkeypatch):
    """
    GOAL: Freeze time for testing time-sensitive operations.

    RETURNS:
      function - Function to set frozen time

    GUARANTEES:
      - Time can be frozen to specific datetime
      - All time operations use frozen time
    """
    frozen_time = None

    def _freeze(dt: datetime):
        nonlocal frozen_time
        frozen_time = dt
        monkeypatch.setattr("django.utils.timezone.now", lambda: dt)

    return _freeze


@pytest.fixture
def telegram_init_data():
    """
    GOAL: Provide valid Telegram initData for testing.

    RETURNS:
      str - Valid Telegram initData string

    GUARANTEES:
      - initData has valid hash
      - initData includes user information
    """
    import hashlib
    import hmac
    import json
    from urllib.parse import urlencode
    
    bot_token = "123:TESTTOKEN"
    auth_date = int(datetime.now(tz=timezone.utc).timestamp())
    user = {"id": 1001, "first_name": "Иван", "username": "ivan_driver"}
    
    data = {
        "auth_date": str(auth_date),
        "query_id": "AAHtest",
        "user": json.dumps(user, separators=(",", ":"))
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    hash_value = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    data["hash"] = hash_value
    
    return urlencode(data)
