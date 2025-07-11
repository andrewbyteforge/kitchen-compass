"""
Configuration settings for ASDA scraper.

File: asda_scraper/scrapers/config.py
"""

# ASDA Category mappings with real category codes
ASDA_CATEGORY_MAPPINGS = {
    # Food Categories Only - No Baby Items
    '1215686352935': {
        'name': 'Fruit, Veg & Flowers',
        'slug': 'fruit-veg-flowers',
        'priority': 1,
        'keywords': ['fruit', 'vegetable', 'veg', 'salad', 'herbs']
    },
    '1215135760597': {
        'name': 'Meat, Poultry & Fish',
        'slug': 'meat-poultry-fish',
        'priority': 1,
        'keywords': ['chicken', 'beef', 'pork', 'lamb', 'fish', 'salmon']
    },
    '1215686354843': {
        'name': 'Bakery',
        'slug': 'bakery',
        'priority': 1,
        'keywords': ['bread', 'roll', 'cake', 'pastry', 'croissant']
    },
    '1215660378320': {
        'name': 'Chilled Food',
        'slug': 'chilled-food',
        'priority': 1,
        'keywords': ['milk', 'cheese', 'yogurt', 'butter', 'cream']
    },
    '1215338621416': {
        'name': 'Frozen Food',
        'slug': 'frozen-food',
        'priority': 1,
        'keywords': ['frozen', 'ice cream', 'frozen vegetables']
    },
    '1215337189632': {
        'name': 'Food Cupboard',
        'slug': 'food-cupboard',
        'priority': 1,
        'keywords': ['pasta', 'rice', 'sauce', 'tin', 'jar']
    },
    '1215686356579': {
        'name': 'Sweets, Treats & Snacks',
        'slug': 'sweets-treats-snacks',
        'priority': 2,
        'keywords': ['chocolate', 'sweet', 'snack', 'crisp']
    },
    '1215686355606': {
        'name': 'Dietary & Lifestyle',
        'slug': 'dietary-lifestyle',
        'priority': 1,
        'keywords': ['gluten free', 'vegan', 'organic', 'free from']
    },
    '1215135760614': {
        'name': 'Drinks',
        'slug': 'drinks',
        'priority': 2,
        'keywords': ['water', 'juice', 'soft drink', 'tea', 'coffee']
    },
    '1215685911554': {
        'name': 'Beer, Wine & Spirits',
        'slug': 'beer-wine-spirits',
        'priority': 3,
        'keywords': ['beer', 'wine', 'spirits', 'alcohol']
    },
    '1215686351451': {
        'name': 'World Food',
        'slug': 'world-food',
        'priority': 2,
        'keywords': ['asian', 'indian', 'mexican', 'italian', 'chinese']
    }
}

# Selenium WebDriver configuration
SELENIUM_CONFIG = {
    'user_agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'default_timeout': 10,
    'page_load_timeout': 30,
    'implicit_wait': 5,
    'window_size': '1920,1080',
}

# Scraper settings
SCRAPER_SETTINGS = {
    'max_pages_per_category': 5,
    'max_retries': 3,
    'retry_delay': 2.0,
    'request_delay': 1.0,
    'category_delay': 2.0,
    'rate_limit_indicators': [
        'too many requests',
        'rate limit',
        'please slow down',
        'access denied',
        'blocked'
    ]
}

# Default crawl settings
DEFAULT_CRAWL_SETTINGS = {
    'max_categories': 10,
    'category_priority': 2,
    'max_products_per_category': 100,
    'delay_between_requests': 2.0,
    'use_selenium': True,
    'headless': False,
    'respect_robots_txt': True,
    'user_agent': SELENIUM_CONFIG['user_agent']
}

# Delay configuration
DELAY_CONFIG = {
    'between_requests': 2.0,
    'between_categories': 60.0,
    'after_popup_handling': 1.0,
    'after_product_extraction': 1.5,
    'after_navigation_error': 5.0,
    'after_rate_limit_detected': 30.0,
    'random_delay_min': 0.5,
    'random_delay_max': 2.0,
    'progressive_delay_factor': 1.5,
    'max_progressive_delay': 60.0,
}