"""
This file configures the settings for Django setup.
"""

from django.apps import AppConfig


# Let Django know that the "classes" directory exists
class ClassesConfig(AppConfig):

    # Automatically set the primary ID for each class
    default_auto_field = "django.db.models.BigAutoField"

    # Let the directory automatically discovered
    name = "classes"
