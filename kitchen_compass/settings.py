"""
Django settings for kitchen_compass project.

This module contains all the Django settings for the KitchenCompass project,
including database configuration, security settings, and application setup.
"""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Time zone settings
time_zone = 'UTC'
TIME_ZONE = time_zone
CELERY_TIMEZONE = TIME_ZONE

# Development Celery Configuration (in-memory, synchronous)
# Overrides Redis broker for local dev; runs tasks eagerly in-process
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Load environment variables from .env file
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# Security Settings
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-&5%cqyny8@vo*x4zjo5@@a-ex9(tza2oe*h2^4vayxh$_+1*#k")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Microsoft OAuth settings
MICROSOFT_AUTH = {
    'CLIENT_ID': os.environ.get('MICROSOFT_CLIENT_ID', ''),
    'CLIENT_SECRET': os.environ.get('MICROSOFT_CLIENT_SECRET', ''),
    'TENANT_ID': os.environ.get('MICROSOFT_TENANT_ID', 'common'),
    'REDIRECT_URI': os.environ.get('MICROSOFT_REDIRECT_URI', 'http://localhost:8000/auth/callback/microsoft/'),
    'SCOPES': ['User.Read', 'Calendars.ReadWrite'],
    'AUTHORITY': 'https://login.microsoftonline.com/common',
}

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "crispy_forms",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # Local apps
    "auth_hub",
    "recipe_hub",
    'meal_planner',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "kitchen_compass.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "kitchen_compass.wsgi.application"

# Database Configuration
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'restaurant_app'),
        'USER': os.getenv('DATABASE_USER', 'postgres'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', 'admin'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'email2*', 'password1*', 'password2*']
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = "/dashboard/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# Email configuration
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
if EMAIL_BACKEND != "django.core.mail.backends.console.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Stripe Configuration
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Production security
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} [{name}] {message}", "style": "{", "datefmt": "%Y-%m-%d %H:%M:%S"},
        "simple": {"format": "{levelname} {message}", "style": "{"},
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "handlers": {
        "console": {"level": "INFO", "filters": ["require_debug_true"], "class": "logging.StreamHandler", "formatter": "simple"},
        "file": {"level": "INFO", "class": "logging.handlers.RotatingFileHandler", "filename": LOGS_DIR / "kitchen_compass.log", "maxBytes": 5*1024*1024, "backupCount": 5, "formatter": "verbose"},
        "error_file": {"level": "ERROR", "class": "logging.handlers.RotatingFileHandler", "filename": LOGS_DIR / "errors.log", "maxBytes": 5*1024*1024, "backupCount": 5, "formatter": "verbose"},
        "security_file": {"level": "INFO", "class": "logging.handlers.RotatingFileHandler", "filename": LOGS_DIR / "security.log", "maxBytes": 5*1024*1024, "backupCount": 5, "formatter": "verbose"},
    },
    "loggers": {
        "django": {"handlers": ["console","file"], "level": "INFO", "propagate": True},
        "django.request": {"handlers": ["error_file"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["security_file"], "level": "INFO", "propagate": False},
        "auth_hub": {"handlers": ["console","file"], "level": "DEBUG", "propagate": False},
        "kitchen_compass": {"handlers": ["console","file"], "level": "DEBUG", "propagate": False},
    }
}

# Cache configuration
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache","LOCATION": "unique-snowflake"}}

# Session configuration
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 1209600
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True

# Messages configuration
from django.contrib.messages import constants as message_constants
MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

# Subscription tiers
SUBSCRIPTION_TIERS = {
    "FREE": {"name": "Home Cook","price": 0,"features": ["7-day menu planning","Basic recipe access","Shopping list generation"]},
    "STARTER": {"name": "Sous Chef","price": 499,"stripe_price_id": os.getenv("STRIPE_STARTER_PRICE_ID", ""),"features": ["All Home Cook features","30-day menu planning","Advanced filtering","Nutritional information","Share menus with 5 people"]},
    "PREMIUM": {"name": "Master Chef","price": 999,"stripe_price_id": os.getenv("STRIPE_PREMIUM_PRICE_ID", ""),"features": ["All Sous Chef features","Unlimited menu planning","Premium recipes","Cooking tutorials","Share menus with unlimited people","Priority support"]},
}

# Site URL
SITE_URL = 'http://127.0.0.1:8000'
DEFAULT_FROM_EMAIL = 'noreply@kitchencompass.com'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

