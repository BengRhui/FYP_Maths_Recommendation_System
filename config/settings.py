"""
This file contains all the configuration settings for the project.
"""

from pathlib import Path
from decouple import config

# The base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# The secret key and developer configurations for the project
SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-mathpath-dev-key-change-me-before-deploy"
)
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*").split(",")

# The applications created for the project
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "curriculum",
    "learning",
    "classes",
    "ml_engine",
]

# The middleware: Code to run on every request
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "learning.middleware.DiagnosticGateMiddleware",
]

# The file that holds the master URL lists
ROOT_URLCONF = "config.urls"

# The location of HTML files
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.role_flags",
            ],
        },
    },
]

# The WSGI application for the project
WSGI_APPLICATION = "config.wsgi.application"

# The database used by the project
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# The user of the project
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "learning:dashboard"
LOGOUT_REDIRECT_URL = "landing"

# The password validation rules set to register accounts
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "accounts.validators.LetterValidator"},
    {"NAME": "accounts.validators.NumberValidator"},
    {"NAME": "accounts.validators.SpecialCharacterValidator"},
]

# The email settings for fallback if SMTP is not working (print at terminal)
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@adeptmath.local")

# Time zone for the project
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_I18N = True
USE_TZ = True

# The location of CSS and JS files
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Generate primary keys for records by default
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The teacher registration code for the project
TEACHER_REGISTRATION_CODE = config(
    "TEACHER_REGISTRATION_CODE", default="ADEPTMATH-TEACHER-2026"
)

# Other custom configurations for the project
PRACTICE_SET_SIZE = 5
DIAGNOSTIC_SET_SIZE = 10
MASTERY_THRESHOLD = 0.8
MASTERY_DEVELOPING = 0.5
ML_MODEL_DIR = BASE_DIR / "ml_engine" / "saved_models"
