#!/usr/bin/env python
"""Django management entry point for FitStart V2."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fitstart.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django is not installed. Activate the virtual environment and "
            "install requirements.txt before running manage.py."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
