"""
GOAL: Test database indexes for DriverCargoResponse model.

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

from apps.telegram_bot.models import DriverCargoResponse


User = get_user_model()


class DriverCargoResponseIndexesTest(TestCase):
    """
    Test that indexes are created and used for DriverCargoResponse model.
    """

    def setUp(self) -> None:
        """
        Create test user and cargo responses for testing.
        """
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        # Create test cargo responses
        for i in range(10):
            DriverCargoResponse.objects.create(
                user=self.user,
                cargo_id=f"cargo_{i}",
                phone=f"+799912345{i}",
                name=f"Driver {i}",
                status="pending" if i % 3 == 0 else ("accepted" if i % 3 == 1 else "rejected")
            )

    def test_driver_cargo_response_cargo_id_created_at_index_exists(self) -> None:
        """
        Test that index on (cargo_id, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'driver_cargo_responses' 
                AND indexname LIKE '%cargo_id%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (cargo_id, created_at) should exist")

    def test_driver_cargo_response_user_created_at_index_exists(self) -> None:
        """
        Test that index on (user, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'driver_cargo_responses' 
                AND indexname LIKE '%user%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (user, created_at) should exist")

    def test_driver_cargo_response_status_created_at_index_exists(self) -> None:
        """
        Test that index on (status, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'driver_cargo_responses' 
                AND indexname LIKE '%status%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (status, created_at) should exist")

    def test_driver_cargo_response_user_created_at_index_used(self) -> None:
        """
        Test that index on (user, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM driver_cargo_responses 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, [self.user.id])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (user, created_at)")

    def test_driver_cargo_response_status_created_at_index_used(self) -> None:
        """
        Test that index on (status, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM driver_cargo_responses 
                WHERE status = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, ["pending"])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (status, created_at)")
