"""
Configuration settings for ASDA scraper with intelligent speed optimizations.

This module provides all configuration settings for the ASDA web scraper,
including category mappings, delay management, selenium settings, and automatic
speed optimization based on environment detection.

File: asda_scraper/scrapers/config.py
"""

import logging
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

# Initialize logger
logger = logging.getLogger(__name__)

# =============================================================================
# SPEED MODE CONFIGURATION - Automatically detects environment
# =============================================================================

# Speed mode detection
DEVELOPMENT_MODE_DETECTED = False
try:
    from django.conf import settings
    DEVELOPMENT_MODE_DETECTED = getattr(settings, 'DEBUG', True)
    logger.info(f"Django detected - DEBUG mode: {DEVELOPMENT_MODE_DETECTED}")
except ImportError:
    # No Django available, assume development for faster defaults
    DEVELOPMENT_MODE_DETECTED = True
    logger.info("No Django detected - defaulting to development mode for speed")

# =============================================================================
# ASDA CATEGORY MAPPINGS - Comprehensive and Organized
# =============================================================================

ASDA_CATEGORY_MAPPINGS = {
    # =========================================================================
    # PRIORITY 1 - ESSENTIAL FOOD CATEGORIES (Primary targets)
    # =========================================================================
    '1215686352935': {
        'name': 'Fruit, Veg & Flowers',
        'slug': 'fruit-veg-flowers',
        'priority': 1,
        'keywords': ['fruit', 'vegetable', 'veg', 'salad', 'herbs'],
        'subcategory_expected': True,
        'max_pages': 8,
        'estimated_products': 400
    },
    '1215135760597': {
        'name': 'Meat, Poultry & Fish',
        'slug': 'meat-poultry-fish',
        'priority': 1,
        'keywords': ['chicken', 'beef', 'pork', 'lamb', 'fish', 'salmon'],
        'subcategory_expected': True,
        'max_pages': 10,
        'estimated_products': 500
    },
    '1215660378320': {
        'name': 'Chilled Food',
        'slug': 'chilled-food',
        'priority': 1,
        'keywords': ['milk', 'cheese', 'yogurt', 'butter', 'cream'],
        'subcategory_expected': True,
        'max_pages': 12,
        'estimated_products': 600
    },
    '1215338621416': {
        'name': 'Frozen Food',
        'slug': 'frozen-food',
        'priority': 1,
        'keywords': ['frozen', 'ice cream', 'frozen vegetables'],
        'subcategory_expected': True,
        'max_pages': 8,
        'estimated_products': 400
    },
    '1215337189632': {
        'name': 'Food Cupboard',
        'slug': 'food-cupboard',
        'priority': 1,
        'keywords': ['pasta', 'rice', 'sauce', 'tin', 'jar'],
        'subcategory_expected': True,
        'max_pages': 15,
        'estimated_products': 750
    },
    '1215686355606': {
        'name': 'Dietary & Lifestyle',
        'slug': 'dietary-lifestyle',
        'priority': 1,
        'keywords': ['gluten free', 'vegan', 'organic', 'free from'],
        'subcategory_expected': True,
        'max_pages': 8,
        'estimated_products': 400
    },
    
    # =========================================================================
    # BAKERY SECTION - Complete hierarchy
    # =========================================================================
    '1215686354843': {
        'name': 'Bakery',
        'slug': 'bakery',
        'priority': 1,
        'keywords': ['bread', 'roll', 'cake', 'pastry', 'croissant'],
        'subcategory_expected': True,
        'max_pages': 6,
        'estimated_products': 300
    },
    # Essential Bread Categories
    '1215686354871': {
        'name': 'Bread',
        'slug': 'bakery/bread',
        'priority': 2,
        'keywords': ['bread', 'loaf'],
        'subcategory_expected': False,
        'max_pages': 4,
        'estimated_products': 100
    },
    '1215686354865': {
        'name': 'Bread & Rolls',
        'slug': 'bakery/bread-rolls',
        'priority': 2,
        'keywords': ['bread', 'roll'],
        'subcategory_expected': False,
        'max_pages': 4,
        'estimated_products': 120
    },
    '1215686354872': {
        'name': 'Bread Rolls',
        'slug': 'bakery/bread-rolls',
        'priority': 3,
        'keywords': ['roll', 'bun'],
        'subcategory_expected': False,
        'max_pages': 3,
        'estimated_products': 80
    },
    '1215675037025': {
        'name': 'Baguettes',
        'slug': 'bakery/baguettes',
        'priority': 3,
        'keywords': ['baguette', 'french bread'],
        'subcategory_expected': False,
        'max_pages': 2,
        'estimated_products': 40
    },
    # Essential Cake Categories
    '1215686354851': {
        'name': 'Cakes',
        'slug': 'bakery/cakes',
        'priority': 2,
        'keywords': ['cake', 'sponge'],
        'subcategory_expected': False,
        'max_pages': 5,
        'estimated_products': 150
    },
    '1215686354898': {
        'name': 'Loaf Cakes',
        'slug': 'bakery/loaf-cakes',
        'priority': 3,
        'keywords': ['cake', 'loaf cake'],
        'subcategory_expected': False,
        'max_pages': 3,
        'estimated_products': 80
    },
    # Specialty Bread
    '1215686354878': {
        'name': 'Naan Bread',
        'slug': 'bakery/naan-bread',
        'priority': 3,
        'keywords': ['naan', 'indian bread'],
        'subcategory_expected': False,
        'max_pages': 2,
        'estimated_products': 30
    },
    '1215686354879': {
        'name': 'Pitta Bread & Flatbread',
        'slug': 'bakery/pitta-flatbread',
        'priority': 3,
        'keywords': ['pitta', 'flatbread'],
        'subcategory_expected': False,
        'max_pages': 2,
        'estimated_products': 40
    },
    '1215686354875': {
        'name': 'Wraps',
        'slug': 'bakery/wraps',
        'priority': 3,
        'keywords': ['wrap', 'tortilla'],
        'subcategory_expected': False,
        'max_pages': 3,
        'estimated_products': 60
    },
    # Problematic category - skip for now
    '1215686354876': {
        'name': 'Bagels',
        'slug': 'bakery',
        'priority': 3,
        'keywords': ['bagel', 'breakfast', 'bread'],
        'subcategory_expected': False,
        'max_pages': 2,
        'skip_validation': True,  # Skip this category for now
        'estimated_products': 30
    },
    
    # =========================================================================
    # PRIORITY 2 - SECONDARY CATEGORIES
    # =========================================================================
    '1215686356579': {
        'name': 'Sweets, Treats & Snacks',
        'slug': 'sweets-treats-snacks',
        'priority': 2,
        'keywords': ['chocolate', 'sweet', 'snack', 'crisp'],
        'subcategory_expected': True,
        'max_pages': 10,
        'estimated_products': 500
    },
    '1215135760614': {
        'name': 'Drinks',
        'slug': 'drinks',
        'priority': 2,
        'keywords': ['water', 'juice', 'soft drink', 'tea', 'coffee'],
        'subcategory_expected': True,
        'max_pages': 10,
        'estimated_products': 500
    },
    '1215686351451': {
        'name': 'World Food',
        'slug': 'world-food',
        'priority': 2,
        'keywords': ['asian', 'indian', 'mexican', 'italian', 'chinese'],
        'subcategory_expected': True,
        'max_pages': 8,
        'estimated_products': 400
    },
    
    # =========================================================================
    # PRIORITY 3 - OPTIONAL CATEGORIES
    # =========================================================================
    '1215685911554': {
        'name': 'Beer, Wine & Spirits',
        'slug': 'beer-wine-spirits',
        'priority': 3,
        'keywords': ['beer', 'wine', 'spirits', 'alcohol'],
        'subcategory_expected': True,
        'max_pages': 12,
        'estimated_products': 600
    }
}

