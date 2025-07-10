"""
Enhanced ASDA Scraper Configuration Module

This module contains all configuration settings for the ASDA web scraper,
including URL patterns, category mappings, selenium settings, and error handling.

File: asda_scraper/scraper_config.py
"""

import os
from pathlib import Path
from typing import Dict, List, Any
import logging

# Get project root directory dynamically
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Base ASDA URL Configuration
ASDA_BASE_URL = "https://groceries.asda.com"
ASDA_CATEGORY_BASE = f"{ASDA_BASE_URL}/browse"

# Rate Limiting and Anti-Bot Detection Configuration
RATE_LIMIT_CONFIG = {
    'requests_per_minute': 30,
    'requests_per_hour': 1000,
    'burst_size': 5,
    'cooldown_period': 300,  # 5 minutes in seconds
    'rate_limit_indicators': [
        'rate limit', 
        'too many requests', 
        'please try again later',
        'access denied',
        'temporarily blocked'
    ]
}

# Enhanced Delay Configuration
DELAY_CONFIG = {
    'between_requests': 2.0,
    'between_categories': 5.0,
    'after_error': 5.0,
    'after_rate_limit_detected': 60.0,
    'page_load_wait': 3.0,
    'element_wait': 1.0,
    'scroll_pause': 1.5,
    'popup_check': 2.0,
    'random_delay_min': 0.5,
    'random_delay_max': 2.0,
    'progressive_delay_factor': 1.5,  # Multiply delay after each error
    'max_progressive_delay': 30.0
}

# Enhanced Category Configuration with Metadata
CATEGORY_CONFIG = {
    # Essential Categories (Priority 1)
    '1215135738497': {
        'name': 'Fresh Food & Bakery',
        'slug': 'fresh-food-bakery',
        'priority': 1,
        'keywords': ['fresh', 'bakery', 'bread', 'produce', 'fruit', 'vegetable'],
        'subcategory_expected': True,
        'max_pages': 10,
        'scraping_strategy': 'pagination'
    },
    '1215135740114': {
        'name': 'Chilled Food',
        'slug': 'chilled-food',
        'priority': 1,
        'keywords': ['chilled', 'dairy', 'meat', 'fish', 'poultry', 'ready meals'],
        'subcategory_expected': True,
        'max_pages': 10,
        'scraping_strategy': 'pagination'
    },
    '1215135741731': {
        'name': 'Food Cupboard',
        'slug': 'food-cupboard',
        'priority': 1,
        'keywords': ['pantry', 'cupboard', 'tinned', 'pasta', 'rice', 'sauce'],
        'subcategory_expected': True,
        'max_pages': 15,
        'scraping_strategy': 'pagination'
    },
    '1215135743349': {
        'name': 'Frozen Food',
        'slug': 'frozen-food',
        'priority': 1,
        'keywords': ['frozen', 'ice cream', 'frozen meat', 'frozen vegetables'],
        'subcategory_expected': True,
        'max_pages': 8,
        'scraping_strategy': 'pagination'
    },
    
    # Core Categories (Priority 2)
    '1215135744966': {
        'name': 'Drinks',
        'slug': 'drinks',
        'priority': 2,
        'keywords': ['drink', 'beverage', 'water', 'juice', 'soft drink', 'alcohol'],
        'subcategory_expected': True,
        'max_pages': 10,
        'scraping_strategy': 'pagination'
    },
    '1215135746106': {
        'name': 'Household',
        'slug': 'household',
        'priority': 2,
        'keywords': ['cleaning', 'household', 'detergent', 'paper', 'kitchen roll'],
        'subcategory_expected': True,
        'max_pages': 8,
        'scraping_strategy': 'pagination'
    },
    '1215135755309': {
        'name': 'Health & Wellness',
        'slug': 'health-wellness',
        'priority': 2,
        'keywords': ['vitamin', 'supplement', 'medicine', 'health', 'wellness', 'pharmacy'],
        'subcategory_expected': True,
        'max_pages': 5,
        'scraping_strategy': 'pagination'
    },
    
    # Specialty Categories (Priority 3)
    '1215686356579': {
        'name': 'Sweets, Treats & Snacks',
        'slug': 'sweets-treats-snacks',
        'priority': 3,
        'keywords': ['chocolate', 'sweet', 'candy', 'snack', 'crisp', 'nuts'],
        'subcategory_expected': False,
        'max_pages': 8,
        'scraping_strategy': 'pagination'
    },
    '1215135760631': {
        'name': 'Baby, Toddler & Kids',
        'slug': 'baby-toddler-kids',
        'priority': 3,
        'keywords': ['baby', 'toddler', 'child', 'kids', 'infant', 'nappy'],
        'subcategory_expected': True,
        'max_pages': 5,
        'scraping_strategy': 'pagination'
    },
    '1215662103573': {
        'name': 'Pet Food & Accessories',
        'slug': 'pet-food-accessories',
        'priority': 3,
        'keywords': ['pet', 'dog', 'cat', 'animal', 'pet food'],
        'subcategory_expected': True,
        'max_pages': 5,
        'scraping_strategy': 'pagination'
    }
}

