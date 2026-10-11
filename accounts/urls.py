"""
This file to map each URL domain to the corresponding backend function.
"""

from django.urls import path

from . import views

# The route name (e.g., abc.com/accounts/login/)
app_name = "accounts"

# The URL paths
urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("register/", views.register_choice, name="register_choice"),
    path("register/student/", views.register_student, name="register_student"),
    path("register/teacher/", views.register_teacher, name="register_teacher"),
    path("profile/", views.profile, name="profile"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("reset/done/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
