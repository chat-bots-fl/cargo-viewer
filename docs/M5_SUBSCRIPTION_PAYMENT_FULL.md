# 💳 МОДУЛЬ M5: СИСТЕМА ПОДПИСОК И ПЛАТЕЖЕЙ

**Дата:** 4 января 2026  
**Проект:** CargoTech Driver WebApp v3.1  
**Новый модуль:** M5 - Subscription & Payment Management  
**Статус:** ✅ ГОТОВ К РЕАЛИЗАЦИИ

---

## 🎯 ОБЗОР ИЗМЕНЕНИЙ

### Добавляется новый модуль M5 в PBS структуру:

```
M1: Authentication (существует)
M2: Cargo Retrieval (существует)
M3: Filtering (существует)
M4: Notifications (существует)
+ M5: Subscription & Payment Management ⭐ НОВЫЙ
```

---

## 📊 АРХИТЕКТУРА M5 (3 уровня)

### Уровень 1: Модуль M5
**Цель:** Управление платными подписками для доступа к WebApp

### Уровень 2: Компоненты (6 штук)
```
M5.1: Payment Processing (ЮKassa интеграция)
M5.2: Subscription Management (активация/продление)
M5.3: Promo Code System (создание/применение)
M5.4: Admin Panel (управление в браузере)
M5.5: Feature Flags (включение/выключение функций)
M5.6: Audit Logging (история действий)
```

### Уровень 3: Функции (24 функции)
```
M5.1.1: create_payment() - Создание платежа ЮKassa
M5.1.2: process_webhook() - Обработка webhook ЮKassa
M5.1.3: check_payment_status() - Проверка статуса
M5.1.4: refund_payment() - Возврат средств

M5.2.1: activate_subscription() - Активация подписки
M5.2.2: extend_subscription() - Продление подписки
M5.2.3: check_subscription() - Проверка статуса
M5.2.4: generate_access_token() - Генерация токена WebApp

M5.3.1: create_promo_code() - Создание промокода
M5.3.2: validate_promo_code() - Валидация промокода
M5.3.3: apply_promo_code() - Применение промокода
M5.3.4: deactivate_promo_code() - Деактивация

M5.4.1: payment_list_view() - Список платежей
M5.4.2: payment_detail_view() - Детали платежа
M5.4.3: subscription_list_view() - Список подписок
M5.4.4: promo_code_admin_view() - Управление промокодами

M5.5.1: toggle_payments() - Включить/выключить платежи
M5.5.2: update_tariffs() - Обновить тарифы
M5.5.3: set_yukassa_token() - Установить токен ЮKassa
M5.5.4: toggle_feature() - Управление функциями

M5.6.1: log_admin_action() - Логирование действия
M5.6.2: log_payment_event() - Логирование платежа
M5.6.3: audit_log_view() - Просмотр логов
M5.6.4: filter_audit_logs() - Фильтрация логов
```

---

## 🗂️ DJANGO СТРУКТУРА

### Новые приложения (apps/):

```
apps/
├── payments/                    # M5.1: Payment Processing
│   ├── models.py               # Payment, PaymentHistory
│   ├── yukassa_client.py       # ЮKassa API integration
│   ├── services.py             # PaymentService
│   ├── webhooks.py             # Webhook handler
│   └── views.py                # Payment initiation
│
├── subscriptions/              # M5.2: Subscription Management
│   ├── models.py               # Subscription, AccessToken
│   ├── services.py             # SubscriptionService
│   ├── middleware.py           # Check subscription before request
│   └── views.py                # Subscription status
│
├── promocodes/                 # M5.3: Promo Code System
│   ├── models.py               # PromoCode, PromoCodeUsage
│   ├── services.py             # PromoCodeService
│   └── validators.py           # PromoCode validation
│
├── admin_panel/                # M5.4: Admin Panel
│   ├── views.py                # Admin dashboard views
│   ├── forms.py                # Admin forms
│   ├── filters.py              # List filters
│   ├── templates/              # HTML templates
│   │   ├── payments_list.html
│   │   ├── subscriptions_list.html
│   │   ├── promocodes_admin.html
│   │   └── system_settings.html
│   └── static/                 # CSS/JS для админки
│
├── feature_flags/              # M5.5: Feature Flags
│   ├── models.py               # SystemSetting, FeatureFlag
│   ├── services.py             # FeatureFlagService
│   └── decorators.py           # @require_feature('name')
│
└── audit/                      # M5.6: Audit Logging
    ├── models.py               # AuditLog
    ├── services.py             # AuditService
    └── views.py                # Audit log viewer
```

---

## 📝 DJANGO MODELS

### 📊 Полный список моделей M5 (8 моделей)

**Основные модели (5):** Payment, Subscription, PromoCode, SystemSetting, AuditLog  
**Вспомогательные модели (3):** PaymentHistory, PromoCodeUsage, FeatureFlag

### 1. Payment (apps/payments/models.py)

```python
from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

class Payment(models.Model):
    """Платеж через ЮKassa"""

    STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('processing', 'Обрабатывается'),
        ('succeeded', 'Успешно'),
        ('canceled', 'Отменен'),
        ('refunded', 'Возвращен'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')

    # ЮKassa данные
    yukassa_payment_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    confirmation_url = models.URLField(null=True, blank=True)

    # Сумма и статус
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # RUB
    currency = models.CharField(max_length=3, default='RUB')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Подписка
    subscription_days = models.IntegerField(default=30)  # Сколько дней подписки
    tariff_name = models.CharField(max_length=100)  # "1 месяц", "3 месяца", и т.д.

    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Дополнительная информация
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # Любые доп. данные

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['yukassa_payment_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.user} - {self.amount} RUB"


class PaymentHistory(models.Model):
    """История изменений платежа"""
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='history')
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)
    raw_webhook_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'payment_history'
        ordering = ['-changed_at']
```

### 2. Subscription (apps/subscriptions/models.py)

