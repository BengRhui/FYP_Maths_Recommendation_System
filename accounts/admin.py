"""
This file is to allow the admin site to add users via GUI.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


# Class to represent users in the system
@admin.register(User)
class UserAdmin(BaseUserAdmin):

    # Sort users alphabetically by email
    ordering = ["email"]

    # Display these details on site
    list_display = ["email", "full_name", "role", "is_staff"]

    # Filter buttons beside the site
    list_filter = ["role", "is_staff", "is_superuser"]

    # Search box above the table
    search_fields = ["email", "full_name"]

    # Layout of the edit user details page
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    # Layout of the create user page
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "full_name", "role", "password1", "password2"),
        }),
    )
