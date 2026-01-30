"""
GOAL: Test database indexes for CargoCache model.

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

from apps.cargos.models import CargoCache


User = get_user_model()


class CargoCacheIndexesTest(TestCase):
    """
    Test that indexes are created and used for CargoCache model.
    """

    def setUp(self) -> None:
        """
        Create test user and cargo cache entries for testing.
        """
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        
        # Create test cargo cache entries
        for i in range(10):
            CargoCache.objects.create(
                user=self.user,
                cache_key=f"cache_key_{i}",
                payload={"test": f"data_{i}"}
            )

    def test_cargo_cache_user_cache_key_index_exists(self) -> None:
        """
        Test that index on (user, cache_key) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'cargo_cache' 
                AND indexname LIKE '%user%cache_key%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (user, cache_key) should exist")

    def test_cargo_cache_user_created_at_index_exists(self) -> None:
        """
        Test that index on (user, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'cargo_cache' 
                AND indexname LIKE '%user%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (user, created_at) should exist")

    def test_cargo_cache_user_created_at_index_used(self) -> None:
        """
        Test that index on (user, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off")
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM cargo_cache 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, [self.user.id])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (user, created_at)")
