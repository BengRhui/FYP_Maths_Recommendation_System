"""
This file defines the configuration for the "learning" Django app
"""

from django.apps import AppConfig


# The class that represents the configuration for the learning app
class LearningConfig(AppConfig):

    # Add a primary key automatically for all models in this app
    default_auto_field = "django.db.models.BigAutoField"

    # The name of the app
    name = "learning"
