"""
Unit tests for apps/audit/.

This module contains tests for audit service.
"""

from __future__ import annotations

from unittest.mock import Mock, patch
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.audit.services import AuditService
from apps.audit.models import AuditLog

User = get_user_model()


class AuditServiceTests(TestCase):
    """Test AuditService for audit logging."""
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
    
    def test_log_creates_audit_entry(self):
        """Test that log creates AuditLog entry."""
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action description",
            target_id="test_target"
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.action_type, "test_action")
        self.assertEqual(audit_log.action, "Test action description")
        self.assertEqual(audit_log.target_id, "test_target")
    
    def test_log_with_details(self):
        """Test that log includes details."""
        details = {"key": "value", "nested": {"data": 123}}
        
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action",
            target_id="test_target",
            details=details
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.details, details)
    
    def test_log_without_details(self):
        """Test that log works without details."""
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action",
            target_id="test_target"
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.details, {})
    
    def test_log_without_user_id(self):
        """Test that log works without user_id."""
        AuditService.log(
            action_type="test_action",
            action="Test action",
            target_id="test_target"
        )
        
        audit_log = AuditLog.objects.filter(action_type="test_action").first()
        self.assertIsNotNone(audit_log)
        self.assertIsNone(audit_log.user_id)
    
    def test_log_without_target_id(self):
        """Test that log works without target_id."""
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action"
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.target_id, "")
    
    def test_log_creates_timestamp(self):
        """Test that log creates timestamp."""
        from django.utils import timezone as dj_timezone
        
        before_log = dj_timezone.now()
        
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action",
            target_id="test_target"
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log.created_at)
        
        # Verify timestamp is recent (within 1 second)
        time_diff = (audit_log.created_at - before_log).total_seconds()
        self.assertLess(abs(time_diff), 2)
    
    def test_log_multiple_entries(self):
        """Test that log creates multiple entries."""
        for i in range(5):
            AuditService.log(
                user_id=self.user.id,
                action_type=f"test_action_{i}",
                action=f"Test action {i}",
                target_id=f"test_target_{i}"
            )
        
        count = AuditLog.objects.filter(user_id=self.user.id).count()
        self.assertEqual(count, 5)
    
    def test_log_with_ip_address(self):
        """Test that log includes IP address."""
        ip_address = "192.168.1.1"
        
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action",
            target_id="test_target",
            ip_address=ip_address
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.ip_address, ip_address)
    
    def test_log_with_user_agent(self):
        """Test that log includes user agent."""
        user_agent = "Test Browser 1.0"
        
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action",
            target_id="test_target",
            user_agent=user_agent
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.user_agent, user_agent)
    
    def test_log_empty_action_type(self):
        """Test that log handles empty action_type."""
        AuditService.log(
            user_id=self.user.id,
            action_type="",
            action="Test action",
            target_id="test_target"
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.action_type, "")
    
    def test_log_empty_action(self):
        """Test that log handles empty action."""
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="",
            target_id="test_target"
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.action, "")
    
    def test_log_with_complex_details(self):
        """Test that log handles complex details structure."""
        details = {
            "nested": {
                "data": [1, 2, 3],
                "objects": [{"id": 1}, {"id": 2}]
            },
            "array": ["a", "b", "c"],
            "number": 123,
            "string": "test"
        }
        
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action",
            target_id="test_target",
            details=details
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.details, details)
    
    def test_log_does_not_raise_on_error(self):
        """Test that log doesn't raise on invalid data."""
        # Should not raise even with invalid data
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action="Test action",
            target_id="test_target",
            details={"invalid": object()}  # Invalid JSON
        )
        
        # Verify log was created
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
    
    def test_log_with_unicode(self):
        """Test that log handles unicode characters."""
        action = "Тестовое действие с юникодом 🚀"
        details = {"ключ": "значение", "emoji": "🎉"}
        
        AuditService.log(
            user_id=self.user.id,
            action_type="test_action",
            action=action,
            target_id="test_target",
            details=details
        )
        
        audit_log = AuditLog.objects.filter(user_id=self.user.id).first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.action, action)
        self.assertEqual(audit_log.details, details)