# Enhanced Selenium WebDriver Configuration
SELENIUM_CONFIG = {
    'user_agents': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ],
    'default_timeout': 15,
    'page_load_timeout': 30,
    'implicit_wait': 5,
    'window_sizes': ['1920,1080', '1366,768', '1536,864'],
    'viewport_randomization': True,
    'disable_blink_features': 'AutomationControlled',
    'experimental_options': {
        'excludeSwitches': ['enable-automation'],
        'useAutomationExtension': False,
        'prefs': {
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False
        }
    }
}

# Enhanced General Scraper Settings
SCRAPER_SETTINGS = {
    'max_pages_per_category': 10,
    'max_retries': 5,
    'retry_delay': 3.0,
    'exponential_backoff': True,
    'request_timeout': 30,
    'connection_timeout': 10,
    'scroll_pause_time': 2.0,
    'popup_check_delay': 2.0,
    'max_popup_attempts': 3,
    'rate_limit_indicators': [
        'rate limit',
        'too many requests',
        'please try again later',
        'temporarily unavailable',
        'access denied'
    ],
    'session_rotation_interval': 100,  # Rotate session after N requests
    'max_consecutive_errors': 10,
    'enable_javascript': True,
    'enable_cookies': True,
    'cookie_persistence': True
}

# Enhanced Product Extraction Configuration
PRODUCT_EXTRACTION_CONFIG = {
    'selectors': {
        'product_containers': [
            'div.co-product',
            'div[class*="co-product"]',
            'div[class*="product-tile"]',
            'div[class*="product-item"]',
            'article[class*="product"]',
            '[data-testid*="product"]',
            'div.product-card',
            'li.product-list-item'
        ],
        'product_title': [
            'a.co-product__anchor',
            'a[href*="/product/"]',
            '.product-title a',
            'h3 a',
            '[data-testid="product-title"]',
            '.co-product__title',
            'span.co-product__title'
        ],
        'product_price': [
            'strong.co-product__price',
            '.price strong',
            '.product-price strong',
            '[data-testid="price"]',
            'span.co-product__price',
            '.price-now'
        ],
        'was_price': [
            'span.co-product__was-price',
            '.was-price',
            '.price-was',
            '[data-testid="was-price"]',
            '.previous-price'
        ],
        'unit_price': [
            'span.co-product__price-per-quantity',
            '.price-per-unit',
            '.unit-price',
            '[data-testid="unit-price"]'
        ],
        'quantity': [
            'span.co-product__volume',
            '.product-unit',
            '.quantity',
            '[data-testid="quantity"]'
        ],
        'image': [
            'img.asda-img',
            '.product-image img',
            'img[src*="product"]',
            '[data-testid="product-image"] img',
            '.co-product__image img'
        ],
        'availability': [
            '.availability-status',
            '[data-testid="availability"]',
            '.stock-level',
            '.out-of-stock'
        ],
        'promotion': [
            '.promotion-badge',
            '.offer-text',
            '[data-testid="promotion"]',
            '.rollback-badge'
        ]
    },
    'regex_patterns': {
        'price': r'£(\d+\.?\d*)',
        'unit_price': r'£(\d+\.?\d*)\s*/\s*(\w+)',
        'quantity': r'(\d+\.?\d*)\s*(\w+)',
        'product_id': r'/product/(\d+)',
        'category_id': r'/cat/(\d+)'
    },
    'data_attributes': [
        'data-product-id',
        'data-sku',
        'data-price',
        'data-category',
        'data-brand'
    ]
}

