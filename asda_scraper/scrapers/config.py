"""
Configuration settings for ASDA scraper.

File: asda_scraper/scrapers/config.py
"""

import logging

logger = logging.getLogger(__name__)

# ASDA Category mappings with real category codes - COMPREHENSIVE UPDATE
ASDA_CATEGORY_MAPPINGS = {
    # Primary Food Categories
    '1215686352935': {
        'name': 'Fruit, Veg & Flowers',
        'slug': 'fruit-veg-flowers',
        'priority': 1,
        'keywords': ['fruit', 'vegetable', 'veg', 'salad', 'herbs'],
        'subcategory_expected': True,
        'max_pages': 8
    },
    '1215135760597': {
        'name': 'Meat, Poultry & Fish',
        'slug': 'meat-poultry-fish',
        'priority': 1,
        'keywords': ['chicken', 'beef', 'pork', 'lamb', 'fish', 'salmon'],
        'subcategory_expected': True,
        'max_pages': 10
    },
    
    # BAKERY SECTION - Main and Essential Subcategories
    '1215686354843': {
        'name': 'Bakery',
        'slug': 'bakery',
        'priority': 1,
        'keywords': ['bread', 'roll', 'cake', 'pastry', 'croissant'],
        'subcategory_expected': True,
        'max_pages': 6
    },
    # Essential Bread Categories
    '1215686354871': {
        'name': 'Bread',
        'slug': 'bakery/bread',
        'priority': 2,
        'keywords': ['bread', 'loaf'],
        'subcategory_expected': False,
        'max_pages': 4
    },
    '1215686354865': {
        'name': 'Bread & Rolls',
        'slug': 'bakery/bread-rolls',
        'priority': 2,
        'keywords': ['bread', 'roll'],
        'subcategory_expected': False,
        'max_pages': 4
    },
    '1215686354872': {
        'name': 'Bread Rolls',
        'slug': 'bakery/bread-rolls',
        'priority': 3,
        'keywords': ['roll', 'bun'],
        'subcategory_expected': False,
        'max_pages': 3
    },
    # Bagels and similar
    '1215686354876': {
        'name': 'Bagels',
        'slug': 'bakery',
        'priority': 3,  # Lower priority since it's getting wrong results
        'keywords': ['bagel', 'breakfast', 'bread'],
        'subcategory_expected': False,
        'max_pages': 2,
        'skip_validation': True  # Skip this category for now
    },
    '1215675037025': {
        'name': 'Baguettes',
        'slug': 'bakery/baguettes',
        'priority': 3,
        'keywords': ['baguette', 'french bread'],
        'subcategory_expected': False,
        'max_pages': 2
    },
    # Essential Cake Categories
    '1215686354851': {
        'name': 'Cakes',
        'slug': 'bakery/cakes',
        'priority': 2,
        'keywords': ['cake', 'sponge'],
        'subcategory_expected': False,
        'max_pages': 5
    },
    '1215686354898': {
        'name': 'Loaf Cakes',
        'slug': 'bakery/loaf-cakes',
        'priority': 3,
        'keywords': ['cake', 'loaf cake'],
        'subcategory_expected': False,
        'max_pages': 3
    },
    # Specialty Bread
    '1215686354878': {
        'name': 'Naan Bread',
        'slug': 'bakery/naan-bread',
        'priority': 3,
        'keywords': ['naan', 'indian bread'],
        'subcategory_expected': False,
        'max_pages': 2
    },
    '1215686354879': {
        'name': 'Pitta Bread & Flatbread',
        'slug': 'bakery/pitta-flatbread',
        'priority': 3,
        'keywords': ['pitta', 'flatbread'],
        'subcategory_expected': False,
        'max_pages': 2
    },
    '1215686354875': {
        'name': 'Wraps',
        'slug': 'bakery/wraps',
        'priority': 3,
        'keywords': ['wrap', 'tortilla'],
        'subcategory_expected': False,
        'max_pages': 3
    },
    '1215660378320': {
        'name': 'Chilled Food',
        'slug': 'chilled-food',
        'priority': 1,
        'keywords': ['milk', 'cheese', 'yogurt', 'butter', 'cream'],
        'subcategory_expected': True,
        'max_pages': 12
    },
    '1215338621416': {
        'name': 'Frozen Food',
        'slug': 'frozen-food',
        'priority': 1,
        'keywords': ['frozen', 'ice cream', 'frozen vegetables'],
        'subcategory_expected': True,
        'max_pages': 8
    },
    '1215337189632': {
        'name': 'Food Cupboard',
        'slug': 'food-cupboard',
        'priority': 1,
        'keywords': ['pasta', 'rice', 'sauce', 'tin', 'jar'],
        'subcategory_expected': True,
        'max_pages': 15
    },
    '1215686356579': {
        'name': 'Sweets, Treats & Snacks',
        'slug': 'sweets-treats-snacks',
        'priority': 2,
        'keywords': ['chocolate', 'sweet', 'snack', 'crisp'],
        'subcategory_expected': True,
        'max_pages': 10
    },
    '1215686355606': {
        'name': 'Dietary & Lifestyle',
        'slug': 'dietary-lifestyle',
        'priority': 1,
        'keywords': ['gluten free', 'vegan', 'organic', 'free from'],
        'subcategory_expected': True,
        'max_pages': 8
    },
    '1215135760614': {
        'name': 'Drinks',
        'slug': 'drinks',
        'priority': 2,
        'keywords': ['water', 'juice', 'soft drink', 'tea', 'coffee'],
        'subcategory_expected': True,
        'max_pages': 10
    },
    '1215685911554': {
        'name': 'Beer, Wine & Spirits',
        'slug': 'beer-wine-spirits',
        'priority': 3,
        'keywords': ['beer', 'wine', 'spirits', 'alcohol'],
        'subcategory_expected': True,
        'max_pages': 12
    },
    '1215686351451': {
        'name': 'World Food',
        'slug': 'world-food',
        'priority': 2,
        'keywords': ['asian', 'indian', 'mexican', 'italian', 'chinese'],
        'subcategory_expected': True,
        'max_pages': 8
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
    'session_rotation_interval': 100,
    'max_consecutive_errors': 10,
    'enable_javascript': True,
    'enable_cookies': True,
    'cookie_persistence': True,
    'category_validation_enabled': True,  # NEW: Enable category validation
    'require_active_categories': True,    # NEW: Require categories to be active
    'skip_invalid_categories': True       # NEW: Skip categories that return 404/errors
}

# Enhanced Product Extraction Configuration
PRODUCT_EXTRACTION_CONFIG = {
    'selectors': {
        # Updated selectors for current ASDA website structure
        'product_grid': [
            '.co-item',
            '.product-item',
            '[data-testid="product-tile"]',
            '.product-card',
            '.product-container'
        ],
        'product_name': [
            '.co-item__title',
            '.product-name',
            '[data-testid="product-title"]',
            '.product-title',
            'h3 a'
        ],
        'product_price': [
            '.co-item__price',
            '.price-current',
            '[data-testid="product-price"]',
            '.product-price',
            '.price'
        ],
        'product_link': [
            '.co-item__anchor',
            '.product-link',
            '[data-testid="product-link"]',
            'a[href*="/product/"]'
        ],
        'product_image': [
            '.co-item__image img',
            '.product-image img',
            '[data-testid="product-image"] img',
            '.product-img img'
        ],
        'next_page': [
            '.pagination__next',
            '.next-page',
            '[aria-label="Next page"]',
            '.pagination-next'
        ],
        'load_more': [
            '.load-more',
            '[data-testid="load-more"]',
            '.show-more-products'
        ]
    },
    'max_products_per_page': 48,
    'pagination_enabled': True,
    'infinite_scroll_enabled': False,
    'product_validation_rules': {
        'min_name_length': 3,
        'require_price': True,
        'require_image': False,
        'price_format_validation': True
    }
}

# Delay Configuration
DELAY_CONFIG = {
    'between_categories': 60.0,      # 60 seconds between main categories
    'between_pages': 3.0,            # 3 seconds between pages
    'after_product_extraction': 2.0, # 2 seconds after extracting products
    'after_popup_handling': 1.0,     # 1 second after handling popups
    'page_load_wait': 3.0,          # 3 seconds for page to load
    'element_wait': 10.0,           # 10 seconds to wait for elements
    'error_backoff_multiplier': 2.0, # Multiply delay by this on errors
    'max_error_delay': 30.0,         # Maximum delay for error backoff
    'random_delay_min': 0.5,         # NEW: Minimum random delay
    'random_delay_max': 2.0,         # NEW: Maximum random delay
    'progressive_delay_factor': 1.5,  # NEW: Progressive delay factor
    'max_progressive_delay': 60.0     # NEW: Maximum progressive delay
}

# Logging Configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} [{name}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '[{levelname}] {name}: {message}',
            'style': '{'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/asda_scraper.log',
            'maxBytes': 10*1024*1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'DEBUG',
            'encoding': 'utf-8'
        }
    },
    'loggers': {
        'asda_scraper': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}


