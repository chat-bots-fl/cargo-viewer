"""
Unit tests for apps/subscriptions/.

This module contains tests for subscription service and subscription model.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone as dj_timezone

from apps.subscriptions.services import SubscriptionService
from apps.subscriptions.models import Subscription
from apps.payments.models import Payment
from apps.promocodes.models import PromoCode

User = get_user_model()


class SubscriptionModelTests(TestCase):
    """Test Subscription model methods."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
    
    def test_is_expired_true(self):
        """Test that is_expired returns True for expired subscription."""
        subscription = Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=dj_timezone.now() - timedelta(days=1)
        )
        
        self.assertTrue(subscription.is_expired())
    
    def test_is_expired_false(self):
        """Test that is_expired returns False for active subscription."""
        subscription = Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=dj_timezone.now() + timedelta(days=30)
        )
        
        self.assertFalse(subscription.is_expired())
    
    def test_is_expired_inactive(self):
        """Test that is_expired returns True for inactive subscription."""
        subscription = Subscription.objects.create(
            user=self.user,
            is_active=False,
            expires_at=dj_timezone.now() + timedelta(days=30)
        )
        
        self.assertTrue(subscription.is_expired())
    
    def test_extend_future_date(self):
        """Test that extend extends future expiration date."""
        subscription = Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=dj_timezone.now() + timedelta(days=30)
        )
        
        original_expires = subscription.expires_at
        subscription.extend(days=15)
        
        self.assertEqual(subscription.expires_at, original_expires + timedelta(days=15))
    
    def test_extend_past_date(self):
        """Test that extend extends from past date."""
        subscription = Subscription.objects.create(
            user=self.user,
            is_active=False,
            expires_at=dj_timezone.now() - timedelta(days=1)
        )
        
        subscription.extend(days=30)
        
        expected = dj_timezone.now() + timedelta(days=30)
        # Allow 1 second tolerance
        time_diff = abs((subscription.expires_at - expected).total_seconds())
        self.assertLess(time_diff, 2)
    
    def test_extend_activates_subscription(self):
        """Test that extend activates inactive subscription."""
        subscription = Subscription.objects.create(
            user=self.user,
            is_active=False,
            expires_at=dj_timezone.now() - timedelta(days=1)
        )
        
        subscription.extend(days=30)
        
        self.assertTrue(subscription.is_active)