# Enhanced Pagination Configuration
PAGINATION_CONFIG = {
    'strategies': {
        'button_click': {
            'selectors': [
                'a[aria-label="Next"]',
                'button[aria-label="Next"]',
                'a.pagination-next',
                'button.pagination-next',
                'a[class*="next"]',
                'button[class*="next"]',
                '.pagination__next'
            ],
            'wait_condition': 'element_to_be_clickable'
        },
        'url_parameter': {
            'param_name': 'page',
            'increment': 1,
            'max_pages': 50
        },
        'infinite_scroll': {
            'scroll_pause_time': 2.0,
            'max_scrolls': 20,
            'check_new_elements': True
        }
    },
    'page_indicators': {
        'current_page': [
            '.pagination__current',
            '[aria-current="page"]',
            '.active-page'
        ],
        'total_pages': [
            '.pagination__total',
            '.page-count',
            '[data-testid="total-pages"]'
        ]
    }
}

# Enhanced Popup and Cookie Banner Configuration
POPUP_CONFIG = {
    'cookie_banners': {
        'selectors': [
            "button[id*='accept']",
            "button[class*='accept']",
            "button[data-testid*='accept']",
            "#onetrust-accept-btn-handler",
            "#accept-cookies",
            ".cookie-accept",
            "[aria-label*='Accept cookies']"
        ],
        'text_patterns': [
            'Accept', 'Accept All', 'Accept all', 
            'Allow All', 'Continue', 'OK', 'I Agree'
        ]
    },
    'modal_popups': {
        'close_selectors': [
            "button[aria-label*='close']",
            "button[aria-label*='Close']",
            ".modal-close",
            ".popup-close",
            "[data-testid*='close']",
            "svg[class*='close']"
        ],
        'overlay_selectors': [
            '.modal-overlay',
            '.popup-overlay',
            '[data-testid="overlay"]'
        ]
    },
    'notification_banners': {
        'selectors': [
            '.notification-banner button',
            '.banner-close',
            '.consent-banner button',
            '[data-testid="dismiss-banner"]'
        ]
    },
    'handling_config': {
        'max_attempts': 5,
        'delay_between_attempts': 1.5,
        'check_interval': 2.0,
        'dismiss_strategy': 'click_first_available'
    }
}

# Enhanced Error Handling Configuration
ERROR_CONFIG = {
    'thresholds': {
        'max_category_errors': 10,
        'max_product_errors': 50,
        'max_consecutive_errors': 5,
        'error_rate_threshold': 0.3  # 30% error rate triggers cooldown
    },
    'retry_config': {
        'status_codes': [429, 502, 503, 504, 520, 521, 522],
        'exceptions': [
            'TimeoutException',
            'NoSuchElementException',
            'WebDriverException',
            'StaleElementReferenceException'
        ],
        'max_retries': 5,
        'backoff_factor': 2.0,
        'max_backoff': 60.0
    },
    'recovery_strategies': {
        'refresh_page': True,
        'clear_cookies': True,
        'rotate_user_agent': True,
        'change_viewport': True,
        'restart_driver': True
    },
    'error_classifications': {
        'recoverable': [
            'TimeoutException',
            'StaleElementReferenceException',
            'ElementClickInterceptedException'
        ],
        'non_recoverable': [
            'InvalidSessionIdException',
            'WebDriverException'
        ]
    }
}

# Enhanced Logging Configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '[%(asctime)s] [%(name)s] [%(levelname)s] [%(funcName)s:%(lineno)d] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'asda_scraper.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'detailed',
            'level': 'DEBUG'
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOGS_DIR / 'asda_scraper_errors.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed',
            'level': 'ERROR'
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'INFO'
        }
    },
    'loggers': {
        'asda_scraper': {
            'handlers': ['file', 'error_file', 'console'],
            'level': 'DEBUG',
            'propagate': False
        },
        'selenium': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False
        }
    }
}