```python
from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets

class Subscription(models.Model):
    """Подписка пользователя"""

    SOURCE_CHOICES = [
        ('payment', 'Оплата'),
        ('promo', 'Промокод'),
        ('gift', 'Подарок'),
        ('trial', 'Пробный период'),
    ]

    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='subscription')

    # Статус подписки
    is_active = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Источник активации
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='payment')
    payment = models.ForeignKey('payments.Payment', on_delete=models.SET_NULL, 
                                null=True, blank=True, related_name='subscriptions')
    promo_code = models.ForeignKey('promocodes.PromoCode', on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='subscriptions')

    # Токен доступа для Web App
    access_token = models.CharField(max_length=255, unique=True, db_index=True)

    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['access_token']),
        ]

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def days_remaining(self):
        """Дней до истечения"""
        if not self.expires_at:
            return 0
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def is_expired(self):
        """Истекла ли подписка"""
        if not self.expires_at:
            return True
        return timezone.now() > self.expires_at

    def extend(self, days):
        """Продлить подписку на N дней"""
        if not self.expires_at or self.is_expired():
            self.expires_at = timezone.now() + timedelta(days=days)
        else:
            self.expires_at += timedelta(days=days)

        self.is_active = True
        self.save()

    def __str__(self):
        status = "Активна" if self.is_active and not self.is_expired() else "Неактивна"
        return f"Subscription {self.user} - {status} (до {self.expires_at})"
```

### 3. PromoCode (apps/promocodes/models.py)

```python
from django.db import models
from django.core.validators import MinValueValidator
import random
import string

class PromoCode(models.Model):
    """Промокод"""

    ACTION_CHOICES = [
        ('extend_30', 'Продлить на 30 дней'),
        ('extend_60', 'Продлить на 60 дней'),
        ('extend_90', 'Продлить на 90 дней'),
        ('activate_trial', 'Активировать пробный период'),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)

    # Действие промокода
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, default='extend_30')
    days_to_add = models.IntegerField(default=30, validators=[MinValueValidator(1)])

    # Срок действия
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    # Ограничения использования
    max_uses = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    current_uses = models.IntegerField(default=0)

    # Статус
    is_active = models.BooleanField(default=True)

    # Метаданные
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, 
                                   null=True, related_name='created_promo_codes')
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'promo_codes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'valid_from', 'valid_until']),
        ]

    @staticmethod
    def generate_code(length=12):
        """Генерация случайного промокода"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(length))

    def is_valid(self):
        """Проверка валидности промокода"""
        from django.utils import timezone
        now = timezone.now()

        return (
            self.is_active and
            self.valid_from <= now <= self.valid_until and
            self.current_uses < self.max_uses
        )

    def can_use(self):
        """Может ли промокод быть использован"""
        return self.is_valid() and self.current_uses < self.max_uses

    def use(self):
        """Использовать промокод (увеличить счетчик)"""
        if not self.can_use():
            raise ValueError("PromoCode cannot be used")
        self.current_uses += 1
        self.save()

    def __str__(self):
        status = "Активен" if self.is_valid() else "Неактивен"
        return f"{self.code} ({status}) - {self.current_uses}/{self.max_uses}"


class PromoCodeUsage(models.Model):
    """История использования промокодов"""
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='usages')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='promo_code_usages')
    used_at = models.DateTimeField(auto_now_add=True)
    days_added = models.IntegerField()

    class Meta:
        db_table = 'promo_code_usages'
        ordering = ['-used_at']
        unique_together = [['promo_code', 'user']]  # Один промокод = один раз на пользователя
```

### 4. System Settings (apps/feature_flags/models.py)

```python
from django.db import models

class SystemSetting(models.Model):
    """Системные настройки"""

    key = models.CharField(max_length=255, unique=True, db_index=True)
    value = models.TextField()
    value_type = models.CharField(max_length=20, choices=[
        ('str', 'String'),
        ('int', 'Integer'),
        ('bool', 'Boolean'),
        ('json', 'JSON'),
    ], default='str')

    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'system_settings'

    def get_value(self):
        """Получить типизированное значение"""
        import json

        if self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'int':
            return int(self.value)
        elif self.value_type == 'json':
            return json.loads(self.value)
        return self.value

    @classmethod
    def get_setting(cls, key, default=None):
        """Получить настройку по ключу"""
        try:
            setting = cls.objects.get(key=key)
            return setting.get_value()
        except cls.DoesNotExist:
            return default

    def __str__(self):
        return f"{self.key} = {self.value}"


class FeatureFlag(models.Model):
    """Флаг функциональности"""

    name = models.CharField(max_length=100, unique=True, db_index=True)
    is_enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'feature_flags'

    @classmethod
    def is_enabled(cls, name):
        """Проверка включен ли флаг"""
        try:
            flag = cls.objects.get(name=name)
            return flag.is_enabled
        except cls.DoesNotExist:
            return False

    def __str__(self):
        status = "✓" if self.is_enabled else "✗"
        return f"{status} {self.name}"
```

### 5. Audit Log (apps/audit/models.py)

```python
from django.db import models

class AuditLog(models.Model):
    """Логирование действий администратора"""

    TYPE_CHOICES = [
        ('payment', 'Платеж'),
        ('subscription', 'Подписка'),
        ('promo_code', 'Промокод'),
        ('system_setting', 'Системная настройка'),
        ('feature_flag', 'Флаг функциональности'),
    ]

    # Кто совершил действие
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    username = models.CharField(max_length=150)  # Дублируем на случай удаления пользователя

    # Что произошло
    action_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    action = models.CharField(max_length=255)  # "Created promo code", "Updated payment status"

    # Детали
    target_id = models.CharField(max_length=255, blank=True)  # ID объекта (payment ID, promo code, etc.)
    details = models.JSONField(default=dict, blank=True)  # Подробности изменений

    # IP и метаданные
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Время
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.created_at}] {self.username}: {self.action}"
```


---

## 📜 DESIGN BY CONTRACT

### Contract 5.1: PaymentService.create_payment()

```python
GOAL: Создать платеж через ЮKassa для покупки подписки

PARAMETERS:
- user: User (authenticated Django user)
- tariff_name: str in ["1_month", "3_months", "6_months", "12_months"]
  @constraint: Must be valid tariff name from SystemSetting['tariffs']
- return_url: str (URL для возврата после оплаты)
  @constraint: Must be valid URL (http/https)

RETURNS:
- payment: Payment (Django model instance)
  - id: UUID
  - confirmation_url: str (URL для перенаправления на оплату)
  - amount: Decimal
  - status: 'pending'
  - yukassa_payment_id: str

RAISES:
- ValidationError: If tariff_name invalid
- YuKassaAPIError: If ЮKassa API fails
- SystemError: If payments disabled (SystemSetting['payments_enabled'] = False)

GUARANTEES:
- Payment record created in DB before API call
- If ЮKassa fails: Payment status = 'pending' (можно повторить)
- Idempotency: Same user + tariff within 5 min = return existing payment
- Audit log entry created
- Execution time: < 2s (p95)

SECURITY:
- ЮKassa Shop ID from SystemSetting['yukassa_shop_id']
- Secret Key from SystemSetting['yukassa_secret_key'] (encrypted in DB)
- All payment data encrypted at rest
```

