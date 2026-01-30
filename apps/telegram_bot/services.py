from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import AuditService
from apps.core.repositories import DriverCargoResponseRepository
from apps.feature_flags.models import SystemSetting
from apps.subscriptions.services import SubscriptionService
from apps.telegram_bot.models import DriverCargoResponse

logger = logging.getLogger(__name__)


"""
GOAL: Read Telegram bot token from SystemSetting or Django settings.

PARAMETERS:
  None

RETURNS:
  str - Telegram bot token - Empty string when not configured

RAISES:
  None

GUARANTEES:
  - Never returns None
  - Strips surrounding whitespace
"""
def _get_telegram_bot_token() -> str:
    """
    Prefer SystemSetting('telegram_bot_token'), fallback to settings.TELEGRAM_BOT_TOKEN.
    """
    token = SystemSetting.get_setting("telegram_bot_token", "")
    if not token:
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    return str(token or "").strip()


"""
GOAL: Read Telegram responses chat id from SystemSetting or Django settings.

PARAMETERS:
  None

RETURNS:
  str - Chat id for admin responses - Empty string when not configured

RAISES:
  None

GUARANTEES:
  - Never returns None
  - Strips surrounding whitespace
"""
def _get_telegram_responses_chat_id() -> str:
    """
    Prefer SystemSetting('telegram_chat_id'), fallback to settings.TELEGRAM_RESPONSES_CHAT_ID.
    """
    chat_id = str(SystemSetting.get_setting("telegram_chat_id", "") or "").strip()
    if chat_id:
        return chat_id

    env_chat_id = int(getattr(settings, "TELEGRAM_RESPONSES_CHAT_ID", 0) or 0)
    return str(env_chat_id) if env_chat_id > 0 else ""


