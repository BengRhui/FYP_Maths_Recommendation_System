"""
This file is the entry point to run different project commands (e.g., run the server)
"""

import os
import sys


def main():

    # Tell Django the location of the configuration file
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    # Make sure that the Django is installed correctly
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Allows users to run project commands via the terminal
    execute_from_command_line(sys.argv)


# Runs the main() function when the manage.py file is called
if __name__ == "__main__":
    main()
