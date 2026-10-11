"""
This file provides the configuration for Django setup.
"""

from django.apps import AppConfig


# The class representing the configuration for `accounts` directory.
class AccountsConfig(AppConfig):

    # Declare the primary key for accounts
    default_auto_field = "django.db.models.BigAutoField"

    # The name of the current directory (to make it importable)
    name = "accounts"