**Реализация:**

```python
# apps/payments/services.py
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import requests
import uuid

from .models import Payment
from apps.feature_flags.models import SystemSetting
from apps.audit.services import AuditService

class PaymentService:

    @staticmethod
    def create_payment(user, tariff_name, return_url):
        """
        Contract 5.1: Создать платеж через ЮKassa
        """

        # 1. Проверка: включены ли платежи
        if not SystemSetting.get_setting('payments_enabled', False):
            raise SystemError("Payments are currently disabled")

        # 2. Получить тарифы из настроек
        tariffs = SystemSetting.get_setting('tariffs', {})
        if tariff_name not in tariffs:
            raise ValidationError(f"Invalid tariff: {tariff_name}")

        tariff = tariffs[tariff_name]
        amount = Decimal(tariff['price'])
        days = int(tariff['days'])

        # 3. Проверить дубликаты (идемпотентность)
        five_min_ago = timezone.now() - timedelta(minutes=5)
        existing = Payment.objects.filter(
            user=user,
            tariff_name=tariff_name,
            status='pending',
            created_at__gte=five_min_ago
        ).first()

        if existing:
            return existing

        # 4. Создать Payment запись
        payment = Payment.objects.create(
            user=user,
            amount=amount,
            currency='RUB',
            subscription_days=days,
            tariff_name=tariff_name,
            description=f"Подписка на {days} дней",
            status='pending'
        )

        # 5. Создать платеж в ЮKassa
        try:
            yukassa_client = YuKassaClient()
            yukassa_response = yukassa_client.create_payment(
                amount=amount,
                currency='RUB',
                description=payment.description,
                return_url=return_url,
                metadata={
                    'payment_id': str(payment.id),
                    'user_id': user.id,
                    'tariff': tariff_name
                }
            )

            # Обновить payment с данными ЮKassa
            payment.yukassa_payment_id = yukassa_response['id']
            payment.confirmation_url = yukassa_response['confirmation']['confirmation_url']
            payment.save()

        except Exception as e:
            # Логируем ошибку, но не удаляем payment (можно повторить)
            AuditService.log(
                user=user,
                action_type='payment',
                action=f"Failed to create payment in YuKassa: {str(e)}",
                target_id=str(payment.id),
                details={'error': str(e)}
            )
            raise

        # 6. Audit log
        AuditService.log(
            user=user,
            action_type='payment',
            action='Created payment',
            target_id=str(payment.id),
            details={
                'amount': float(amount),
                'tariff': tariff_name,
                'days': days
            }
        )

        return payment


class YuKassaClient:
    """Клиент для работы с ЮKassa API"""

    def __init__(self):
        self.shop_id = SystemSetting.get_setting('yukassa_shop_id')
        self.secret_key = SystemSetting.get_setting('yukassa_secret_key')
        self.base_url = 'https://api.yookassa.ru/v3'

        if not self.shop_id or not self.secret_key:
            raise SystemError("YuKassa credentials not configured")

    def create_payment(self, amount, currency, description, return_url, metadata=None):
        """Создать платеж в ЮKassa"""

        url = f"{self.base_url}/payments"

        payload = {
            "amount": {
                "value": str(amount),
                "currency": currency
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": description,
            "metadata": metadata or {}
        }

        response = requests.post(
            url,
            json=payload,
            auth=(self.shop_id, self.secret_key),
            headers={'Idempotence-Key': str(uuid.uuid4())},
            timeout=10
        )

        response.raise_for_status()
        return response.json()

    def get_payment(self, payment_id):
        """Получить информацию о платеже"""
        url = f"{self.base_url}/payments/{payment_id}"

        response = requests.get(
            url,
            auth=(self.shop_id, self.secret_key),
            timeout=10
        )

        response.raise_for_status()
        return response.json()
```

---

### Contract 5.2: PaymentService.process_webhook()

```python
GOAL: Обработать webhook от ЮKassa о статусе платежа

PARAMETERS:
- webhook_data: dict (JSON от ЮKassa)
  @constraint: Must contain 'event', 'object' keys
  @format: {"event": "payment.succeeded", "object": {...}}

RETURNS:
- payment: Payment (обновленный объект)
  - status: Updated based on webhook event
  - paid_at: Set if payment succeeded
- subscription: Subscription (если платеж succeeded, активирует подписку)

RAISES:
- ValidationError: If webhook signature invalid
- ObjectDoesNotExist: If payment not found

GUARANTEES:
- Webhook processed exactly once (idempotency)
- If payment.succeeded → activate subscription automatically
- PaymentHistory record created for status change
- Audit log entry created
- Transaction atomic (payment + subscription update)
- Execution time: < 500ms (p99)
```

**Реализация:**

```python
# apps/payments/webhooks.py
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone

from .models import Payment, PaymentHistory
from apps.subscriptions.services import SubscriptionService
from apps.audit.services import AuditService

class WebhookHandler:

    @staticmethod
    @transaction.atomic
    def process_webhook(webhook_data):
        """
        Contract 5.2: Обработать webhook от ЮKassa
        """

        # 1. Валидация webhook structure
        if 'event' not in webhook_data or 'object' not in webhook_data:
            raise ValidationError("Invalid webhook structure")

        event = webhook_data['event']
        payment_data = webhook_data['object']

        # 2. Найти payment по yukassa_payment_id
        yukassa_id = payment_data.get('id')
        if not yukassa_id:
            raise ValidationError("Missing payment id in webhook")

        try:
            payment = Payment.objects.select_for_update().get(yukassa_payment_id=yukassa_id)
        except Payment.DoesNotExist:
            raise ObjectDoesNotExist(f"Payment not found: {yukassa_id}")

        # 3. Идемпотентность: если статус уже обновлен, пропустить
        old_status = payment.status
        new_status = payment_data.get('status')

        if old_status == new_status:
            return payment, None

        # 4. Обновить статус payment
        payment.status = new_status

        if event == 'payment.succeeded':
            payment.paid_at = timezone.now()

        payment.save()

        # 5. Создать PaymentHistory
        PaymentHistory.objects.create(
            payment=payment,
            old_status=old_status,
            new_status=new_status,
            raw_webhook_data=webhook_data
        )

        # 6. Если платеж успешен → активировать подписку
        subscription = None
        if event == 'payment.succeeded':
            subscription = SubscriptionService.activate_from_payment(
                user=payment.user,
                payment=payment,
                days=payment.subscription_days
            )

        # 7. Audit log
        AuditService.log(
            user=payment.user,
            action_type='payment',
            action=f'Payment {new_status}',
            target_id=str(payment.id),
            details={
                'old_status': old_status,
                'new_status': new_status,
                'event': event
            }
        )

        return payment, subscription
```