class SubscriptionServiceTests(TestCase):
    """Test SubscriptionService for subscription management."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
    
    def test_activate_from_payment_creates_subscription(self):
        """Test that activate_from_payment creates new subscription."""
        payment = Payment.objects.create(
            user=self.user,
            amount=Decimal("499.00"),
            currency="RUB",
            subscription_days=30,
            tariff_name="1_month",
            description="Подписка на 30 дней",
            status=Payment.STATUS_SUCCEEDED
        )
        
        subscription = SubscriptionService.activate_from_payment(payment)
        
        self.assertEqual(subscription.user, self.user)
        self.assertTrue(subscription.is_active)
        self.assertIsNotNone(subscription.expires_at)
        
        # Verify expiration is approximately 30 days from now
        expected_expiry = dj_timezone.now() + timedelta(days=30)
        time_diff = abs((subscription.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 2)
    
    def test_activate_from_payment_extends_existing(self):
        """Test that activate_from_payment extends existing subscription."""
        # Create existing subscription
        existing = Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=dj_timezone.now() + timedelta(days=10)
        )
        
        payment = Payment.objects.create(
            user=self.user,
            amount=Decimal("499.00"),
            currency="RUB",
            subscription_days=30,
            tariff_name="1_month",
            description="Подписка на 30 дней",
            status=Payment.STATUS_SUCCEEDED
        )
        
        subscription = SubscriptionService.activate_from_payment(payment)
        
        self.assertEqual(subscription.id, existing.id)
        self.assertTrue(subscription.is_active)
        
        # Verify expiration is extended by 30 days
        expected_expiry = existing.expires_at + timedelta(days=30)
        time_diff = abs((subscription.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 2)
    
    def test_activate_from_payment_activates_expired(self):
        """Test that activate_from_payment activates expired subscription."""
        # Create expired subscription
        existing = Subscription.objects.create(
            user=self.user,
            is_active=False,
            expires_at=dj_timezone.now() - timedelta(days=1)
        )
        
        payment = Payment.objects.create(
            user=self.user,
            amount=Decimal("499.00"),
            currency="RUB",
            subscription_days=30,
            tariff_name="1_month",
            description="Подписка на 30 дней",
            status=Payment.STATUS_SUCCEEDED
        )
        
        subscription = SubscriptionService.activate_from_payment(payment)
        
        self.assertEqual(subscription.id, existing.id)
        self.assertTrue(subscription.is_active)
    
    def test_activate_from_promo_creates_subscription(self):
        """Test that activate_from_promo creates new subscription."""
        now = dj_timezone.now()
        promocode = PromoCode.objects.create(
            code="TESTCODE",
            action="extend_subscription",
            days_to_add=7,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            max_uses=100,
            current_uses=0,
            disabled=False,
            created_by=self.user,
        )
        
        subscription = SubscriptionService.activate_from_promo(self.user, promocode)
        
        self.assertEqual(subscription.user, self.user)
        self.assertTrue(subscription.is_active)
        self.assertIsNotNone(subscription.expires_at)
        
        # Verify expiration is approximately 7 days from now
        expected_expiry = dj_timezone.now() + timedelta(days=7)
        time_diff = abs((subscription.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 2)
    
    def test_activate_from_promo_extends_existing(self):
        """Test that activate_from_promo extends existing subscription."""
        # Create existing subscription
        existing = Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=dj_timezone.now() + timedelta(days=10)
        )
        
        now = dj_timezone.now()
        promocode = PromoCode.objects.create(
            code="TESTCODE",
            action="extend_subscription",
            days_to_add=7,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            max_uses=100,
            current_uses=0,
            disabled=False,
            created_by=self.user,
        )
        
        subscription = SubscriptionService.activate_from_promo(self.user, promocode)
        
        self.assertEqual(subscription.id, existing.id)
        self.assertTrue(subscription.is_active)
        
        # Verify expiration is extended by 7 days
        expected_expiry = existing.expires_at + timedelta(days=7)
        time_diff = abs((subscription.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 2)
    
    def test_activate_from_promo_activates_expired(self):
        """Test that activate_from_promo activates expired subscription."""
        # Create expired subscription
        existing = Subscription.objects.create(
            user=self.user,
            is_active=False,
            expires_at=dj_timezone.now() - timedelta(days=1)
        )
        
        now = dj_timezone.now()
        promocode = PromoCode.objects.create(
            code="TESTCODE",
            action="extend_subscription",
            days_to_add=7,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            max_uses=100,
            current_uses=0,
            disabled=False,
            created_by=self.user,
        )
        
        subscription = SubscriptionService.activate_from_promo(self.user, promocode)
        
        self.assertEqual(subscription.id, existing.id)
        self.assertTrue(subscription.is_active)
    
    def test_activate_from_promo_inactive_promo(self):
        """Test that activate_from_promo handles inactive promocode."""
        now = dj_timezone.now()
        promocode = PromoCode.objects.create(
            code="TESTCODE",
            action="extend_subscription",
            days_to_add=7,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            max_uses=100,
            current_uses=0,
            disabled=True,
            created_by=self.user,
        )
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            SubscriptionService.activate_from_promo(self.user, promocode)
    
    def test_activate_from_promo_expired_promo(self):
        """Test that activate_from_promo handles expired promocode."""
        now = dj_timezone.now()
        promocode = PromoCode.objects.create(
            code="TESTCODE",
            action="extend_subscription",
            days_to_add=7,
            valid_from=now - timedelta(days=30),
            valid_until=now - timedelta(days=1),
            max_uses=100,
            current_uses=0,
            disabled=False,
            created_by=self.user,
        )
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            SubscriptionService.activate_from_promo(self.user, promocode)
    
    def test_activate_from_promo_max_uses_reached(self):
        """Test that activate_from_promo handles promocode with max uses reached."""
        now = dj_timezone.now()
        promocode = PromoCode.objects.create(
            code="TESTCODE",
            action="extend_subscription",
            days_to_add=7,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            max_uses=1,
            current_uses=1,
            disabled=False,
            created_by=self.user,
        )
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            SubscriptionService.activate_from_promo(self.user, promocode)
    
    def test_is_access_allowed_no_subscription(self):
        """Test that is_access_allowed returns False without subscription."""
        result = SubscriptionService.is_access_allowed(self.user)
        
        self.assertFalse(result)
    
    def test_is_access_allowed_with_active_subscription(self):
        """Test that is_access_allowed returns True with active subscription."""
        Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=dj_timezone.now() + timedelta(days=30)
        )
        
        result = SubscriptionService.is_access_allowed(self.user)
        
        self.assertTrue(result)
    
    def test_is_access_allowed_with_expired_subscription(self):
        """Test that is_access_allowed returns False with expired subscription."""
        Subscription.objects.create(
            user=self.user,
            is_active=True,
            expires_at=dj_timezone.now() - timedelta(days=1)
        )
        
        result = SubscriptionService.is_access_allowed(self.user)
        
        self.assertFalse(result)
    
    def test_is_access_allowed_with_inactive_subscription(self):
        """Test that is_access_allowed returns False with inactive subscription."""
        Subscription.objects.create(
            user=self.user,
            is_active=False,
            expires_at=dj_timezone.now() + timedelta(days=30)
        )
        
        result = SubscriptionService.is_access_allowed(self.user)
        
        self.assertFalse(result)
    
    def test_is_access_allowed_none_user(self):
        """Test that is_access_allowed returns False for None user."""
        result = SubscriptionService.is_access_allowed(None)
        
        self.assertFalse(result)
    
    def test_is_access_allowed_anonymous_user(self):
        """Test that is_access_allowed returns False for anonymous user."""
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        
        result = SubscriptionService.is_access_allowed(anon)
        
        self.assertFalse(result)
    
    def test_activate_from_payment_with_custom_days(self):
        """Test that activate_from_payment uses custom subscription days from payment."""
        payment = Payment.objects.create(
            user=self.user,
            amount=Decimal("1299.00"),
            currency="RUB",
            subscription_days=90,
            tariff_name="3_months",
            description="Подписка на 90 дней",
            status=Payment.STATUS_SUCCEEDED
        )
        
        subscription = SubscriptionService.activate_from_payment(payment)
        
        # Verify expiration is approximately 90 days from now
        expected_expiry = dj_timezone.now() + timedelta(days=90)
        time_diff = abs((subscription.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 2)
    
    def test_activate_from_promo_with_custom_days(self):
        """Test that activate_from_promo uses custom days from promocode."""
        now = dj_timezone.now()
        promocode = PromoCode.objects.create(
            code="TESTCODE",
            action="extend_subscription",
            days_to_add=14,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            max_uses=100,
            current_uses=0,
            disabled=False,
            created_by=self.user,
        )
        
        subscription = SubscriptionService.activate_from_promo(self.user, promocode)
        
        # Verify expiration is approximately 14 days from now
        expected_expiry = dj_timezone.now() + timedelta(days=14)
        time_diff = abs((subscription.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 2)