def validate_category_mapping(url_code: str) -> bool:
    """
    Validate if a category URL code exists in mappings.
    
    Args:
        url_code (str): Category URL code to validate
        
    Returns:
        bool: True if category exists in mappings
    """
    try:
        return url_code in ASDA_CATEGORY_MAPPINGS
    except Exception as e:
        logger.error(f"Error validating category mapping for {url_code}: {e}")
        return False


def get_category_info(url_code: str) -> dict:
    """
    Get category information for a given URL code.
    
    Args:
        url_code (str): Category URL code
        
    Returns:
        dict: Category information or empty dict if not found
    """
    try:
        return ASDA_CATEGORY_MAPPINGS.get(url_code, {})
    except Exception as e:
        logger.error(f"Error getting category info for {url_code}: {e}")
        return {}


def get_selector_fallbacks(selector_type: str) -> list:
    """
    Get fallback selectors for a given selector type.
    
    Args:
        selector_type (str): Type of selector (e.g., 'product_grid')
        
    Returns:
        list: List of selector strings to try
    """
    try:
        selectors = PRODUCT_EXTRACTION_CONFIG.get('selectors', {})
        return selectors.get(selector_type, [])
    except Exception as e:
        logger.error(f"Error getting selector fallbacks for {selector_type}: {e}")
        return []