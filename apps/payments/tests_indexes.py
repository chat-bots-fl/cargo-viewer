"""
GOAL: Test database indexes for Payment and PaymentHistory models.

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  None

GUARANTEES:
  - All tests verify index existence
  - Tests check index usage with EXPLAIN ANALYZE
"""

import pytest
from django.db import connection
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal

from apps.payments.models import Payment, PaymentHistory


User = get_user_model()


class PaymentIndexesTest(TestCase):
    """
    Test that indexes are created and used for Payment model.
    """

    def setUp(self) -> None:
        """
        Create test user and payments for testing.
        """
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        # Create test payments
        for i in range(10):
            Payment.objects.create(
                user=self.user,
                amount=Decimal("100.00"),
                status=Payment.STATUS_SUCCEEDED if i % 2 == 0 else Payment.STATUS_PENDING,
                tariff_name="premium",
                subscription_days=30,
                yukassa_payment_id=f"test_payment_{i}"
            )

    def test_payment_user_created_at_index_exists(self) -> None:
        """
        Test that index on (user, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'payments' 
                AND indexname LIKE '%user%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (user, created_at) should exist")

    def test_payment_yukassa_payment_id_index_exists(self) -> None:
        """
        Test that index on yukassa_payment_id exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'payments' 
                AND indexname LIKE '%yukassa%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on yukassa_payment_id should exist")

    def test_payment_status_created_at_index_exists(self) -> None:
        """
        Test that index on (status, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'payments' 
                AND indexname LIKE '%status%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (status, created_at) should exist")

    def test_payment_status_created_at_index_used(self) -> None:
        """
        Test that index on (status, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM payments 
                WHERE status = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, [Payment.STATUS_SUCCEEDED])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan, 
                         "Query should use index scan for (status, created_at)")

    def test_payment_user_created_at_index_used(self) -> None:
        """
        Test that index on (user, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM payments 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, [self.user.id])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (user, created_at)")


class PaymentHistoryIndexesTest(TestCase):
    """
    Test that indexes are created and used for PaymentHistory model.
    """

    def setUp(self) -> None:
        """
        Create test user, payment and history records for testing.
        """
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        self.payment = Payment.objects.create(
            user=self.user,
            amount=Decimal("100.00"),
            status=Payment.STATUS_SUCCEEDED,
            tariff_name="premium",
            subscription_days=30,
            yukassa_payment_id="test_payment_1"
        )
        
        # Create test history records
        for i in range(10):
            PaymentHistory.objects.create(
                payment=self.payment,
                event_type="status_change" if i % 2 == 0 else "webhook_received",
                old_status="pending",
                new_status="succeeded" if i % 2 == 0 else "processing"
            )

    def test_payment_history_event_type_created_at_index_exists(self) -> None:
        """
        Test that index on (event_type, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'payment_history' 
                AND indexname LIKE '%event_type%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (event_type, created_at) should exist")

    def test_payment_history_payment_created_at_index_exists(self) -> None:
        """
        Test that index on (payment, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'payment_history' 
                AND indexname LIKE '%payment%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (payment, created_at) should exist")

    def test_payment_history_payment_created_at_index_used(self) -> None:
        """
        Test that index on (payment, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM payment_history 
                WHERE payment_id = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, [self.payment.id])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (payment, created_at)")
