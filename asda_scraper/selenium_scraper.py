"""
Refactored Selenium-based ASDA Scraper

This module provides a production-ready Selenium WebDriver scraper for ASDA
with improved architecture, error handling, logging, and maintainability.

File: asda_scraper/selenium_scraper.py
"""

import logging
import time
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from django.utils import timezone

from .models import AsdaCategory, AsdaProduct, CrawlSession

logger = logging.getLogger(__name__)


"""
Manual logging setup for ASDA scraper
Add this at the top of selenium_scraper.py and asda_link_crawler.py
"""

import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).resolve().parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Configure logging manually for the asda_scraper module
def setup_asda_logging():
    """Setup logging for ASDA scraper with console and file handlers."""
    
    # Create formatter
    formatter = logging.Formatter(
        '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    # Force UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'asda_scraper.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'  # Ensure file handler also uses UTF-8
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Get the asda_scraper logger and configure it
    asda_logger = logging.getLogger('asda_scraper')
    asda_logger.setLevel(logging.DEBUG)
    asda_logger.handlers.clear()  # Remove any existing handlers
    asda_logger.addHandler(console_handler)
    asda_logger.addHandler(file_handler)
    asda_logger.propagate = False
    
    # Also configure submodule loggers
    for submodule in ['selenium_scraper', 'asda_link_crawler', 'management.commands.run_asda_crawl']:
        sublogger = logging.getLogger(f'asda_scraper.{submodule}')
        sublogger.setLevel(logging.DEBUG)
        sublogger.handlers.clear()
        sublogger.addHandler(console_handler)
        sublogger.addHandler(file_handler)
        sublogger.propagate = False
    
    return asda_logger




# Setup logging when module is imported
logger = setup_asda_logging()
logger.info("ASDA scraper logging configured successfully")

# Configuration constants (moved inline for now)
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

SCRAPER_SETTINGS = {
    'max_pages_per_category': 5,
    'max_retries': 3,
    'retry_delay': 2.0,
    'request_delay': 1.0,
    'category_delay': 2.0,
}

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


# Custom exception classes
class ScraperException(Exception):
    """Base exception class for scraper-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        logger.error(f"ScraperException: {message}")


class DriverSetupException(ScraperException):
    """Exception raised when WebDriver setup fails."""
    
    def __init__(self, message: str, driver_type: str = "Chrome", **kwargs):
        super().__init__(
            message=f"WebDriver setup failed for {driver_type}: {message}",
            error_code="DRIVER_SETUP_FAILED",
            context={"driver_type": driver_type, **kwargs.get('context', {})}
        )


@dataclass
class ScrapingResult:
    """Data class to encapsulate scraping results."""
    products_found: int = 0
    products_saved: int = 0
    categories_processed: int = 0
    errors: List[str] = None
    duration: Optional[float] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class ProductData:
    """Data class for product information."""
    name: str
    price: float
    was_price: Optional[float] = None
    unit: str = 'each'
    description: str = ''
    image_url: str = ''
    product_url: str = ''
    asda_id: str = ''
    in_stock: bool = True
    special_offer: str = ''
    rating: Optional[float] = None
    review_count: str = ''
    price_per_unit: str = ''


class WebDriverManager:
    """Manages WebDriver setup and configuration."""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        
    def setup_driver(self) -> webdriver.Chrome:
        """Set up Chrome WebDriver with improved Windows compatibility."""
        try:
            logger.info("Setting up Chrome WebDriver...")
            
            chrome_options = self._get_chrome_options()
            
            # Try multiple approaches to setup the driver
            setup_methods = [
                self._setup_with_chrome_driver_manager,
                self._setup_with_system_chrome,
                self._setup_with_manual_paths
            ]
            
            for setup_method in setup_methods:
                try:
                    self.driver = setup_method(chrome_options)
                    if self.driver:
                        self._configure_driver()
                        logger.info("✅ WebDriver setup successful")
                        return self.driver
                except Exception as e:
                    logger.warning(f"Setup method failed: {e}")
                    continue
            
            raise DriverSetupException("All WebDriver setup methods failed")
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {e}")
            raise DriverSetupException(f"WebDriver setup failed: {e}")
    
    def _get_chrome_options(self) -> Options:
        """Get Chrome options configuration."""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Essential options for web scraping
        options_list = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-gpu",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--window-size=1920,1080",
            f"--user-agent={SELENIUM_CONFIG['user_agent']}"
        ]
        
        for option in options_list:
            chrome_options.add_argument(option)
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        return chrome_options
    
    def _setup_with_chrome_driver_manager(self, chrome_options: Options) -> webdriver.Chrome:
        """Setup driver using ChromeDriverManager auto-download."""
        logger.info("Attempting ChromeDriverManager auto-download...")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    
    def _setup_with_system_chrome(self, chrome_options: Options) -> webdriver.Chrome:
        """Setup driver using system Chrome installation."""
        logger.info("Attempting system Chrome setup...")
        return webdriver.Chrome(options=chrome_options)
    
    def _setup_with_manual_paths(self, chrome_options: Options) -> webdriver.Chrome:
        """Setup driver using manual chromedriver paths."""
        import os
        
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
            r"C:\chromedriver\chromedriver.exe",
            "./chromedriver.exe",
            "chromedriver.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Trying manual path: {path}")
                service = Service(path)
                return webdriver.Chrome(service=service, options=chrome_options)
        
        raise Exception("No valid chromedriver path found")
    
    def _configure_driver(self):
        """Configure driver after setup."""
        # Set up WebDriverWait
        self.wait = WebDriverWait(self.driver, 10)
        
        # Remove navigator.webdriver flag
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        # Test the driver
        self.driver.get("about:blank")
        logger.info("WebDriver test successful")
    
    def cleanup(self):
        """Clean up WebDriver resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver cleanup complete")
            except Exception as e:
                logger.error(f"Error during WebDriver cleanup: {e}")


class PopupHandler:
    """Handles cookie banners and other popups on ASDA website."""
    
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
    
    def handle_popups(self) -> int:
        """Handle cookie banners and other popups with enhanced detection."""
        try:
            logger.info("🍪 Checking for popups and cookie banners")
            time.sleep(2)  # Wait for popups to appear
            
            popup_selectors = self._get_popup_selectors()
            popups_handled = 0
            
            for selector in popup_selectors:
                try:
                    elements = self._find_elements_by_selector(selector)
                    
                    for element in elements:
                        if self._is_element_interactable(element):
                            if self._click_element(element):
                                logger.info(f"✅ Clicked popup with selector: {selector}")
                                popups_handled += 1
                                time.sleep(1)
                                break
                    
                    if popups_handled >= 3:  # Don't handle too many popups
                        break
                        
                except Exception as e:
                    logger.debug(f"Popup selector {selector} failed: {e}")
                    continue
            
            if popups_handled > 0:
                logger.info(f"🎯 Successfully handled {popups_handled} popups")
            else:
                logger.info("ℹ️ No popups found to handle")
            
            return popups_handled
                
        except Exception as e:
            logger.warning(f"⚠️ Error handling popups: {e}")
            return 0
    
    def _get_popup_selectors(self) -> List[str]:
        """Get list of popup selectors."""
        return [
            "button[id*='accept']",
            "button[class*='accept']", 
            "button[data-testid*='accept']",
            "#accept-cookies",
            ".cookie-accept",
            "button[aria-label*='close']",
            "button[aria-label*='Close']",
            ".modal-close",
            ".popup-close",
            "[data-testid*='close']",
            ".notification-banner button",
            ".banner-close",
            ".consent-banner button"
        ]
    
    def _find_elements_by_selector(self, selector: str) -> List:
        """Find elements by CSS selector or XPath."""
        if ':contains(' in selector:
            text = selector.split("'")[1]
            xpath = f"//button[contains(text(), '{text}')]"
            return self.driver.find_elements(By.XPATH, xpath)
        else:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
    
    def _is_element_interactable(self, element) -> bool:
        """Check if element is displayable and enabled."""
        try:
            return element.is_displayed() and element.is_enabled()
        except:
            return False
    
    def _click_element(self, element) -> bool:
        """Attempt to click element with fallback methods."""
        try:
            element.click()
            return True
        except:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except:
                return False


class CategoryManager:
    """Manages ASDA category discovery and validation."""
    
    def __init__(self, driver: webdriver.Chrome, session: CrawlSession):
        self.driver = driver
        self.session = session
        self._category_cache = {}
    
    def discover_categories(self) -> bool:
        """Create categories using ASDA's actual category structure with real codes."""
        try:
            logger.info("🏪 Setting up ASDA categories using real category structure")
            
            max_categories = self.session.crawl_settings.get('max_categories', 10)
            include_priority = self.session.crawl_settings.get('category_priority', 2)
            
            categories_created = 0
            
            for url_code, cat_info in ASDA_CATEGORY_MAPPINGS.items():
                if cat_info['priority'] > include_priority:
                    continue
                    
                if categories_created >= max_categories:
                    break
                
                if self._create_or_update_category(url_code, cat_info):
                    categories_created += 1
            
            self._deactivate_promotional_categories()
            
            active_categories = AsdaCategory.objects.filter(is_active=True).count()
            logger.info(f"🏁 Category setup complete. Active categories: {active_categories}")
            
            return active_categories > 0
            
        except Exception as e:
            logger.error(f"❌ Critical error in category discovery: {e}")
            return False
    
    def _create_or_update_category(self, url_code: str, cat_info: Dict) -> bool:
        """Create or update a single category."""
        try:
            test_url = f"https://groceries.asda.com/cat/{cat_info['slug']}/{url_code}"
            logger.info(f"🧪 Testing category: {cat_info['name']} → {test_url}")
            
            self.driver.get(test_url)
            time.sleep(2)
            
            if self._is_valid_category_page():
                category, created = AsdaCategory.objects.get_or_create(
                    url_code=url_code,
                    defaults={
                        'name': cat_info['name'],
                        'is_active': True
                    }
                )
                
                if category.name != cat_info['name']:
                    category.name = cat_info['name']
                    category.save()
                
                action = "Created" if created else "Updated"
                logger.info(f"✅ {action} category: {category.name}")
                
                return True
            else:
                logger.warning(f"❌ Invalid category URL: {cat_info['name']}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error processing category {cat_info['name']}: {e}")
            return False
    
    def _is_valid_category_page(self) -> bool:
        """Check if current page is a valid category page."""
        page_title = self.driver.title.lower()
        current_url = self.driver.current_url
        
        return ('404' not in page_title and 
                'error' not in page_title and 
                'not found' not in page_title and
                'groceries.asda.com' in current_url)
    
    def _deactivate_promotional_categories(self):
        """Deactivate old/promotional categories."""
        promotional_codes = ['rollback', 'summer', 'events-inspiration']
        for promo in promotional_codes:
            AsdaCategory.objects.filter(
                url_code__icontains=promo
            ).update(is_active=False)
            logger.info(f"🚫 Deactivated promotional category: {promo}")


class ProductExtractor:
    """Extracts product data from ASDA category pages."""
    
    def __init__(self, driver: webdriver.Chrome, session: CrawlSession):
        self.driver = driver
        self.session = session
        self.base_url = "https://groceries.asda.com"
    
    def extract_products_from_category(self, category: AsdaCategory) -> int:
        """Extract products from a specific category."""
        try:
            category_url = self._build_category_url(category)
            if not category_url:
                return 0
            
            logger.info(f"🛒 Crawling category: {category.name}")
            logger.info(f"🔗 URL: {category_url}")
            
            self.driver.get(category_url)
            time.sleep(3)
            
            popup_handler = PopupHandler(self.driver)
            popup_handler.handle_popups()
            
            return self._extract_products_from_current_page(category)
            
        except Exception as e:
            logger.error(f"❌ Error crawling category {category.name}: {e}")
            return 0
    
    def _build_category_url(self, category: AsdaCategory) -> Optional[str]:
        """Build category URL from category object."""
        for url_code, cat_info in ASDA_CATEGORY_MAPPINGS.items():
            if url_code == category.url_code:
                return f"https://groceries.asda.com/cat/{cat_info['slug']}/{category.url_code}"
        
        logger.warning(f"⚠️ No URL slug found for category {category.name} ({category.url_code})")
        return None
    
    def _extract_products_from_current_page(self, category: AsdaCategory) -> int:
        """Extract products from the current page with pagination support."""
        try:
            products_found = 0
            max_products = self.session.crawl_settings.get('max_products_per_category', 100)
            
            logger.info(f"🔍 Extracting products from {category.name} page")
            
            if not self._wait_for_products_to_load():
                logger.warning(f"⏰ Timeout waiting for products to load on {category.name}")
                return 0
            
            page_num = 1
            max_pages = SCRAPER_SETTINGS.get('max_pages_per_category', 5)
            
            while page_num <= max_pages and products_found < max_products:
                logger.info(f"📄 Processing page {page_num} of {category.name}")
                
                page_products = self._extract_products_from_page(category)
                products_found += page_products
                
                logger.info(f"📊 Page {page_num}: {page_products} products extracted")
                
                if page_products > 0 and products_found < max_products:
                    if not self._navigate_to_next_page():
                        logger.info(f"🔚 No more pages available for {category.name}")
                        break
                    page_num += 1
                    time.sleep(2)
                else:
                    break
            
            logger.info(f"🎯 Total products extracted from {category.name}: {products_found}")
            return products_found
            
        except Exception as e:
            logger.error(f"❌ Error extracting products from {category.name}: {e}")
            return 0

    def _extract_products_from_current_page_by_url(self, url=None):
        """
        Extract products from the current page without requiring a category object.
        This method is used by the link crawler when processing discovered links.
        
        Args:
            url: Optional URL (for logging purposes, doesn't navigate)
            
        Returns:
            int: Number of products found and saved
        """
        logger.info("="*80)
        logger.info("🛒 PRODUCT EXTRACTION STARTED (BY URL)")
        if url:
            logger.info(f"📍 Called for URL: {url}")
        logger.info(f"📍 Current page URL: {self.driver.current_url}")
        logger.info("="*80)
        
        products_found = 0
        products_saved = 0
        products_skipped = 0
        products_errors = 0
        
        try:
            # Wait for products to load
            logger.info("⏳ Waiting for product elements to load...")
            
            # Try multiple selectors for products
            product_selectors = [
                "div.co-product",
                "div[class*='co-product']",
                "article[class*='product-tile']",
                "div[class*='product-item']",
                "div[class*='productListing']",
                "li[class*='product']",
                "[data-testid*='product']"
            ]
            
            product_elements = []
            for selector in product_selectors:
                try:
                    # Use find_elements to avoid exceptions
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"✅ Found {len(elements)} products using selector: {selector}")
                        product_elements = elements
                        break
                    else:
                        logger.debug(f"  No products with selector: {selector}")
                except Exception as e:
                    logger.debug(f"  Error with selector {selector}: {str(e)}")
                    continue
            
            if not product_elements:
                logger.warning("⚠️ No product elements found on page")
                # Log page source snippet to help debug
                try:
                    page_source = self.driver.page_source[:1000]
                    logger.debug(f"Page source snippet: {page_source}")
                except:
                    pass
                return 0
            
            logger.info(f"📦 Found {len(product_elements)} product elements to process")
            
            # Try to determine category from URL or page content
            category = self._infer_category_from_page()
            
            # Process each product
            for idx, product_element in enumerate(product_elements):
                try:
                    logger.info(f"\n{'─'*60}")
                    logger.info(f"🔍 Processing product {idx + 1}/{len(product_elements)}")
                    
                    # Extract product details using BeautifulSoup for better parsing
                    product_html = product_element.get_attribute('outerHTML')
                    soup = BeautifulSoup(product_html, 'html.parser')
                    
                    product_data = {}
                    
                    # Product Name - try multiple selectors
                    name = None
                    name_selectors = [
                        "h3 a", "h3", "a.co-product__anchor", 
                        "[class*='title']", "[class*='name']",
                        "a[href*='/product/']"
                    ]
                    for selector in name_selectors:
                        name_elem = soup.select_one(selector)
                        if name_elem and name_elem.get_text(strip=True):
                            name = name_elem.get_text(strip=True)
                            break
                    
                    if not name:
                        logger.warning(f"⚠️ Could not find name for product {idx + 1}")
                        products_skipped += 1
                        continue
                    
                    product_data['name'] = name
                    logger.info(f"📝 Name: {name}")
                    
                    # Price - try multiple selectors
                    price = None
                    price_selectors = [
                        "strong.co-product__price",
                        ".price strong",
                        "[class*='price'] strong",
                        "[class*='price']",
                        "[data-auto-id*='price']"
                    ]
                    
                    for selector in price_selectors:
                        price_elem = soup.select_one(selector)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price_match = re.search(r'£?(\d+\.?\d*)', price_text)
                            if price_match:
                                price = float(price_match.group(1))
                                logger.info(f"💰 Price: £{price}")
                                break
                    
                    if price is None:
                        logger.warning(f"⚠️ No price found for: {name}")
                        products_skipped += 1
                        continue
                    
                    product_data['price'] = price
                    
                    # Product URL
                    url_elem = soup.select_one("a[href*='/product/']")
                    if url_elem:
                        product_url = url_elem.get('href', '')
                        if product_url:
                            product_data['url'] = urljoin(self.base_url, product_url)
                            logger.info(f"🔗 URL: {product_data['url'][:80]}...")
                    
                    # ASDA ID from URL
                    if 'url' in product_data:
                        asda_id_match = re.search(r'/(\d+)$', product_data['url'])
                        if asda_id_match:
                            product_data['asda_id'] = asda_id_match.group(1)
                        else:
                            # Generate a unique ID
                            product_data['asda_id'] = f"gen_{hash(name) % 1000000}"
                    
                    # Image URL
                    img_elem = soup.select_one("img")
                    if img_elem:
                        img_url = img_elem.get('src', '')
                        if img_url:
                            product_data['image_url'] = img_url
                            logger.debug(f"[IMAGE] Image: {img_url[:80]}...")
                    
                    # Unit/Size
                    unit_selectors = [
                        "span.co-product__volume",
                        "[class*='weight']",
                        "[class*='size']",
                        "[class*='unit']"
                    ]
                    
                    for selector in unit_selectors:
                        unit_elem = soup.select_one(selector)
                        if unit_elem:
                            unit_text = unit_elem.get_text(strip=True)
                            if unit_text:
                                product_data['unit'] = unit_text
                                logger.info(f"[SIZE] Unit/Size: {unit_text}")
                                break
                    
                    # Was price (for offers)
                    was_price_elem = soup.select_one("span.co-product__was-price, [class*='was-price']")
                    if was_price_elem:
                        was_price_match = re.search(r'£?(\d+\.?\d*)', was_price_elem.get_text())
                        if was_price_match:
                            product_data['was_price'] = float(was_price_match.group(1))
                            logger.info(f"🏷️ Was price: £{product_data['was_price']}")
                    
                    # Save the product
                    if self._save_product_from_data(product_data, category):
                        products_saved += 1
                        logger.info(f"[OK] PRODUCT {idx + 1} SAVED SUCCESSFULLY")
                    else:
                        products_skipped += 1
                        logger.warning(f"⚠️ Failed to save product {idx + 1}")
                    
                    products_found += 1
                    
                except Exception as e:
                    products_errors += 1
                    logger.error(f"❌ Error processing product {idx + 1}: {str(e)}")
                    import traceback
                    logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Summary
            logger.info(f"\n{'='*80}")
            logger.info(f"📊 PRODUCT EXTRACTION SUMMARY:")
            logger.info(f"  Total product elements: {len(product_elements)}")
            logger.info(f"  Products found: {products_found}")
            logger.info(f"  Products saved: {products_saved}")
            logger.info(f"  Products skipped: {products_skipped}")
            logger.info(f"  Extraction errors: {products_errors}")
            if len(product_elements) > 0:
                logger.info(f"  Success rate: {(products_saved/len(product_elements)*100):.1f}%")
            logger.info(f"{'='*80}\n")
            
            return products_saved
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in product extraction: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return 0

    def _infer_category_from_page(self):
        """
        Try to infer the category from the current page URL or content.
        
        Returns:
            AsdaCategory or None
        """
        try:
            current_url = self.driver.current_url
            
            # Try to extract category code from URL
            category_code_match = re.search(r'(\d{13})', current_url)
            if category_code_match:
                category_code = category_code_match.group(1)
                
                # Try to find existing category
                try:
                    category = AsdaCategory.objects.get(url_code=category_code)
                    logger.info(f"📁 Found category from URL: {category.name}")
                    return category
                except AsdaCategory.DoesNotExist:
                    # Create a basic category
                    category_name = "Unknown Category"
                    
                    # Try to get category name from page
                    try:
                        breadcrumb = self.driver.find_element(By.CSS_SELECTOR, "[class*='breadcrumb'] span:last-child")
                        category_name = breadcrumb.text.strip()
                    except:
                        try:
                            title = self.driver.title
                            if " | " in title:
                                category_name = title.split(" | ")[0].strip()
                        except:
                            pass
                    
                    category = AsdaCategory.objects.create(
                        url_code=category_code,
                        name=category_name,
                        is_active=True
                    )
                    logger.info(f"📁 Created new category: {category_name}")
                    return category
            
            # If no category code in URL, use a default category
            default_category, created = AsdaCategory.objects.get_or_create(
                url_code='0000000000000',
                defaults={'name': 'Uncategorized', 'is_active': True}
            )
            return default_category
            
        except Exception as e:
            logger.error(f"Error inferring category: {str(e)}")
            return None

    def _save_product_from_data(self, product_data, category):
        """
        Save product from extracted data dictionary.
        
        Args:
            product_data: Dictionary with product information
            category: AsdaCategory object (can be None)
            
        Returns:
            bool: True if saved successfully
        """
        try:
            if not product_data.get('name') or product_data.get('price') is None:
                logger.warning("Missing required product data (name or price)")
                return False
            
            # Create or update the product
            asda_id = product_data.get('asda_id', f"gen_{hash(product_data['name']) % 1000000}")
            
            product, created = AsdaProduct.objects.get_or_create(
                asda_id=asda_id,
                defaults={
                    'name': product_data['name'],
                    'price': product_data['price'],
                    'was_price': product_data.get('was_price'),
                    'unit': product_data.get('unit', 'each'),
                    'description': product_data.get('description', product_data['name']),
                    'image_url': product_data.get('image_url', ''),
                    'product_url': product_data.get('url', ''),
                    'category': category,
                    'in_stock': True,
                    'special_offer': '',
                }
            )
            
            if not created:
                # Update existing product
                product.name = product_data['name']
                product.price = product_data['price']
                if 'was_price' in product_data:
                    product.was_price = product_data.get('was_price')
                if 'unit' in product_data:
                    product.unit = product_data['unit']
                if 'image_url' in product_data:
                    product.image_url = product_data['image_url']
                if 'url' in product_data:
                    product.product_url = product_data['url']
                if category:
                    product.category = category
                product.save()
                
                logger.info(f"[UPDATE] Updated existing product: {product.name}")
            else:
                logger.info(f"[NEW] Created new product: {product.name}")
            
            # Update session statistics
            if created:
                self.session.products_found += 1
            else:
                self.session.products_updated += 1
            self.session.save()
            
            # Update category product count if applicable
            if category:
                category.product_count = category.products.count()
                category.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving product: {str(e)}")
            return False
    
    def _wait_for_products_to_load(self, timeout: int = 10) -> bool:
        """Wait for products to load on the page."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    'div.co-product, div[class*="co-product"], div[class*="product-tile"]'
                ))
            )
            return True
        except TimeoutException:
            return False
    
    def _extract_products_from_page(self, category: AsdaCategory) -> int:
        """Extract products from the current page."""
        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            product_containers = self._find_product_containers(soup)
            
            if not product_containers:
                logger.warning(f"❌ No product containers found on {category.name}")
                return 0
            
            logger.info(f"🛍️ Found {len(product_containers)} product containers")
            
            products_saved = 0
            for container in product_containers:
                try:
                    product_data = self._extract_product_data(container, category)
                    
                    if product_data:
                        if self._save_product_data(product_data, category):
                            products_saved += 1
                            logger.debug(f"✅ Saved product: {product_data.name[:50]}...")
                
                except Exception as e:
                    logger.error(f"❌ Error extracting product data: {e}")
                    continue
            
            return products_saved
            
        except Exception as e:
            logger.error(f"❌ Error extracting products from page: {e}")
            return 0
    
    def _find_product_containers(self, soup: BeautifulSoup) -> List:
        """Find product containers using multiple selectors."""
        selectors = [
            'div.co-product',
            'div[class*="co-product"]',
            'div[class*="product-tile"]',
            'div[class*="product-item"]',
            'article[class*="product"]',
            '[data-testid*="product"]'
        ]
        
        for selector in selectors:
            containers = soup.select(selector)
            if containers:
                logger.info(f"Found {len(containers)} products using selector: {selector}")
                return containers
        
        logger.warning("No product containers found with any selector")
        return []
    
    def _extract_product_data(self, container, category: AsdaCategory) -> Optional[ProductData]:
        """Extract product data from container."""
        try:
            title_link = container.select_one('a.co-product__anchor, a[href*="/product/"]')
            if not title_link:
                return None
            
            name = title_link.get_text(strip=True)
            product_url = urljoin(self.base_url, title_link.get('href', ''))
            
            price_element = container.select_one('strong.co-product__price, .price strong')
            if not price_element:
                return None
            
            price_text = price_element.get_text(strip=True)
            price_match = re.search(r'£(\d+\.?\d*)', price_text)
            if not price_match:
                return None
            
            price = float(price_match.group(1))
            
            asda_id_match = re.search(r'/(\d+)$', product_url)
            asda_id = (asda_id_match.group(1) if asda_id_match 
                      else f"{category.url_code}_{hash(name) % 100000}")
            
            was_price = self._extract_was_price(container)
            unit = self._extract_unit(container)
            image_url = self._extract_image_url(container)
            
            return ProductData(
                name=name,
                price=price,
                was_price=was_price,
                unit=unit,
                description=name,
                image_url=image_url,
                product_url=product_url,
                asda_id=asda_id,
                in_stock=True,
                special_offer='',
                rating=None,
                review_count='',
                price_per_unit='',
            )
            
        except Exception as e:
            logger.error(f"Error extracting product data: {e}")
            return None
    
    def _extract_was_price(self, container) -> Optional[float]:
        """Extract was price if product is on sale."""
        was_price_element = container.select_one('span.co-product__was-price')
        if was_price_element:
            was_price_match = re.search(r'£(\d+\.?\d*)', was_price_element.get_text())
            if was_price_match:
                return float(was_price_match.group(1))
        return None
    
    def _extract_unit(self, container) -> str:
        """Extract unit information."""
        unit_element = container.select_one('span.co-product__volume')
        return unit_element.get_text(strip=True) if unit_element else 'each'
    
    def _extract_image_url(self, container) -> str:
        """Extract product image URL."""
        img_element = container.select_one('img.asda-img')
        return img_element.get('src', '') if img_element else ''
    
    def _save_product_data(self, product_data: ProductData, category: AsdaCategory) -> bool:
        """Save product data to database."""
        try:
            product, created = AsdaProduct.objects.get_or_create(
                asda_id=product_data.asda_id,
                defaults={
                    'name': product_data.name,
                    'price': product_data.price,
                    'was_price': product_data.was_price,
                    'unit': product_data.unit,
                    'description': product_data.description,
                    'image_url': product_data.image_url,
                    'product_url': product_data.product_url,
                    'asda_id': product_data.asda_id,
                    'category': category,
                    'in_stock': product_data.in_stock,
                    'special_offer': product_data.special_offer,
                    'rating': product_data.rating,
                    'review_count': product_data.review_count,
                    'price_per_unit': product_data.price_per_unit,
                }
            )
            
            if created:
                self.session.products_found += 1
                logger.info(f"✅ Created: {product.name} in {category.name}")
            else:
                for field in ['name', 'price', 'was_price', 'unit', 'description', 
                             'image_url', 'product_url', 'in_stock', 'special_offer',
                             'rating', 'review_count', 'price_per_unit']:
                    value = getattr(product_data, field)
                    if value is not None:
                        setattr(product, field, value)
                product.category = category
                product.save()
                self.session.products_updated += 1
                logger.info(f"📝 Updated: {product.name} in {category.name}")
            
            self.session.save()
            
            category.product_count = category.products.count()
            category.save()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving product {product_data.name}: {e}")
            return False
    
    def _navigate_to_next_page(self) -> bool:
        """Navigate to the next page of products if pagination exists."""
        try:
            next_selectors = [
                'a[aria-label="Next"]',
                'a.pagination-next',
                'a[class*="next"]',
                'button[aria-label="Next"]',
                'button.pagination-next',
                'button[class*="next"]'
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if next_button.is_enabled() and next_button.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(1)
                        next_button.click()
                        time.sleep(3)
                        logger.debug(f"✅ Navigated to next page using selector: {selector}")
                        return True
                        
                except (NoSuchElementException, Exception):
                    continue
            
            logger.debug("🔚 No next page button found or enabled")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error navigating to next page: {e}")
            return False

    


class SeleniumAsdaScraper:
    """Production-ready Selenium-based ASDA scraper."""
    
    def __init__(self, crawl_session: CrawlSession, headless: bool = False):
        self.session = crawl_session
        self.headless = headless
        self.driver_manager = None
        self.driver = None
        self.base_url = "https://groceries.asda.com"
        
        logger.info(f"Selenium ASDA Scraper initialized for session {self.session.pk}")
        
        try:
            self.driver_manager = WebDriverManager(headless=headless)
            self.driver = self.driver_manager.setup_driver()
        except DriverSetupException as e:
            logger.error(f"Failed to initialize scraper: {e}")
            raise
    
    def start_crawl(self) -> ScrapingResult:
        """Start the crawling process using Selenium."""
        start_time = time.time()
        result = ScrapingResult()
        
        try:
            logger.info(f"Starting Selenium crawl session {self.session.pk}")
            
            self.session.status = 'RUNNING'
            self.session.save()
            
            if self._should_discover_categories():
                category_manager = CategoryManager(self.driver, self.session)
                if not category_manager.discover_categories():
                    raise ScraperException("Category discovery failed")
            
            result = self._crawl_all_products()
            
            self.session.mark_completed()
            result.duration = time.time() - start_time
            
            logger.info(f"🎉 Crawl completed successfully in {result.duration:.2f} seconds")
            return result
            
        except Exception as e:
            logger.error(f"Error in Selenium crawl session {self.session.pk}: {e}")
            self.session.mark_failed(str(e))
            result.errors.append(str(e))
            result.duration = time.time() - start_time
            return result
        finally:
            self._cleanup()
    
    def _should_discover_categories(self) -> bool:
        """Determine if category discovery is needed."""
        active_categories = AsdaCategory.objects.filter(is_active=True).count()
        return active_categories == 0
    
    def _crawl_all_products(self) -> ScrapingResult:
        """Crawl products for all active categories with intelligent delays."""
        result = ScrapingResult()
        
        try:
            active_categories = AsdaCategory.objects.filter(is_active=True)
            total_categories = active_categories.count()
            
            logger.info(f"Crawling products for {total_categories} categories")
            
            # Initialize components
            product_extractor = ProductExtractor(self.driver, self.session)
            from .asda_link_crawler import AsdaLinkCrawler
            link_crawler = AsdaLinkCrawler(self)
            link_crawler.scraper = product_extractor
            
            # Initialize delay manager
            delay_manager = DelayManager()
            
            logger.info("="*80)
            logger.info("LINK CRAWLER INITIALIZED - Will discover and follow subcategory links")
            logger.info("DELAY STRATEGY: 60 seconds between main categories")
            logger.info("="*80)
            
            for i, category in enumerate(active_categories, 1):
                try:
                    logger.info(f"\n{'='*80}")
                    logger.info(f"PROCESSING MAIN CATEGORY {i}/{total_categories}: {category.name}")
                    logger.info(f"{'='*80}")
                    
                    self.session.categories_crawled = i
                    self.session.save()
                    
                    # Build and navigate to category URL
                    category_url = product_extractor._build_category_url(category)
                    if not category_url:
                        logger.warning(f"Skipping {category.name} - no URL mapping")
                        continue
                    
                    logger.info(f"Navigating to category: {category_url}")
                    self.driver.get(category_url)
                    
                    # Check for rate limiting
                    if delay_manager.check_rate_limit(self.driver.page_source):
                        logger.warning("Rate limit detected - applying extended delay")
                    
                    # Wait after navigation
                    delay_manager.wait('between_requests')
                    
                    # Handle popups
                    popup_handler = PopupHandler(self.driver)
                    popup_handler.handle_popups()
                    delay_manager.wait('after_popup_handling')
                    
                    # Extract products from main category page
                    logger.info(f"Extracting products from main category page...")
                    main_page_products = product_extractor._extract_products_from_page(category)
                    result.products_found += main_page_products
                    logger.info(f"Found {main_page_products} products on main category page")
                    
                    # Delay after extraction
                    delay_manager.wait('after_product_extraction')
                    
                    # Discover links on this category page
                    logger.info(f"Discovering subcategory links...")
                    discovered_links = link_crawler.discover_page_links(category_url)
                    
                    # Process subcategory links with delays
                    subcategory_links = discovered_links.get('subcategories', [])
                    if subcategory_links:
                        logger.info(f"Found {len(subcategory_links)} subcategory links to explore")
                        
                        # Add delay manager to link crawler
                        link_crawler.delay_manager = delay_manager
                        
                        # Crawl subcategories
                        link_crawler.crawl_discovered_links(discovered_links, max_depth=2, current_depth=0)
                    else:
                        logger.warning(f"No subcategory links found on {category.name} page")
                    
                    # Update category timestamp
                    category.last_crawled = timezone.now()
                    category.save()
                    
                    # Reset delay multiplier after successful category
                    delay_manager.reset_delay()
                    
                    # Apply delay between main categories (except for last one)
                    if i < total_categories:
                        logger.info(f"[DELAY] Applying 60-second delay before next main category...")
                        delay_manager.wait('between_categories')
                    
                except Exception as e:
                    error_msg = f"Error crawling category {category.name}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    
                    # Increase delay after error
                    delay_manager.increase_delay()
                    delay_manager.wait('after_navigation_error')
                    continue
            
            # Update final counts
            result.categories_processed = total_categories
            result.products_saved = self.session.products_found
            
            # Keep browser open for inspection
            logger.info("\n" + "="*80)
            logger.info("CRAWLING COMPLETE - Browser window will remain open")
            logger.info("Close the browser window manually when done inspecting")
            logger.info("="*80)
            
            # Wait for user to close browser
            input("\nPress Enter to close the browser and complete cleanup...")
            
        except Exception as e:
            logger.error(f"Error crawling products: {e}")
            result.errors.append(str(e))
        
        return result







    def _cleanup(self):
        """Clean up resources."""
        try:
            if self.driver_manager:
                self.driver_manager.cleanup()
            logger.info("Scraper cleanup complete")
        except Exception as e:
            logger.error(f"Error during scraper cleanup: {e}")


def create_selenium_scraper(crawl_session: CrawlSession, headless: bool = False) -> SeleniumAsdaScraper:
    """Factory function to create a Selenium scraper instance."""
    return SeleniumAsdaScraper(crawl_session, headless)


# Add this class to selenium_scraper.py

import random
from datetime import datetime, timedelta

class DelayManager:
    """Manages intelligent delays to avoid rate limiting."""
    
    def __init__(self):
        self.last_request_time = None
        self.error_count = 0
        self.current_delay_multiplier = 1.0
        
    def wait(self, delay_type='between_requests', force_delay=None):
        """
        Apply intelligent delay based on context.
        
        Args:
            delay_type: Type of delay from DELAY_CONFIG
            force_delay: Override with specific delay in seconds
        """
        if force_delay:
            delay = force_delay
        else:
            # Get base delay from config
            from .scraper_config import DELAY_CONFIG
            base_delay = DELAY_CONFIG.get(delay_type, 2.0)
            
            # Apply progressive delay if errors occurred
            delay = base_delay * self.current_delay_multiplier
            
            # Add random component
            random_addition = random.uniform(
                DELAY_CONFIG['random_delay_min'],
                DELAY_CONFIG['random_delay_max']
            )
            delay += random_addition
            
            # Cap at maximum
            delay = min(delay, DELAY_CONFIG['max_progressive_delay'])
        
        logger.info(f"[DELAY] Waiting {delay:.1f} seconds ({delay_type})")
        time.sleep(delay)
        self.last_request_time = datetime.now()
        
    def increase_delay(self):
        """Increase delay multiplier after errors."""
        from .scraper_config import DELAY_CONFIG
        self.error_count += 1
        self.current_delay_multiplier *= DELAY_CONFIG['progressive_delay_factor']
        logger.warning(f"[DELAY] Increased delay multiplier to {self.current_delay_multiplier:.2f} after {self.error_count} errors")
        
    def reset_delay(self):
        """Reset delay multiplier after successful operations."""
        if self.error_count > 0:
            logger.info("[DELAY] Resetting delay multiplier after successful operation")
        self.error_count = 0
        self.current_delay_multiplier = 1.0
        
    def check_rate_limit(self, page_source):
        """Check if page indicates rate limiting."""
        from .scraper_config import SCRAPER_SETTINGS
        
        page_text = page_source.lower()
        for indicator in SCRAPER_SETTINGS['rate_limit_indicators']:
            if indicator in page_text:
                logger.error(f"[RATE LIMIT] Detected rate limit indicator: '{indicator}'")
                self.wait('after_rate_limit_detected')
                return True
        return False