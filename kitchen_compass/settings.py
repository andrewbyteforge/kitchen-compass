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
    'asda_scraper.apps.AsdaScraperConfig',
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

# Manual logging configuration
# Logging configuration (add this AFTER the security settings section, not inside it)
# Updated LOGGING configuration with Unicode handling for Windows
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
    },  # ← end of handlers
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
        "asda_scraper.selenium_scraper": {
            "handlers": ["console", "scraper_file"],
            "level": "DEBUG",
            "propagate": False
        },
        "asda_scraper.asda_link_crawler": {
            "handlers": ["console", "scraper_file"],
            "level": "DEBUG",
            "propagate": False
        },
        "asda_scraper.management.commands.run_asda_crawl": {
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

# Add enhanced scraper settings to settings.py:
ASDA_SCRAPER_SETTINGS = {
    'MAX_CRAWL_DEPTH': 5,
    'DEFAULT_DELAY': 2.0,
    'MAX_PAGES_PER_SESSION': 10000,
    'REQUEST_TIMEOUT': 30,
    'MAX_RETRIES': 3,
    'RESPECT_ROBOTS_TXT': True,
    'USER_AGENT': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    'ALLOWED_DOMAINS': ['groceries.asda.com'],
    'BLOCKED_EXTENSIONS': ['.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip'],
    'PRIORITY_KEYWORDS': ['fresh', 'meat', 'dairy', 'bakery', 'fruit', 'vegetable'],
}


# ===========================
# PROXY PROVIDER CONFIGURATION
# ===========================

PROXY_PROVIDERS = {
    # Premium Residential Proxies (Most Expensive, Highest Quality)
    'bright_data': {
        'tier': 'premium',
        'api_key': config('BRIGHT_DATA_API_KEY', default=''),
        'username': config('BRIGHT_DATA_USERNAME', default=''),
        'password': config('BRIGHT_DATA_PASSWORD', default=''),
        'api_endpoint': 'zproxy.lum-superproxy.io:22225',
        'cost_per_gb': 3.0,  # $3 per GB
        'supports_targeting': True,
        'sticky_sessions': True,
        'countries': ['US', 'UK', 'CA'],  # Limit to specific countries
    },
    
    # Standard Datacenter Proxies (Good Balance)
    'smartproxy': {
        'tier': 'standard',
        'username': config('SMARTPROXY_USERNAME', default=''),
        'password': config('SMARTPROXY_PASSWORD', default=''),
        'api_endpoint': 'gate.smartproxy.com:10000',
        'cost_per_gb': 1.5,  # $1.5 per GB
        'supports_targeting': True,
        'pool_size': 40000,  # Number of IPs in pool
    },
    
    # Budget Datacenter Proxies
    'blazing_seo': {
        'tier': 'standard',
        'username': config('BLAZING_USERNAME', default=''),
        'password': config('BLAZING_PASSWORD', default=''),
        'api_endpoint': 'premium.blazingseollc.com:5432',
        'cost_per_gb': 0.5,  # $0.50 per GB
        'pool_size': 300,
    },
    
    # Storm Proxies (Rotating Residential)
    'storm_proxies': {
        'tier': 'premium',
        'username': config('STORM_USERNAME', default=''),
        'password': config('STORM_PASSWORD', default=''),
        'api_endpoint': 'rotating.stormproxies.com:9040',
        'cost_per_gb': 2.5,  # $2.5 per GB
        'rotation_time': 300,  # Rotate every 5 minutes
    }
}

# ===========================
# PROXY BEHAVIOR SETTINGS
# ===========================

PROXY_SETTINGS = {
    # Priority Settings
    'prefer_paid': True,  # Use paid proxies first
    'fallback_to_free': True,  # Fallback to free if paid fail
    'tier_preference': ['premium', 'standard', 'free'],  # Order of preference
    
    # Free Proxy Settings
    'free_proxy_sources': [
        'free_proxy_list',
        'ssl_proxies',
        'proxy_scrape',
    ],
    'free_proxy_update_interval': 3600,  # Update every hour
    'free_proxy_validation_timeout': 5,  # 5 seconds timeout for validation
    'max_free_proxies': 200,  # Limit number of free proxies to store
    
    # Performance Settings
    'max_consecutive_failures': 3,  # Blacklist after 3 failures
    'health_check_interval': 300,  # Check proxy health every 5 minutes
    'performance_threshold': 5.0,  # Max acceptable response time (seconds)
    'min_success_rate': 70,  # Minimum success rate to keep proxy active
    
    # Rotation Settings
    'rotation_strategy': 'performance_based',  # Options: round_robin, random, least_used, performance_based
    'max_requests_per_proxy': 100,  # Rotate after X requests
    'session_duration': 600,  # Keep same proxy for 10 minutes (sticky sessions)
    
    # Cost Management
    'cost_alert_threshold': 100.0,  # Alert if daily cost exceeds $100
    'budget_daily_limit': 150.0,  # Stop using paid proxies if daily limit exceeded
    'cost_optimization': True,  # Automatically switch to cheaper proxies when possible
}

# ===========================
# PROXY AUTHENTICATION
# ===========================

# Some providers require special authentication methods
PROXY_AUTH_METHODS = {
    'bright_data': 'username-session',  # username-session-sessionid
    'smartproxy': 'username-password',  # standard auth
    'oxylabs': 'username-password',
    'storm_proxies': 'gateway',  # Single gateway with auth
}

# ===========================
# FALLBACK CONFIGURATION
# ===========================

PROXY_FALLBACK_CHAIN = [
    # Try these in order if previous fails
    {'tier': 'premium', 'max_attempts': 2},
    {'tier': 'standard', 'max_attempts': 3},
    {'tier': 'free', 'max_attempts': 5},
    {'tier': 'direct', 'max_attempts': 1},  # Direct connection as last resort
]

# ===========================
# MONITORING AND ALERTS
# ===========================

PROXY_MONITORING = {
    'enabled': True,
    'metrics_retention_days': 30,  # Keep metrics for 30 days
    'alert_email': config('ADMIN_EMAIL', default=''),
    'alert_conditions': {
        'all_proxies_failed': True,
        'success_rate_below': 50,  # Alert if overall success < 50%
        'daily_cost_exceeded': True,
        'free_proxy_shortage': 10,  # Alert if less than 10 free proxies
    },
    'webhook_url': config('SLACK_WEBHOOK_URL', default=''),  # For Slack alerts
}

# ===========================
# SCRAPING PROFILE SETTINGS
# ===========================

# Different proxy configurations for different scraping scenarios
PROXY_PROFILES = {
    'aggressive': {
        # Fast scraping, cost is not a concern
        'prefer_tier': 'premium',
        'concurrent_requests': 10,
        'timeout': 5,
        'retry_count': 2,
    },
    'balanced': {
        # Default profile - balance between cost and performance
        'prefer_tier': 'standard',
        'concurrent_requests': 5,
        'timeout': 10,
        'retry_count': 3,
    },
    'conservative': {
        # Slow, careful scraping to avoid detection
        'prefer_tier': 'free',
        'concurrent_requests': 2,
        'timeout': 15,
        'retry_count': 5,
        'delay_between_requests': 5,
    },
    'test': {
        # For testing - use only free proxies
        'prefer_tier': 'free',
        'concurrent_requests': 1,
        'timeout': 10,
        'retry_count': 1,
    }
}

# ===========================
# INTEGRATION WITH SELENIUM
# ===========================

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

# ===========================
# EXAMPLE USAGE IN CODE
# ===========================

"""
Example of how to use in your scraper:

from django.conf import settings
from asda_scraper.tiered_proxy_manager import TieredProxyManager

# Initialize manager with settings
manager = TieredProxyManager(
    prefer_paid=settings.PROXY_SETTINGS['prefer_paid'],
    fallback_to_free=settings.PROXY_SETTINGS['fallback_to_free']
)

# Get proxy based on profile
profile = settings.PROXY_PROFILES['balanced']
proxy = manager.get_proxy(tier_preference=[profile['prefer_tier']])

# Use different profiles for different tasks
if is_critical_task:
    proxy = manager.get_proxy(tier_preference=['premium'])
else:
    proxy = manager.get_proxy(tier_preference=['free', 'standard'])
"""