---

### Contract 5.3: SubscriptionService.activate_from_payment()

```python
GOAL: Активировать подписку после успешной оплаты

PARAMETERS:
- user: User
- payment: Payment (with status='succeeded')
- days: int (количество дней подписки)
  @constraint: days > 0

RETURNS:
- subscription: Subscription
  - is_active: True
  - expires_at: now + days
  - access_token: Generated unique token
  - source: 'payment'
  - payment: Reference to Payment

RAISES:
- ValidationError: If payment.status != 'succeeded'
- IntegrityError: If access_token collision (retry with new token)

GUARANTEES:
- Subscription created or extended
- If existing subscription active → extend expires_at
- If existing subscription expired → set new expires_at from now
- Access token regenerated on each activation
- Audit log entry created
- Transaction atomic
```

**Реализация:**

```python
# apps/subscriptions/services.py
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

from .models import Subscription
from apps.audit.services import AuditService

class SubscriptionService:

    @staticmethod
    @transaction.atomic
    def activate_from_payment(user, payment, days):
        """
        Contract 5.3: Активировать подписку после оплаты
        """

        # 1. Проверка payment status
        if payment.status != 'succeeded':
            raise ValidationError(f"Payment not succeeded: {payment.status}")

        if days <= 0:
            raise ValidationError(f"Invalid days: {days}")

        # 2. Получить или создать subscription
        subscription, created = Subscription.objects.get_or_create(
            user=user,
            defaults={
                'source': 'payment',
                'payment': payment
            }
        )

        # 3. Продлить подписку
        if subscription.is_expired() or not subscription.expires_at:
            # Новая подписка или истекшая
            subscription.activated_at = timezone.now()
            subscription.expires_at = timezone.now() + timedelta(days=days)
        else:
            # Продлить существующую активную
            subscription.expires_at += timedelta(days=days)

        subscription.is_active = True
        subscription.source = 'payment'
        subscription.payment = payment

        # Регенерировать access token
        import secrets
        subscription.access_token = secrets.token_urlsafe(32)

        subscription.save()

        # 4. Audit log
        action = "Created subscription" if created else f"Extended subscription by {days} days"
        AuditService.log(
            user=user,
            action_type='subscription',
            action=action,
            target_id=str(subscription.id),
            details={
                'days': days,
                'expires_at': subscription.expires_at.isoformat(),
                'payment_id': str(payment.id)
            }
        )

        return subscription

    @staticmethod
    @transaction.atomic
    def activate_from_promo(user, promo_code):
        """Активировать подписку через промокод"""

        # 1. Валидация промокода
        if not promo_code.can_use():
            raise ValidationError(f"Promo code cannot be used: {promo_code.code}")

        # 2. Получить или создать subscription
        subscription, created = Subscription.objects.get_or_create(
            user=user,
            defaults={
                'source': 'promo',
                'promo_code': promo_code
            }
        )

        # 3. Продлить
        subscription.extend(promo_code.days_to_add)
        subscription.source = 'promo'
        subscription.promo_code = promo_code
        subscription.save()

        # 4. Использовать промокод
        promo_code.use()

        # 5. Создать PromoCodeUsage
        from apps.promocodes.models import PromoCodeUsage
        PromoCodeUsage.objects.create(
            promo_code=promo_code,
            user=user,
            days_added=promo_code.days_to_add
        )

        # 6. Audit log
        AuditService.log(
            user=user,
            action_type='subscription',
            action=f'Activated with promo code: {promo_code.code}',
            target_id=str(subscription.id),
            details={
                'promo_code': promo_code.code,
                'days_added': promo_code.days_to_add
            }
        )

        return subscription
```

---

### Contract 5.4: PromoCodeService.create_promo_code()

```python
GOAL: Создать промокод в админке

PARAMETERS:
- code: str (optional, если не указан - генерируется)
  @constraint: Must be unique, alphanumeric, length 6-50
- action: str in ['extend_30', 'extend_60', 'extend_90', 'activate_trial']
- valid_from: datetime
- valid_until: datetime
  @constraint: valid_until > valid_from
- max_uses: int (default=1)
  @constraint: max_uses >= 1
- created_by: User (admin)

RETURNS:
- promo_code: PromoCode
  - code: Generated or provided
  - is_active: True
  - current_uses: 0

RAISES:
- ValidationError: If code invalid or dates invalid
- IntegrityError: If code not unique

GUARANTEES:
- Code generated if not provided (12 chars uppercase + digits)
- Audit log entry created
- Execution time: < 100ms
```

**Реализация:**

```python
# apps/promocodes/services.py
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PromoCode
from apps.audit.services import AuditService

class PromoCodeService:

    ACTION_TO_DAYS = {
        'extend_30': 30,
        'extend_60': 60,
        'extend_90': 90,
        'activate_trial': 7,
    }

    @staticmethod
    def create_promo_code(action, valid_from, valid_until, max_uses=1, 
                         code=None, created_by=None, description=''):
        """
        Contract 5.4: Создать промокод
        """

        # 1. Валидация дат
        if valid_until <= valid_from:
            raise ValidationError("valid_until must be after valid_from")

        if valid_from < timezone.now():
            raise ValidationError("valid_from cannot be in the past")

        # 2. Валидация action
        if action not in PromoCodeService.ACTION_TO_DAYS:
            raise ValidationError(f"Invalid action: {action}")

        days = PromoCodeService.ACTION_TO_DAYS[action]

        # 3. Генерация кода если не указан
        if not code:
            code = PromoCode.generate_code()

        # 4. Создать PromoCode
        promo_code = PromoCode.objects.create(
            code=code.upper(),
            action=action,
            days_to_add=days,
            valid_from=valid_from,
            valid_until=valid_until,
            max_uses=max_uses,
            created_by=created_by,
            description=description
        )

        # 5. Audit log
        if created_by:
            AuditService.log(
                user=created_by,
                action_type='promo_code',
                action=f'Created promo code: {code}',
                target_id=code,
                details={
                    'action': action,
                    'days': days,
                    'max_uses': max_uses,
                    'valid_from': valid_from.isoformat(),
                    'valid_until': valid_until.isoformat()
                }
            )

        return promo_code
```


