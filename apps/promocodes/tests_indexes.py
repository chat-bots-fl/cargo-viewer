"""
GOAL: Test database indexes for PromoCode and PromoCodeUsage models.

PARAMETERS:
  None

RETURNS:
  None

RAARISES:
  None

GUARANTEES:
  - All tests verify index existence
  - Tests check index usage with EXPLAIN ANALYZE
"""

import pytest
from datetime import timedelta
from django.db import connection
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.promocodes.models import PromoCode, PromoCodeUsage


User = get_user_model()


class PromoCodeIndexesTest(TestCase):
    """
    Test that indexes are created and used for PromoCode model.
    """

    def setUp(self) -> None:
        """
        Create test user and promo codes for testing.
        """
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        now = timezone.now()
        
        # Create test promo codes
        for i in range(10):
            PromoCode.objects.create(
                code=f"TEST{i}",
                action="extend_subscription" if i % 2 == 0 else "discount",
                days_to_add=30,
                valid_from=now - timedelta(days=1),
                valid_until=now + timedelta(days=30),
                max_uses=100,
                current_uses=i,
                disabled=i % 3 == 0,
                created_by=self.user
            )

    def test_promo_code_action_valid_until_index_exists(self) -> None:
        """
        Test that index on (action, valid_until) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'promo_codes' 
                AND indexname LIKE '%action%valid_until%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (action, valid_until) should exist")

    def test_promo_code_disabled_valid_until_index_exists(self) -> None:
        """
        Test that index on (disabled, valid_until) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'promo_codes' 
                AND indexname LIKE '%disabled%valid_until%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (disabled, valid_until) should exist")

    def test_promo_code_disabled_valid_until_index_used(self) -> None:
        """
        Test that index on (disabled, valid_until) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM promo_codes 
                WHERE disabled = %s 
                ORDER BY valid_until DESC 
                LIMIT 10
            """, [False])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (disabled, valid_until)")


class PromoCodeUsageIndexesTest(TestCase):
    """
    Test that indexes are created and used for PromoCodeUsage model.
    """

    def setUp(self) -> None:
        """
        Create test user, promo code and usage records for testing.
        """
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        now = timezone.now()
        
        self.promo_code = PromoCode.objects.create(
            code="TEST123",
            action="extend_subscription",
            days_to_add=30,
            valid_from=now - timedelta(days=1),
            valid_until=now + timedelta(days=30),
            max_uses=100,
            current_uses=0,
            disabled=False,
            created_by=self.user
        )
        
        # Create test usage records
        for i in range(10):
            PromoCodeUsage.objects.create(
                promo_code=self.promo_code,
                user=self.user,
                success=i % 2 == 0,
                reason="Test usage",
                days_added=30
            )

    def test_promo_code_usage_promo_code_used_at_index_exists(self) -> None:
        """
        Test that index on (promo_code, used_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'promo_code_usage' 
                AND indexname LIKE '%promo_code%used_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (promo_code, used_at) should exist")

    def test_promo_code_usage_user_used_at_index_exists(self) -> None:
        """
        Test that index on (user, used_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'promo_code_usage' 
                AND indexname LIKE '%user%used_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (user, used_at) should exist")

    def test_promo_code_usage_success_used_at_index_exists(self) -> None:
        """
        Test that index on (success, used_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'promo_code_usage' 
                AND indexname LIKE '%success%used_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (success, used_at) should exist")

    def test_promo_code_usage_success_used_at_index_used(self) -> None:
        """
        Test that index on (success, used_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM promo_code_usage 
                WHERE success = %s 
                ORDER BY used_at DESC 
                LIMIT 10
            """, [True])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (success, used_at)")
