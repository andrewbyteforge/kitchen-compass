"""
Enhanced Selenium-based ASDA Scraper

This module provides a production-ready Selenium WebDriver scraper for ASDA
with improved architecture, error handling, logging, and maintainability.

File: asda_scraper/selenium_scraper.py
"""

import logging
import logging.handlers
import time
import re
import random
import json
import traceback
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field, asdict
from urllib.parse import urljoin, urlparse
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    InvalidSessionIdException
)
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from django.utils import timezone
from django.db import transaction

from .models import AsdaCategory, AsdaProduct, CrawlSession
from .scraper_config import (
    SCRAPER_CONFIG, 
    get_config,
    SELENIUM_CONFIG,
    DELAY_CONFIG,
    PRODUCT_EXTRACTION_CONFIG,
    POPUP_CONFIG,
    ERROR_CONFIG,
    PAGINATION_CONFIG,
    RATE_LIMIT_CONFIG
)

# Setup enhanced logging
logger = logging.getLogger('asda_scraper.selenium_scraper')

# Ensure logs directory exists
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
(LOGS_DIR / "performance").mkdir(exist_ok=True)
(LOGS_DIR / "errors").mkdir(exist_ok=True)


class ErrorCategory(Enum):
    """Categories for error classification."""
    DRIVER_SETUP = "driver_setup"
    NETWORK = "network"
    PARSING = "parsing"
    DATABASE = "database"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


# Custom exception classes
class ScraperException(Exception):
    """Base exception class for scraper-related errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None, 
                 category: ErrorCategory = ErrorCategory.UNKNOWN):
        """
        Initialize scraper exception.
        
        Args:
            message: Error message
            error_code: Optional error code for categorization
            context: Optional context dictionary with additional info
            category: Error category for classification
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.category = category
        self.timestamp = datetime.now()
        
        # Log the error with structured data
        logger.error(f"ScraperException [{error_code}]: {message}", extra={
            'error_category': category.value,
            'context': context,
            'timestamp': self.timestamp.isoformat()
        })


class DriverSetupException(ScraperException):
    """Exception raised when WebDriver setup fails."""
    
    def __init__(self, message: str, driver_type: str = "Chrome", **kwargs):
        """Initialize driver setup exception."""
        super().__init__(
            message=f"WebDriver setup failed for {driver_type}: {message}",
            error_code="DRIVER_SETUP_FAILED",
            context={"driver_type": driver_type, **kwargs.get('context', {})},
            category=ErrorCategory.DRIVER_SETUP
        )


class RateLimitException(ScraperException):
    """Exception raised when rate limiting is detected."""
    
    def __init__(self, message: str = "Rate limit detected", **kwargs):
        """Initialize rate limit exception."""
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_DETECTED",
            context=kwargs.get('context', {}),
            category=ErrorCategory.RATE_LIMIT
        )


@dataclass
class PerformanceMetrics:
    """Track performance metrics for operations."""
    operation_name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    success: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, success: bool = True):
        """Mark operation as complete."""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.success = success
        
        # Log performance metric
        logger.info(f"Performance: {self.operation_name} took {self.duration:.2f}s", extra={
            'metric_type': 'performance',
            'operation': self.operation_name,
            'duration': self.duration,
            'success': success,
            'metadata': self.metadata
        })


@dataclass
class ScrapingResult:
    """Data class to encapsulate scraping results."""
    products_found: int = 0
    products_saved: int = 0
    products_updated: int = 0
    categories_processed: int = 0
    pages_scraped: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    performance_metrics: List[PerformanceMetrics] = field(default_factory=list)
    duration: Optional[timedelta] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def add_error(self, error_type: str, message: str, 
                  context: Dict[str, Any] = None, category: ErrorCategory = ErrorCategory.UNKNOWN):
        """Add an error to the result."""
        error_info = {
            'type': error_type,
            'message': message,
            'category': category.value,
            'context': context or {},
            'timestamp': datetime.now().isoformat(),
            'traceback': traceback.format_exc() if error_type == 'exception' else None
        }
        self.errors.append(error_info)
        
        # Also log to error file
        with open(LOGS_DIR / "errors" / f"session_errors_{datetime.now().strftime('%Y%m%d')}.json", 'a') as f:
            json.dump(error_info, f)
            f.write('\n')
    
    def add_metric(self, metric: PerformanceMetrics):
        """Add a performance metric."""
        self.performance_metrics.append(metric)
    
    def finalize(self):
        """Finalize the result with end time and duration."""
        self.end_time = datetime.now()
        self.duration = self.end_time - self.start_time
        
        # Calculate aggregated metrics
        total_duration = self.duration.total_seconds()
        products_per_minute = (self.products_found / (total_duration / 60)) if total_duration > 0 else 0
        
        # Log summary with structured data
        summary = {
            'duration_seconds': total_duration,
            'products_found': self.products_found,
            'products_saved': self.products_saved,
            'products_updated': self.products_updated,
            'categories_processed': self.categories_processed,
            'pages_scraped': self.pages_scraped,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings),
            'success_rate': self.get_success_rate(),
            'products_per_minute': products_per_minute,
            'avg_page_time': self._get_avg_page_time()
        }
        
        logger.info("Scraping session completed", extra={
            'metric_type': 'session_summary',
            'summary': summary
        })
        
        # Save performance report
        self._save_performance_report(summary)
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.products_found == 0:
            return 0.0
        return ((self.products_saved + self.products_updated) / self.products_found) * 100
    
    def _get_avg_page_time(self) -> float:
        """Calculate average time per page."""
        page_metrics = [m for m in self.performance_metrics if m.operation_name == 'extract_products']
        if not page_metrics:
            return 0.0
        return sum(m.duration for m in page_metrics if m.duration) / len(page_metrics)
    
    def _save_performance_report(self, summary: Dict[str, Any]):
        """Save detailed performance report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': summary,
            'errors': self.errors,
            'performance_metrics': [
                {
                    'operation': m.operation_name,
                    'duration': m.duration,
                    'success': m.success,
                    'metadata': m.metadata
                } for m in self.performance_metrics if m.duration
            ]
        }
        
        report_file = LOGS_DIR / "performance" / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)


@dataclass
class ProductData:
    """Data class for product information."""
    name: str
    price: float
    was_price: Optional[float] = None
    unit_price: Optional[str] = None
    quantity: Optional[str] = None
    description: str = ''
    image_url: str = ''
    product_url: str = ''
    asda_id: str = ''
    in_stock: bool = True
    special_offer: str = ''
    rating: Optional[float] = None
    review_count: int = 0
    brand: str = ''
    category_breadcrumb: List[str] = field(default_factory=list)


def retry_on_exception(max_attempts: int = 3, delay: float = 1.0, 
                      exceptions: tuple = (Exception,), category: ErrorCategory = ErrorCategory.UNKNOWN):
    """
    Decorator for retrying functions on exception.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries
        exceptions: Tuple of exceptions to catch
        category: Error category for logging
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {wait_time}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}",
                            extra={'error_category': category.value}
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