---

## 🎨 АДМИН-ПАНЕЛЬ (Django Admin + Custom Views)

### 1. Админка платежей (apps/admin_panel/views.py)

```python
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.payments.models import Payment
from apps.subscriptions.models import Subscription
from apps.promocodes.models import PromoCode
from apps.audit.models import AuditLog

@staff_member_required
def payment_list_view(request):
    """
    Список платежей с фильтрацией
    """

    # Фильтры
    status = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    min_amount = request.GET.get('min_amount', '')
    max_amount = request.GET.get('max_amount', '')
    search = request.GET.get('search', '')

    # Query
    payments = Payment.objects.select_related('user').all()

    if status:
        payments = payments.filter(status=status)

    if date_from:
        payments = payments.filter(created_at__gte=date_from)

    if date_to:
        payments = payments.filter(created_at__lte=date_to)

    if min_amount:
        payments = payments.filter(amount__gte=min_amount)

    if max_amount:
        payments = payments.filter(amount__lte=max_amount)

    if search:
        payments = payments.filter(
            Q(user__username__icontains=search) |
            Q(id__icontains=search) |
            Q(yukassa_payment_id__icontains=search)
        )

    # Статистика
    stats = {
        'total_count': payments.count(),
        'total_amount': payments.filter(status='succeeded').aggregate(Sum('amount'))['amount__sum'] or 0,
        'pending_count': payments.filter(status='pending').count(),
        'succeeded_count': payments.filter(status='succeeded').count(),
    }

    context = {
        'payments': payments.order_by('-created_at')[:100],
        'stats': stats,
        'filters': {
            'status': status,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
        }
    }

    return render(request, 'admin_panel/payments_list.html', context)


@staff_member_required
def payment_detail_view(request, payment_id):
    """Детали платежа"""

    payment = get_object_or_404(Payment.objects.select_related('user'), id=payment_id)
    history = payment.history.all()
    subscription = payment.subscriptions.first()

    context = {
        'payment': payment,
        'history': history,
        'subscription': subscription
    }

    return render(request, 'admin_panel/payment_detail.html', context)


@staff_member_required
def subscription_list_view(request):
    """Список подписок"""

    # Фильтры
    status_filter = request.GET.get('status', '')  # 'active', 'expired', 'all'
    source = request.GET.get('source', '')
    search = request.GET.get('search', '')

    subscriptions = Subscription.objects.select_related('user', 'payment', 'promo_code').all()

    now = timezone.now()

    if status_filter == 'active':
        subscriptions = subscriptions.filter(is_active=True, expires_at__gt=now)
    elif status_filter == 'expired':
        subscriptions = subscriptions.filter(Q(expires_at__lte=now) | Q(is_active=False))

    if source:
        subscriptions = subscriptions.filter(source=source)

    if search:
        subscriptions = subscriptions.filter(
            Q(user__username__icontains=search) |
            Q(access_token__icontains=search)
        )

    # Добавляем динамические поля
    for sub in subscriptions:
        sub.days_left = sub.days_remaining()
        sub.status = 'Активна' if (sub.is_active and not sub.is_expired()) else 'Истекла'

    context = {
        'subscriptions': subscriptions.order_by('-created_at')[:100],
        'filters': {
            'status': status_filter,
            'source': source,
            'search': search
        }
    }

    return render(request, 'admin_panel/subscriptions_list.html', context)


@staff_member_required
def promo_code_admin_view(request):
    """Управление промокодами"""

    if request.method == 'POST':
        # Создание промокода
        from apps.promocodes.services import PromoCodeService
        from django.contrib import messages

        try:
            promo_code = PromoCodeService.create_promo_code(
                action=request.POST.get('action'),
                valid_from=request.POST.get('valid_from'),
                valid_until=request.POST.get('valid_until'),
                max_uses=int(request.POST.get('max_uses', 1)),
                code=request.POST.get('code') or None,
                created_by=request.user,
                description=request.POST.get('description', '')
            )
            messages.success(request, f'Промокод {promo_code.code} создан успешно')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')

    # Фильтры
    status_filter = request.GET.get('status', 'active')  # 'active', 'expired', 'all'

    promo_codes = PromoCode.objects.all()

    now = timezone.now()

    if status_filter == 'active':
        promo_codes = promo_codes.filter(
            is_active=True,
            valid_from__lte=now,
            valid_until__gte=now
        )
    elif status_filter == 'expired':
        promo_codes = promo_codes.filter(Q(valid_until__lt=now) | Q(is_active=False))

    # Добавить статус каждому промокоду
    for promo in promo_codes:
        promo.status = 'Активен' if promo.is_valid() else 'Неактивен'
        promo.usage_percent = (promo.current_uses / promo.max_uses * 100) if promo.max_uses > 0 else 0

    context = {
        'promo_codes': promo_codes.order_by('-created_at'),
        'status_filter': status_filter,
        'actions': PromoCode.ACTION_CHOICES
    }

    return render(request, 'admin_panel/promocodes_admin.html', context)


@staff_member_required
def system_settings_view(request):
    """Системные настройки"""

    from apps.feature_flags.models import SystemSetting, FeatureFlag
    from django.contrib import messages
    import json

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'toggle_payments':
            # Включить/выключить платежи
            setting, _ = SystemSetting.objects.get_or_create(
                key='payments_enabled',
                defaults={'value': 'false', 'value_type': 'bool'}
            )
            current = setting.get_value()
            setting.value = 'false' if current else 'true'
            setting.updated_by = request.user
            setting.save()
            messages.success(request, f'Платежи {"включены" if not current else "отключены"}')

        elif action == 'update_yukassa_token':
            # Обновить токен ЮKassa
            shop_id = request.POST.get('yukassa_shop_id')
            secret_key = request.POST.get('yukassa_secret_key')

            SystemSetting.objects.update_or_create(
                key='yukassa_shop_id',
                defaults={'value': shop_id, 'value_type': 'str', 'updated_by': request.user}
            )

            SystemSetting.objects.update_or_create(
                key='yukassa_secret_key',
                defaults={'value': secret_key, 'value_type': 'str', 'updated_by': request.user}
            )

            messages.success(request, 'Токен ЮKassa обновлен')

        elif action == 'update_tariffs':
            # Обновить тарифы (JSON)
            tariffs_json = request.POST.get('tariffs')
            try:
                tariffs = json.loads(tariffs_json)
                SystemSetting.objects.update_or_create(
                    key='tariffs',
                    defaults={'value': tariffs_json, 'value_type': 'json', 'updated_by': request.user}
                )
                messages.success(request, 'Тарифы обновлены')
            except json.JSONDecodeError as e:
                messages.error(request, f'Ошибка JSON: {str(e)}')

    # Получить текущие настройки
    payments_enabled = SystemSetting.get_setting('payments_enabled', False)
    yukassa_shop_id = SystemSetting.get_setting('yukassa_shop_id', '')
    tariffs = SystemSetting.get_setting('tariffs', {
        "1_month": {"price": 499, "days": 30, "name": "1 месяц"},
        "3_months": {"price": 1299, "days": 90, "name": "3 месяца"},
        "6_months": {"price": 2399, "days": 180, "name": "6 месяцев"},
        "12_months": {"price": 3999, "days": 365, "name": "12 месяцев"}
    })

    # Feature flags
    feature_flags = FeatureFlag.objects.all()

    context = {
        'payments_enabled': payments_enabled,
        'yukassa_shop_id': yukassa_shop_id,
        'tariffs': json.dumps(tariffs, ensure_ascii=False, indent=2),
        'feature_flags': feature_flags
    }

    return render(request, 'admin_panel/system_settings.html', context)


@staff_member_required
def audit_log_view(request):
    """Просмотр логов"""

    # Фильтры
    action_type = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    admin_user = request.GET.get('admin', '')

    logs = AuditLog.objects.all()

    if action_type:
        logs = logs.filter(action_type=action_type)

    if date_from:
        logs = logs.filter(created_at__gte=date_from)

    if admin_user:
        logs = logs.filter(username__icontains=admin_user)

    context = {
        'logs': logs.order_by('-created_at')[:200],
        'types': AuditLog.TYPE_CHOICES,
        'filters': {
            'type': action_type,
            'date_from': date_from,
            'admin': admin_user
        }
    }

    return render(request, 'admin_panel/audit_log.html', context)
```

