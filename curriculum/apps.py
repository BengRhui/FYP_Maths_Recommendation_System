"""
This file configures the settings for the "curriculum" Django app.
"""

from django.apps import AppConfig

# Define the configuration for curriculum
class CurriculumConfig(AppConfig):

    # Provide primary key automatically
    default_auto_field = "django.db.models.BigAutoField"

    # Set the name of the app
    name = "curriculum"
