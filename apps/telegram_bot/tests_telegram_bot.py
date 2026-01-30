"""
Unit tests for apps/telegram_bot/.

This module contains tests for Telegram bot service.
"""

from __future__ import annotations

from unittest.mock import Mock, patch
from django.test import TestCase
from django.core.cache import cache
from requests.exceptions import HTTPError

from apps.telegram_bot.services import TelegramBotService


class TelegramBotServiceTests(TestCase):
    """Test TelegramBotService for Telegram bot operations."""
    
    def setUp(self):
        cache.clear()
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_message_success(self, mock_get_setting, mock_post):
        """Test that send_message sends message successfully."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.send_message(
            chat_id="test_chat_id",
            text="Test message"
        )
        
        self.assertTrue(result)
        mock_post.assert_called_once()
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_message_with_parse_mode(self, mock_get_setting, mock_post):
        """Test that send_message sends message with parse_mode."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        TelegramBotService.send_message(
            chat_id="test_chat_id",
            text="Test message",
            parse_mode="HTML"
        )
        
        call_args = mock_post.call_args
        self.assertIn("parse_mode", call_args[1]["json"])
        self.assertEqual(call_args[1]["json"]["parse_mode"], "HTML")
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_message_http_error(self, mock_get_setting, mock_post):
        """Test that send_message handles HTTP error."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_post.side_effect = HTTPError("500 Internal Server Error")
        
        result = TelegramBotService.send_message(
            chat_id="test_chat_id",
            text="Test message"
        )
        
        self.assertFalse(result)
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_message_telegram_error(self, mock_get_setting, mock_post):
        """Test that send_message handles Telegram API error."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.send_message(
            chat_id="test_chat_id",
            text="Test message"
        )
        
        self.assertFalse(result)
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_status_success(self, mock_get_setting, mock_post):
        """Test that send_status sends status message successfully."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.send_status(
            chat_id="test_chat_id",
            status="active",
            message="Subscription is active"
        )
        
        self.assertTrue(result)
        mock_post.assert_called_once()
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_status_with_custom_message(self, mock_get_setting, mock_post):
        """Test that send_status includes custom message."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        TelegramBotService.send_status(
            chat_id="test_chat_id",
            status="active",
            message="Custom status message"
        )
        
        call_args = mock_post.call_args
        self.assertIn("Custom status message", call_args[1]["json"]["text"])
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_status_without_message(self, mock_get_setting, mock_post):
        """Test that send_status works without custom message."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.send_status(
            chat_id="test_chat_id",
            status="active"
        )
        
        self.assertTrue(result)
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_handle_response_success(self, mock_get_setting, mock_post):
        """Test that handle_response processes response successfully."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.handle_response(
            chat_id="test_chat_id",
            response_data={
                "cargo_id": "12345",
                "phone": "+79001234567",
                "name": "Test User"
            }
        )
        
        self.assertTrue(result)
        mock_post.assert_called_once()
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_handle_response_with_empty_data(self, mock_get_setting, mock_post):
        """Test that handle_response handles empty response data."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.handle_response(
            chat_id="test_chat_id",
            response_data={}
        )
        
        self.assertTrue(result)
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_handle_response_http_error(self, mock_get_setting, mock_post):
        """Test that handle_response handles HTTP error."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_post.side_effect = HTTPError("500 Internal Server Error")
        
        result = TelegramBotService.handle_response(
            chat_id="test_chat_id",
            response_data={"cargo_id": "12345"}
        )
        
        self.assertFalse(result)
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_handle_response_telegram_error(self, mock_get_setting, mock_post):
        """Test that handle_response handles Telegram API error."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": False, "description": "Bad Request"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.handle_response(
            chat_id="test_chat_id",
            response_data={"cargo_id": "12345"}
        )
        
        self.assertFalse(result)
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_message_with_reply_markup(self, mock_get_setting, mock_post):
        """Test that send_message includes reply_markup."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        reply_markup = {"inline_keyboard": [[{"text": "Button"}]]}
        TelegramBotService.send_message(
            chat_id="test_chat_id",
            text="Test message",
            reply_markup=reply_markup
        )
        
        call_args = mock_post.call_args
        self.assertIn("reply_markup", call_args[1]["json"])
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_message_empty_text(self, mock_get_setting, mock_post):
        """Test that send_message handles empty text."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = TelegramBotService.send_message(
            chat_id="test_chat_id",
            text=""
        )
        
        # Should still send empty message
        self.assertTrue(result)
    
    @patch('apps.telegram_bot.services.requests.post')
    @patch('apps.telegram_bot.services.SystemSetting.get_setting')
    def test_send_status_different_statuses(self, mock_get_setting, mock_post):
        """Test that send_status handles different status values."""
        mock_get_setting.side_effect = lambda key, default: {
            "telegram_bot_token": "test_token",
            "telegram_chat_id": "test_chat_id"
        }.get(key, default)
        
        mock_response = Mock()
        mock_response.json.return_value = {"ok": True, "result": {"message_id": 123}}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        for status in ["active", "inactive", "pending", "expired"]:
            result = TelegramBotService.send_status(
                chat_id="test_chat_id",
                status=status
            )
            self.assertTrue(result, f"Failed for status: {status}")
