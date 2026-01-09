from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from datetime import datetime

from apps.audit.services import AuditService
from apps.core.dtos import TelegramResponseDTO, dto_to_dict
from apps.core.repositories import DriverCargoResponseRepository
from apps.subscriptions.services import SubscriptionService
from apps.telegram_bot.models import DriverCargoResponse

logger = logging.getLogger(__name__)

# Import Sentry monitoring functions (graceful degradation if not available)
try:
    from apps.core.monitoring import (
        capture_exception,
        add_breadcrumb,
        set_transaction,
        set_user_context,
    )
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    logger.warning("Sentry monitoring not available in telegram_bot")
    
    # Fallback functions
    def capture_exception(*args, **kwargs):
        return None
    def add_breadcrumb(*args, **kwargs):
        pass
    def set_transaction(*args, **kwargs):
        return None
    def set_user_context(*args, **kwargs):
        pass


class TelegramBotService:
    """
    Minimal Telegram Bot API client for WebApp flows.
    """

    """
    GOAL: Send a message via Telegram Bot API.

    PARAMETERS:
      chat_id: int - Target chat id - Must be > 0
      text: str - Message text - Must be non-empty
      reply_markup: dict[str, Any] | None - Telegram reply_markup - Optional

    RETURNS:
      TelegramResponseDTO - Telegram response DTO - Never None

    RAISES:
      ValidationError: If TELEGRAM_BOT_TOKEN missing or inputs invalid
      requests.HTTPError: If Telegram API returns non-200

    GUARANTEES:
      - Uses HTTPS Telegram Bot API endpoint
    """
    @staticmethod
    def send_message(*, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> TelegramResponseDTO:
        """
        POST sendMessage with optional reply_markup.
        """
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise ValidationError("TELEGRAM_BOT_TOKEN is not configured")
        if chat_id <= 0:
            raise ValidationError("chat_id must be > 0")
        text = str(text or "").strip()
        if not text:
            raise ValidationError("text is required")

        # Add breadcrumb for Telegram message send
        add_breadcrumb(
            message=f"Telegram send_message: chat_id={chat_id}",
            category="telegram",
            level="info",
            data={
                "service": "telegram",
                "chat_id": chat_id,
                "text_length": len(text),
            }
        )
        
        # Start transaction for performance monitoring
        transaction = set_transaction(
            name="Telegram send_message",
            op="telegram.send_message",
            tags={
                "service": "telegram",
            }
        )
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload: dict[str, Any] = {"chat_id": int(chat_id), "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            if transaction:
                with transaction:
                    resp = requests.post(url, json=payload, timeout=10)
            else:
                resp = requests.post(url, json=payload, timeout=10)
            
            resp.raise_for_status()
            
            # Add breadcrumb for successful message send
            add_breadcrumb(
                message=f"Telegram send_message success",
                category="telegram",
                level="info",
                data={
                    "service": "telegram",
                    "chat_id": chat_id,
                }
            )
            
            response_json = resp.json()
            return TelegramResponseDTO(
                message_id=int((response_json.get("result") or {}).get("message_id") or 0) or None,
                chat_id=chat_id,
                text=text,
                parse_mode=None,
                reply_markup=reply_markup,
                success=True,
                error_message=None,
                created_at=datetime.utcnow(),
            )
        except Exception as exc:
            # Add breadcrumb for error
            add_breadcrumb(
                message=f"Telegram send_message error: {type(exc).__name__}",
                category="telegram",
                level="error",
                data={
                    "service": "telegram",
                    "chat_id": chat_id,
                    "error_type": type(exc).__name__,
                }
            )
            
            # Send exception to Sentry
            capture_exception(
                exc,
                level="error",
                extra={
                    "service": "telegram",
                    "chat_id": chat_id,
                    "text_length": len(text),
                },
                tags={
                    "service": "telegram",
                    "operation": "send_message",
                }
            )
            
            return TelegramResponseDTO(
                message_id=None,
                chat_id=chat_id,
                text=text,
                parse_mode=None,
                reply_markup=reply_markup,
                success=False,
                error_message=str(exc),
                created_at=datetime.utcnow(),
            )

    """
    GOAL: Send status update to a driver in Telegram.

    PARAMETERS:
      driver_id: int - Telegram user id - Must be > 0
      cargo_id: str - Cargo id - Must be non-empty
      status: str - One of accepted/rejected/completed/sent - Must be non-empty

    RETURNS:
      bool - True if sent successfully - Never None

    RAISES:
      ValidationError: If inputs invalid

    GUARANTEES:
      - Errors are logged and return False (best-effort)
    """
    @staticmethod
    def send_status(*, driver_id: int, cargo_id: str, status: str) -> bool:
        """
        Best-effort Telegram notification to the driver chat.
        """
        try:
            TelegramBotService.send_message(
                chat_id=int(driver_id),
                text=f"Статус по грузу {cargo_id}: {status}",
            )
            return True
        except Exception as exc:
            logger.warning("Failed to send status: %s", exc)
            return False

    """
    GOAL: Handle a driver response to a cargo (idempotent) and forward it via Telegram bot.

    PARAMETERS:
      user_id: int - Django user id - Must be > 0
      telegram_user_id: int - Telegram user id - Must be > 0
      cargo_id: str - Cargo id - Must be non-empty
      phone: str - Driver phone number - Can be empty but recommended
      name: str - Driver display name - Can be empty
      driver_cargo_response_repo: DriverCargoResponseRepository | None - Repository for driver cargo response operations - Optional

    RETURNS:
      TelegramResponseDTO - Telegram response DTO - Never None

    RAISES:
      ValidationError: If cargo_id missing or user not allowed (no subscription)

    GUARANTEES:
      - Prevents duplicate responses per (user_id, cargo_id)
      - Creates DB record before sending to Telegram
      - Logs to audit
    """
    @staticmethod
    @transaction.atomic
    def handle_response(
        *,
        user_id: int,
        telegram_user_id: int,
        cargo_id: str,
        phone: str,
        name: str,
        driver_cargo_response_repo: DriverCargoResponseRepository | None = None,
    ) -> TelegramResponseDTO:
        """
        Enforce subscription access, then create-or-reuse response record and send a bot message.
        """
        cargo_id = str(cargo_id or "").strip()
        if not cargo_id:
            raise ValidationError("cargo_id is required")

        if not SubscriptionService.is_access_allowed(user_id=user_id, feature_key="respond_to_cargo"):
            raise ValidationError("payment_required")

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if driver_cargo_response_repo is not None:
            from asgiref.sync import sync_to_async
            existing_response = sync_to_async(driver_cargo_response_repo.get_by_user_and_cargo)(
                user_id=int(user_id), cargo_id=cargo_id
            )
            if existing_response:
                response = existing_response
                created = False
            else:
                response = DriverCargoResponse(
                    user_id=int(user_id),
                    cargo_id=cargo_id,
                    phone=phone,
                    name=name,
                    status="pending",
                )
                response.save()
                created = True
        else:
            response, created = DriverCargoResponse.objects.select_for_update().get_or_create(
                user_id=int(user_id),
                cargo_id=cargo_id,
                defaults={"phone": phone, "name": name, "status": "pending"},
            )

        if not created and response.status in {"sent", "pending"}:
            return TelegramResponseDTO(
                message_id=None,
                chat_id=telegram_user_id,
                text=f"Статус по грузу {cargo_id}: {response.status}",
                parse_mode=None,
                reply_markup=None,
                success=True,
                error_message=None,
                created_at=datetime.utcnow(),
            )

        chat_id = int(getattr(settings, "TELEGRAM_RESPONSES_CHAT_ID", 0) or 0)
        if chat_id <= 0:
            raise ValidationError("TELEGRAM_RESPONSES_CHAT_ID is not configured")

        text = "\n".join(
            [
                "🚚 Отклик водителя",
                f"Груз: {cargo_id}",
                f"Имя: {name or '—'}",
                f"Телефон: {phone or '—'}",
                f"Telegram ID: {telegram_user_id}",
            ]
        )
        telegram_resp = TelegramBotService.send_message(chat_id=chat_id, text=text)
        msg_id = int((telegram_resp.get("result") or {}).get("message_id") or 0) or None

        response.phone = phone
        response.name = name
        response.status = "sent"
        response.telegram_message_id = msg_id
        response.save(update_fields=["phone", "name", "status", "telegram_message_id", "updated_at"])

        AuditService.log(
            user_id=user_id,
            action_type="telegram_bot",
            action="Driver response sent",
            target_id=str(response.id),
            details={"cargo_id": cargo_id, "telegram_message_id": msg_id},
        )

        TelegramBotService.send_status(driver_id=telegram_user_id, cargo_id=cargo_id, status="sent")

        return TelegramResponseDTO(
            message_id=None,
            chat_id=telegram_user_id,
            text=f"Статус по грузу {cargo_id}: sent",
            parse_mode=None,
            reply_markup=None,
            success=True,
            error_message=None,
            created_at=datetime.utcnow(),
        )