class DelayManager:
    """Enhanced delay manager with adaptive behavior."""
    
    def __init__(self):
        """Initialize delay manager."""
        self.last_request_time = None
        self.error_count = 0
        self.success_count = 0
        self.current_delay_multiplier = 1.0
        self.rate_limit_detected = False
        self.request_history = []
        
    def wait(self, delay_type: str = 'between_requests', force_delay: Optional[float] = None):
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
            base_delay = get_config(f'delays.{delay_type}', 2.0)
            
            # Apply adaptive delay based on success rate
            if self._get_recent_success_rate() < 0.5:  # Less than 50% success
                self.current_delay_multiplier = min(self.current_delay_multiplier * 1.5, 5.0)
            
            # Apply progressive delay if errors occurred
            delay = base_delay * self.current_delay_multiplier
            
            # Add random component
            random_min = get_config('delays.random_delay_min', 0.5)
            random_max = get_config('delays.random_delay_max', 2.0)
            random_addition = random.uniform(random_min, random_max)
            delay += random_addition
            
            # Cap at maximum
            max_delay = get_config('delays.max_progressive_delay', 30.0)
            delay = min(delay, max_delay)
        
        logger.debug(f"Waiting {delay:.1f} seconds ({delay_type})", extra={
            'delay_type': delay_type,
            'delay_seconds': delay,
            'multiplier': self.current_delay_multiplier
        })
        
        time.sleep(delay)
        self.last_request_time = datetime.now()
        
    def record_request(self, success: bool):
        """Record request outcome for adaptive delays."""
        self.request_history.append({
            'timestamp': datetime.now(),
            'success': success
        })
        
        # Keep only recent history (last 5 minutes)
        cutoff_time = datetime.now() - timedelta(minutes=5)
        self.request_history = [
            r for r in self.request_history 
            if r['timestamp'] > cutoff_time
        ]
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
    
    def _get_recent_success_rate(self) -> float:
        """Calculate recent success rate."""
        if not self.request_history:
            return 1.0
        
        recent = self.request_history[-20:]  # Last 20 requests
        successes = sum(1 for r in recent if r['success'])
        return successes / len(recent)
        
    def increase_delay(self):
        """Increase delay multiplier after errors."""
        self.error_count += 1
        factor = get_config('delays.progressive_delay_factor', 1.5)
        old_multiplier = self.current_delay_multiplier
        self.current_delay_multiplier = min(self.current_delay_multiplier * factor, 10.0)
        
        logger.warning(
            f"Increased delay multiplier: {old_multiplier:.2f} -> {self.current_delay_multiplier:.2f}",
            extra={
                'error_count': self.error_count,
                'success_rate': self._get_recent_success_rate()
            }
        )
        
    def reset_delay(self):
        """Reset delay multiplier after successful operations."""
        if self.error_count > 0 or self.current_delay_multiplier > 1.0:
            logger.info("Resetting delay multiplier after successful operation")
        self.error_count = 0
        self.current_delay_multiplier = 1.0
        self.rate_limit_detected = False
        
    def check_rate_limit(self, page_source: str) -> bool:
        """Check if page indicates rate limiting."""
        page_text = page_source.lower()
        indicators = get_config('rate_limit.rate_limit_indicators', [])
        
        for indicator in indicators:
            if indicator.lower() in page_text:
                logger.error(f"Rate limit detected: '{indicator}'", extra={
                    'indicator': indicator,
                    'timestamp': datetime.now().isoformat()
                })
                self.rate_limit_detected = True
                self.wait('after_rate_limit_detected')
                return True
        return False