# =============================================================================
# INTELLIGENT DELAY CONFIGURATION - Auto-optimizes based on environment
# =============================================================================

# Production delays (conservative, respectful)
PRODUCTION_DELAY_CONFIG = {
    'between_categories': 60.0,       # 1 minute between categories
    'between_subcategories': 3.0,     # 3 seconds between subcategories
    'between_pages': 3.0,             # 3 seconds between pages
    'after_product_extraction': 2.0,  # 2 seconds after extracting products
    'after_popup_handling': 1.0,      # 1 second after handling popups
    'page_load_wait': 3.0,           # 3 seconds for page to load
    'element_wait': 10.0,            # 10 seconds to wait for elements
    'between_requests': 2.0,          # 2 seconds between general requests
    'error_backoff_multiplier': 2.0,  # Multiply delay by this on errors
    'max_error_delay': 30.0,          # Maximum delay for error backoff
    'random_delay_min': 0.5,          # Minimum random delay
    'random_delay_max': 2.0,          # Maximum random delay
    'progressive_delay_factor': 1.5,   # Progressive delay factor
    'max_progressive_delay': 60.0      # Maximum progressive delay
}

# Development delays (fast, for testing)
DEVELOPMENT_DELAY_CONFIG = {
    'between_categories': 2.0,        # 2 seconds between categories (97% faster)
    'between_subcategories': 0.5,     # 0.5 seconds between subcategories
    'between_pages': 0.3,             # 0.3 seconds between pages (90% faster)
    'after_product_extraction': 0.2,  # 0.2 seconds after extracting
    'after_popup_handling': 0.1,      # 0.1 seconds after popup handling
    'page_load_wait': 1.0,           # 1 second for page load (67% faster)
    'element_wait': 3.0,             # 3 seconds to wait for elements (70% faster)
    'between_requests': 0.2,          # 0.2 seconds between requests
    'error_backoff_multiplier': 1.2,  # Minimal backoff multiplier
    'max_error_delay': 5.0,           # 5 seconds max error delay (83% faster)
    'random_delay_min': 0.05,         # Minimal random delay
    'random_delay_max': 0.15,         # Minimal random delay
    'progressive_delay_factor': 1.1,   # Minimal progressive factor
    'max_progressive_delay': 8.0       # 8 seconds max progressive delay
}

