#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для установки webhook для Telegram бота.

Использование:
    python setup_telegram_webhook.py
"""

import os
import sys
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.conf import settings


def setup_webhook():
    """
    GOAL: Установить webhook для Telegram бота, используя URL из настроек.

    PARAMETERS:
        None

    RETURNS:
        bool - True если webhook успешно установлен, False иначе

    RAISES:
        ValueError - Если TELEGRAM_BOT_TOKEN или WEBAPP_URL не настроены

    GUARANTEES:
        - Webhook URL будет установлен в Telegram API
        - Результат операции будет выведен в консоль
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    webapp_url = getattr(settings, 'WEBAPP_URL', None)

    if not token:
        print("[ERROR] TELEGRAM_BOT_TOKEN is not configured in .env")
        return False

    if not webapp_url:
        print("[ERROR] WEBAPP_URL is not configured in .env")
        return False

    # Удаляем слеш в конце, если есть
    webapp_url = webapp_url.rstrip('/')

    # Формируем URL webhook
    webhook_url = f"{webapp_url}/telegram/webhook/"

    print(f"[INFO] Setting up Telegram bot webhook...")
    print(f"   Webhook URL: {webhook_url}")

    # Устанавливаем webhook
    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    response = requests.post(api_url, json={
        "url": webhook_url,
        "drop_pending_updates": True  # Сбрасываем ожидающие обновления
    }, timeout=10)

    result = response.json()

    if result.get('ok'):
        print(f"[SUCCESS] Webhook set up successfully!")
        print(f"   URL: {webhook_url}")
        return True
    else:
        print(f"[ERROR] Failed to set up webhook:")
        print(f"   {result.get('description', 'Unknown error')}")
        return False


def get_webhook_info():
    """
    GOAL: Получить информацию о текущем webhook.

    PARAMETERS:
        None

    RETURNS:
        dict - Информация о webhook из Telegram API

    GUARANTEES:
        - Возвращает текущую информацию о webhook или None при ошибке
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)

    if not token:
        print("[ERROR] TELEGRAM_BOT_TOKEN is not configured in .env")
        return None

    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    response = requests.get(api_url, timeout=10)

    result = response.json()

    if result.get('ok'):
        webhook_info = result.get('result', {})
        print(f"[INFO] Current webhook information:")
        print(f"   URL: {webhook_info.get('url', 'Not set')}")
        print(f"   Pending updates: {webhook_info.get('pending_update_count', 0)}")
        print(f"   Last error: {webhook_info.get('last_error_message', 'None')}")
        return webhook_info
    else:
        print(f"[ERROR] Failed to get webhook information:")
        print(f"   {result.get('description', 'Unknown error')}")
        return None


def delete_webhook():
    """
    GOAL: Удалить webhook для Telegram бота.

    PARAMETERS:
        None

    RETURNS:
        bool - True если webhook успешно удален, False иначе

    GUARANTEES:
        - Webhook будет удален из Telegram API
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)

    if not token:
        print("[ERROR] TELEGRAM_BOT_TOKEN is not configured in .env")
        return False

    print(f"[INFO] Deleting webhook...")

    api_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    response = requests.post(api_url, json={
        "drop_pending_updates": True
    }, timeout=10)

    result = response.json()

    if result.get('ok'):
        print(f"[SUCCESS] Webhook deleted successfully!")
        return True
    else:
        print(f"[ERROR] Failed to delete webhook:")
        print(f"   {result.get('description', 'Unknown error')}")
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Telegram bot webhook management')
    parser.add_argument(
        'action',
        choices=['setup', 'info', 'delete'],
        help='Action: setup - set webhook, info - show information, delete - delete webhook'
    )

    args = parser.parse_args()

    if args.action == 'setup':
        setup_webhook()
    elif args.action == 'info':
        get_webhook_info()
    elif args.action == 'delete':
        delete_webhook()
