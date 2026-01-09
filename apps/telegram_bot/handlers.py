from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.telegram_bot.services import TelegramBotService


class TelegramUpdateHandler:
    """
    Handle incoming Telegram webhook updates (only minimal /start is supported here).
    """

    """
    GOAL: Process Telegram webhook update and respond to /start with a WebApp button.

    PARAMETERS:
      update: dict[str, Any] - Telegram update payload - Must be a dict

    RETURNS:
      bool - True if handled, False if ignored - Never None

    RAISES:
      ValidationError: If WEBAPP_URL is not configured

    GUARANTEES:
      - Does not raise for unknown updates (returns False)
      - /start produces a message with inline web_app button
    """
    @staticmethod
    def handle_update(update: dict[str, Any]) -> bool:
        """
        Detect /start in message text and send a WebApp launch button back to the same chat.
        """
        message = update.get("message") or {}
        text = str(message.get("text") or "").strip()
        chat_id = (message.get("chat") or {}).get("id")
        if not text or not chat_id:
            return False

        if text.startswith("/start"):
            webapp_url = str(getattr(settings, "WEBAPP_URL", "") or "").strip()
            if not webapp_url:
                raise ValidationError("WEBAPP_URL is not configured")

            markup: dict[str, Any] = {
                "inline_keyboard": [
                    [{"text": "Открыть приложение", "web_app": {"url": webapp_url}}],
                ]
            }
            TelegramBotService.send_message(chat_id=int(chat_id), text="Откройте WebApp:", reply_markup=markup)
            return True

        return False