"""
GOAL: Send a Telegram sendMessage request and return parsed JSON on success.

PARAMETERS:
  token: str - Bot token - Must be non-empty
  payload: dict[str, Any] - sendMessage payload - Must include chat_id and text

RETURNS:
  dict[str, Any] | None - Telegram response JSON when ok=True, else None

RAISES:
  requests.RequestException: If network/HTTP layer fails
  ValueError: If response body is not valid JSON

GUARANTEES:
  - Returns None on non-ok Telegram responses
"""
def _send_message_raw(token: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    POST https://api.telegram.org/bot{token}/sendMessage and validate {"ok": true}.
    """
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    return data


class TelegramBotService:
    """
    Telegram bot helper service (sending messages + processing driver responses).
    """

    """
    GOAL: Send a message via Telegram Bot API.

    PARAMETERS:
      chat_id: str | int - Target chat id - Must be non-empty
      text: str - Message text - Can be empty
      parse_mode: str | None - Telegram parse mode (e.g. HTML/Markdown) - Optional
      reply_markup: dict[str, Any] | None - Telegram reply_markup JSON - Optional

    RETURNS:
      bool - True when Telegram returns ok=True - Never None

    RAISES:
      None (best-effort; returns False on failures)

    GUARANTEES:
      - Uses token from SystemSetting or settings
      - Returns False when token missing
    """
    @staticmethod
    def send_message(
        *,
        chat_id: str | int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """
        Compose sendMessage payload and interpret Telegram ok flag as success.
        """
        token = _get_telegram_bot_token()
        if not token:
            logger.warning("Telegram bot token is not configured")
            return False

        payload: dict[str, Any] = {"chat_id": chat_id, "text": str(text or "")}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            data = _send_message_raw(token, payload)
        except requests.RequestException as exc:
            logger.warning("Telegram send_message failed: %s", exc)
            return False
        except ValueError as exc:
            logger.warning("Telegram send_message invalid response: %s", exc)
            return False

        return data is not None

    """
    GOAL: Send a status update message to Telegram.

    PARAMETERS:
      status: str - Status label - Must be non-empty
      chat_id: str | int | None - Target chat id - Optional if driver_id provided
      driver_id: int | None - Telegram user id - Optional if chat_id provided
      cargo_id: str | None - Cargo id context - Optional
      message: str | None - Optional custom message - Optional

    RETURNS:
      bool - True if sent successfully - Never None

    RAISES:
      None (best-effort; returns False on failures)

    GUARANTEES:
      - Includes custom message in sent text when provided
    """
    @staticmethod
    def send_status(
        *,
        status: str,
        chat_id: str | int | None = None,
        driver_id: int | None = None,
        cargo_id: str | None = None,
        message: str | None = None,
    ) -> bool:
        """
        Format a status message and send via send_message.
        """
        target_chat_id = chat_id if chat_id is not None else driver_id
        if target_chat_id is None:
            return False

        status = str(status or "").strip()
        if not status:
            return False

        if cargo_id:
            base = f"Статус по грузу {cargo_id}: {status}"
        else:
            base = f"Status: {status}"

        text = f"{base}\n{message}" if message else base
        return TelegramBotService.send_message(chat_id=target_chat_id, text=text)

    """
    GOAL: Forward a driver response to Telegram and optionally persist idempotency record.

    PARAMETERS:
      chat_id: str | int | None - Target chat id for simple forwarding - Required when response_data provided
      response_data: dict[str, Any] | None - Arbitrary response payload - When set, sends a formatted message and returns bool
      user_id: int | None - Django user id - Required for idempotent DB-backed flow
      telegram_user_id: int | None - Telegram user id - Required for DB-backed flow
      cargo_id: str | None - Cargo id - Required for DB-backed flow
      phone: str - Phone number - Optional
      name: str - Driver name - Optional
      driver_cargo_response_repo: DriverCargoResponseRepository | None - Optional repository - Optional

    RETURNS:
      bool | dict[str, Any] - bool for simple forwarding, dict with response_id/status for DB-backed flow

    RAISES:
      ValidationError: If DB-backed flow inputs invalid or payment_required

    GUARANTEES:
      - Simple forwarding never raises (returns False on failures)
      - DB-backed flow is idempotent per (user_id, cargo_id)
      - DB-backed flow writes audit log on success
    """
    @staticmethod
    @transaction.atomic
    def handle_response(
        *,
        chat_id: str | int | None = None,
        response_data: dict[str, Any] | None = None,
        user_id: int | None = None,
        telegram_user_id: int | None = None,
        cargo_id: str | None = None,
        phone: str = "",
        name: str = "",
        driver_cargo_response_repo: DriverCargoResponseRepository | None = None,
    ) -> bool | dict[str, Any]:
        """
        Either send a formatted telegram message or run the DB-backed driver response flow.
        """
        if response_data is not None:
            target_chat_id = chat_id
            if target_chat_id is None:
                return False

            data = response_data or {}
            cargo = str(data.get("cargo_id") or "").strip()
            phone_val = str(data.get("phone") or "").strip()
            name_val = str(data.get("name") or "").strip()

            lines = ["Driver response"]
            if cargo:
                lines.append(f"Cargo ID: {cargo}")
            if phone_val:
                lines.append(f"Phone: {phone_val}")
            if name_val:
                lines.append(f"Name: {name_val}")
            if len(lines) == 1:
                lines.append("No details provided")

            text = "\n".join(lines)
            return TelegramBotService.send_message(chat_id=target_chat_id, text=text)

        if user_id is None or telegram_user_id is None:
            raise ValidationError("user_id and telegram_user_id are required")
        cargo_id = str(cargo_id or "").strip()
        if not cargo_id:
            raise ValidationError("cargo_id is required")

        if not SubscriptionService.is_access_allowed(user_id=int(user_id), feature_key="respond_to_cargo"):
            raise ValidationError("payment_required")

        if driver_cargo_response_repo is not None:
            existing = driver_cargo_response_repo.get_by_user_and_cargo(user_id=int(user_id), cargo_id=cargo_id)
            if existing is not None:
                response = existing
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
            return {"status": response.status, "response_id": str(response.id)}

        admin_chat_id = _get_telegram_responses_chat_id()
        if not admin_chat_id:
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

        token = _get_telegram_bot_token()
        if not token:
            raise ValidationError("telegram_bot_token is not configured")

        payload: dict[str, Any] = {"chat_id": admin_chat_id, "text": text}
        try:
            data = _send_message_raw(token, payload)
        except requests.RequestException as exc:
            raise ValidationError(f"Telegram request failed: {exc}") from exc
        except ValueError as exc:
            raise ValidationError("Telegram returned invalid JSON") from exc

        if not data:
            raise ValidationError("Telegram API error")

        raw_message_id = (data.get("result") or {}).get("message_id")
        message_id = int(raw_message_id) if raw_message_id is not None else None

        response.phone = phone
        response.name = name
        response.status = "sent"
        response.telegram_message_id = message_id
        response.save(update_fields=["phone", "name", "status", "telegram_message_id", "updated_at"])

        AuditService.log(
            user_id=int(user_id),
            action_type="telegram_bot",
            action="Driver response sent",
            target_id=str(response.id),
            details={"cargo_id": cargo_id, "telegram_message_id": message_id},
        )

        TelegramBotService.send_status(driver_id=int(telegram_user_id), cargo_id=cargo_id, status="sent")
        return {"status": "sent", "response_id": str(response.id)}

