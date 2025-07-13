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
from django.contrib.messages import constants as message_constants

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Load environment variables from .env file
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# ===========================
# CORE DJANGO SETTINGS
# ===========================

# Security Settings
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-&5%cqyny8@vo*x4zjo5@@a-ex9(tza2oe*h2^4vayxh$_+1*#k")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Application definition
INSTALLED_APPS = [
    # Django apps
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
    "meal_planner",
    "asda_scraper",
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

# ===========================
# DATABASE CONFIGURATION
# ===========================

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

# ===========================
# AUTHENTICATION & AUTHORIZATION
# ===========================

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Authentication backends
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Allauth settings
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'email2*', 'password1*', 'password2*']
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = "/dashboard/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

# Microsoft OAuth settings
MICROSOFT_AUTH = {
    'CLIENT_ID': os.environ.get('MICROSOFT_CLIENT_ID', ''),
    'CLIENT_SECRET': os.environ.get('MICROSOFT_CLIENT_SECRET', ''),
    'TENANT_ID': os.environ.get('MICROSOFT_TENANT_ID', 'common'),
    'REDIRECT_URI': os.environ.get('MICROSOFT_REDIRECT_URI', 'http://localhost:8000/auth/callback/microsoft/'),
    'SCOPES': ['User.Read', 'Calendars.ReadWrite'],
    'AUTHORITY': 'https://login.microsoftonline.com/common',
}

# ===========================
# INTERNATIONALIZATION
# ===========================

LANGUAGE_CODE = "en-us"
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ===========================
# STATIC & MEDIA FILES
# ===========================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ===========================
# EMAIL CONFIGURATION
# ===========================

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
if EMAIL_BACKEND != "django.core.mail.backends.console.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
else:
    DEFAULT_FROM_EMAIL = 'noreply@kitchencompass.com'

SERVER_EMAIL = DEFAULT_FROM_EMAIL
SITE_URL = 'http://127.0.0.1:8000'

# ===========================
# THIRD-PARTY CONFIGURATIONS
# ===========================

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Stripe Configuration
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# ===========================
# CELERY CONFIGURATION
# ===========================

CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# ===========================
# CACHING
# ===========================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake"
    }
}

# ===========================
# SESSION CONFIGURATION
# ===========================

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True

# ===========================
# MESSAGES CONFIGURATION
# ===========================

MESSAGE_TAGS = {
    message_constants.DEBUG: "debug",
    message_constants.INFO: "info",
    message_constants.SUCCESS: "success",
    message_constants.WARNING: "warning",
    message_constants.ERROR: "danger",
}

# ===========================
# LOGGING CONFIGURATION
# ===========================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} [{name}] {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{"
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse"
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue"
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "kitchen_compass.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
            "delay": True
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "errors.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8"
        },
        "security_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "security.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8"
        },
        "scraper_file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "asda_scraper.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
            "delay": True
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True
        },
        "django.request": {
            "handlers": ["error_file"],
            "level": "ERROR",
            "propagate": False
        },
        "django.security": {
            "handlers": ["security_file"],
            "level": "INFO",
            "propagate": False
        },
        "auth_hub": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False
        },
        "kitchen_compass": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False
        },
        "asda_scraper": {
            "handlers": ["console", "scraper_file"],
            "level": "DEBUG",
            "propagate": False
        },
        "selenium": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False
        },
        "urllib3": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False
        }
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO"
    }
}

# ===========================
# SECURITY SETTINGS
# ===========================

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Production security settings
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

# ===========================
# APPLICATION SETTINGS
# ===========================

# Subscription tiers
SUBSCRIPTION_TIERS = {
    "FREE": {
        "name": "Home Cook",
        "price": 0,
        "features": [
            "7-day menu planning",
            "Basic recipe access",
            "Shopping list generation"
        ]
    },
    "STARTER": {
        "name": "Sous Chef",
        "price": 499,
        "stripe_price_id": os.getenv("STRIPE_STARTER_PRICE_ID", ""),
        "features": [
            "All Home Cook features",
            "30-day menu planning",
            "Advanced filtering",
            "Nutritional information",
            "Share menus with 5 people"
        ]
    },
    "PREMIUM": {
        "name": "Master Chef",
        "price": 999,
        "stripe_price_id": os.getenv("STRIPE_PREMIUM_PRICE_ID", ""),
        "features": [
            "All Sous Chef features",
            "Unlimited menu planning",
            "Premium recipes",
            "Cooking tutorials",
            "Share menus with unlimited people",
            "Priority support"
        ]
    },
}

# ===========================
# ASDA SCRAPER CONFIGURATION
# ===========================

ASDA_SCRAPER_SETTINGS = {
    # User Agent Settings
    'USER_AGENTS': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ],

    # Request Settings
    'REQUEST_DELAY': (2, 5),  # Random delay between 2-5 seconds
    'TIMEOUT': 30,
    'MAX_RETRIES': 3,
    'HEADLESS': True,

    # Crawling Settings
    'MAX_CRAWL_DEPTH': 5,
    'DEFAULT_DELAY': 2.0,
    'MAX_PAGES_PER_SESSION': 10000,
    'RESPECT_ROBOTS_TXT': True,
    'ALLOWED_DOMAINS': ['groceries.asda.com'],
    'BLOCKED_EXTENSIONS': ['.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip'],
    'PRIORITY_KEYWORDS': ['fresh', 'meat', 'dairy', 'bakery', 'fruit', 'vegetable'],

    # Category URLs
    'CATEGORIES': [
        'https://groceries.asda.com/cat/fruit-veg-flowers/1215686352935',
        'https://groceries.asda.com/cat/meat-poultry-fish/1215135760597',
        'https://groceries.asda.com/cat/bakery/1215686354843',
        'https://groceries.asda.com/cat/chilled-food/1215660378320',
        'https://groceries.asda.com/cat/frozen-food/1215338621416',
        'https://groceries.asda.com/cat/sweets-treats-snacks/1215686356579',
        'https://groceries.asda.com/cat/dietary-lifestyle/1215686355606',
        'https://groceries.asda.com/cat/drinks/1215135760614',
        'https://groceries.asda.com/cat/beer-wine-spirits/1215685911554',
        'https://groceries.asda.com/cat/world-food/1215686351451',
    ]
}