# Browser Driver Paths (Windows) - Enhanced
DRIVER_PATHS = {
    'chrome': {
        'driver_paths': [
            r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
            r"C:\chromedriver\chromedriver.exe",
            r"C:\WebDriver\bin\chromedriver.exe",
            str(PROJECT_ROOT / "drivers" / "chromedriver.exe"),
            "./chromedriver.exe",
            "chromedriver.exe"
        ],
        'binary_paths': [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"
        ]
    },
    'edge': {
        'driver_paths': [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedgedriver.exe",
            r"C:\WebDriver\bin\msedgedriver.exe",
            str(PROJECT_ROOT / "drivers" / "msedgedriver.exe")
        ],
        'binary_paths': [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        ]
    }
}

# Enhanced Default Crawl Session Settings
DEFAULT_CRAWL_SETTINGS = {
    'max_categories': 20,
    'category_priority_threshold': 2,
    'max_products_per_category': 200,
    'batch_size': 50,
    'delay_between_requests': 2.0,
    'use_selenium': True,
    'headless': False,
    'browser': 'chrome',
    'respect_robots_txt': True,
    'user_agent_rotation': True,
    'session_persistence': True,
    'enable_caching': True,
    'cache_expiry': 3600,  # 1 hour
    'screenshot_on_error': True,
    'save_html_on_error': True,
    'performance_monitoring': True
}

# Category Validation Settings
CATEGORY_VALIDATION = {
    'url_patterns': {
        'required': ['groceries.asda.com', '/cat/'],
        'forbidden': ['checkout', 'basket', 'account', 'login']
    },
    'title_validation': {
        'invalid_keywords': [
            '404', 'error', 'not found', 'page not found',
            'access denied', 'forbidden'
        ],
        'min_length': 3,
        'max_length': 100
    },
    'content_validation': {
        'min_products': 1,
        'required_elements': ['product', 'price'],
        'timeout': 30
    }
}

# Performance Monitoring Configuration
PERFORMANCE_CONFIG = {
    'metrics': {
        'page_load_time': {'threshold': 10.0, 'unit': 'seconds'},
        'element_wait_time': {'threshold': 5.0, 'unit': 'seconds'},
        'memory_usage': {'threshold': 512, 'unit': 'MB'},
        'cpu_usage': {'threshold': 80, 'unit': 'percent'}
    },
    'monitoring_interval': 60,  # seconds
    'alert_thresholds': {
        'slow_page_loads': 5,
        'memory_warnings': 3,
        'cpu_warnings': 3
    }
}

# Data Quality Configuration
DATA_QUALITY_CONFIG = {
    'validation_rules': {
        'price': {
            'min': 0.01,
            'max': 1000.00,
            'required': True
        },
        'title': {
            'min_length': 3,
            'max_length': 500,
            'required': True
        },
        'url': {
            'pattern': r'^https?://.*',
            'required': True
        }
    },
    'cleaning_rules': {
        'strip_whitespace': True,
        'remove_special_chars': False,
        'normalize_prices': True,
        'extract_quantity': True
    }
}

# Export all configuration as a single dict for easy access
SCRAPER_CONFIG = {
    'base_url': ASDA_BASE_URL,
    'category_base': ASDA_CATEGORY_BASE,
    'rate_limit': RATE_LIMIT_CONFIG,
    'delays': DELAY_CONFIG,
    'categories': CATEGORY_CONFIG,
    'selenium': SELENIUM_CONFIG,
    'scraper': SCRAPER_SETTINGS,
    'extraction': PRODUCT_EXTRACTION_CONFIG,
    'pagination': PAGINATION_CONFIG,
    'popups': POPUP_CONFIG,
    'errors': ERROR_CONFIG,
    'logging': LOGGING_CONFIG,
    'drivers': DRIVER_PATHS,
    'crawl_defaults': DEFAULT_CRAWL_SETTINGS,
    'validation': CATEGORY_VALIDATION,
    'performance': PERFORMANCE_CONFIG,
    'data_quality': DATA_QUALITY_CONFIG
}

# Utility function to get config
def get_config(key: str, default: Any = None) -> Any:
    """
    Get configuration value by key with dot notation support.
    
    Args:
        key: Configuration key (supports dot notation like 'selenium.user_agents')
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    try:
        value = SCRAPER_CONFIG
        for part in key.split('.'):
            value = value[part]
        return value
    except (KeyError, TypeError):
        logging.warning(f"Configuration key '{key}' not found, using default: {default}")
        return default


# Initialize logging when module is imported
logging.config.dictConfig(LOGGING_CONFIG)