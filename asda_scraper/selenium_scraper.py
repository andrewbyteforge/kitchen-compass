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
        """Crawl products for all active categories."""
        result = ScrapingResult()
        
        try:
            active_categories = AsdaCategory.objects.filter(is_active=True)
            total_categories = active_categories.count()
            
            logger.info(f"Crawling products for {total_categories} categories")
            
            product_extractor = ProductExtractor(self.driver, self.session)
            
            for i, category in enumerate(active_categories, 1):
                try:
                    logger.info(f"Crawling category {i}/{total_categories}: {category.name}")
                    
                    self.session.categories_crawled = i
                    self.session.save()
                    
                    products_found = product_extractor.extract_products_from_category(category)
                    result.products_found += products_found
                    
                    category.last_crawled = timezone.now()
                    category.save()
                    
                    logger.info(f"Found {products_found} products in {category.name}")
                    
                    delay = self.session.crawl_settings.get('delay_between_requests', 2.0)
                    time.sleep(delay)
                    
                except Exception as e:
                    error_msg = f"Error crawling category {category.name}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    continue
            
            result.categories_processed = total_categories
            result.products_saved = self.session.products_found
            
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