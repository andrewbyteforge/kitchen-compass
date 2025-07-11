"""
Refactored Selenium-based ASDA Scraper

This module provides a production-ready Selenium WebDriver scraper for ASDA
with improved architecture, error handling, logging, and maintainability.

File: asda_scraper/selenium_scraper.py
"""

import logging
import time
import re
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from urllib.parse import urljoin
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from django.utils import timezone

from .models import AsdaCategory, AsdaProduct, CrawlSession

logger = logging.getLogger(__name__)


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


class DelayManager:
    """Manages intelligent delays to avoid rate limiting."""
    
    def __init__(self):
        self.last_request_time = None
        self.error_count = 0
        self.current_delay_multiplier = 1.0
        
    def wait(self, delay_type='between_requests', force_delay=None):
        """Apply intelligent delay based on context."""
        try:
            if force_delay:
                delay_seconds = force_delay
            else:
                base_delays = {
                    'between_requests': 2.0,
                    'between_categories': 60.0,
                    'after_error': 5.0,
                    'after_navigation_error': 10.0,
                    'page_load': 3.0
                }
                delay_seconds = base_delays.get(delay_type, 2.0) * self.current_delay_multiplier
            
            # Add random jitter
            jitter = random.uniform(0.8, 1.2)
            actual_delay = delay_seconds * jitter
            
            logger.debug(f"[DELAY] Applying {actual_delay:.2f}s delay for {delay_type}")
            time.sleep(actual_delay)
            
            self.last_request_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Error in delay manager: {e}")
    
    def increase_delay(self):
        """Increase delay multiplier after errors."""
        self.error_count += 1
        self.current_delay_multiplier = min(5.0, 1.0 + (self.error_count * 0.5))
        logger.info(f"[DELAY] Increased delay multiplier to {self.current_delay_multiplier:.1f}x")
    
    def reset_delay(self):
        """Reset delay multiplier after success."""
        self.error_count = 0
        self.current_delay_multiplier = 1.0


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
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        # Standard options for stability
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        options.add_argument("--disable-javascript")
        options.add_argument("--window-size=1920,1080")
        
        # Anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # User agent
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        options.add_argument(f"--user-agent={user_agent}")
        
        return options
    
    def _setup_with_chrome_driver_manager(self, options: Options) -> webdriver.Chrome:
        """Setup using ChromeDriverManager."""
        logger.info("Attempting ChromeDriverManager auto-download...")
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    
    def _setup_with_system_chrome(self, options: Options) -> webdriver.Chrome:
        """Setup using system Chrome."""
        logger.info("Attempting system Chrome setup...")
        return webdriver.Chrome(options=options)
    
    def _setup_with_manual_paths(self, options: Options) -> webdriver.Chrome:
        """Setup using manual paths."""
        logger.info("Attempting manual Chrome paths...")
        
        driver_paths = [
            r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
            r"C:\chromedriver\chromedriver.exe",
            "./chromedriver.exe",
        ]
        
        for driver_path in driver_paths:
            try:
                service = Service(driver_path)
                return webdriver.Chrome(service=service, options=options)
            except Exception:
                continue
        
        raise DriverSetupException("No valid Chrome driver path found")
    
    def _configure_driver(self):
        """Configure the driver after setup."""
        # Set timeouts
        self.driver.set_page_load_timeout(30)
        self.driver.implicitly_wait(5)
        
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
            
            popup_selectors = [
                # Cookie banners
                'button[id*="accept"]',
                'button[class*="accept"]',
                'button:contains("Accept")',
                'button:contains("Allow")',
                '#onetrust-accept-btn-handler',
                '.cookie-banner button',
                '[data-testid="accept-cookies"]',
                
                # Close buttons
                'button[aria-label="Close"]',
                'button[class*="close"]',
                '.modal-close',
                '[data-testid="close"]',
            ]
            
            popups_handled = 0
            
            for selector in popup_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            try:
                                element.click()
                                logger.info(f"✅ Clicked popup with selector: {selector}")
                                popups_handled += 1
                                time.sleep(1)
                                break
                            except Exception:
                                continue
                    
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