# Ultra-fast delays (for testing only - may trigger rate limiting)
ULTRA_FAST_DELAY_CONFIG = {
    'between_categories': 0.5,        # 0.5 seconds between categories
    'between_subcategories': 0.2,     # 0.2 seconds between subcategories
    'between_pages': 0.1,             # 0.1 seconds between pages
    'after_product_extraction': 0.05, # 0.05 seconds after extracting
    'after_popup_handling': 0.05,     # 0.05 seconds after popup handling
    'page_load_wait': 0.5,           # 0.5 seconds for page load
    'element_wait': 1.0,             # 1 second to wait for elements
    'between_requests': 0.1,          # 0.1 seconds between requests
    'error_backoff_multiplier': 1.1,  # Minimal backoff multiplier
    'max_error_delay': 2.0,           # 2 seconds max error delay
    'random_delay_min': 0.01,         # Minimal random delay
    'random_delay_max': 0.05,         # Minimal random delay
    'progressive_delay_factor': 1.05,  # Minimal progressive factor
    'max_progressive_delay': 3.0       # 3 seconds max progressive delay
}

# Set initial delay configuration based on environment
if DEVELOPMENT_MODE_DETECTED:
    DELAY_CONFIG = DEVELOPMENT_DELAY_CONFIG.copy()
    logger.info("🚀 DEVELOPMENT MODE: Fast delays activated automatically")
else:
    DELAY_CONFIG = PRODUCTION_DELAY_CONFIG.copy()
    logger.info("🐌 PRODUCTION MODE: Conservative delays activated")

# =============================================================================
# SELENIUM WEBDRIVER CONFIGURATION - Optimized
# =============================================================================

