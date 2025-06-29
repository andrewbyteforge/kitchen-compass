"""
ASDA Scraper Configuration

This module contains configuration settings for the ASDA scraper including
category mappings, Selenium settings, and general scraper parameters.

File: asda_scraper/config/scraper_config.py
"""

# ASDA Category Mappings with Real Category Codes
ASDA_CATEGORY_MAPPINGS = {
    # Core Food Categories (Priority 1)
    '1215686352935': {
        'name': 'Fruit, Veg & Flowers',
        'slug': 'fruit-veg-flowers',
        'priority': 1,
        'keywords': [
            'banana', 'apple', 'orange', 'grape', 'tomato', 'cucumber',
            'lettuce', 'carrot', 'onion', 'potato', 'avocado', 'melon',
            'berry', 'cherry', 'plum', 'spinach', 'broccoli', 'pepper',
            'fruit', 'vegetable', 'veg', 'salad', 'herbs', 'flowers'
        ]
    },
    '1215135760597': {
        'name': 'Meat, Poultry & Fish',
        'slug': 'meat-poultry-fish',
        'priority': 1,
        'keywords': [
            'chicken', 'beef', 'pork', 'lamb', 'turkey', 'bacon', 'ham',
            'sausage', 'mince', 'steak', 'chop', 'breast', 'thigh', 'wing',
            'fish', 'salmon', 'cod', 'tuna', 'meat', 'poultry'
        ]
    },
    '1215660378320': {
        'name': 'Chilled Food',
        'slug': 'chilled-food',
        'priority': 1,
        'keywords': [
            'milk', 'cheese', 'yogurt', 'butter', 'cream', 'egg', 'dairy',
            'fresh', 'organic', 'free range', 'chilled', 'refrigerated'
        ]
    },
    '1215338621416': {
        'name': 'Frozen Food',
        'slug': 'frozen-food',
        'priority': 1,
        'keywords': [
            'frozen', 'ice cream', 'ice', 'freezer', 'sorbet', 'gelato',
            'frozen meal', 'frozen pizza', 'frozen vegetables'
        ]
    },
    '1215337189632': {
        'name': 'Food Cupboard',
        'slug': 'food-cupboard',
        'priority': 1,
        'keywords': [
            'pasta', 'rice', 'flour', 'sugar', 'oil', 'vinegar', 'sauce',
            'tin', 'can', 'jar', 'packet', 'cereal', 'biscuit', 'crisp',
            'canned', 'dried', 'instant', 'cooking', 'seasoning', 'spice'
        ]
    },
    '1215686354843': {
        'name': 'Bakery',
        'slug': 'bakery',
        'priority': 1,
        'keywords': [
            'bread', 'roll', 'bun', 'cake', 'pastry', 'croissant', 'bagel',
            'bakery', 'baked', 'loaf', 'sandwich', 'toast', 'muffin', 'scone'
        ]
    },
    '1215135760614': {
        'name': 'Drinks',
        'slug': 'drinks',
        'priority': 1,
        'keywords': [
            'water', 'juice', 'soft drink', 'tea', 'coffee', 'squash',
            'drink', 'beverage', 'cola', 'lemonade', 'smoothie', 'energy drink'
        ]
    },
    
    # Household & Personal Care (Priority 2)
    '1215135760665': {
        'name': 'Laundry & Household',
        'slug': 'laundry-household',
        'priority': 2,
        'keywords': [
            'cleaning', 'cleaner', 'toilet', 'kitchen', 'bathroom', 'washing up',
            'detergent', 'bleach', 'disinfectant', 'sponge', 'cloth', 'foil',
            'cling film', 'bag', 'bin', 'tissue', 'paper', 'household', 'laundry'
        ]
    },
    '1215135760648': {
        'name': 'Toiletries & Beauty',
        'slug': 'toiletries-beauty',
        'priority': 2,
        'keywords': [
            'toothpaste', 'shampoo', 'soap', 'deodorant', 'moisturiser',
            'makeup', 'skincare', 'hair', 'dental', 'beauty', 'cosmetic',
            'toiletries', 'personal care', 'hygiene'
        ]
    },
    '1215686353929': {
        'name': 'Health & Wellness',
        'slug': 'health-wellness',
        'priority': 2,
        'keywords': [
            'vitamin', 'supplement', 'medicine', 'health', 'wellness',
            'pharmacy', 'medical', 'first aid', 'pain relief'
        ]
    },
    
    # Specialty Categories (Priority 3)
    '1215686356579': {
        'name': 'Sweets, Treats & Snacks',
        'slug': 'sweets-treats-snacks',
        'priority': 3,
        'keywords': [
            'chocolate', 'sweet', 'candy', 'snack', 'crisp', 'nuts',
            'treat', 'biscuit', 'cookie', 'confectionery'
        ]
    },
    '1215135760631': {
        'name': 'Baby, Toddler & Kids',
        'slug': 'baby-toddler-kids',
        'priority': 3,
        'keywords': [
            'baby', 'toddler', 'child', 'kids', 'infant', 'nappy',
            'formula', 'baby food', 'children'
        ]
    },
    '1215662103573': {
        'name': 'Pet Food & Accessories',
        'slug': 'pet-food-accessories',
        'priority': 3,
        'keywords': [
            'pet', 'dog', 'cat', 'animal', 'pet food', 'dog food', 'cat food'
        ]
    },
    '1215686351451': {
        'name': 'World Food',
        'slug': 'world-food',
        'priority': 3,
        'keywords': [
            'world', 'international', 'ethnic', 'asian', 'indian',
            'chinese', 'mexican', 'italian', 'foreign'
        ]
    },
    '1215686355606': {
        'name': 'Dietary & Lifestyle',
        'slug': 'dietary-lifestyle',
        'priority': 3,
        'keywords': [
            'organic', 'gluten free', 'vegan', 'vegetarian', 'healthy',
            'diet', 'low fat', 'sugar free', 'free from'
        ]
    }
}