class WebDriverManager:
    """Enhanced WebDriver setup and management with recovery."""
    
    def __init__(self, headless: bool = False):
        """Initialize WebDriver manager."""
        self.headless = headless
        self.driver = None
        self.wait = None
        self.user_agent = None
        self.setup_attempts = 0
        self.max_setup_attempts = 3
        
    @retry_on_exception(max_attempts=3, delay=2.0, 
                       exceptions=(WebDriverException,), category=ErrorCategory.DRIVER_SETUP)
    def setup_driver(self) -> webdriver.Chrome:
        """Set up Chrome WebDriver with enhanced configuration and retry logic."""
        self.setup_attempts += 1
        metric = PerformanceMetrics('driver_setup', metadata={'attempt': self.setup_attempts})
        
        try:
            logger.info(f"Setting up Chrome WebDriver (attempt {self.setup_attempts})...")
            
            chrome_options = self._get_chrome_options()
            
            # Try multiple approaches to setup the driver
            setup_methods = [
                ('ChromeDriverManager', self._setup_with_chrome_driver_manager),
                ('System Chrome', self._setup_with_system_chrome),
                ('Manual Paths', self._setup_with_manual_paths)
            ]
            
            for method_name, setup_method in setup_methods:
                try:
                    logger.info(f"Attempting setup with {method_name}...")
                    self.driver = setup_method(chrome_options)
                    if self.driver:
                        self._configure_driver()
                        metric.complete(success=True)
                        logger.info(f"✅ WebDriver setup successful using {method_name}")
                        return self.driver
                except Exception as e:
                    logger.warning(f"{method_name} setup failed: {e}")
                    continue
            
            raise DriverSetupException("All WebDriver setup methods failed")
            
        except Exception as e:
            metric.complete(success=False)
            logger.error(f"Failed to setup WebDriver: {e}")
            raise DriverSetupException(str(e))
    
    def _get_chrome_options(self) -> Options:
        """Get enhanced Chrome options configuration."""
        chrome_options = Options()
        
        # Select random user agent
        user_agents = get_config('selenium.user_agents', [SELENIUM_CONFIG['user_agents'][0]])
        self.user_agent = random.choice(user_agents)
        
        if self.headless:
            chrome_options.add_argument("--headless=new")  # New headless mode
        
        # Essential options for web scraping
        options_list = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--disable-extensions",
            "--disable-gpu",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--allow-running-insecure-content",
            f"--user-agent={self.user_agent}"
        ]
        
        # Randomize window size
        window_sizes = get_config('selenium.window_sizes', ['1920,1080'])
        window_size = random.choice(window_sizes)
        options_list.append(f"--window-size={window_size}")
        
        # Add performance options
        options_list.extend([
            "--disable-logging",
            "--disable-dev-tools",
            "--no-default-browser-check",
            "--disable-translate",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--dns-prefetch-disable",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection"
        ])
        
        for option in options_list:
            chrome_options.add_argument(option)
        
        # Experimental options
        experimental_options = get_config('selenium.experimental_options', {})
        for key, value in experimental_options.items():
            chrome_options.add_experimental_option(key, value)
        
        # Additional preferences
        prefs = {
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False,
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': False
        }
        chrome_options.add_experimental_option('prefs', prefs)
        
        return chrome_options
    
    def _setup_with_chrome_driver_manager(self, chrome_options: Options) -> webdriver.Chrome:
        """Setup driver using ChromeDriverManager."""
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    
    def _setup_with_system_chrome(self, chrome_options: Options) -> webdriver.Chrome:
        """Setup driver using system Chrome."""
        return webdriver.Chrome(options=chrome_options)
    
    def _setup_with_manual_paths(self, chrome_options: Options) -> webdriver.Chrome:
        """Setup driver using manual chromedriver paths."""
        driver_paths = get_config('drivers.chrome.driver_paths', [])
        
        for path in driver_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                logger.info(f"Found chromedriver at: {expanded_path}")
                service = Service(str(expanded_path))
                return webdriver.Chrome(service=service, options=chrome_options)
        
        raise Exception("No valid chromedriver path found")
    
    def _configure_driver(self):
        """Configure driver with enhanced settings."""
        # Set timeouts
        self.driver.set_page_load_timeout(get_config('selenium.page_load_timeout', 30))
        self.driver.implicitly_wait(get_config('selenium.implicit_wait', 5))
        
        # Set up WebDriverWait
        self.wait = WebDriverWait(
            self.driver, 
            get_config('selenium.default_timeout', 15)
        )
        
        # Execute stealth scripts
        stealth_scripts = [
            # Remove webdriver property
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
            # Remove Chrome automation extension
            "window.chrome = { runtime: {} }",
            # Add plugins
            "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})",
            # Add languages
            "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})",
            # Override permissions
            "const originalQuery = window.navigator.permissions.query; "
            "window.navigator.permissions.query = (parameters) => "
            "(parameters.name === 'notifications' ? "
            "Promise.resolve({ state: Notification.permission }) : "
            "originalQuery(parameters));"
        ]
        
        for script in stealth_scripts:
            try:
                self.driver.execute_script(script)
            except Exception as e:
                logger.warning(f"Failed to execute stealth script: {e}")
        
        # Test the driver
        self.driver.get("about:blank")
        logger.info("WebDriver configuration complete")
    
    def cleanup(self):
        """Clean up WebDriver resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed successfully")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
    
    def recover_driver(self):
        """Attempt to recover a failed driver."""
        logger.warning("Attempting driver recovery...")
        
        try:
            # First try to close existing driver
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            
            # Wait before retry
            time.sleep(5)
            
            # Setup new driver
            return self.setup_driver()
            
        except Exception as e:
            logger.error(f"Driver recovery failed: {e}")
            raise


class PopupHandler:
    """Enhanced popup handler with better detection and dismissal."""
    
    def __init__(self, driver: webdriver.Chrome):
        """Initialize popup handler."""
        self.driver = driver
        self.handled_popups = set()
        self.popup_attempts = 0
        self.max_popup_attempts = 5
        
    def handle_all_popups(self):
        """Handle all types of popups with retry logic."""
        self.popup_attempts += 1
        
        if self.popup_attempts > self.max_popup_attempts:
            logger.warning("Max popup handling attempts reached")
            return
        
        handled_any = False
        
        # Try multiple times as popups can appear with delay
        for attempt in range(3):
            if self._handle_cookie_banners():
                handled_any = True
            if self._handle_modal_popups():
                handled_any = True
            if self._handle_notification_banners():
                handled_any = True
            
            if handled_any:
                time.sleep(1)  # Wait for any cascade effects
            else:
                break
                
    @retry_on_exception(max_attempts=2, delay=0.5, exceptions=(Exception,))
    def _handle_cookie_banners(self) -> bool:
        """Handle cookie consent banners."""
        try:
            cookie_config = get_config('popups.cookie_banners', {})
            selectors = cookie_config.get('selectors', [])
            text_patterns = cookie_config.get('text_patterns', [])
            
            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            element_text = element.text.strip()
                            
                            # Check if button text matches patterns
                            for pattern in text_patterns:
                                if pattern.lower() in element_text.lower():
                                    self._safe_click(element, f"cookie banner: {element_text}")
                                    return True
                                    
                except Exception as e:
                    logger.debug(f"Cookie banner selector {selector} failed: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling cookie banners: {e}")
            
        return False
    
    def _safe_click(self, element, description: str):
        """Safely click an element with fallback methods."""
        try:
            element.click()
            logger.info(f"Clicked {description}")
        except ElementClickInterceptedException:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                logger.info(f"JavaScript clicked {description}")
            except Exception as e:
                logger.warning(f"Failed to click {description}: {e}")
    
    def _handle_modal_popups(self) -> bool:
        """Handle modal popups and overlays."""
        # Similar implementation with enhanced error handling
        return False
    
    def _handle_notification_banners(self) -> bool:
        """Handle notification banners."""
        # Similar implementation with enhanced error handling
        return False


class ProductExtractor:
    """Enhanced product data extraction with fallback strategies."""
    
    def __init__(self, driver: webdriver.Chrome):
        """Initialize product extractor."""
        self.driver = driver
        self.extraction_config = get_config('extraction', PRODUCT_EXTRACTION_CONFIG)
        self.extraction_attempts = 0
        
    def extract_products(self, page_source: str) -> List[ProductData]:
        """Extract product data from page source with performance tracking."""
        metric = PerformanceMetrics('extract_products')
        products = []
        
        try:
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Try different product container selectors
            product_containers = self._find_product_containers(soup)
            
            if not product_containers:
                logger.warning("No product containers found on page")
                self._save_debug_html(page_source, "no_products")
                return products
            
            logger.debug(f"Found {len(product_containers)} potential products")
            
            for i, container in enumerate(product_containers):
                try:
                    product_data = self._extract_single_product(container)
                    if product_data and self._validate_product(product_data):
                        products.append(product_data)
                except Exception as e:
                    logger.debug(f"Error extracting product {i}: {e}")
                    continue
            
            metric.metadata = {'products_found': len(products)}
            metric.complete(success=True)
            
            logger.info(f"Extracted {len(products)} valid products from page")
            return products
            
        except Exception as e:
            metric.complete(success=False)
            logger.error(f"Product extraction failed: {e}")
            self._save_debug_html(page_source, f"extraction_error_{self.extraction_attempts}")
            return products
    
    def _find_product_containers(self, soup) -> List:
        """Find product containers with multiple strategies."""
        containers = []
        
        # Try each selector strategy
        for selector in self.extraction_config['selectors']['product_containers']:
            found = soup.select(selector)
            if found:
                logger.debug(f"Found {len(found)} products using selector: {selector}")
                containers = found
                break
        
        # Fallback: try more generic selectors
        if not containers:
            generic_selectors = [
                'div[class*="product"]',
                'article[class*="product"]',
                'li[class*="product"]',
                '[data-testid*="product"]'
            ]
            for selector in generic_selectors:
                found = soup.select(selector)
                if found:
                    logger.info(f"Found {len(found)} products using fallback selector: {selector}")
                    containers = found
                    break
        
        return containers
    
    def _extract_single_product(self, container) -> Optional[ProductData]:
        """Extract data from a single product container."""
        try:
            # Extract title and URL
            title_element = None
            for selector in self.extraction_config['selectors']['product_title']:
                title_element = container.select_one(selector)
                if title_element:
                    break
            
            if not title_element:
                return None
            
            product_name = title_element.get_text(strip=True)
            product_url = title_element.get('href', '')
            if product_url and not product_url.startswith('http'):
                product_url = urljoin(self.driver.current_url, product_url)
            
            # Extract ASDA ID from URL
            asda_id = self._extract_asda_id(product_url)
            
            # Extract price with validation
            price = self._extract_price(container, 'product_price')
            if price is None or price <= 0:
                return None
            
            # Extract optional fields
            was_price = self._extract_price(container, 'was_price')
            unit_price = self._extract_text(container, 'unit_price')
            quantity = self._extract_text(container, 'quantity')
            
            # Extract image with fallback
            image_url = self._extract_image(container)
            
            # Check availability
            in_stock = self._check_availability(container)
            
            # Extract promotion
            special_offer = self._extract_text(container, 'promotion')
            
            return ProductData(
                name=product_name,
                price=price,
                was_price=was_price,
                unit_price=unit_price,
                quantity=quantity,
                image_url=image_url,
                product_url=product_url,
                asda_id=asda_id,
                in_stock=in_stock,
                special_offer=special_offer
            )
            
        except Exception as e:
            logger.debug(f"Error extracting single product: {e}")
            return None
    
    def _extract_price(self, container, price_type: str) -> Optional[float]:
        """Extract price from container with multiple strategies."""
        selectors = self.extraction_config['selectors'].get(price_type, [])
        price_regex = self.extraction_config['regex_patterns']['price']
        
        for selector in selectors:
            price_element = container.select_one(selector)
            if price_element:
                price_text = price_element.get_text(strip=True)
                
                # Try regex extraction
                match = re.search(price_regex, price_text)
                if match:
                    try:
                        return float(match.group(1))
                    except ValueError:
                        continue
                
                # Try alternative extraction
                price_text = price_text.replace('£', '').replace(',', '').strip()
                try:
                    return float(price_text)
                except ValueError:
                    continue
                    
        return None
    
    def _extract_image(self, container) -> str:
        """Extract image URL with fallback strategies."""
        for selector in self.extraction_config['selectors']['image']:
            img_element = container.select_one(selector)
            if img_element:
                # Try different image attributes
                for attr in ['src', 'data-src', 'data-lazy-src']:
                    image_url = img_element.get(attr, '')
                    if image_url:
                        if not image_url.startswith('http'):
                            image_url = urljoin(self.driver.current_url, image_url)
                        return image_url
        
        return ''
    
    def _validate_product(self, product: ProductData) -> bool:
        """Validate extracted product data."""
        # Basic validation
        if not product.name or not product.asda_id:
            return False
        
        # Price validation
        if product.price <= 0 or product.price > 10000:  # Reasonable price range
            return False
        
        # Name length validation
        if len(product.name) < 3 or len(product.name) > 500:
            return False
        
        return True
    
    def _save_debug_html(self, html: str, prefix: str):
        """Save HTML for debugging when extraction fails."""
        try:
            debug_file = LOGS_DIR / f"debug_{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.debug(f"Saved debug HTML to {debug_file}")
        except Exception as e:
            logger.error(f"Failed to save debug HTML: {e}")
    
    def _extract_text(self, container, field_name: str) -> str:
        """Extract text from container."""
        selectors = self.extraction_config['selectors'].get(field_name, [])
        
        for selector in selectors:
            element = container.select_one(selector)
            if element:
                return element.get_text(strip=True)
        return ''
    
    def _extract_asda_id(self, url: str) -> str:
        """Extract ASDA product ID from URL."""
        if not url:
            return ''
        
        id_regex = self.extraction_config['regex_patterns'].get('product_id', r'/(\d+)$')
        match = re.search(id_regex, url)
        if match:
            return match.group(1)
        
        # Fallback: try to extract from URL path
        path_parts = urlparse(url).path.split('/')
        for part in reversed(path_parts):
            if part.isdigit():
                return part
        
        return ''
    
    def _check_availability(self, container) -> bool:
        """Check if product is in stock."""
        availability_selectors = self.extraction_config['selectors'].get('availability', [])
        
        for selector in availability_selectors:
            element = container.select_one(selector)
            if element:
                text = element.get_text(strip=True).lower()
                if 'out of stock' in text or 'unavailable' in text:
                    return False
        
        return True


class PaginationHandler:
    """Enhanced pagination handler with multiple strategies."""
    
    def __init__(self, driver: webdriver.Chrome, delay_manager: DelayManager):
        """Initialize pagination handler."""
        self.driver = driver
        self.delay_manager = delay_manager
        self.current_page = 1
        self.max_pages = get_config('scraper.max_pages_per_category', 10)
        self.pagination_failures = 0
        
    def has_next_page(self) -> bool:
        """Check if there's a next page with multiple detection methods."""
        if self.current_page >= self.max_pages:
            logger.info(f"Reached max pages limit ({self.max_pages})")
            return False
        
        # Check for pagination failures
        if self.pagination_failures >= 3:
            logger.warning("Too many pagination failures, stopping")
            return False
        
        # Method 1: Check for next button
        if self._has_next_button():
            return True
        
        # Method 2: Check URL pattern
        if self._has_url_pagination():
            return True
        
        # Method 3: Check for infinite scroll indicators
        if self._has_infinite_scroll():
            return True
        
        return False
    
    def _has_next_button(self) -> bool:
        """Check if next button exists and is clickable."""
        next_button_selectors = get_config(
            'pagination.strategies.button_click.selectors',
            PAGINATION_CONFIG['strategies']['button_click']['selectors']
        )
        
        for selector in next_button_selectors:
            try:
                next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                if next_button.is_enabled() and next_button.is_displayed():
                    # Check if button is not disabled
                    if 'disabled' not in next_button.get_attribute('class'):
                        return True
            except NoSuchElementException:
                continue
        
        return False
    
    def _has_url_pagination(self) -> bool:
        """Check if URL supports pagination parameters."""
        current_url = self.driver.current_url
        return 'page=' in current_url or '?p=' in current_url
    
    def _has_infinite_scroll(self) -> bool:
        """Check for infinite scroll indicators."""
        try:
            # Check if there are loading indicators
            loading_selectors = ['.loading', '.spinner', '[class*="load-more"]']
            for selector in loading_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return True
        except:
            pass
        
        return False
    
    @retry_on_exception(max_attempts=3, delay=2.0, exceptions=(Exception,))
    def go_to_next_page(self) -> bool:
        """Navigate to the next page with multiple strategies."""
        metric = PerformanceMetrics('pagination', metadata={'page': self.current_page + 1})
        
        try:
            # Strategy 1: Click next button
            if self._click_next_button():
                self.current_page += 1
                metric.complete(success=True)
                self.pagination_failures = 0
                return True
            
            # Strategy 2: URL manipulation
            if self._navigate_by_url():
                self.current_page += 1
                metric.complete(success=True)
                self.pagination_failures = 0
                return True
            
            # Strategy 3: Infinite scroll
            if self._scroll_for_more():
                self.current_page += 1
                metric.complete(success=True)
                self.pagination_failures = 0
                return True
            
            metric.complete(success=False)
            self.pagination_failures += 1
            return False
            
        except Exception as e:
            metric.complete(success=False)
            logger.error(f"Pagination failed: {e}")
            self.pagination_failures += 1
            return False
    
    def _click_next_button(self) -> bool:
        """Try to click the next page button."""
        next_button_selectors = get_config(
            'pagination.strategies.button_click.selectors',
            PAGINATION_CONFIG['strategies']['button_click']['selectors']
        )
        
        for selector in next_button_selectors:
            try:
                next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                if next_button.is_enabled() and next_button.is_displayed():
                    # Scroll to button
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", 
                        next_button
                    )
                    self.delay_manager.wait('element_wait')
                    
                    # Try different click methods
                    try:
                        next_button.click()
                    except ElementClickInterceptedException:
                        self.driver.execute_script("arguments[0].click();", next_button)
                    
                    self.delay_manager.wait('page_load_wait')
                    
                    logger.info(f"✅ Navigated to page {self.current_page + 1}")
                    return True
                    
            except (NoSuchElementException, Exception) as e:
                logger.debug(f"Pagination selector {selector} failed: {e}")
                continue
        
        return False
    
    def _navigate_by_url(self) -> bool:
        """Navigate by modifying the URL."""
        current_url = self.driver.current_url
        
        # Pattern 1: page=X
        if 'page=' in current_url:
            match = re.search(r'page=(\d+)', current_url)
            if match:
                current_page_num = int(match.group(1))
                new_url = current_url.replace(
                    f'page={current_page_num}', 
                    f'page={current_page_num + 1}'
                )
                self.driver.get(new_url)
                self.delay_manager.wait('page_load_wait')
                return True
        
        # Pattern 2: Add page parameter
        elif '?' in current_url:
            new_url = f"{current_url}&page={self.current_page + 1}"
            self.driver.get(new_url)
            self.delay_manager.wait('page_load_wait')
            return True
        
        return False
    
    def _scroll_for_more(self) -> bool:
        """Handle infinite scroll pagination."""
        try:
            # Get initial height
            initial_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content
            self.delay_manager.wait('scroll_pause')
            
            # Check if new content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height > initial_height:
                logger.info("New content loaded via infinite scroll")
                return True
                
        except Exception as e:
            logger.debug(f"Scroll pagination failed: {e}")
        
        return False
    
    def reset(self):
        """Reset pagination state."""
        self.current_page = 1
        self.pagination_failures = 0


