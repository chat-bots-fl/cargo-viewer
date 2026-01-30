"""
GOAL: Test database indexes for SystemSetting and FeatureFlag models.

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

from apps.feature_flags.models import SystemSetting, FeatureFlag


class SystemSettingIndexesTest(TestCase):
    """
    Test that indexes are created and used for SystemSetting model.
    """

    def setUp(self) -> None:
        """
        Create test system settings for testing.
        """
        # Create test settings
        for i in range(10):
            SystemSetting.objects.create(
                key=f"setting_{i}",
                value={"test": f"value_{i}"},
                is_secret=i % 2 == 0
            )

    def test_system_setting_is_secret_created_at_index_exists(self) -> None:
        """
        Test that index on (is_secret, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'system_settings' 
                AND indexname LIKE '%is_secret%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (is_secret, created_at) should exist")

    def test_system_setting_is_secret_created_at_index_used(self) -> None:
        """
        Test that index on (is_secret, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off;")
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM system_settings 
                WHERE is_secret = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, [False])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (is_secret, created_at)")


class FeatureFlagIndexesTest(TestCase):
    """
    Test that indexes are created and used for FeatureFlag model.
    """

    def setUp(self) -> None:
        """
        Create test feature flags for testing.
        """
        # Create test feature flags
        for i in range(10):
            FeatureFlag.objects.create(
                key=f"feature_{i}",
                enabled=i % 2 == 0,
                description=f"Test feature {i}"
            )

    def test_feature_flag_enabled_created_at_index_exists(self) -> None:
        """
        Test that index on (enabled, created_at) exists.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'feature_flags' 
                AND indexname LIKE '%enabled%created_at%'
            """)
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index on (enabled, created_at) should exist")

    def test_feature_flag_enabled_created_at_index_used(self) -> None:
        """
        Test that index on (enabled, created_at) is used in query.
        """
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off;")
            cursor.execute("""
                EXPLAIN ANALYZE
                SELECT * FROM feature_flags 
                WHERE enabled = %s 
                ORDER BY created_at DESC 
                LIMIT 10
            """, [True])
            result = cursor.fetchall()
            query_plan = " ".join(row[0] for row in result)
            self.assertIn("Index Scan", query_plan,
                         "Query should use index scan for (enabled, created_at)")
