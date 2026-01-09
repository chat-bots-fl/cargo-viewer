"""
Unit tests for apps/payments/.

This module contains tests for payment service and YuKassa client.
"""

from __future__ import annotations

from unittest.mock import Mock, patch
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from requests.exceptions import HTTPError

from apps.payments.services import YuKassaClient, PaymentService, YuKassaAPIError
from apps.payments.models import Payment, PaymentHistory
from apps.feature_flags.models import SystemSetting

User = get_user_model()


class YuKassaClientTests(TestCase):
    """Test YuKassaClient for YuKassa API integration."""
    
    def setUp(self):
        cache.clear()
    
    @override_settings(YOOKASSA_SHOP_ID="test_shop", YOOKASSA_SECRET_KEY="test_secret")
    def test_init_with_settings(self):
        """Test that YuKassaClient initializes with settings."""
        client = YuKassaClient()
        
        self.assertEqual(client.shop_id, "test_shop")
        self.assertEqual(client.secret_key, "test_secret")
    
    @patch('apps.payments.services.SystemSetting.get_setting')
    @override_settings(YOOKASSA_SHOP_ID="", YOOKASSA_SECRET_KEY="")
    def test_init_with_system_settings(self, mock_get_setting):
        """Test that YuKassaClient initializes with system settings."""
        mock_get_setting.side_effect = lambda key, default: {
            "yookassa_shop_id": "system_shop",
            "yookassa_secret_key": "system_secret"
        }.get(key, default)
        
        client = YuKassaClient()
        
        self.assertEqual(client.shop_id, "system_shop")
        self.assertEqual(client.secret_key, "system_secret")
    
    @override_settings(YOOKASSA_SHOP_ID="", YOOKASSA_SECRET_KEY="")
    def test_init_without_credentials(self):
        """Test that YuKassaClient raises YuKassaAPIError without credentials."""
        with self.assertRaises(YuKassaAPIError):
            YuKassaClient()
    
    @patch('apps.payments.services.requests.post')
    @override_settings(YOOKASSA_SHOP_ID="test_shop", YOOKASSA_SECRET_KEY="test_secret")
    def test_create_payment_success(self, mock_post):
        """Test that create_payment makes successful API call."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "test_payment_id",
            "status": "pending",
            "confirmation": {
                "type": "redirect",
                "confirmation_url": "https://test.example.com/confirm"
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        client = YuKassaClient()
        result = client.create_payment(
            amount=Decimal("499.00"),
            currency="RUB",
            description="Test payment",
            return_url="https://example.com/return",
            metadata={"user_id": 1}
        )
        
        self.assertEqual(result["id"], "test_payment_id")
        self.assertEqual(result["status"], "pending")
        mock_post.assert_called_once()
    
    @patch('apps.payments.services.requests.post')
    @override_settings(YOOKASSA_SHOP_ID="test_shop", YOOKASSA_SECRET_KEY="test_secret")
    def test_create_payment_http_error(self, mock_post):
        """Test that create_payment raises YuKassaAPIError on HTTP error."""
        mock_post.side_effect = HTTPError("500 Internal Server Error")
        
        client = YuKassaClient()
        
        with self.assertRaises(YuKassaAPIError):
            client.create_payment(
                amount=Decimal("499.00"),
                currency="RUB",
                description="Test payment",
                return_url="https://example.com/return",
                metadata={}
            )
    
    @patch('apps.payments.services.requests.get')
    @override_settings(YOOKASSA_SHOP_ID="test_shop", YOOKASSA_SECRET_KEY="test_secret")
    def test_get_payment_success(self, mock_get):
        """Test that get_payment makes successful API call."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "test_payment_id",
            "status": "succeeded",
            "amount": {"value": "499.00", "currency": "RUB"}
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        client = YuKassaClient()
        result = client.get_payment(payment_id="test_payment_id")
        
        self.assertEqual(result["id"], "test_payment_id")
        self.assertEqual(result["status"], "succeeded")
        mock_get.assert_called_once()
    
    @patch('apps.payments.services.requests.get')
    @override_settings(YOOKASSA_SHOP_ID="test_shop", YOOKASSA_SECRET_KEY="test_secret")
    def test_get_payment_http_error(self, mock_get):
        """Test that get_payment raises YuKassaAPIError on HTTP error."""
        mock_get.side_effect = HTTPError("404 Not Found")
        
        client = YuKassaClient()
        
        with self.assertRaises(YuKassaAPIError):
            client.get_payment(payment_id="test_payment_id")