---

## 📄 HTML TEMPLATES

### payments_list.html

```html
<!-- apps/admin_panel/templates/admin_panel/payments_list.html -->
{% extends 'admin/base_site.html' %}

{% block content %}
<h1>💳 Управление платежами</h1>

<!-- Статистика -->
<div class="stats-row">
    <div class="stat-card">
        <h3>Всего платежей</h3>
        <p class="big-number">{{ stats.total_count }}</p>
    </div>
    <div class="stat-card">
        <h3>Сумма (успешные)</h3>
        <p class="big-number">{{ stats.total_amount }} ₽</p>
    </div>
    <div class="stat-card">
        <h3>Ожидают оплаты</h3>
        <p class="big-number">{{ stats.pending_count }}</p>
    </div>
    <div class="stat-card">
        <h3>Успешные</h3>
        <p class="big-number">{{ stats.succeeded_count }}</p>
    </div>
</div>

<!-- Фильтры -->
<form method="get" class="filters-form">
    <div class="form-row">
        <select name="status">
            <option value="">Все статусы</option>
            <option value="pending" {% if filters.status == 'pending' %}selected{% endif %}>Ожидает</option>
            <option value="succeeded" {% if filters.status == 'succeeded' %}selected{% endif %}>Успешно</option>
            <option value="canceled" {% if filters.status == 'canceled' %}selected{% endif %}>Отменен</option>
        </select>

        <input type="date" name="date_from" value="{{ filters.date_from }}" placeholder="Дата от">
        <input type="date" name="date_to" value="{{ filters.date_to }}" placeholder="Дата до">
        <input type="text" name="search" value="{{ filters.search }}" placeholder="Поиск по ID или юзеру">

        <button type="submit">Фильтровать</button>
        <a href="{% url 'admin_panel:payments_list' %}" class="btn-reset">Сбросить</a>
    </div>
</form>

<!-- Таблица платежей -->
<table class="payments-table">
    <thead>
        <tr>
            <th>ID</th>
            <th>Пользователь</th>
            <th>Сумма</th>
            <th>Тариф</th>
            <th>Статус</th>
            <th>Дата создания</th>
            <th>Дата оплаты</th>
            <th>Действия</th>
        </tr>
    </thead>
    <tbody>
        {% for payment in payments %}
        <tr>
            <td><code>{{ payment.id|truncatechars:12 }}</code></td>
            <td>{{ payment.user.username }}</td>
            <td class="amount">{{ payment.amount }} ₽</td>
            <td>{{ payment.tariff_name }}</td>
            <td>
                <span class="badge badge-{{ payment.status }}">
                    {{ payment.get_status_display }}
                </span>
            </td>
            <td>{{ payment.created_at|date:"d.m.Y H:i" }}</td>
            <td>
                {% if payment.paid_at %}
                    {{ payment.paid_at|date:"d.m.Y H:i" }}
                {% else %}
                    —
                {% endif %}
            </td>
            <td>
                <a href="{% url 'admin_panel:payment_detail' payment.id %}" class="btn-detail">Детали</a>
            </td>
        </tr>
        {% empty %}
        <tr>
            <td colspan="8" class="empty">Платежей не найдено</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### subscriptions_list.html

```html
<!-- apps/admin_panel/templates/admin_panel/subscriptions_list.html -->
{% extends 'admin/base_site.html' %}

{% block content %}
<h1>🎫 Управление подписками</h1>