SELENIUM_CONFIG = {
    'user_agents': [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ],
    # Optimized timeouts based on mode
    'default_timeout': 8 if DEVELOPMENT_MODE_DETECTED else 15,
    'page_load_timeout': 15 if DEVELOPMENT_MODE_DETECTED else 30,
    'implicit_wait': 2 if DEVELOPMENT_MODE_DETECTED else 5,
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

# =============================================================================
# SCRAPER SETTINGS - Performance optimized
# =============================================================================

SCRAPER_SETTINGS = {
    'max_pages_per_category': 10,
    # Optimized retry settings based on mode
    'max_retries': 3 if DEVELOPMENT_MODE_DETECTED else 5,
    'retry_delay': 1.0 if DEVELOPMENT_MODE_DETECTED else 3.0,
    'exponential_backoff': True,
    # Optimized timeout settings
    'request_timeout': 15 if DEVELOPMENT_MODE_DETECTED else 30,
    'connection_timeout': 5 if DEVELOPMENT_MODE_DETECTED else 10,
    'scroll_pause_time': 0.5 if DEVELOPMENT_MODE_DETECTED else 2.0,
    'popup_check_delay': 0.5 if DEVELOPMENT_MODE_DETECTED else 2.0,
    'max_popup_attempts': 2 if DEVELOPMENT_MODE_DETECTED else 3,
    'rate_limit_indicators': [
        'rate limit',
        'too many requests',
        'please try again later',
        'temporarily unavailable',
        'access denied'
    ],
    'session_rotation_interval': 200 if DEVELOPMENT_MODE_DETECTED else 100,
    'max_consecutive_errors': 15 if DEVELOPMENT_MODE_DETECTED else 10,
    'enable_javascript': True,
    'enable_cookies': True,
    'cookie_persistence': True,
    'category_validation_enabled': True,
    'require_active_categories': True,
    'skip_invalid_categories': True
}

# =============================================================================
# PRODUCT EXTRACTION CONFIGURATION
# =============================================================================

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

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

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

# =============================================================================
# DYNAMIC SPEED CONTROL FUNCTIONS
# =============================================================================

def switch_to_production_mode():
    """
    Switch to production mode with conservative delays.
    
    Use this when deploying to production or when you want to be
    respectful to the target website.
    """
    global DELAY_CONFIG, SELENIUM_CONFIG, SCRAPER_SETTINGS
    
    logger.info("🐌 SWITCHING TO PRODUCTION MODE")
    DELAY_CONFIG.update(PRODUCTION_DELAY_CONFIG)
    
    # Update timeouts for production
    SELENIUM_CONFIG.update({
        'default_timeout': 15,
        'page_load_timeout': 30,
        'implicit_wait': 5
    })
    
    SCRAPER_SETTINGS.update({
        'max_retries': 5,
        'retry_delay': 3.0,
        'request_timeout': 30,
        'connection_timeout': 10,
        'scroll_pause_time': 2.0,
        'popup_check_delay': 2.0,
        'max_popup_attempts': 3,
        'session_rotation_interval': 100,
        'max_consecutive_errors': 10
    })
    
    logger.info("✅ Production mode activated - conservative settings")
    _log_speed_summary()

def switch_to_development_mode():
    """
    Switch to development mode with fast delays.
    
    Use this for development, testing, or when you need faster crawling.
    """
    global DELAY_CONFIG, SELENIUM_CONFIG, SCRAPER_SETTINGS
    
    logger.info("🚀 SWITCHING TO DEVELOPMENT MODE")
    DELAY_CONFIG.update(DEVELOPMENT_DELAY_CONFIG)
    
    # Update timeouts for development
    SELENIUM_CONFIG.update({
        'default_timeout': 8,
        'page_load_timeout': 15,
        'implicit_wait': 2
    })
    
    SCRAPER_SETTINGS.update({
        'max_retries': 3,
        'retry_delay': 1.0,
        'request_timeout': 15,
        'connection_timeout': 5,
        'scroll_pause_time': 0.5,
        'popup_check_delay': 0.5,
        'max_popup_attempts': 2,
        'session_rotation_interval': 200,
        'max_consecutive_errors': 15
    })
    
    logger.info("✅ Development mode activated - fast settings")
    _log_speed_summary()

def switch_to_ultra_fast_mode():
    """
    Switch to ultra-fast mode for testing only.
    
    WARNING: This may trigger rate limiting! Use only for testing
    with a small number of categories.
    """
    global DELAY_CONFIG
    
    logger.warning("⚡ SWITCHING TO ULTRA-FAST MODE")
    logger.warning("⚠️  WARNING: This may trigger rate limiting!")
    
    DELAY_CONFIG.update(ULTRA_FAST_DELAY_CONFIG)
    
    logger.warning("✅ Ultra-fast mode activated - maximum speed!")
    _log_speed_summary()

def get_delay_setting(delay_type: str, default: float = 2.0) -> float:
    """
    Get delay setting with fallback to default.
    
    Args:
        delay_type: Type of delay from DELAY_CONFIG
        default: Default delay if not found
        
    Returns:
        float: Delay in seconds
    """
    return DELAY_CONFIG.get(delay_type, default)

def _log_speed_summary():
    """
    Log a summary of current speed settings.
    """
    category_delay = DELAY_CONFIG['between_categories']
    page_delay = DELAY_CONFIG['between_pages']
    element_wait = DELAY_CONFIG['element_wait']
    
    logger.info("=== CURRENT SPEED SETTINGS ===")
    logger.info(f"Between categories: {category_delay}s")
    logger.info(f"Between pages: {page_delay}s") 
    logger.info(f"Element wait: {element_wait}s")
    
    # Estimate time for 10 categories with 5 pages each
    estimated_time = (category_delay * 10) + (page_delay * 50) + (element_wait * 50)
    logger.info(f"Estimated time for 10 categories: {estimated_time/60:.1f} minutes")
    
    if category_delay > 10:
        logger.warning("⚠️  Slow mode active - consider switching to development mode for faster crawling")
    else:
        logger.info("✅ Fast mode active")

def verify_speed_optimization():
    """
    Verify that speed optimizations are working correctly.
    """
    logger.info("=== SPEED OPTIMIZATION VERIFICATION ===")
    
    mode = "DEVELOPMENT" if DEVELOPMENT_MODE_DETECTED else "PRODUCTION"
    logger.info(f"Environment mode: {mode}")
    
    _log_speed_summary()
    
    # Check if delays are reasonable
    if DELAY_CONFIG['between_categories'] > 30:
        logger.warning("⚠️  Category delays are very high - consider using switch_to_development_mode()")
    elif DELAY_CONFIG['between_categories'] > 10:
        logger.warning("⚠️  Category delays are high - this will be slow")
    else:
        logger.info("✅ Category delays are optimized for speed")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

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

def get_priority_categories(max_priority: int = 2) -> Dict[str, dict]:
    """
    Get categories up to a certain priority level.
    
    Args:
        max_priority: Maximum priority level to include (1=highest, 3=lowest)
        
    Returns:
        dict: Filtered category mappings
    """
    return {
        code: info for code, info in ASDA_CATEGORY_MAPPINGS.items()
        if info.get('priority', 3) <= max_priority
    }

def estimate_crawl_time(categories: Optional[Dict[str, dict]] = None) -> float:
    """
    Estimate total crawl time based on current delay settings.
    
    Args:
        categories: Category mappings to estimate for (default: all priority 1-2)
        
    Returns:
        float: Estimated time in minutes
    """
    if categories is None:
        categories = get_priority_categories(max_priority=2)
    
    total_time = 0
    category_delay = DELAY_CONFIG['between_categories']
    page_delay = DELAY_CONFIG['between_pages']
    
    for code, info in categories.items():
        max_pages = info.get('max_pages', 5)
        total_time += category_delay  # Time between categories
        total_time += (page_delay * max_pages)  # Time for pages
    
    return total_time / 60  # Convert to minutes

# =============================================================================
# AUTO-INITIALIZATION
# =============================================================================

# Log initial configuration
logger.info("=== ASDA SCRAPER CONFIG INITIALIZED ===")
logger.info(f"Environment: {'DEVELOPMENT' if DEVELOPMENT_MODE_DETECTED else 'PRODUCTION'}")
logger.info(f"Total categories configured: {len(ASDA_CATEGORY_MAPPINGS)}")
logger.info(f"Priority 1 categories: {len(get_priority_categories(1))}")
logger.info(f"Priority 1-2 categories: {len(get_priority_categories(2))}")

# Verify speed settings on import
verify_speed_optimization()

# Estimate crawl time
estimated_time = estimate_crawl_time()
logger.info(f"Estimated crawl time for priority 1-2 categories: {estimated_time:.1f} minutes")

logger.info("=== CONFIG READY ===")

# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

# Keep old function names for backward compatibility
use_fast_delays = switch_to_development_mode
use_normal_delays = switch_to_production_mode
auto_configure_delays = verify_speed_optimization