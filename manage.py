#!/usr/bin/env python
import os
import sys


"""
GOAL: Execute Django management commands using the configured settings module.

PARAMETERS:
  None

RETURNS:
  None

RAISES:
  ImportError: If Django is not installed/available

GUARANTEES:
  - Uses DJANGO_SETTINGS_MODULE=config.settings by default
"""
def main() -> None:
    """Run Django management commands."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