class PaymentServiceTests(TestCase):
    """Test PaymentService for payment creation and management."""
    
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="testuser", password="testpass")
    
    @patch('apps.payments.services.YuKassaClient')
    @patch('apps.payments.services.AuditService.log')
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_success(self, mock_get_setting, mock_audit, mock_client):
        """Test that create_payment creates payment successfully."""
        mock_get_setting.side_effect = lambda key, default: {
            "payments_enabled": True,
            "tariffs": PaymentService.DEFAULT_TARIFFS
        }.get(key, default)
        
        mock_yukassa = Mock()
        mock_yukassa.create_payment.return_value = {
            "id": "yookassa_payment_id",
            "confirmation": {"confirmation_url": "https://test.example.com/confirm"}
        }
        mock_client.return_value = mock_yukassa
        
        payment = PaymentService.create_payment(
            user=self.user,
            tariff_name="1_month",
            return_url="https://example.com/return"
        )
        
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.status, Payment.STATUS_PENDING)
        self.assertEqual(payment.amount, Decimal("499.00"))
        self.assertEqual(payment.tariff_name, "1_month")
        self.assertEqual(payment.yukassa_payment_id, "yookassa_payment_id")
        self.assertEqual(payment.confirmation_url, "https://test.example.com/confirm")
        mock_audit.assert_called()
    
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_disabled(self, mock_get_setting):
        """Test that create_payment raises SystemError when payments disabled."""
        mock_get_setting.return_value = False
        
        from builtins import SystemError
        with self.assertRaises(SystemError):
            PaymentService.create_payment(
                user=self.user,
                tariff_name="1_month",
                return_url="https://example.com/return"
            )
    
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_invalid_tariff(self, mock_get_setting):
        """Test that create_payment raises ValidationError for invalid tariff."""
        mock_get_setting.side_effect = lambda key, default: {
            "payments_enabled": True,
            "tariffs": PaymentService.DEFAULT_TARIFFS
        }.get(key, default)
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                user=self.user,
                tariff_name="invalid_tariff",
                return_url="https://example.com/return"
            )
    
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_invalid_return_url(self, mock_get_setting):
        """Test that create_payment raises ValidationError for invalid return_url."""
        mock_get_setting.side_effect = lambda key, default: {
            "payments_enabled": True,
            "tariffs": PaymentService.DEFAULT_TARIFFS
        }.get(key, default)
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            PaymentService.create_payment(
                user=self.user,
                tariff_name="1_month",
                return_url="invalid_url"
            )
    
    @patch('apps.payments.services.YuKassaClient')
    @patch('apps.payments.services.AuditService.log')
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_idempotent(self, mock_get_setting, mock_audit, mock_client):
        """Test that create_payment returns existing payment within 5 minutes."""
        mock_get_setting.side_effect = lambda key, default: {
            "payments_enabled": True,
            "tariffs": PaymentService.DEFAULT_TARIFFS
        }.get(key, default)
        
        # Create existing payment
        existing_payment = Payment.objects.create(
            user=self.user,
            amount=Decimal("499.00"),
            currency="RUB",
            subscription_days=30,
            tariff_name="1_month",
            description="Подписка на 30 дней",
            status=Payment.STATUS_PENDING
        )
        
        payment = PaymentService.create_payment(
            user=self.user,
            tariff_name="1_month",
            return_url="https://example.com/return"
        )
        
        self.assertEqual(payment.id, existing_payment.id)
        mock_client.assert_not_called()
    
    @patch('apps.payments.services.YuKassaClient')
    @patch('apps.payments.services.AuditService.log')
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_creates_history(self, mock_get_setting, mock_audit, mock_client):
        """Test that create_payment creates payment history."""
        mock_get_setting.side_effect = lambda key, default: {
            "payments_enabled": True,
            "tariffs": PaymentService.DEFAULT_TARIFFS
        }.get(key, default)
        
        mock_yukassa = Mock()
        mock_yukassa.create_payment.return_value = {
            "id": "yookassa_payment_id",
            "confirmation": {"confirmation_url": "https://test.example.com/confirm"}
        }
        mock_client.return_value = mock_yukassa
        
        PaymentService.create_payment(
            user=self.user,
            tariff_name="1_month",
            return_url="https://example.com/return"
        )
        
        history_count = PaymentHistory.objects.filter(payment__user=self.user).count()
        self.assertGreater(history_count, 0)
    
    @patch('apps.payments.services.YuKassaClient')
    @patch('apps.payments.services.AuditService.log')
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_yukassa_error(self, mock_get_setting, mock_audit, mock_client):
        """Test that create_payment handles YuKassa errors."""
        mock_get_setting.side_effect = lambda key, default: {
            "payments_enabled": True,
            "tariffs": PaymentService.DEFAULT_TARIFFS
        }.get(key, default)
        
        mock_yukassa = Mock()
        mock_yukassa.create_payment.side_effect = YuKassaAPIError("YuKassa API Error")
        mock_client.return_value = mock_yukassa
        
        with self.assertRaises(YuKassaAPIError):
            PaymentService.create_payment(
                user=self.user,
                tariff_name="1_month",
                return_url="https://example.com/return"
            )
        
        # Verify payment was created but not updated with YuKassa data
        payment = Payment.objects.filter(user=self.user, tariff_name="1_month").first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, Payment.STATUS_PENDING)
        self.assertEqual(payment.yukassa_payment_id, "")
    
    @patch('apps.payments.services.YuKassaClient')
    @patch('apps.payments.services.AuditService.log')
    @patch('apps.payments.services.SystemSetting.get_setting')
    def test_create_payment_custom_tariffs(self, mock_get_setting, mock_audit, mock_client):
        """Test that create_payment uses custom tariffs from SystemSetting."""
        custom_tariffs = {
            "custom_month": {"price": "999.00", "days": 60}
        }
        mock_get_setting.side_effect = lambda key, default: {
            "payments_enabled": True,
            "tariffs": custom_tariffs
        }.get(key, default)
        
        mock_yukassa = Mock()
        mock_yukassa.create_payment.return_value = {
            "id": "yookassa_payment_id",
            "confirmation": {"confirmation_url": "https://test.example.com/confirm"}
        }
        mock_client.return_value = mock_yukassa
        
        payment = PaymentService.create_payment(
            user=self.user,
            tariff_name="custom_month",
            return_url="https://example.com/return"
        )
        
        self.assertEqual(payment.amount, Decimal("999.00"))
        self.assertEqual(payment.subscription_days, 60)
