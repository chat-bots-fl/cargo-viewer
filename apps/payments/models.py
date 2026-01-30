from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_CANCELED = "canceled"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "pending"),
        (STATUS_SUCCEEDED, "succeeded"),
        (STATUS_CANCELED, "canceled"),
        (STATUS_FAILED, "failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=8, default="RUB")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    tariff_name = models.CharField(max_length=64, blank=True, db_index=True)
    subscription_days = models.IntegerField(default=0)
    description = models.TextField(blank=True)

    yukassa_payment_id = models.CharField(max_length=128, blank=True, db_index=True)
    confirmation_url = models.URLField(blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    raw_yukassa_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        indexes = [
            models.Index(fields=["user", "created_at"], name="payments_user_created_at_idx"),
            models.Index(fields=["status", "created_at"], name="payments_status_created_at_idx"),
        ]

    def __str__(self) -> str:
        return f"Payment(id={self.id}, user_id={self.user_id}, status={self.status})"


class PaymentHistory(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="history")
    event_type = models.CharField(max_length=64, db_index=True)
    old_status = models.CharField(max_length=32, blank=True)
    new_status = models.CharField(max_length=32, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "payment_history"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"], name="payhist_event_type_created_at"),
            models.Index(fields=["payment", "created_at"], name="payhist_payment_created_at"),
        ]

    def __str__(self) -> str:
        return f"PaymentHistory(payment_id={self.payment_id}, event_type={self.event_type})"