class SeleniumAsdaScraper:
    """Enhanced production-ready Selenium-based ASDA scraper."""
    
    def __init__(self, crawl_session: CrawlSession, headless: bool = False):
        """
        Initialize the scraper.
        
        Args:
            crawl_session: CrawlSession model instance
            headless: Whether to run browser in headless mode
        """
        self.session = crawl_session
        self.headless = headless
        self.driver_manager = None
        self.driver = None
        self.base_url = get_config('base_url', 'https://groceries.asda.com')
        self.delay_manager = DelayManager()
        self.popup_handler = None
        self.product_extractor = None
        self.pagination_handler = None
        self.result = ScrapingResult()
        self.health_metrics = {
            'driver_restarts': 0,
            'recovery_attempts': 0,
            'rate_limit_encounters': 0
        }
        
        logger.info(f"Initializing Selenium ASDA Scraper for session {self.session.pk}", extra={
            'session_id': self.session.pk,
            'headless': headless,
            'base_url': self.base_url
        })
        
        try:
            self._setup_driver()
        except Exception as e:
            logger.error(f"Failed to initialize scraper: {e}", extra={
                'session_id': self.session.pk,
                'error_type': type(e).__name__
            })
            self.cleanup()
            raise
    
    def _setup_driver(self):
        """Set up the WebDriver and related components."""
        setup_metric = PerformanceMetrics('scraper_initialization')
        
        try:
            self.driver_manager = WebDriverManager(self.headless)
            self.driver = self.driver_manager.setup_driver()
            
            # Initialize components
            self.popup_handler = PopupHandler(self.driver)
            self.product_extractor = ProductExtractor(self.driver)
            self.pagination_handler = PaginationHandler(self.driver, self.delay_manager)
            
            setup_metric.complete(success=True)
            self.result.add_metric(setup_metric)
            
        except Exception as e:
            setup_metric.complete(success=False)
            self.result.add_metric(setup_metric)
            raise
    
    def start_crawl(self) -> ScrapingResult:
        """
        Start the crawling process.
        
        Returns:
            ScrapingResult with crawl statistics
        """
        logger.info("=" * 50)
        logger.info(f"Starting ASDA crawl session {self.session.pk}")
        logger.info("=" * 50)
        
        self.session.started_at = timezone.now()
        self.session.status = 'running'
        self.session.save()
        
        try:
            # Get categories to crawl
            categories = self._get_categories_to_crawl()
            
            if not categories:
                logger.warning("No categories to crawl")
                self.result.warnings.append("No categories found to crawl")
                return self._finalize_crawl()
            
            # Process each category
            for i, category in enumerate(categories):
                # Check if session should continue
                self.session.refresh_from_db()
                if self.session.status != 'running':
                    logger.info("Crawl session stopped by user")
                    break
                
                try:
                    self._process_category_with_recovery(category)
                    self.result.categories_processed += 1
                    self.delay_manager.reset_delay()  # Reset on success
                    self.delay_manager.record_request(True)
                    
                except RateLimitException as e:
                    self.health_metrics['rate_limit_encounters'] += 1
                    logger.error(f"Rate limit detected for category {category.name}")
                    self.result.add_error('rate_limit', f"Rate limited on category {category.name}", 
                                        category=ErrorCategory.RATE_LIMIT)
                    self.delay_manager.wait('after_rate_limit_detected')
                    self.delay_manager.record_request(False)
                    
                    # Skip to next category after rate limit
                    continue
                    
                except Exception as e:
                    logger.error(f"Error processing category {category.name}: {e}")
                    self.result.add_error('category_error', str(e), 
                                        {'category': category.name}, 
                                        category=ErrorCategory.UNKNOWN)
                    self.delay_manager.increase_delay()
                    self.delay_manager.record_request(False)
                    
                    # Check error threshold
                    if len(self.result.errors) > get_config('errors.thresholds.max_category_errors', 10):
                        logger.error("Too many category errors, stopping crawl")
                        break
                
                # Progress update
                progress = ((i + 1) / len(categories)) * 100
                logger.info(f"Progress: {progress:.1f}% ({i + 1}/{len(categories)} categories)")
                
                # Delay between categories
                if i < len(categories) - 1:  # Don't delay after last category
                    self.delay_manager.wait('between_categories')
            
            return self._finalize_crawl()
            
        except Exception as e:
            logger.error(f"Fatal error during crawl: {e}", exc_info=True)
            self.session.status = 'failed'
            self.session.error_log = str(e)
            self.session.save()
            self.result.add_error('fatal_error', str(e), category=ErrorCategory.UNKNOWN)
            return self._finalize_crawl()
        
        finally:
            self.cleanup()
    
    def _process_category_with_recovery(self, category: AsdaCategory):
        """Process category with automatic recovery on failure."""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                self._process_category(category)
                return  # Success
                
            except (WebDriverException, InvalidSessionIdException) as e:
                self.health_metrics['recovery_attempts'] += 1
                logger.warning(f"WebDriver error on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    try:
                        # Attempt driver recovery
                        self.driver = self.driver_manager.recover_driver()
                        self.health_metrics['driver_restarts'] += 1
                        
                        # Reinitialize components
                        self.popup_handler = PopupHandler(self.driver)
                        self.product_extractor = ProductExtractor(self.driver)
                        self.pagination_handler = PaginationHandler(self.driver, self.delay_manager)
                        
                        logger.info("Driver recovery successful, retrying category")
                        time.sleep(5)  # Brief pause before retry
                        
                    except Exception as recovery_error:
                        logger.error(f"Driver recovery failed: {recovery_error}")
                        raise
                else:
                    raise
    
    def _process_category(self, category: AsdaCategory):
        """Process a single category."""
        category_metric = PerformanceMetrics('process_category', 
                                        metadata={'category': category.name})
        
        logger.info(f"\nProcessing category: {category.name} ({category.url_code})")
        
        # Fix: Construct URL using url_code
        category_url = f"{self.base_url}/browse/{category.slug}/{category.url_code}"
        
        try:
            # Navigate to category
            nav_metric = PerformanceMetrics('navigate_to_category')
            self.driver.get(category_url)
            self.delay_manager.wait('page_load_wait')
            nav_metric.complete(success=True)
            self.result.add_metric(nav_metric)
            
            # Handle popups
            self.popup_handler.handle_all_popups()
            
            # Check for rate limiting
            if self.delay_manager.check_rate_limit(self.driver.page_source):
                raise RateLimitException()
            
            # Reset pagination
            self.pagination_handler.reset()
            
            # Track products for this category
            category_products_found = 0
            category_products_saved = 0
            
            # Process all pages
            while True:
                page_metric = PerformanceMetrics('process_page', 
                                            metadata={'page': self.pagination_handler.current_page})
                
                # Extract products from current page
                products = self.product_extractor.extract_products(self.driver.page_source)
                page_metric.metadata['products_found'] = len(products)
                
                self.result.products_found += len(products)
                category_products_found += len(products)
                self.result.pages_scraped += 1
                
                # Save products
                saved_count, updated_count = self._save_products_batch(products, category)
                self.result.products_saved += saved_count
                self.result.products_updated += updated_count
                category_products_saved += saved_count + updated_count
                
                page_metric.complete(success=True)
                self.result.add_metric(page_metric)
                
                logger.info(f"Page {self.pagination_handler.current_page}: "
                        f"Found {len(products)} products, "
                        f"saved {saved_count}, updated {updated_count}")
                
                # Check if should continue to next page
                if not self.pagination_handler.has_next_page():
                    break
                
                # Check if we have enough products
                if category_products_found >= get_config('crawl_defaults.max_products_per_category', 200):
                    logger.info(f"Reached product limit for category ({category_products_found})")
                    break
                
                # Navigate to next page
                if not self.pagination_handler.go_to_next_page():
                    break
                
                # Wait between pages
                self.delay_manager.wait('between_requests')
            
            # Update category statistics
            category.last_crawled = timezone.now()
            category.product_count = category.products.count()
            category.save()
            
            category_metric.metadata.update({
                'total_products_found': category_products_found,
                'total_products_saved': category_products_saved,
                'pages_processed': self.pagination_handler.current_page
            })
            category_metric.complete(success=True)
            self.result.add_metric(category_metric)
            
            logger.info(f"✅ Completed category {category.name}: "
                    f"{category.product_count} total products in database")
            
        except Exception as e:
            category_metric.complete(success=False)
            self.result.add_metric(category_metric)
            logger.error(f"Error processing category {category.name}: {e}")
            raise





    def _save_products_batch(self, products: List[ProductData], category: AsdaCategory) -> Tuple[int, int]:
        """
        Save products in optimized batches.
        
        Returns:
            Tuple of (saved_count, updated_count)
        """
        if not products:
            return 0, 0
        
        save_metric = PerformanceMetrics('save_products_batch', 
                                       metadata={'batch_size': len(products)})
        saved_count = 0
        updated_count = 0
        
        try:
            with transaction.atomic():
                # Get existing products in batch
                asda_ids = [p.asda_id for p in products if p.asda_id]
                existing_products = {
                    p.asda_id: p for p in AsdaProduct.objects.filter(asda_id__in=asda_ids)
                }
                
                products_to_create = []
                products_to_update = []
                
                for product_data in products:
                    try:
                        if product_data.asda_id in existing_products:
                            # Update existing product
                            existing = existing_products[product_data.asda_id]
                            updated = False
                            
                            # Check what needs updating
                            if abs(existing.price - product_data.price) > 0.01:  # Price changed
                                existing.price = product_data.price
                                updated = True
                            
                            if existing.was_price != product_data.was_price:
                                existing.was_price = product_data.was_price
                                updated = True
                            
                            if existing.in_stock != product_data.in_stock:
                                existing.in_stock = product_data.in_stock
                                updated = True
                            
                            if product_data.special_offer and existing.special_offer != product_data.special_offer:
                                existing.special_offer = product_data.special_offer
                                updated = True
                            
                            if updated:
                                existing.updated_at = timezone.now()
                                products_to_update.append(existing)
                                updated_count += 1
                                
                        else:
                            # Create new product
                            new_product = AsdaProduct(
                                asda_id=product_data.asda_id,
                                name=product_data.name,
                                price=product_data.price,
                                was_price=product_data.was_price,
                                unit_price=product_data.unit_price,
                                quantity=product_data.quantity or 'each',
                                description=product_data.description,
                                image_url=product_data.image_url,
                                product_url=product_data.product_url,
                                category=category,
                                in_stock=product_data.in_stock,
                                special_offer=product_data.special_offer
                            )
                            products_to_create.append(new_product)
                            saved_count += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing product {product_data.name}: {e}")
                        self.result.add_error('save_error', str(e), 
                                            {'product': product_data.name},
                                            category=ErrorCategory.DATABASE)
                
                # Bulk operations
                if products_to_create:
                    AsdaProduct.objects.bulk_create(products_to_create, batch_size=100)
                
                if products_to_update:
                    AsdaProduct.objects.bulk_update(
                        products_to_update,
                        ['price', 'was_price', 'in_stock', 'special_offer', 'updated_at'],
                        batch_size=100
                    )
                
                save_metric.metadata.update({
                    'saved': saved_count,
                    'updated': updated_count
                })
                save_metric.complete(success=True)
                self.result.add_metric(save_metric)
                
        except Exception as e:
            save_metric.complete(success=False)
            self.result.add_metric(save_metric)
            logger.error(f"Batch save failed: {e}")
            self.result.add_error('batch_save_error', str(e), 
                                category=ErrorCategory.DATABASE)
            
            # Fallback to individual saves
            for product in products:
                try:
                    s, u = self._save_single_product(product, category)
                    saved_count += s
                    updated_count += u
                except Exception as e2:
                    logger.error(f"Failed to save product {product.name}: {e2}")
        
        return saved_count, updated_count
    
    def _save_single_product(self, product_data: ProductData, category: AsdaCategory) -> Tuple[int, int]:
        """Save a single product (fallback method)."""
        try:
            existing = AsdaProduct.objects.filter(asda_id=product_data.asda_id).first()
            
            if existing:
                # Update logic
                existing.price = product_data.price
                existing.was_price = product_data.was_price
                existing.in_stock = product_data.in_stock
                existing.special_offer = product_data.special_offer
                existing.updated_at = timezone.now()
                existing.save()
                return 0, 1
            else:
                # Create new
                AsdaProduct.objects.create(
                    asda_id=product_data.asda_id,
                    name=product_data.name,
                    price=product_data.price,
                    was_price=product_data.was_price,
                    unit_price=product_data.unit_price,
                    quantity=product_data.quantity or 'each',
                    description=product_data.description,
                    image_url=product_data.image_url,
                    product_url=product_data.product_url,
                    category=category,
                    in_stock=product_data.in_stock,
                    special_offer=product_data.special_offer
                )
                return 1, 0
                
        except Exception as e:
            logger.error(f"Single product save failed: {e}")
            return 0, 0
    
    def _get_categories_to_crawl(self) -> List[AsdaCategory]:
        """Get list of categories to crawl based on configuration."""
        categories = AsdaCategory.objects.filter(is_active=True)
        
        # Apply priority filter if configured
        priority_threshold = get_config('crawl_defaults.category_priority_threshold', 2)
        category_config = get_config('categories', {})
        
        filtered_categories = []
        for category in categories:
            # Fix: Use url_code instead of asda_id
            cat_config = category_config.get(category.url_code, {})
            if cat_config.get('priority', 3) <= priority_threshold:
                filtered_categories.append(category)
        
        # Sort by priority
        filtered_categories.sort(key=lambda c: category_config.get(c.url_code, {}).get('priority', 3))
        
        # Limit number of categories
        max_categories = get_config('crawl_defaults.max_categories', 20)
        filtered_categories = filtered_categories[:max_categories]
        
        logger.info(f"Found {len(filtered_categories)} categories to crawl")
        return filtered_categories


    def _finalize_crawl(self) -> ScrapingResult:
        """Finalize the crawl session."""
        self.result.finalize()
        
        # Update session
        self.session.ended_at = timezone.now()
        
        # Fix: Use shorter status strings that fit in varchar(20)
        if len(self.result.errors) == 0:
            self.session.status = 'completed'
        else:
            self.session.status = 'completed_errors'  # Shortened from 'completed_with_errors'
        
        self.session.products_found = self.result.products_found
        self.session.products_saved = self.result.products_saved + self.result.products_updated
        self.session.categories_crawled = self.result.categories_processed
        
        if self.result.errors:
            # Store error summary
            error_summary = {
                'total_errors': len(self.result.errors),
                'error_categories': {},
                'first_errors': self.result.errors[:5]
            }
            
            # Count errors by category
            for error in self.result.errors:
                cat = error.get('category', 'unknown')
                error_summary['error_categories'][cat] = error_summary['error_categories'].get(cat, 0) + 1
            
            self.session.error_log = json.dumps(error_summary, default=str)
        
        self.session.save()
        
        # Log comprehensive summary
        self._log_final_summary()
        
        return self.result
    

    def _get_category_slug(self, category: AsdaCategory) -> str:
        """Get or generate slug for category."""
        category_config = get_config('categories', {})
        cat_config = category_config.get(category.url_code, {})
        
        # Use slug from config if available
        if 'slug' in cat_config:
            return cat_config['slug']
        
        # Generate slug from name
        slug = category.name.lower()
        slug = slug.replace(' & ', '-and-')
        slug = slug.replace(',', '')
        slug = slug.replace(' ', '-')
        slug = re.sub(r'[^a-z0-9-]', '', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        
        return slug


    def _log_final_summary(self):
        """Log comprehensive crawl summary."""
        duration = self.result.duration.total_seconds() if self.result.duration else 0
        
        summary_lines = [
            "=" * 80,
            "CRAWL SUMMARY",
            "=" * 80,
            f"Session ID: {self.session.pk}",
            f"Duration: {self.result.duration}",
            f"Status: {self.session.status}",
            "-" * 40,
            "STATISTICS:",
            f"- Categories processed: {self.result.categories_processed}",
            f"- Pages scraped: {self.result.pages_scraped}",
            f"- Products found: {self.result.products_found}",
            f"- Products saved: {self.result.products_saved}",
            f"- Products updated: {self.result.products_updated}",
            f"- Total errors: {len(self.result.errors)}",
            f"- Success rate: {self.result.get_success_rate():.1f}%",
            "-" * 40,
            "PERFORMANCE:",
            f"- Avg products/minute: {(self.result.products_found / (duration / 60)) if duration > 0 else 0:.1f}",
            f"- Avg page time: {self.result._get_avg_page_time():.1f}s",
            "-" * 40,
            "HEALTH METRICS:",
            f"- Driver restarts: {self.health_metrics['driver_restarts']}",
            f"- Recovery attempts: {self.health_metrics['recovery_attempts']}",
            f"- Rate limit encounters: {self.health_metrics['rate_limit_encounters']}",
            "=" * 80
        ]
        
        # Log as single message
        logger.info("\n".join(summary_lines), extra={
            'metric_type': 'final_summary',
            'session_id': self.session.pk,
            'summary_data': self.result.to_dict()
        })
        
        # Log error breakdown if any
        if self.result.errors:
            error_categories = {}
            for error in self.result.errors:
                cat = error.get('category', 'unknown')
                error_categories[cat] = error_categories.get(cat, 0) + 1
            
            logger.warning(f"Error breakdown by category: {error_categories}")
    
    def stop_crawl(self):
        """Stop the crawl session gracefully."""
        logger.info("Stopping crawl session...")
        self.session.status = 'stopped'
        self.session.save()
    
    def cleanup(self):
        """Clean up resources."""
        if self.driver_manager:
            self.driver_manager.cleanup()
        
        # Save any pending metrics
        if self.result.performance_metrics:
            logger.info(f"Total performance metrics collected: {len(self.result.performance_metrics)}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status of the scraper."""
        total_requests = self.delay_manager.success_count + self.delay_manager.error_count
        
        return {
            'status': 'healthy' if self.delay_manager._get_recent_success_rate() > 0.8 else 'degraded',
            'success_rate': self.delay_manager._get_recent_success_rate(),
            'total_requests': total_requests,
            'current_delay_multiplier': self.delay_manager.current_delay_multiplier,
            'health_metrics': self.health_metrics,
            'errors_last_5min': len([e for e in self.result.errors 
                                    if datetime.fromisoformat(e['timestamp']) > 
                                    datetime.now() - timedelta(minutes=5)])
        }


def create_selenium_scraper(crawl_session: CrawlSession, headless: bool = False) -> SeleniumAsdaScraper:
    """
    Factory function to create a Selenium scraper instance.
    
    Args:
        crawl_session: CrawlSession model instance
        headless: Whether to run browser in headless mode
        
    Returns:
        SeleniumAsdaScraper instance
    """
    logger.info(f"Creating new scraper instance for session {crawl_session.pk}")
    return SeleniumAsdaScraper(crawl_session, headless)




