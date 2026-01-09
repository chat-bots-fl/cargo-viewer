"""
Core app configuration for Django.

This app provides shared utilities and middleware for the entire application.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """
    Configuration for the core application.

    Provides:
    - Custom exception classes
    - Exception handling middleware
    - Shared utilities
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"
