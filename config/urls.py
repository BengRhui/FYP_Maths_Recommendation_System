"""
This file contains the base URL routes for the project
"""

from django.contrib import admin
from django.urls import include, path

from learning.views import landing

# The different routes that can be accessed by the user
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", landing, name="landing"),
    path("accounts/", include("accounts.urls")),
    path("", include("learning.urls")),
    path("classes/", include("classes.urls")),
]