# ===========================
# PROXY CONFIGURATION
# ===========================

# Proxy Provider Configuration
PROXY_PROVIDERS = {
    'bright_data': {
        'tier': 'premium',
        'api_key': config('BRIGHT_DATA_API_KEY', default=''),
        'username': config('BRIGHT_DATA_USERNAME', default=''),
        'password': config('BRIGHT_DATA_PASSWORD', default=''),
        'api_endpoint': 'zproxy.lum-superproxy.io:22225',
        'cost_per_gb': 3.0,
        'supports_targeting': True,
        'sticky_sessions': True,
        'countries': ['US', 'UK', 'CA'],
    },
    'smartproxy': {
        'tier': 'standard',
        'username': config('SMARTPROXY_USERNAME', default=''),
        'password': config('SMARTPROXY_PASSWORD', default=''),
        'api_endpoint': 'gate.smartproxy.com:10000',
        'cost_per_gb': 1.5,
        'supports_targeting': True,
        'pool_size': 40000,
    },
    'blazing_seo': {
        'tier': 'standard',
        'username': config('BLAZING_USERNAME', default=''),
        'password': config('BLAZING_PASSWORD', default=''),
        'api_endpoint': 'premium.blazingseollc.com:5432',
        'cost_per_gb': 0.5,
        'pool_size': 300,
    },
    'storm_proxies': {
        'tier': 'premium',
        'username': config('STORM_USERNAME', default=''),
        'password': config('STORM_PASSWORD', default=''),
        'api_endpoint': 'rotating.stormproxies.com:9040',
        'cost_per_gb': 2.5,
        'rotation_time': 300,
    }
}

# Proxy Behavior Settings
PROXY_SETTINGS = {
    # Priority Settings
    'prefer_paid': True,
    'fallback_to_free': True,
    'tier_preference': ['premium', 'standard', 'free'],

    # Free Proxy Settings
    'free_proxy_sources': ['free_proxy_list', 'ssl_proxies', 'proxy_scrape'],
    'free_proxy_update_interval': 3600,
    'free_proxy_validation_timeout': 5,
    'max_free_proxies': 200,

    # Performance Settings
    'max_consecutive_failures': 3,
    'health_check_interval': 300,
    'performance_threshold': 5.0,
    'min_success_rate': 70,

    # Rotation Settings
    'rotation_strategy': 'performance_based',
    'max_requests_per_proxy': 100,
    'session_duration': 600,

    # Cost Management
    'cost_alert_threshold': 100.0,
    'budget_daily_limit': 150.0,
    'cost_optimization': True,
}

# Proxy Authentication Methods
PROXY_AUTH_METHODS = {
    'bright_data': 'username-session',
    'smartproxy': 'username-password',
    'oxylabs': 'username-password',
    'storm_proxies': 'gateway',
}

# Proxy Fallback Configuration
PROXY_FALLBACK_CHAIN = [
    {'tier': 'premium', 'max_attempts': 2},
    {'tier': 'standard', 'max_attempts': 3},
    {'tier': 'free', 'max_attempts': 5},
    {'tier': 'direct', 'max_attempts': 1},
]

# Proxy Monitoring
PROXY_MONITORING = {
    'enabled': True,
    'metrics_retention_days': 30,
    'alert_email': config('ADMIN_EMAIL', default=''),
    'alert_conditions': {
        'all_proxies_failed': True,
        'success_rate_below': 50,
        'daily_cost_exceeded': True,
        'free_proxy_shortage': 10,
    },
    'webhook_url': config('SLACK_WEBHOOK_URL', default=''),
}

# Scraping Profile Settings
PROXY_PROFILES = {
    'aggressive': {
        'prefer_tier': 'premium',
        'concurrent_requests': 10,
        'timeout': 5,
        'retry_count': 2,
    },
    'balanced': {
        'prefer_tier': 'standard',
        'concurrent_requests': 5,
        'timeout': 10,
        'retry_count': 3,
    },
    'conservative': {
        'prefer_tier': 'free',
        'concurrent_requests': 2,
        'timeout': 15,
        'retry_count': 5,
        'delay_between_requests': 5,
    },
    'test': {
        'prefer_tier': 'free',
        'concurrent_requests': 1,
        'timeout': 10,
        'retry_count': 1,
    }
}

# Selenium Integration
SELENIUM_PROXY_CONFIG = {
    'proxy_auth_plugin_path': os.path.join(BASE_DIR, 'extensions', 'proxy_auth_plugin.zip'),
    'use_proxy_rotation': True,
    'rotate_user_agent_with_proxy': True,
    'clear_cookies_on_rotation': True,
    'handle_proxy_errors': True,
    'proxy_error_patterns': [
        'ERR_PROXY_CONNECTION_FAILED',
        'ERR_TUNNEL_CONNECTION_FAILED',
        'proxy authentication required',
        'access denied',
    ]
}