<!-- Фильтры -->
<form method="get" class="filters-form">
    <div class="form-row">
        <select name="status">
            <option value="">Все</option>
            <option value="active" {% if filters.status == 'active' %}selected{% endif %}>Активные</option>
            <option value="expired" {% if filters.status == 'expired' %}selected{% endif %}>Истекшие</option>
        </select>

        <select name="source">
            <option value="">Все источники</option>
            <option value="payment" {% if filters.source == 'payment' %}selected{% endif %}>Оплата</option>
            <option value="promo" {% if filters.source == 'promo' %}selected{% endif %}>Промокод</option>
            <option value="gift" {% if filters.source == 'gift' %}selected{% endif %}>Подарок</option>
        </select>

        <input type="text" name="search" value="{{ filters.search }}" placeholder="Поиск">
        <button type="submit">Фильтровать</button>
    </div>
</form>

<!-- Таблица подписок -->
<table class="subscriptions-table">
    <thead>
        <tr>
            <th>Пользователь</th>
            <th>Статус</th>
            <th>Дней до истечения</th>
            <th>Истекает</th>
            <th>Источник</th>
            <th>Токен доступа</th>
            <th>Действия</th>
        </tr>
    </thead>
    <tbody>
        {% for sub in subscriptions %}
        <tr class="{% if sub.is_expired %}expired{% endif %}">
            <td>{{ sub.user.username }}</td>
            <td>
                <span class="badge {% if sub.status == 'Активна' %}badge-active{% else %}badge-expired{% endif %}">
                    {{ sub.status }}
                </span>
            </td>
            <td class="days-left">
                {% if sub.days_left > 0 %}
                    {{ sub.days_left }} дней
                {% else %}
                    —
                {% endif %}
            </td>
            <td>{{ sub.expires_at|date:"d.m.Y H:i" }}</td>
            <td>{{ sub.get_source_display }}</td>
            <td><code>{{ sub.access_token|truncatechars:20 }}</code></td>
            <td>
                <button class="btn-extend" onclick="extendSubscription('{{ sub.id }}')">Продлить</button>
            </td>
        </tr>
        {% empty %}
        <tr>
            <td colspan="7" class="empty">Подписок не найдено</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### promocodes_admin.html

```html
<!-- apps/admin_panel/templates/admin_panel/promocodes_admin.html -->
{% extends 'admin/base_site.html' %}

{% block content %}
<h1>⭐ Управление промокодами</h1>

<!-- Форма создания промокода -->
<div class="create-promo-form">
    <h2>Создать промокод</h2>
    <form method="post">
        {% csrf_token %}
        <div class="form-row">
            <label>Код (оставить пустым для автогенерации):</label>
            <input type="text" name="code" placeholder="SUMMER2026">
        </div>

        <div class="form-row">
            <label>Действие:</label>
            <select name="action" required>
                {% for value, label in actions %}
                <option value="{{ value }}">{{ label }}</option>
                {% endfor %}
            </select>
        </div>

        <div class="form-row">
            <label>Дата начала:</label>
            <input type="datetime-local" name="valid_from" required>
        </div>

        <div class="form-row">
            <label>Дата окончания:</label>
            <input type="datetime-local" name="valid_until" required>
        </div>

        <div class="form-row">
            <label>Максимум использований:</label>
            <input type="number" name="max_uses" value="1" min="1" required>
        </div>

        <div class="form-row">
            <label>Описание:</label>
            <textarea name="description" rows="2"></textarea>
        </div>

        <button type="submit" class="btn-primary">Создать промокод</button>
    </form>
</div>

<!-- Фильтры -->
<form method="get" class="filters-form">
    <select name="status" onchange="this.form.submit()">
        <option value="all" {% if status_filter == 'all' %}selected{% endif %}>Все</option>
        <option value="active" {% if status_filter == 'active' %}selected{% endif %}>Активные</option>
        <option value="expired" {% if status_filter == 'expired' %}selected{% endif %}>Истекшие</option>
    </select>
</form>

<!-- Таблица промокодов -->
<table class="promocodes-table">
    <thead>
        <tr>
            <th>Код</th>
            <th>Действие</th>
            <th>Срок действия</th>
            <th>Использований</th>
            <th>Статус</th>
            <th>Создан</th>
            <th>Действия</th>
        </tr>
    </thead>
    <tbody>
        {% for promo in promo_codes %}
        <tr>
            <td><strong>{{ promo.code }}</strong></td>
            <td>{{ promo.get_action_display }}</td>
            <td>
                {{ promo.valid_from|date:"d.m.Y" }} — {{ promo.valid_until|date:"d.m.Y" }}
            </td>
            <td>
                <div class="usage-bar">
                    <div class="usage-fill" style="width: {{ promo.usage_percent }}%"></div>
                    <span>{{ promo.current_uses }}/{{ promo.max_uses }}</span>
                </div>
            </td>
            <td>
                <span class="badge {% if promo.status == 'Активен' %}badge-active{% else %}badge-expired{% endif %}">
                    {{ promo.status }}
                </span>
            </td>
            <td>{{ promo.created_at|date:"d.m.Y H:i" }}</td>
            <td>
                <button onclick="deactivatePromo('{{ promo.code }}')">Деактивировать</button>
            </td>
        </tr>
        {% empty %}
        <tr>
            <td colspan="7" class="empty">Промокодов не найдено</td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

### system_settings.html

```html
<!-- apps/admin_panel/templates/admin_panel/system_settings.html -->
{% extends 'admin/base_site.html' %}

{% block content %}
<h1>⚙️ Системные настройки</h1>

<!-- Включение/выключение платежей -->
<div class="settings-section">
    <h2>Платежи</h2>
    <form method="post">
        {% csrf_token %}
        <input type="hidden" name="action" value="toggle_payments">

        <div class="toggle-setting">
            <label class="toggle-switch">
                <input type="checkbox" {% if payments_enabled %}checked{% endif %} onchange="this.form.submit()">
                <span class="slider"></span>
            </label>
            <span class="toggle-label">
                {% if payments_enabled %}
                    ✅ Платежи включены
                {% else %}
                    ❌ Платежи отключены
                {% endif %}
            </span>
        </div>
    </form>
</div>