class CategoryManager:
    """Manages category discovery and navigation."""
    
    def __init__(self, driver: webdriver.Chrome, session: CrawlSession):
        self.driver = driver
        self.session = session
    
    def discover_categories(self) -> bool:
        """Discover categories from ASDA homepage."""
        try:
            logger.info("🔍 Starting category discovery")
            
            self.driver.get("https://groceries.asda.com/")
            time.sleep(3)
            
            # Handle popups first
            popup_handler = PopupHandler(self.driver)
            popup_handler.handle_popups()
            
            # Find navigation menu
            nav_selectors = [
                'nav[class*="navigation"]',
                '.main-nav',
                '[data-testid="navigation"]',
                'ul[class*="category"]'
            ]
            
            nav_element = None
            for selector in nav_selectors:
                try:
                    nav_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if nav_element:
                        break
                except NoSuchElementException:
                    continue
            
            if not nav_element:
                logger.warning("Could not find navigation menu")
                return False
            
            # Extract category links
            category_links = nav_element.find_elements(By.TAG_NAME, "a")
            categories_found = 0
            
            for link in category_links:
                try:
                    href = link.get_attribute("href")
                    text = link.text.strip()
                    
                    if href and "dept" in href and text:
                        category_code = self._extract_category_code(href)
                        if category_code:
                            category, created = AsdaCategory.objects.get_or_create(
                                url_code=category_code,
                                defaults={
                                    'name': text,
                                    'full_url': href,
                                    'is_active': True
                                }
                            )
                            
                            if created:
                                categories_found += 1
                                logger.info(f"📂 Found category: {text}")
                
                except Exception as e:
                    logger.debug(f"Error processing category link: {e}")
                    continue
            
            logger.info(f"✅ Category discovery complete. Found {categories_found} new categories")
            return categories_found > 0
            
        except Exception as e:
            logger.error(f"❌ Category discovery failed: {e}")
            return False
    
    def _extract_category_code(self, url: str) -> Optional[str]:
        """Extract category code from URL."""
        try:
            match = re.search(r'/dept/([^/]+)', url)
            return match.group(1) if match else None
        except Exception:
            return None


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
        delay_manager = DelayManager()
        
        try:
            # Get categories to crawl (priority 1 and 2 only for efficiency)
            categories = AsdaCategory.objects.filter(
                is_active=True
            ).order_by('priority', 'name')
            
            if not categories.exists():
                logger.warning("⚠️ No active categories found")
                return result
            
            total_categories = categories.count()
            logger.info(f"🎯 Starting product crawl for {total_categories} categories")
            
            # Process each category
            for i, category in enumerate(categories, 1):
                try:
                    logger.info(f"\n{'='*80}")
                    logger.info(f"📂 CATEGORY {i}/{total_categories}: {category.name}")
                    logger.info(f"🔗 URL: {category.full_url}")
                    logger.info(f"{'='*80}")
                    
                    # Navigate to category
                    self.driver.get(category.full_url)
                    delay_manager.wait('page_load')
                    
                    # Handle popups
                    popup_handler = PopupHandler(self.driver)
                    popup_handler.handle_popups()
                    
                    # Extract products from this category
                    products_found = self._extract_products_from_current_page_by_url(category.full_url)
                    logger.info(f"✅ Found {products_found} products on {category.name} page")
                    
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
    
    def _extract_products_from_current_page_by_url(self, url=None) -> int:
        """Extract products from current page."""
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
                            price_match = re.search(r'£?(\d+\.\d*)', price_text)
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
                        was_price_match = re.search(r'£?(\d+\.\d*)', was_price_elem.get_text())
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
        """Try to infer the category from the current page URL or content."""
        try:
            current_url = self.driver.current_url
            
            # Extract dept code from URL
            dept_match = re.search(r'/dept/([^/]+)', current_url)
            if dept_match:
                dept_code = dept_match.group(1)
                
                # Try to find existing category
                category = AsdaCategory.objects.filter(url_code=dept_code).first()
                if category:
                    logger.info(f"📂 Matched category: {category.name}")
                    return category
            
            # Fallback: create a generic category
            fallback_category, created = AsdaCategory.objects.get_or_create(
                url_code='general',
                defaults={'name': 'General Products', 'is_active': True}
            )
            
            if created:
                logger.info("📂 Created fallback 'General Products' category")
            
            return fallback_category
            
        except Exception as e:
            logger.error(f"Error inferring category: {e}")
            return None

    def _save_product_from_data(self, product_data: dict, category) -> bool:
        """Save product data to database."""
        try:
            if not category:
                logger.warning("Cannot save product: no category provided")
                return False
                
            product, created = AsdaProduct.objects.get_or_create(
                asda_id=product_data.get('asda_id', ''),
                defaults={
                    'name': product_data.get('name', ''),
                    'price': product_data.get('price', 0),
                    'was_price': product_data.get('was_price'),
                    'unit': product_data.get('unit', 'each'),
                    'description': product_data.get('name', ''),
                    'image_url': product_data.get('image_url', ''),
                    'product_url': product_data.get('url', ''),
                    'category': category,
                    'in_stock': True,
                }
            )
            
            if created:
                self.session.products_found += 1
                logger.info(f"✅ Created: {product.name} in {category.name}")
            else:
                # Update existing product
                for field in ['name', 'price', 'was_price', 'unit', 'description', 
                             'image_url', 'product_url', 'in_stock']:
                    value = product_data.get(field)
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
            logger.error(f"❌ Error saving product {product_data.get('name', 'Unknown')}: {e}")
            return False

    # ==============================================================================
    # NUTRITIONAL INFORMATION EXTRACTION METHODS
    # ==============================================================================
    
    def cleanup(self):
        """
        Clean up the scraper resources.
        Public method that calls the private _cleanup method.
        """
        try:
            self._cleanup()
            logger.info("🧹 Public cleanup completed")
        except Exception as e:
            logger.error(f"❌ Error during public cleanup: {str(e)}")

    def _extract_nutritional_info_from_product_page(self, product_url: str, max_retries: int = 3) -> dict:
        """
        Navigate to individual product page and extract nutritional information.
        
        Args:
            product_url: Full URL to the product detail page
            max_retries: Maximum number of retry attempts
            
        Returns:
            dict: Nutritional information dictionary
        """
        logger.info(f"🧪 Extracting nutritional info from: {product_url[:60]}...")
        
        # Store current URL to return to it later
        original_url = self.driver.current_url
        nutritional_data = {}
        
        for attempt in range(max_retries):
            try:
                # Navigate to product page
                logger.debug(f"📍 Navigating to product page (attempt {attempt + 1})")
                self.driver.get(product_url)
                
                # Wait for page to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Small delay to ensure dynamic content loads
                time.sleep(2)
                
                # Check if we've been redirected or blocked
                current_page_url = self.driver.current_url
                if 'error' in current_page_url.lower() or 'block' in current_page_url.lower():
                    logger.warning(f"⚠️ Possible block detected on attempt {attempt + 1}")
                    time.sleep(5)  # Wait longer before retry
                    continue
                
                # Extract nutritional information
                nutritional_data = self._parse_nutritional_info_from_page()
                
                if nutritional_data:
                    logger.info(f"✅ Successfully extracted nutritional info with {len(nutritional_data)} fields")
                    break
                else:
                    logger.warning(f"⚠️ No nutritional data found on attempt {attempt + 1}")
                    
            except TimeoutException:
                logger.warning(f"⏰ Timeout loading product page on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Error extracting nutritional info on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
        
        # Return to original page
        try:
            if original_url != self.driver.current_url:
                logger.debug(f"🔙 Returning to original page: {original_url[:60]}...")
                self.driver.get(original_url)
                time.sleep(2)
        except Exception as e:
            logger.error(f"❌ Error returning to original page: {str(e)}")
        
        return nutritional_data

    def _parse_nutritional_info_from_page(self) -> dict:
        """
        Enhanced parsing of nutritional information from the current product page.
        
        Returns:
            dict: Dictionary containing all nutritional values
        """
        logger.debug("🔍 Parsing nutritional information from page...")
        
        try:
            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            nutritional_data = {}
            
            # Strategy 1: Look for "Nutritional Values" heading and nearby table
            nutrition_section = self._find_nutrition_section(soup)
            
            if nutrition_section:
                logger.debug("📊 Found nutritional values section")
                
                # Extract from table structure (primary method)
                nutritional_data = self._extract_from_nutrition_table(nutrition_section)
                
                # If table extraction didn't get everything, try additional methods
                if len(nutritional_data) < 6:  # We expect at least 6-9 nutritional values
                    logger.debug("🔄 Table extraction incomplete, trying additional methods...")
                    additional_data = self._extract_from_nutrition_divs(nutrition_section)
                    nutritional_data.update(additional_data)
            
            # Strategy 2: If main section not found, try alternative page-wide extraction
            if not nutritional_data:
                logger.debug("🔄 Main nutrition section not found, trying page-wide extraction...")
                nutritional_data = self._extract_nutrition_from_entire_page(soup)
            
            # Strategy 3: Try regex patterns on raw text as final fallback
            if len(nutritional_data) < 4:  # If we still don't have enough data
                logger.debug("🔄 Trying regex patterns on page text...")
                regex_data = self._extract_nutrition_with_regex(soup)
                nutritional_data.update(regex_data)
            
            # Clean and validate the data
            nutritional_data = self._clean_and_validate_nutritional_data(nutritional_data)
            
            if nutritional_data:
                logger.info(f"📊 Extracted {len(nutritional_data)} nutritional values")
                for key, value in sorted(nutritional_data.items()):
                    logger.debug(f"  {key}: {value}")
            else:
                logger.warning("⚠️ No nutritional data could be extracted from page")
                # Debug: Save page source for analysis
                self._debug_save_page_source(soup)
            
            return nutritional_data
            
        except Exception as e:
            logger.error(f"❌ Error parsing nutritional information: {str(e)}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return {}

    def _find_nutrition_section(self, soup) -> object:
        """
        Find the nutritional values section using multiple strategies.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            BeautifulSoup element containing nutrition data or None
        """
        # Strategy 1: Look for exact text matches
        nutrition_headers = [
            'Nutritional Values',
            'Nutrition Information', 
            'Nutrition Facts',
            'Nutritional Information',
            'Per 100g'
        ]
        
        for header_text in nutrition_headers:
            # Try different heading levels
            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                section = soup.find(tag, string=header_text)
                if section:
                    logger.debug(f"Found nutrition section with {tag}: {header_text}")
                    return section.find_parent() or section
        
        # Strategy 2: Look for partial text matches
        nutrition_section = soup.find(string=lambda text: text and 'nutritional' in text.lower())
        if nutrition_section:
            logger.debug("Found nutrition section with partial text match")
            return nutrition_section.find_parent()
        
        # Strategy 3: Look for elements with nutrition-related classes or IDs
        nutrition_selectors = [
            '[class*="nutrition"]',
            '[id*="nutrition"]',
            '[class*="nutritional"]',
            '[id*="nutritional"]',
            '.product-nutrition',
            '.nutrition-table',
            '#nutrition-info'
        ]
        
        for selector in nutrition_selectors:
            section = soup.select_one(selector)
            if section:
                logger.debug(f"Found nutrition section with CSS selector: {selector}")
                return section
        
        # Strategy 4: Look for tables containing nutrition keywords
        tables = soup.find_all('table')
        for table in tables:
            table_text = table.get_text().lower()
            nutrition_keywords = ['energy', 'protein', 'fat', 'carbohydrate', 'salt', 'kj', 'kcal']
            if any(keyword in table_text for keyword in nutrition_keywords):
                logger.debug("Found nutrition section in table containing nutrition keywords")
                return table
        
        logger.debug("❌ No nutrition section found")
        return None

    def _extract_from_nutrition_table(self, container) -> dict:
        """
        Enhanced extraction from table structure with better pattern recognition.
        IMPROVED to handle ASDA's specific table format.
        
        Args:
            container: BeautifulSoup element containing the nutrition table
            
        Returns:
            dict: Nutritional data dictionary
        """
        nutritional_data = {}
        
        try:
            # Find all tables in the container
            tables = container.find_all('table') if container else []
            if not tables and hasattr(container, 'name') and container.name == 'table':
                tables = [container]
            
            for table in tables:
                rows = table.find_all('tr')
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        # Get nutrient name from first cell
                        nutrient_name = cells[0].get_text(strip=True)
                        # Get value from last cell (in case there are multiple columns)
                        nutrient_value = cells[-1].get_text(strip=True)
                        
                        # Skip header rows
                        if nutrient_name.lower() in ['typical values', 'per 100g', 'nutritional values']:
                            continue
                        
                        if nutrient_name and nutrient_value and nutrient_name.lower() != nutrient_value.lower():
                            # Clean and standardize the data
                            clean_name = self._standardize_nutrient_name(nutrient_name)
                            clean_value = self._standardize_nutrient_value(nutrient_value)
                            
                            # Additional validation for table data
                            if clean_name and clean_value and len(clean_value) < 20:  # Reasonable length
                                nutritional_data[clean_name] = clean_value
                                logger.debug(f"  Table extraction: {clean_name} = {clean_value}")
            
            # If no table data found, try looking for structured divs/spans
            if not nutritional_data:
                logger.debug("🔄 No table data found, trying structured elements...")
                nutritional_data = self._extract_from_structured_elements(container)
        
        except Exception as e:
            logger.error(f"❌ Error extracting from nutrition table: {str(e)}")
        
        return nutritional_data
    
    def _extract_nutrition_aggressive_regex(self, text: str) -> dict:
        """
        More aggressive regex extraction for ASDA's specific format.
        
        Args:
            text: Nutrition section text
            
        Returns:
            dict: Additional nutritional data
        """
        nutritional_data = {}
        
        try:
            # ASDA concatenates everything together, so we need to be very specific
            # Example: "Energy kJ559Energy kcal132Fat1.9gof which saturates0.5gCarbohydrate<0.5g"
            
            # Split the text on nutrition keywords to isolate values
            nutrition_keywords = [
                'energy kj', 'energy kcal', 'fat', 'carbohydrate', 
                'protein', 'salt', 'fibre', 'saturates', 'sugars'
            ]
            
            # Create pattern to capture: keyword + value + optional next keyword
            master_pattern = r'(energy\s*kj|energy\s*kcal|(?:of\s+which\s+)?(?:fat|carbohydrate|protein|salt|fibre|saturates|sugars))\s*([<>]?\d+(?:\.\d+)?)\s*(?:g|kj|kcal)?'
            
            matches = re.findall(master_pattern, text, re.IGNORECASE)
            
            for keyword, value in matches:
                # Clean up the keyword
                clean_keyword = keyword.strip().lower()
                
                # Map to standard names
                name_mapping = {
                    'energy kj': 'Energy (kJ)',
                    'energy kcal': 'Energy (kcal)',
                    'fat': 'Fat',
                    'of which saturates': 'Saturates',
                    'saturates': 'Saturates',
                    'carbohydrate': 'Carbohydrate',
                    'of which sugars': 'Sugars',
                    'sugars': 'Sugars',
                    'fibre': 'Fibre',
                    'protein': 'Protein',
                    'salt': 'Salt'
                }
                
                standard_name = name_mapping.get(clean_keyword)
                if standard_name and value:
                    # Format the value
                    if standard_name in ['Energy (kJ)', 'Energy (kcal)']:
                        unit = 'kJ' if 'kJ' in standard_name else 'kcal'
                        formatted_value = f"{value}{unit}"
                    else:
                        formatted_value = f"{value}g"
                    
                    nutritional_data[standard_name] = formatted_value
                    logger.debug(f"  Aggressive regex: {standard_name} = {formatted_value}")
        
        except Exception as e:
            logger.error(f"❌ Error in aggressive regex extraction: {str(e)}")
        
        return nutritional_data

    def _extract_from_nutrition_divs(self, container) -> dict:
        """
        Extract nutritional data from div/span structure with improved parsing.
        
        Args:
            container: BeautifulSoup element containing nutrition data
            
        Returns:
            dict: Nutritional data dictionary
        """
        nutritional_data = {}
        
        try:
            # Look for common nutrition layout patterns
            nutrition_patterns = [
                # Pattern 1: Two adjacent elements (name and value)
                {'name_selector': 'dt', 'value_selector': 'dd'},
                {'name_selector': '.nutrient-name', 'value_selector': '.nutrient-value'},
                {'name_selector': '[class*="name"]', 'value_selector': '[class*="value"]'},
                
                # Pattern 2: Single elements containing both name and value
                {'combined_selector': '.nutrition-item'},
                {'combined_selector': '.nutrient'},
                {'combined_selector': '[class*="nutrition"]'},
            ]
            
            for pattern in nutrition_patterns:
                if 'combined_selector' in pattern:
                    # Handle combined name+value elements
                    elements = container.select(pattern['combined_selector'])
                    for element in elements:
                        text = element.get_text(strip=True)
                        name, value = self._split_nutrient_text(text)
                        if name and value:
                            clean_name = self._standardize_nutrient_name(name)
                            clean_value = self._standardize_nutrient_value(value)
                            if clean_name and clean_value:
                                nutritional_data[clean_name] = clean_value
                else:
                    # Handle separate name and value elements
                    name_elements = container.select(pattern['name_selector'])
                    value_elements = container.select(pattern['value_selector'])
                    
                    for name_elem, value_elem in zip(name_elements, value_elements):
                        name = name_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)
                        
                        if name and value:
                            clean_name = self._standardize_nutrient_name(name)
                            clean_value = self._standardize_nutrient_value(value)
                            if clean_name and clean_value:
                                nutritional_data[clean_name] = clean_value
        
        except Exception as e:
            logger.error(f"❌ Error extracting from nutrition divs: {str(e)}")
        
        return nutritional_data

    def _extract_from_structured_elements(self, container) -> dict:
        """
        Extract from structured HTML elements like lists, divs with specific patterns.
        
        Args:
            container: BeautifulSoup element containing nutrition data
            
        Returns:
            dict: Nutritional data dictionary
        """
        nutritional_data = {}
        
        try:
            # Look for list items
            list_items = container.find_all(['li', 'div', 'span', 'p'])
            
            for item in list_items:
                text = item.get_text(strip=True)
                if text and any(keyword in text.lower() for keyword in 
                              ['kj', 'kcal', 'energy', 'fat', 'protein', 'carbohydrate', 'salt', 'sugar', 'fibre']):
                    
                    name, value = self._split_nutrient_text(text)
                    if name and value:
                        clean_name = self._standardize_nutrient_name(name)
                        clean_value = self._standardize_nutrient_value(value)
                        if clean_name and clean_value:
                            nutritional_data[clean_name] = clean_value
        
        except Exception as e:
            logger.error(f"❌ Error extracting from structured elements: {str(e)}")
        
        return nutritional_data

    def _extract_nutrition_from_entire_page(self, soup) -> dict:
        """
        Fallback method to extract nutrition data from the entire page.
        
        Args:
            soup: BeautifulSoup object of the entire page
            
        Returns:
            dict: Nutritional data dictionary
        """
        nutritional_data = {}
        
        try:
            # Get all text from the page
            page_text = soup.get_text()
            lines = page_text.split('\n')
            
            # Look for lines that might contain nutritional information
            for i, line in enumerate(lines):
                line = line.strip()
                if line and any(keyword in line.lower() for keyword in 
                              ['energy', 'fat', 'protein', 'carbohydrate', 'salt', 'sugar', 'fibre', 'saturates']):
                    
                    # Try to extract name and value from this line
                    name, value = self._split_nutrient_text(line)
                    
                    # If value not found in same line, check next few lines
                    if name and not value and i + 1 < len(lines):
                        for j in range(1, min(4, len(lines) - i)):  # Check next 3 lines
                            next_line = lines[i + j].strip()
                            if next_line and re.search(r'\d', next_line):  # Contains numbers
                                value = self._extract_numeric_value(next_line)
                                if value:
                                    break
                    
                    if name and value:
                        clean_name = self._standardize_nutrient_name(name)
                        clean_value = self._standardize_nutrient_value(value)
                        if clean_name and clean_value:
                            nutritional_data[clean_name] = clean_value
        
        except Exception as e:
            logger.error(f"❌ Error extracting nutrition from entire page: {str(e)}")
        
        return nutritional_data

    def _extract_nutrition_with_regex(self, soup) -> dict:
        """
        Use regex patterns to extract nutrition data as final fallback.
        IMPROVED VERSION specifically for ASDA's concatenated format.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            dict: Nutritional data dictionary
        """
        nutritional_data = {}
        
        try:
            # Get text but focus on the nutritional section only
            page_text = soup.get_text()
            
            # Try to find the nutritional section first
            nutrition_section_match = re.search(
                r'(nutritional\s+values.*?(?=features|storage|cooking|ingredients|allergens|quality|$))',
                page_text, 
                re.IGNORECASE | re.DOTALL
            )
            
            if nutrition_section_match:
                # Focus on just the nutritional section
                nutrition_text = nutrition_section_match.group(1)
                logger.debug(f"Found nutrition section: {nutrition_text[:200]}...")
            else:
                # Fallback to full page but with more careful extraction
                nutrition_text = page_text
                logger.debug("No specific nutrition section found, using full page")
            
            # ASDA specific patterns - they concatenate values without spaces
            # Format: "Energy kJ559Energy kcal132Fat1.9gof which saturates0.5g"
            nutrition_patterns = {
                'Energy (kJ)': [
                    r'energy\s*kj\s*(\d+)',
                    r'kj\s*(\d+)',
                ],
                'Energy (kcal)': [
                    r'energy\s*kcal\s*(\d+)',
                    r'kcal\s*(\d+)',
                ],
                'Fat': [
                    r'fat\s*([<>]?\d+(?:\.\d+)?)g',
                    r'(?<!which\s)fat([<>]?\d+(?:\.\d+)?)g',  # Not preceded by "which"
                ],
                'Saturates': [
                    r'saturates\s*([<>]?\d+(?:\.\d+)?)g',
                    r'which\s+saturates\s*([<>]?\d+(?:\.\d+)?)g',
                ],
                'Carbohydrate': [
                    r'carbohydrate\s*([<>]?\d+(?:\.\d+)?)g',
                    r'(?<!of\s)carbohydrate([<>]?\d+(?:\.\d+)?)g',
                ],
                'Sugars': [
                    r'sugars\s*([<>]?\d+(?:\.\d+)?)g',
                    r'which\s+sugars\s*([<>]?\d+(?:\.\d+)?)g',
                ],
                'Fibre': [
                    r'fibre\s*([<>]?\d+(?:\.\d+)?)g',
                    r'fibre([<>]?\d+(?:\.\d+)?)g',
                ],
                'Protein': [
                    r'protein\s*([<>]?\d+(?:\.\d+)?)g',
                    r'protein([<>]?\d+(?:\.\d+)?)g',
                ],
                'Salt': [
                    r'salt\s*([<>]?\d+(?:\.\d+)?)g',
                    r'salt([<>]?\d+(?:\.\d+)?)g',
                ]
            }
            
            # Apply patterns to extract data from nutrition section only
            for nutrient_name, patterns in nutrition_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, nutrition_text, re.IGNORECASE)
                    if matches:
                        # Take the first match found
                        value = matches[0]
                        
                        # Format the value properly
                        if nutrient_name in ['Energy (kJ)', 'Energy (kcal)']:
                            unit = 'kJ' if 'kJ' in nutrient_name else 'kcal'
                            formatted_value = f"{value}{unit}"
                        else:
                            # Add 'g' if not present
                            formatted_value = f"{value}g" if not value.endswith('g') else value
                        
                        nutritional_data[nutrient_name] = formatted_value
                        logger.debug(f"  Regex extraction: {nutrient_name} = {formatted_value}")
                        break  # Stop after first successful match for this nutrient
            
            # If we still don't have enough data, try a more aggressive approach
            if len(nutritional_data) < 6:
                logger.debug("🔄 Trying more aggressive regex extraction...")
                additional_data = self._extract_nutrition_aggressive_regex(nutrition_text)
                nutritional_data.update(additional_data)
        
        except Exception as e:
            logger.error(f"❌ Error extracting nutrition with regex: {str(e)}")
        
        return nutritional_data
    
    def _split_nutrient_text(self, text: str) -> tuple:
        """
        Split text containing both nutrient name and value.
        
        Args:
            text: Text like "Energy kJ 559" or "Fat: 1.9g"
            
        Returns:
            tuple: (nutrient_name, value) or (name, None) if value not found
        """
        try:
            # Common separators
            separators = [':', '-', '–', '—', '\t']
            
            # Try splitting by separators first
            for sep in separators:
                if sep in text:
                    parts = text.split(sep, 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        value = parts[1].strip()
                        if name and value:
                            return name, value
            
            # Try regex patterns for different formats
            patterns = [
                r'^(.+?)\s+([<>]?\d+(?:\.\d+)?(?:\s*[a-zA-Z]+)?)$',  # "Energy kJ 559"
                r'^(.+?)\s*:\s*([<>]?\d+(?:\.\d+)?(?:\s*[a-zA-Z]+)?)$',  # "Fat: 1.9g"
                r'^(.+?)\s*\(\s*([^)]+)\s*\)$',  # "Energy (559 kJ)"
            ]
            
            for pattern in patterns:
                match = re.match(pattern, text.strip())
                if match:
                    name = match.group(1).strip()
                    value = match.group(2).strip()
                    if name and value:
                        return name, value
            
            # If no clear separation, check if text contains nutrition keywords
            nutrition_keywords = ['energy', 'fat', 'protein', 'carbohydrate', 'salt', 'sugar', 'fibre', 'saturates']
            text_lower = text.lower()
            
            for keyword in nutrition_keywords:
                if keyword in text_lower:
                    # Extract numeric value from the text
                    value = self._extract_numeric_value(text)
                    if value:
                        return keyword.title(), value
            
            return text, None
            
        except Exception as e:
            logger.debug(f"Error splitting nutrient text '{text}': {e}")
            return text, None

    def _extract_numeric_value(self, text: str) -> str:
        """
        Extract numeric value with units from text.
        
        Args:
            text: Text containing numeric value
            
        Returns:
            str: Extracted value with unit or None
        """
        try:
            # Patterns to match values with units
            value_patterns = [
                r'([<>]?\d+(?:\.\d+)?)\s*(kj|kcal|g|mg|μg|mcg)',  # With unit
                r'([<>]?\d+(?:\.\d+)?)',  # Just number
            ]
            
            for pattern in value_patterns:
                match = re.search(pattern, text.lower())
                if match:
                    if len(match.groups()) == 2:
                        return f"{match.group(1)}{match.group(2)}"
                    else:
                        return match.group(1)
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting numeric value from '{text}': {e}")
            return None

    def _standardize_nutrient_name(self, name: str) -> str:
        """
        Enhanced standardization of nutrient names to match ASDA format exactly.
        
        Args:
            name: Raw nutrient name
            
        Returns:
            str: Standardized nutrient name
        """
        if not name:
            return ""
        
        # Remove extra whitespace and normalize
        clean_name = name.strip()
        
        # Comprehensive mappings based on ASDA format
        mappings = {
            # Energy variations
            'energy kj': 'Energy (kJ)',
            'energy (kj)': 'Energy (kJ)', 
            'energy kilojoules': 'Energy (kJ)',
            'kj': 'Energy (kJ)',
            
            'energy kcal': 'Energy (kcal)',
            'energy (kcal)': 'Energy (kcal)',
            'energy kilocalories': 'Energy (kcal)',
            'kcal': 'Energy (kcal)',
            'calories': 'Energy (kcal)',
            
            # Fat variations
            'fat': 'Fat',
            'total fat': 'Fat',
            'fats': 'Fat',
            
            'of which saturates': 'Saturates',
            'saturates': 'Saturates',
            'saturated fat': 'Saturates',
            'saturated fats': 'Saturates',
            
            # Carbohydrate variations
            'carbohydrate': 'Carbohydrate',
            'carbohydrates': 'Carbohydrate',
            'total carbohydrate': 'Carbohydrate',
            'carbs': 'Carbohydrate',
            
            'of which sugars': 'Sugars',
            'sugars': 'Sugars',
            'sugar': 'Sugars',
            'total sugars': 'Sugars',
            
            # Fiber variations
            'fibre': 'Fibre',
            'fiber': 'Fibre',
            'dietary fibre': 'Fibre',
            'dietary fiber': 'Fibre',
            
            # Protein variations
            'protein': 'Protein',
            'proteins': 'Protein',
            'total protein': 'Protein',
            
            # Salt variations
            'salt': 'Salt',
            'sodium': 'Salt',  # Convert sodium to salt for consistency
        }
        
        # Check for exact matches first
        clean_lower = clean_name.lower()
        if clean_lower in mappings:
            return mappings[clean_lower]
        
        # Check for partial matches
        for key, value in mappings.items():
            if key in clean_lower or clean_lower in key:
                return value
        
        # If no mapping found, clean up and capitalize
        # Remove common prefixes/suffixes
        clean_name = re.sub(r'^(typical\s+values?\s*)', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*(per\s+100g?)\s*$', '', clean_name, flags=re.IGNORECASE)
        
        return clean_name.title()

    def _standardize_nutrient_value(self, value: str) -> str:
        """
        Enhanced standardization of nutrient values.
        
        Args:
            value: Raw nutrient value
            
        Returns:
            str: Standardized nutrient value
        """
        if not value:
            return ""
        
        # Remove extra whitespace
        clean_value = value.strip()
        
        # Remove any parenthetical notes like "(overbaked)" or "(per 100g)"
        clean_value = re.sub(r'\([^)]*\)', '', clean_value).strip()
        
        # Remove common non-nutritional text
        clean_value = re.sub(r'(per\s+100g?|typical\s+values?)', '', clean_value, flags=re.IGNORECASE).strip()
        
        # Standardize spacing around units
        clean_value = re.sub(r'(\d)\s*([a-zA-Z]+)', r'\1\2', clean_value)
        
        # Ensure proper formatting for less than/greater than values
        clean_value = re.sub(r'<\s*(\d)', r'<\1', clean_value)
        clean_value = re.sub(r'>\s*(\d)', r'>\1', clean_value)
        
        return clean_value

    def _clean_and_validate_nutritional_data(self, data: dict) -> dict:
        """
        Enhanced cleaning and validation of nutritional data with strict filtering.
        
        Args:
            data: Raw nutritional data dictionary
            
        Returns:
            dict: Cleaned and validated nutritional data
        """
        cleaned_data = {}
        
        # Words to exclude from keys
        exclude_keys = [
            'typical values', 'per 100g', 'overbaked', 'preparation', 
            'instructions', 'contains', 'allergens', 'ingredients', 
            'storage', 'best before', 'use by', 'nutritional values',
            'cooking', 'cook', 'oven', 'fry', 'chill', 'refrigerat'
        ]
        
        # Words that indicate cooking instructions (not nutritional data)
        cooking_keywords = [
            'cook', 'oven', 'fry', 'heat', 'temperature', 'minutes', 'mins',
            'preheat', 'oil', 'season', 'pepper', 'salt and pepper', 'serving',
            'reheat', 'foil', 'rest', 'instructions', 'guide', 'chilled',
            'packaging', 'refrigerat', 'freezing', 'defrost', 'storage',
            'skewer', 'juices', 'piping hot', 'bones', 'wash', 'handling'
        ]
        
        for key, value in data.items():
            if not key or not value:
                continue
                
            key_lower = key.lower()
            value_lower = value.lower()
            
            # Skip excluded keys
            if any(exclude in key_lower for exclude in exclude_keys):
                logger.debug(f"❌ Excluded key: {key}")
                continue
                
            # Skip if key and value are the same (likely header text)
            if key_lower == value_lower:
                logger.debug(f"❌ Key equals value: {key}")
                continue
                
            # Skip if value doesn't contain numbers (likely not a nutritional value)
            if not re.search(r'\d', value):
                logger.debug(f"❌ No numbers in value: {key} = {value}")
                continue
            
            # NEW: Skip if value is too long (likely cooking instructions)
            if len(value) > 50:  # Nutritional values should be short like "559kJ" or "<0.5g"
                logger.debug(f"❌ Value too long (cooking instructions): {key} = {value[:50]}...")
                continue
                
            # NEW: Skip if value contains cooking-related keywords
            if any(cooking_word in value_lower for cooking_word in cooking_keywords):
                logger.debug(f"❌ Contains cooking keywords: {key} = {value[:50]}...")
                continue
                
            # NEW: Validate that nutritional values follow expected patterns
            if not self._is_valid_nutritional_value(key, value):
                logger.debug(f"❌ Invalid nutritional format: {key} = {value}")
                continue
                
            # Add to cleaned data
            cleaned_data[key] = value
            logger.debug(f"✅ Valid nutritional data: {key} = {value}")
        
        # Log final results
        if cleaned_data:
            logger.debug(f"✅ Final cleaned nutritional data ({len(cleaned_data)} items):")
            for key, value in sorted(cleaned_data.items()):
                logger.debug(f"    {key}: {value}")
        
        return cleaned_data
    
    def _is_valid_nutritional_value(self, key: str, value: str) -> bool:
        """
        Validate that a key-value pair represents actual nutritional information.
        
        Args:
            key: Nutrient name
            value: Nutrient value
            
        Returns:
            bool: True if this appears to be valid nutritional data
        """
        try:
            # Expected nutritional value patterns
            valid_patterns = [
                r'^[<>]?\d+(?:\.\d+)?[a-zA-Z]*$',           # "559", "1.9g", "<0.5g"
                r'^[<>]?\d+(?:\.\d+)?\s*[a-zA-Z]+$',        # "559 kJ", "1.9 g"
                r'^\d+(?:\.\d+)?[a-zA-Z]{1,4}$',            # "559kJ", "1.9g"
            ]
            
            # Check if value matches expected nutritional patterns
            value_clean = value.strip()
            for pattern in valid_patterns:
                if re.match(pattern, value_clean):
                    return True
            
            # Additional validation for energy values
            if 'energy' in key.lower():
                # Energy values should be 2-4 digits, possibly with kJ/kcal
                if re.match(r'^\d{2,4}(?:kj|kcal)?$', value_clean.lower()):
                    return True
            
            # Additional validation for other nutrients (should be decimal + unit)
            expected_nutrients = ['fat', 'protein', 'carbohydrate', 'salt', 'sugar', 'fibre', 'saturates']
            if any(nutrient in key.lower() for nutrient in expected_nutrients):
                # Should be like "1.9g", "<0.5g", "28g"
                if re.match(r'^[<>]?\d+(?:\.\d+)?g?$', value_clean.lower()):
                    return True
            
            logger.debug(f"Value '{value}' doesn't match expected nutritional patterns")
            return False
            
        except Exception as e:
            logger.debug(f"Error validating nutritional value: {e}")
            return False


    def _debug_save_page_source(self, soup):
        """
        Save page source for debugging when no nutrition data is found.
        
        Args:
            soup: BeautifulSoup object of the page
        """
        try:
            # Save a snippet of the page source for debugging
            debug_text = soup.get_text()[:2000]  # First 2000 characters
            logger.debug(f"DEBUG: Page content snippet for analysis:\n{debug_text}")
            
            # Look for any nutrition-related text in the page
            nutrition_keywords = ['energy', 'kj', 'kcal', 'fat', 'protein', 'carbohydrate', 'salt']
            found_keywords = []
            
            for keyword in nutrition_keywords:
                if keyword.lower() in debug_text.lower():
                    found_keywords.append(keyword)
            
            if found_keywords:
                logger.debug(f"DEBUG: Found nutrition keywords in page: {found_keywords}")
            else:
                logger.debug("DEBUG: No nutrition keywords found in page text")
                
        except Exception as e:
            logger.debug(f"Error in debug page source analysis: {e}")

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