# Selenium WebDriver Configuration
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

# General Scraper Settings
SCRAPER_SETTINGS = {
    'max_pages_per_category': 5,
    'max_retries': 3,
    'retry_delay': 2.0,
    'request_delay': 1.0,
    'category_delay': 2.0,
    'scroll_pause_time': 2.0,
    'popup_check_delay': 2.0,
    'max_popup_attempts': 3,
}

# Product Extraction Settings
PRODUCT_EXTRACTION_CONFIG = {
    'selectors': {
        'product_containers': [
            'div.co-product',
            'div[class*="co-product"]',
            'div[class*="product-tile"]',
            'div[class*="product-item"]',
            'article[class*="product"]',
            '[data-testid*="product"]'
        ],
        'product_title': [
            'a.co-product__anchor',
            'a[href*="/product/"]',
            '.product-title a',
            'h3 a'
        ],
        'product_price': [
            'strong.co-product__price',
            '.price strong',
            '.product-price strong',
            '[data-testid="price"]'
        ],
        'was_price': [
            'span.co-product__was-price',
            '.was-price',
            '.price-was'
        ],
        'unit': [
            'span.co-product__volume',
            '.product-unit',
            '.unit-price'
        ],
        'image': [
            'img.asda-img',
            '.product-image img',
            'img[src*="product"]'
        ]
    },
    'price_regex': r'£(\d+\.?\d*)',
    'id_regex': r'/(\d+)$',
}

# Pagination Settings
PAGINATION_CONFIG = {
    'next_button_selectors': [
        'a[aria-label="Next"]',
        'a.pagination-next',
        'a[class*="next"]',
        'button[aria-label="Next"]',
        'button.pagination-next',
        'button[class*="next"]'
    ],
    'page_number_selectors': [
        'a[class*="pagination"]',
        'a[class*="page"]',
        '.pagination a'
    ]
}

# Popup and Cookie Banner Settings
POPUP_CONFIG = {
    'selectors': [
        # Cookie banners
        "button[id*='accept']",
        "button[class*='accept']",
        "button[data-testid*='accept']",
        "#accept-cookies",
        ".cookie-accept",
        
        # Generic close buttons
        "button[aria-label*='close']",
        "button[aria-label*='Close']",
        ".modal-close",
        ".popup-close",
        "[data-testid*='close']",
        
        # ASDA specific
        ".notification-banner button",
        ".banner-close",
        ".consent-banner button"
    ],
    'text_selectors': [
        'Accept',
        'Accept All',
        'Allow All',
        'Continue',
        'OK'
    ],
    'max_attempts': 3,
    'delay_between_attempts': 1.0
}

# Error Handling Configuration
ERROR_CONFIG = {
    'max_category_errors': 5,
    'max_product_errors': 20,
    'retry_status_codes': [429, 502, 503, 504],
    'timeout_errors': [
        'TimeoutException',
        'NoSuchElementException',
        'WebDriverException'
    ]
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_handler': {
        'filename': 'logs/selenium_scraper.log',
        'max_bytes': 10485760,  # 10MB
        'backup_count': 5
    }
}

# Browser Driver Paths (Windows)
DRIVER_PATHS = {
    'chromedriver_paths': [
        r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
        r"C:\chromedriver\chromedriver.exe",
        "./chromedriver.exe",
        "chromedriver.exe"
    ],
    'chrome_binary_paths': [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
}

# Default Crawl Session Settings
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

# Category Validation Settings
CATEGORY_VALIDATION = {
    'required_url_patterns': [
        'groceries.asda.com',
        '/cat/'
    ],
    'invalid_title_keywords': [
        '404',
        'error',
        'not found',
        'page not found'
    ],
    'promotional_keywords': [
        'rollback',
        'summer',
        'events-inspiration',
        'deals',
        'offers',
        'sale'
    ]
}

# Updated scraper_config.py with enhanced delay settings

# Delay Configuration
DELAY_CONFIG = {
    # Base delays
    'between_requests': 3.0,           # Between any two requests
    'between_categories': 60.0,        # 1 minute between main categories
    'between_subcategories': 15.0,     # 15 seconds between subcategories
    'between_pages': 5.0,              # Between pagination pages
    'after_product_extraction': 2.0,   # After extracting products from a page
    
    # Random delay ranges (adds randomness to avoid pattern detection)
    'random_delay_min': 1.0,           # Minimum random delay to add
    'random_delay_max': 5.0,           # Maximum random delay to add
    
    # Longer delays after certain actions
    'after_popup_handling': 3.0,       # After handling popups
    'after_navigation_error': 10.0,    # After navigation errors
    'after_rate_limit_detected': 300.0, # 5 minutes if rate limit detected
    
    # Progressive delays (increase delay if errors occur)
    'progressive_delay_factor': 1.5,   # Multiply delay by this on errors
    'max_progressive_delay': 120.0,    # Maximum progressive delay (2 minutes)
}

# Add this to your existing SCRAPER_SETTINGS
SCRAPER_SETTINGS = {
    'max_pages_per_category': 5,
    'max_retries': 3,
    'retry_delay': 2.0,
    'request_delay': 1.0,
    'category_delay': 60.0,  # Updated to 1 minute
    'scroll_pause_time': 2.0,
    'popup_check_delay': 2.0,
    'max_popup_attempts': 3,
    # Add rate limit detection
    'rate_limit_indicators': [
        'too many requests',
        'rate limit',
        'access denied',
        '429',
        'please slow down'
    ]
}