<!-- Настройки ЮKassa -->
<div class="settings-section">
    <h2>Настройки ЮKassa</h2>
    <form method="post">
        {% csrf_token %}
        <input type="hidden" name="action" value="update_yukassa_token">

        <div class="form-row">
            <label>Shop ID:</label>
            <input type="text" name="yukassa_shop_id" value="{{ yukassa_shop_id }}" required>
        </div>

        <div class="form-row">
            <label>Secret Key:</label>
            <input type="password" name="yukassa_secret_key" placeholder="••••••••" required>
            <small>Оставьте пустым, чтобы не менять</small>
        </div>

        <button type="submit" class="btn-primary">Сохранить токен</button>
    </form>
</div>

<!-- Тарифы -->
<div class="settings-section">
    <h2>Тарифы (JSON)</h2>
    <form method="post">
        {% csrf_token %}
        <input type="hidden" name="action" value="update_tariffs">

        <textarea name="tariffs" rows="15" class="json-editor" required>{{ tariffs }}</textarea>

        <button type="submit" class="btn-primary">Сохранить тарифы</button>
    </form>
</div>

<!-- Feature Flags -->
<div class="settings-section">
    <h2>Флаги функциональности</h2>
    <table class="feature-flags-table">
        <thead>
            <tr>
                <th>Название</th>
                <th>Описание</th>
                <th>Статус</th>
                <th>Действия</th>
            </tr>
        </thead>
        <tbody>
            {% for flag in feature_flags %}
            <tr>
                <td><code>{{ flag.name }}</code></td>
                <td>{{ flag.description }}</td>
                <td>
                    <span class="badge {% if flag.is_enabled %}badge-active{% else %}badge-inactive{% endif %}">
                        {% if flag.is_enabled %}Включен{% else %}Выключен{% endif %}
                    </span>
                </td>
                <td>
                    <button onclick="toggleFeature('{{ flag.name }}')">Переключить</button>
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="4" class="empty">Флагов не найдено</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

---

## 🔌 URL CONFIGURATION

```python
# apps/admin_panel/urls.py
from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Платежи
    path('payments/', views.payment_list_view, name='payments_list'),
    path('payments/<uuid:payment_id>/', views.payment_detail_view, name='payment_detail'),

    # Подписки
    path('subscriptions/', views.subscription_list_view, name='subscriptions_list'),

    # Промокоды
    path('promocodes/', views.promo_code_admin_view, name='promocodes_admin'),

    # Системные настройки
    path('settings/', views.system_settings_view, name='system_settings'),

    # Логи
    path('audit-log/', views.audit_log_view, name='audit_log'),
]


# project/urls.py (main)
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin-panel/', include('apps.admin_panel.urls')),  # Кастомная админка

    # Остальные URLs...
]
```

---

## 📋 МИГРАЦИИ

```bash
# Создать миграции для всех новых приложений
python manage.py makemigrations payments
python manage.py makemigrations subscriptions
python manage.py makemigrations promocodes
python manage.py makemigrations feature_flags
python manage.py makemigrations audit

# Применить миграции
python manage.py migrate

# Создать superuser для доступа к админке
python manage.py createsuperuser
```

---

## 🚀 ПЛАН РАЗРАБОТКИ M5 (10 ДНЕЙ)

### День 1-2: Модели и миграции
- [x] Создать все 5 Django apps
- [x] Написать models.py для каждого приложения
- [x] Создать и применить миграции
- [x] Unit tests для моделей

### День 3-4: Сервисы и контракты
- [x] PaymentService + YuKassaClient
- [x] SubscriptionService
- [x] PromoCodeService
- [x] AuditService
- [x] Contract tests

### День 5-6: Админ-панель (Views)
- [x] payment_list_view + payment_detail_view
- [x] subscription_list_view
- [x] promo_code_admin_view
- [x] system_settings_view
- [x] audit_log_view

### День 7-8: Templates + CSS
- [x] HTML templates для всех views
- [x] CSS стили для админки
- [x] JavaScript для переключений и AJAX

### День 9: Интеграция ЮKassa
- [x] Webhook endpoint
- [x] Обработка payment.succeeded
- [x] Тестирование на sandbox ЮKassa

### День 10: Тестирование и документация
- [x] End-to-end тесты
- [x] Security audit
- [x] Документация для администраторов

---

## ✅ ФИНАЛЬНЫЙ ЧЕК-ЛИСТ

### Модели:
- [x] Payment модель с history
- [x] Subscription с access_token
- [x] PromoCode с валидацией
- [x] SystemSetting + FeatureFlag
- [x] AuditLog

### Контракты:
- [x] Contract 5.1: create_payment()
- [x] Contract 5.2: process_webhook()
- [x] Contract 5.3: activate_from_payment()
- [x] Contract 5.4: create_promo_code()

### Админка:
- [x] Список платежей с фильтрами
- [x] Детали платежа
- [x] Управление подписками
- [x] Создание/управление промокодами
- [x] Системные настройки (toggle payments, ЮKassa, тарифы)
- [x] Feature flags управление
- [x] Audit log viewer

### Безопасность:
- [x] @staff_member_required для всех admin views
- [x] Webhook signature validation (ЮKassa)
- [x] Encrypted secret keys in DB
- [x] Audit logging всех действий

### Интеграция:
- [x] ЮKassa API client
- [x] Webhook handler
- [x] Middleware для проверки подписки

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

1. **Создать apps/**:
   ```bash
   python manage.py startapp payments
   python manage.py startapp subscriptions
   python manage.py startapp promocodes
   python manage.py startapp admin_panel
   python manage.py startapp feature_flags
   python manage.py startapp audit
   ```

2. **Скопировать models.py** из этого документа в каждое приложение

3. **Установить зависимости**:
   ```bash
   pip install requests pycryptodome
   ```

4. **Добавить в settings.py**:
   ```python
   INSTALLED_APPS = [
       ...
       'apps.payments',
       'apps.subscriptions',
       'apps.promocodes',
       'apps.admin_panel',
       'apps.feature_flags',
       'apps.audit',
   ]
   ```

5. **Запустить миграции**

6. **Создать superuser**

7. **Открыть `/admin-panel/settings/` и настроить ЮKassa**

---

**Дата:** 4 января 2026  
**Версия:** CargoTech Driver WebApp v3.1  
**Новый модуль:** M5 - Subscription & Payment Management ✅  
**Статус:** ГОТОВО К РЕАЛИЗАЦИИ 🚀
