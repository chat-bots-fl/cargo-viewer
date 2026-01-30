from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any, Optional

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.audit.services import AuditService
from apps.core.decorators import circuit_breaker
from apps.core.repositories import PaymentHistoryRepository, PaymentRepository, SystemSettingRepository
from apps.feature_flags.models import SystemSetting
from apps.payments.models import Payment, PaymentHistory

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
    logger.warning("Sentry monitoring not available in payments")
    
    # Fallback functions
    def capture_exception(*args, **kwargs):
        return None
    def add_breadcrumb(*args, **kwargs):
        pass
    def set_transaction(*args, **kwargs):
        return None
    def set_user_context(*args, **kwargs):
        pass


class YuKassaAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class Tariff:
    name: str
    price: Decimal
    days: int


class YuKassaClient:
    base_url = "https://api.yookassa.ru/v3"

    """
    GOAL: Initialize YuKassa API client with credentials from SystemSetting or environment.

    PARAMETERS:
      None

    RETURNS:
      None

    RAISES:
      YuKassaAPIError: If shop_id/secret_key are not configured

    GUARANTEES:
      - shop_id and secret_key are stored on the instance for Basic auth
    """
    def __init__(self, *, system_setting_repo: SystemSettingRepository | None = None) -> None:
        # Use repository if provided, otherwise direct model access for backward compatibility
        if system_setting_repo is not None:
            from asgiref.sync import sync_to_async
            shop_id = sync_to_async(system_setting_repo.get_by_key)("yookassa_shop_id")
            secret_key = sync_to_async(system_setting_repo.get_by_key)("yookassa_secret_key")
            self.shop_id = str(shop_id.value if shop_id else "") or str(settings.YOOKASSA_SHOP_ID or "").strip()
            self.secret_key = str(secret_key.value if secret_key else "") or str(settings.YOOKASSA_SECRET_KEY or "").strip()
        else:
            self.shop_id = str(SystemSetting.get_setting("yookassa_shop_id", "") or settings.YOOKASSA_SHOP_ID or "").strip()
            self.secret_key = str(
                SystemSetting.get_setting("yookassa_secret_key", "") or settings.YOOKASSA_SECRET_KEY or ""
            ).strip()

        if not self.shop_id or not self.secret_key:
            raise YuKassaAPIError("YuKassa credentials are not configured (shop_id/secret_key)")

    """
    GOAL: Create a payment in YuKassa and return the raw API response with circuit breaker protection.

    PARAMETERS:
      amount: Decimal - Payment amount - Must be > 0
      currency: str - Currency code - Usually 'RUB'
      description: str - Payment description - Must be non-empty
      return_url: str - Redirect return URL - Must be http/https
      metadata: dict[str, Any] - Metadata attached to payment - Must be JSON-serializable

    RETURNS:
      dict[str, Any] - YuKassa payment object JSON - Never None

    RAISES:
      YuKassaAPIError: If API call fails
      ExternalServiceError: If circuit breaker is OPEN

    GUARANTEES:
      - Uses Idempotence-Key header (UUID)
      - Uses HTTP Basic auth with shop_id/secret_key
      - Protected by circuit breaker
    """
    @circuit_breaker(service_name="yukassa")
    def create_payment(self, *, amount: Decimal, currency: str, description: str, return_url: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Create a payment in YuKassa using HTTP Basic auth and Idempotence-Key.
        """
        # Add breadcrumb for payment creation start
        add_breadcrumb(
            message=f"YuKassa create_payment: {amount} {currency}",
            category="payment",
            level="info",
            data={
                "service": "yukassa",
                "amount": str(amount),
                "currency": currency,
                "description": description,
            }
        )
        
        # Start transaction for performance monitoring
        transaction = set_transaction(
            name="YuKassa create_payment",
            op="payment.create",
            tags={
                "service": "yukassa",
                "currency": currency,
            }
        )
        
        url = f"{self.base_url}/payments"
        payload = {
            "amount": {"value": str(amount), "currency": currency},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
            "metadata": metadata,
        }
        
        try:
            try:
                if transaction:
                    with transaction:
                        resp = requests.post(
                            url,
                            json=payload,
                            auth=(self.shop_id, self.secret_key),
                            headers={"Idempotence-Key": str(uuid.uuid4())},
                            timeout=10,
                        )
                else:
                    resp = requests.post(
                        url,
                        json=payload,
                        auth=(self.shop_id, self.secret_key),
                        headers={"Idempotence-Key": str(uuid.uuid4())},
                        timeout=10,
                    )
            except requests.RequestException as exc:
                raise YuKassaAPIError(f"YuKassa create_payment request failed: {exc}") from exc
            
            try:
                resp.raise_for_status()
            except requests.HTTPError as exc:
                # Add breadcrumb for API error
                add_breadcrumb(
                    message=f"YuKassa create_payment failed: {resp.status_code}",
                    category="payment",
                    level="error",
                    data={
                        "service": "yukassa",
                        "status_code": resp.status_code,
                        "response_body": resp.text[:200],
                    }
                )
                
                # Send exception to Sentry
                capture_exception(
                    exc,
                    level="error",
                    extra={
                        "service": "yukassa",
                        "amount": str(amount),
                        "currency": currency,
                        "status_code": resp.status_code,
                        "response_body": resp.text[:200],
                    },
                    tags={
                        "service": "yukassa",
                        "operation": "create_payment",
                        "status_code": str(resp.status_code),
                    }
                )
                
                raise YuKassaAPIError(f"YuKassa create_payment failed: {exc} body={resp.text[:200]}") from exc
            
            # Add breadcrumb for successful payment creation
            add_breadcrumb(
                message=f"YuKassa create_payment success",
                category="payment",
                level="info",
                data={
                    "service": "yukassa",
                    "amount": str(amount),
                    "currency": currency,
                }
            )
            
            return resp.json()
        except Exception as exc:
            # Add breadcrumb for unexpected error
            add_breadcrumb(
                message=f"YuKassa create_payment unexpected error: {type(exc).__name__}",
                category="payment",
                level="error",
                data={
                    "service": "yukassa",
                    "error_type": type(exc).__name__,
                }
            )
            
            # Send exception to Sentry if not already sent
            if not isinstance(exc, YuKassaAPIError):
                capture_exception(
                    exc,
                    level="error",
                    extra={
                        "service": "yukassa",
                        "amount": str(amount),
                        "currency": currency,
                    },
                    tags={
                        "service": "yukassa",
                        "operation": "create_payment",
                    }
                )
            
            raise

    """
    GOAL: Fetch payment information from YuKassa by payment id with circuit breaker protection.

    PARAMETERS:
      payment_id: str - YuKassa payment id - Must be non-empty

    RETURNS:
      dict[str, Any] - YuKassa payment object JSON - Never None

    RAISES:
      YuKassaAPIError: If API call fails
      ExternalServiceError: If circuit breaker is OPEN

    GUARANTEES:
      - Uses HTTP Basic auth with shop_id/secret_key
      - Protected by circuit breaker
    """
    @circuit_breaker(service_name="yukassa")
    def get_payment(self, *, payment_id: str) -> dict[str, Any]:
        """
        Get payment info from YuKassa.
        """
        # Add breadcrumb for payment fetch start
        add_breadcrumb(
            message=f"YuKassa get_payment: {payment_id}",
            category="payment",
            level="info",
            data={
                "service": "yukassa",
                "payment_id": payment_id,
            }
        )
        
        # Start transaction for performance monitoring
        transaction = set_transaction(
            name="YuKassa get_payment",
            op="payment.get",
            tags={
                "service": "yukassa",
            }
        )
        
        url = f"{self.base_url}/payments/{payment_id}"
        
        try:
            try:
                if transaction:
                    with transaction:
                        resp = requests.get(url, auth=(self.shop_id, self.secret_key), timeout=10)
                else:
                    resp = requests.get(url, auth=(self.shop_id, self.secret_key), timeout=10)
            except requests.RequestException as exc:
                raise YuKassaAPIError(f"YuKassa get_payment request failed: {exc}") from exc
            
            try:
                resp.raise_for_status()
            except requests.HTTPError as exc:
                # Add breadcrumb for API error
                add_breadcrumb(
                    message=f"YuKassa get_payment failed: {resp.status_code}",
                    category="payment",
                    level="error",
                    data={
                        "service": "yukassa",
                        "payment_id": payment_id,
                        "status_code": resp.status_code,
                        "response_body": resp.text[:200],
                    }
                )
                
                # Send exception to Sentry
                capture_exception(
                    exc,
                    level="error",
                    extra={
                        "service": "yukassa",
                        "payment_id": payment_id,
                        "status_code": resp.status_code,
                        "response_body": resp.text[:200],
                    },
                    tags={
                        "service": "yukassa",
                        "operation": "get_payment",
                        "status_code": str(resp.status_code),
                    }
                )
                
                raise YuKassaAPIError(f"YuKassa get_payment failed: {exc} body={resp.text[:200]}") from exc
            
            # Add breadcrumb for successful payment fetch
            add_breadcrumb(
                message=f"YuKassa get_payment success",
                category="payment",
                level="info",
                data={
                    "service": "yukassa",
                    "payment_id": payment_id,
                }
            )
            
            return resp.json()
        except Exception as exc:
            # Add breadcrumb for unexpected error
            add_breadcrumb(
                message=f"YuKassa get_payment unexpected error: {type(exc).__name__}",
                category="payment",
                level="error",
                data={
                    "service": "yukassa",
                    "payment_id": payment_id,
                    "error_type": type(exc).__name__,
                }
            )
            
            # Send exception to Sentry if not already sent
            if not isinstance(exc, YuKassaAPIError):
                capture_exception(
                    exc,
                    level="error",
                    extra={
                        "service": "yukassa",
                        "payment_id": payment_id,
                    },
                    tags={
                        "service": "yukassa",
                        "operation": "get_payment",
                    }
                )
            
            raise


class PaymentService:
    DEFAULT_TARIFFS: dict[str, dict[str, Any]] = {
        "1_month": {"price": "499.00", "days": 30},
        "3_months": {"price": "1299.00", "days": 90},
        "6_months": {"price": "2399.00", "days": 180},
        "12_months": {"price": "3999.00", "days": 365},
    }

    """
    GOAL: Create a YuKassa payment for a subscription purchase and persist Payment record.

    PARAMETERS:
      user: Any - Authenticated Django user - Must be non-null
      tariff_name: str - One of ["1_month","3_months","6_months","12_months"] - Must exist in SystemSetting['tariffs']
      return_url: str - URL to return after payment - Must be http/https URL
      payment_repo: PaymentRepository | None - Repository for payment operations - Optional
      payment_history_repo: PaymentHistoryRepository | None - Repository for payment history operations - Optional
      system_setting_repo: SystemSettingRepository | None - Repository for system setting operations - Optional

    RETURNS:
      Payment - Payment model instance with status='pending' and confirmation_url when available - Never None

    RAISES:
      ValidationError: If tariff invalid or return_url invalid
      YuKassaAPIError: If YuKassa API fails
      SystemError: If payments disabled

    GUARANTEES:
      - Payment row is created before calling YuKassa
      - If YuKassa fails, Payment remains pending (retriable)
      - Idempotency: same user+tariff within 5 min returns existing pending payment
      - Audit log entry created
    """
    @staticmethod
    def create_payment(
        *,
        user: Any,
        tariff_name: str,
        return_url: str,
        payment_repo: PaymentRepository | None = None,
        payment_history_repo: PaymentHistoryRepository | None = None,
        system_setting_repo: SystemSettingRepository | None = None,
    ) -> Payment:
        """
        Validate tariff, create DB record, call YuKassa, update record, and write audit+history.
        """
        # Use repository if provided, otherwise direct model access for backward compatibility
        if system_setting_repo is not None:
            from asgiref.sync import sync_to_async
            payments_enabled_setting = sync_to_async(system_setting_repo.get_by_key)("payments_enabled")
            payments_enabled = bool(payments_enabled_setting.value if payments_enabled_setting else True)
            tariffs_setting = sync_to_async(system_setting_repo.get_by_key)("tariffs")
            tariffs = tariffs_setting.value if tariffs_setting else PaymentService.DEFAULT_TARIFFS
        else:
            payments_enabled = bool(SystemSetting.get_setting("payments_enabled", True))
            tariffs = SystemSetting.get_setting("tariffs", None) or PaymentService.DEFAULT_TARIFFS
        
        if not payments_enabled:
            raise SystemError("Payments are currently disabled")

        if tariff_name not in tariffs:
            raise ValidationError(f"Invalid tariff: {tariff_name}")

        if not (return_url.startswith("http://") or return_url.startswith("https://")):
            raise ValidationError("return_url must be http/https")

        tariff = tariffs[tariff_name]
        amount = Decimal(str(tariff["price"]))
        days = int(tariff["days"])

        five_min_ago = timezone.now() - timedelta(minutes=5)
        
        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if payment_repo is not None:
            from asgiref.sync import sync_to_async
            existing_payments = sync_to_async(payment_repo.filter)(
                user=user, tariff_name=tariff_name, status=Payment.STATUS_PENDING, created_at__gte=five_min_ago
            )
            existing = existing_payments[0] if existing_payments else None
        else:
            existing = (
                Payment.objects.filter(user=user, tariff_name=tariff_name, status=Payment.STATUS_PENDING, created_at__gte=five_min_ago)
                .order_by("-created_at")
                .first()
            )
        
        if existing:
            return existing

        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if payment_repo is not None:
            from asgiref.sync import sync_to_async
            payment = sync_to_async(payment_repo.create)(
                user=user,
                amount=amount,
                currency="RUB",
                subscription_days=days,
                tariff_name=tariff_name,
                description=f"Подписка на {days} дней",
                status=Payment.STATUS_PENDING,
            )
        else:
            payment = Payment.objects.create(
                user=user,
                amount=amount,
                currency="RUB",
                subscription_days=days,
                tariff_name=tariff_name,
                description=f"Подписка на {days} дней",
                status=Payment.STATUS_PENDING,
            )
        
        # Use repository if provided, otherwise direct ORM access for backward compatibility
        if payment_history_repo is not None:
            from asgiref.sync import sync_to_async
            sync_to_async(payment_history_repo.create_history_event)(
                payment=payment,
                event_type="created",
                old_status="",
                new_status=payment.status,
                raw_payload={},
            )
        else:
            PaymentHistory.objects.create(payment=payment, event_type="created", old_status="", new_status=payment.status, raw_payload={})

        try:
            client = YuKassaClient(system_setting_repo=system_setting_repo)
            yresp = client.create_payment(
                amount=amount,
                currency="RUB",
                description=payment.description,
                return_url=return_url,
                metadata={"payment_id": str(payment.id), "user_id": user.id, "tariff": tariff_name},
            )
            payment.yukassa_payment_id = str(yresp.get("id") or "")
            payment.confirmation_url = str(((yresp.get("confirmation") or {}) or {}).get("confirmation_url") or "")
            payment.raw_yukassa_response = yresp
            payment.save(update_fields=["yukassa_payment_id", "confirmation_url", "raw_yukassa_response", "updated_at"])

            # Use repository if provided, otherwise direct ORM access for backward compatibility
            if payment_history_repo is not None:
                from asgiref.sync import sync_to_async
                sync_to_async(payment_history_repo.create_history_event)(
                    payment=payment,
                    event_type="yookassa_created",
                    old_status="",
                    new_status=payment.status,
                    raw_payload=yresp,
                )
            else:
                PaymentHistory.objects.create(
                    payment=payment,
                    event_type="yookassa_created",
                    old_status="",
                    new_status=payment.status,
                    raw_payload=yresp,
                )
        except Exception as exc:
            AuditService.log(
                user_id=getattr(user, "id", None),
                action_type="payment",
                action=f"Failed to create payment in YuKassa: {exc}",
                target_id=str(payment.id),
            )
            # Use repository if provided, otherwise direct ORM access for backward compatibility
            if payment_history_repo is not None:
                from asgiref.sync import sync_to_async
                sync_to_async(payment_history_repo.create_history_event)(
                    payment=payment,
                    event_type="yookassa_error",
                    old_status="",
                    new_status=payment.status,
                    raw_payload={"error": str(exc)},
                )
            else:
                PaymentHistory.objects.create(
                    payment=payment,
                    event_type="yookassa_error",
                    old_status="",
                    new_status=payment.status,
                    raw_payload={"error": str(exc)},
                )
            raise

        AuditService.log(
            user_id=getattr(user, "id", None),
            action_type="payment",
            action="Created payment",
            target_id=str(payment.id),
            details={"tariff": tariff_name, "days": days, "amount": str(amount)},
        )

        return payment
