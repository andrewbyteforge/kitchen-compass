"""
Enhanced base scraper class for ASDA website scraping with debug fixes.

ISSUE ANALYSIS:
1. The run() method calls setup_driver() then scrape(), which should work
2. The problem is likely in the CategoryMapperCrawler.scrape() method
3. Need to add more debug logging to identify where it's getting stuck
4. HEADLESS_MODE in settings might be preventing visible crawling

KEY FIXES:
- Add comprehensive debug logging to track execution flow
- Fix HEADLESS setting (currently HEADLESS=False but HEADLESS_MODE controls it)
- Add timeout checks and browser health verification
- Improve error handling in the scrape() method
"""

import logging
import random
import time
import hashlib
import json
import traceback
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable, Tuple
from urllib.parse import urlparse
from datetime import datetime, timedelta
from collections import deque
from functools import wraps
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchWindowException,
    StaleElementReferenceException,
)
from selenium_stealth import stealth
from django.conf import settings
from django.utils import timezone
from django.db import transaction, DatabaseError

from ..models import CrawlSession, CrawledURL


logger = logging.getLogger(__name__)


class ScraperException(Exception):
    """Custom exception for scraper-specific errors."""
    pass


class TemporaryError(ScraperException):
    """Error that might be resolved by retrying."""
    pass


class PermanentError(ScraperException):
    """Error that won't be resolved by retrying."""
    pass


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (TemporaryError, TimeoutException, WebDriverException),
    jitter: bool = True
):
    """
    Enhanced decorator for automatic retry with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff: Backoff multiplier for exponential delay
        exceptions: Tuple of exceptions to retry on
        jitter: Add random jitter to prevent thundering herd
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    logger.debug(f"🔄 Attempt {attempt + 1}/{max_attempts} for {func.__name__}")
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        # Add jitter if enabled
                        sleep_time = current_delay
                        if jitter:
                            sleep_time *= (0.5 + random.random())
                        
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {sleep_time:.2f}s"
                        )
                        
                        time.sleep(sleep_time)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
                        
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


class CircuitBreaker:
    """Simple circuit breaker implementation."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, expected_exception_types: tuple = ()):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception_types = expected_exception_types
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
                logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                raise TemporaryError("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception_types as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == 'HALF_OPEN':
            self.state = 'CLOSED'
            logger.info("Circuit breaker closed after successful call")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class RateLimiter:
    """Rate limiter for request throttling."""
    
    def __init__(self, max_requests: int = 60, time_window: int = 60, burst_size: int = 10):
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_size = burst_size
        self.requests = deque()
        self.tokens = burst_size
        self.last_refill = time.time()
    
    def wait_if_needed(self):
        """Block if rate limit would be exceeded."""
        current_time = time.time()
        
        # Refill tokens
        time_passed = current_time - self.last_refill
        self.tokens = min(self.burst_size, self.tokens + time_passed * (self.burst_size / self.time_window))
        self.last_refill = current_time
        
        # Clean old requests
        cutoff_time = current_time - self.time_window
        while self.requests and self.requests[0] < cutoff_time:
            self.requests.popleft()
        
        # Check if we need to wait
        if len(self.requests) >= self.max_requests or self.tokens < 1:
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (self.time_window / self.burst_size)
            else:
                wait_time = self.time_window - (current_time - self.requests[0])
            
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            self.tokens = 1
        
        # Consume a token and record request
        self.tokens -= 1
        self.requests.append(current_time)


class HealthMonitor:
    """Monitor scraper health and performance metrics."""
    
    def __init__(self, error_threshold: float = 0.1):
        self.error_threshold = error_threshold
        self.stats = {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'total_time': 0,
            'error_types': {},
        }
        self.recent_errors = deque(maxlen=100)
        self.start_time = time.time()
    
    def record_request(self, success: bool, duration: float, error: Optional[Exception] = None):
        """Record request metrics."""
        self.stats['requests'] += 1
        self.stats['total_time'] += duration
        
        if success:
            self.stats['successes'] += 1
        else:
            self.stats['failures'] += 1
            if error:
                error_type = type(error).__name__
                self.stats['error_types'][error_type] = (
                    self.stats['error_types'].get(error_type, 0) + 1
                )
                self.recent_errors.append({
                    'time': time.time(),
                    'error': str(error),
                    'type': error_type
                })
    
    def is_healthy(self) -> bool:
        """Check if scraper is operating within acceptable parameters."""
        if self.stats['requests'] == 0:
            return True
        
        error_rate = self.stats['failures'] / self.stats['requests']
        return error_rate <= self.error_threshold
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current health statistics."""
        runtime = time.time() - self.start_time
        avg_time = (
            self.stats['total_time'] / self.stats['requests']
            if self.stats['requests'] > 0 else 0
        )
        
        return {
            'runtime_seconds': runtime,
            'total_requests': self.stats['requests'],
            'successes': self.stats['successes'],
            'failures': self.stats['failures'],
            'error_rate': (
                self.stats['failures'] / self.stats['requests']
                if self.stats['requests'] > 0 else 0
            ),
            'average_request_time': avg_time,
            'requests_per_minute': (
                self.stats['requests'] / (runtime / 60)
                if runtime > 0 else 0
            ),
            'error_types': self.stats['error_types'],
            'recent_errors': list(self.recent_errors)[-10:],
        }


class BaseScraper(ABC):
    """Enhanced abstract base class for ASDA scrapers with improved stability."""

    def __init__(self, session: Optional[CrawlSession] = None) -> None:
        """
        Initialize the enhanced base scraper.

        Args:
            session: Optional CrawlSession instance for tracking progress
        """
        logger.info("🚀 Initializing BaseScraper")
        
        self.settings = settings.ASDA_SCRAPER_SETTINGS
        self.session = session
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.processed_urls: set = set()
        self.failed_urls: set = set()
        
        # DEBUG: Log current settings
        logger.info(f"📊 Scraper settings: {json.dumps(self.settings, indent=2)}")
        
        # Initialize resilience components
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.get('CIRCUIT_BREAKER_THRESHOLD', 5),
            recovery_timeout=self.settings.get('CIRCUIT_BREAKER_TIMEOUT', 60),
            expected_exception_types=(WebDriverException, TimeoutException)
        )
        
        self.rate_limiter = RateLimiter(
            max_requests=self.settings.get('RATE_LIMIT_REQUESTS', 60),
            time_window=self.settings.get('RATE_LIMIT_WINDOW', 60),
            burst_size=self.settings.get('RATE_LIMIT_BURST', 10)
        )
        
        self.health_monitor = HealthMonitor(
            error_threshold=self.settings.get('ERROR_THRESHOLD', 0.1)
        )
        
        # Driver recovery tracking
        self.driver_restarts = 0
        self.max_driver_restarts = 3
        
        logger.info("✅ Enhanced scraper initialized with resilience components")

    @contextmanager
    def error_tracking(self, context: str):
        """Context manager for consistent error tracking."""
        logger.debug(f"🔍 Starting operation: {context}")
        start_time = time.time()
        try:
            yield
            duration = time.time() - start_time
            self.health_monitor.record_request(True, duration)
            logger.debug(f"✅ Completed operation: {context} (took {duration:.2f}s)")
        except Exception as e:
            duration = time.time() - start_time
            self.health_monitor.record_request(False, duration, e)
            logger.error(f"❌ Error in {context}: {str(e)}", exc_info=True)
            
            # Check if we should continue
            if not self.health_monitor.is_healthy():
                logger.critical(
                    f"🚨 Health check failed. Error rate too high: "
                    f"{self.health_monitor.get_stats()}"
                )
                if self.session:
                    self.session.status = 'FAILED'
                    self.session.error_log = json.dumps(self.health_monitor.get_stats())
                    self.session.save()
                raise PermanentError("Scraper health check failed")
            
            raise

    @with_retry(max_attempts=3)
    def setup_driver(self) -> None:
        """Enhanced Chrome WebDriver setup with better error recovery."""
        with self.error_tracking("driver_setup"):
            try:
                # Clean up any existing driver
                if self.driver:
                    self.teardown_driver()
                
                logger.info("🌐 Setting up Chrome WebDriver with enhanced stealth mode")

                options = Options()

                # Enhanced stealth mode options
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                # Stability options
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-notifications')
                options.add_argument('--disable-popup-blocking')
                options.add_argument('--disable-translate')
                options.add_argument('--disable-features=TranslateUI')
                options.add_argument('--disable-infobars')
                
                # Memory optimization
                options.add_argument('--memory-pressure-off')
                options.add_argument('--max_old_space_size=4096')
                
                # Better viewport
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--start-maximized')
                
                # User agent rotation
                user_agents = self.settings.get('USER_AGENTS', [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                ])
                selected_agent = random.choice(user_agents)
                options.add_argument(f'user-agent={selected_agent}')
                logger.info(f"🎭 Using User Agent: {selected_agent}")
                
                # CRITICAL FIX: Check the correct headless setting
                # The settings use 'HEADLESS' not 'HEADLESS_MODE'
                headless_mode = self.settings.get('HEADLESS', False)
                logger.info(f"🖥️  Headless mode: {headless_mode}")
                
                if headless_mode:
                    options.add_argument('--headless=new')  # New headless mode
                    logger.info("🖥️  Running in HEADLESS mode")
                else:
                    logger.info("🖥️  Running in VISIBLE mode (browser will be visible)")
                
                # Create driver
                logger.info("🔧 Creating Chrome WebDriver instance...")
                self.driver = webdriver.Chrome(options=options)
                
                # Apply stealth settings
                logger.info("🥷 Applying stealth configuration...")
                stealth(
                    self.driver,
                    languages=["en-GB", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True,
                )
                
                # Configure timeouts
                timeout_value = self.settings.get('TIMEOUT', 30)
                logger.info(f"⏱️  Setting timeouts to {timeout_value} seconds")
                self.driver.set_page_load_timeout(timeout_value)
                self.driver.implicitly_wait(10)  # Add implicit wait
                self.wait = WebDriverWait(self.driver, timeout_value)
                
                # Test driver is working
                logger.info("🧪 Testing driver functionality...")
                user_agent = self.driver.execute_script("return navigator.userAgent")
                logger.info(f"🧪 Driver test successful. User agent: {user_agent}")
                
                logger.info("✅ Chrome WebDriver setup completed successfully")
                
            except Exception as e:
                logger.error(f"❌ Failed to setup Chrome WebDriver: {str(e)}")
                self.driver_restarts += 1
                if self.driver_restarts > self.max_driver_restarts:
                    raise PermanentError(f"Driver setup failed after {self.max_driver_restarts} attempts")
                raise TemporaryError(str(e))

    def teardown_driver(self) -> None:
        """Enhanced cleanup of WebDriver resources."""
        try:
            if self.driver:
                logger.info("🧹 Closing Chrome WebDriver")
                # Take screenshot before closing if in debug mode
                if self.settings.get('DEBUG_MODE', False):
                    try:
                        filename = f"debug_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        self.driver.save_screenshot(filename)
                        logger.info(f"📸 Debug screenshot saved: {filename}")
                    except:
                        pass
                
                self.driver.quit()
                self.driver = None
                self.wait = None
                logger.info("✅ Chrome WebDriver closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing Chrome WebDriver: {str(e)}")
            # Force cleanup
            self.driver = None
            self.wait = None

    @with_retry(max_attempts=3, exceptions=(TimeoutException, WebDriverException))
    def get_page(self, url: str) -> bool:
        """Enhanced page navigation with better error handling."""
        with self.error_tracking(f"get_page:{url}"):
            try:
                # Rate limiting
                logger.debug(f"🚦 Checking rate limits for {url}")
                self.rate_limiter.wait_if_needed()
                
                # Circuit breaker check
                def navigate():
                    logger.info(f"🌐 Navigating to: {url}")
                    self.driver.get(url)
                    
                    # Wait for page to be interactive
                    logger.debug("⏳ Waiting for page to become interactive...")
                    self.wait.until(
                        lambda driver: driver.execute_script(
                            "return document.readyState"
                        ) in ["interactive", "complete"]
                    )
                    
                    # Get current URL and title for verification
                    current_url = self.driver.current_url
                    title = self.driver.title
                    logger.info(f"📄 Page loaded - URL: {current_url}, Title: {title[:100]}")
                    
                    # Check for common error pages
                    if self._is_error_page():
                        raise TemporaryError("Error page detected")
                    
                    return True
                
                result = self.circuit_breaker.call(navigate)
                
                # Human-like delay
                min_delay, max_delay = self.settings.get('REQUEST_DELAY', (2, 5))
                delay = random.uniform(min_delay, max_delay)
                logger.debug(f"💤 Human-like delay: {delay:.2f} seconds")
                time.sleep(delay)
                
                return result
                
            except Exception as e:
                logger.error(f"❌ Navigation failed for {url}: {str(e)}")
                # Check if driver is still alive
                if not self._is_driver_alive():
                    logger.warning("🚨 Driver appears to be dead, attempting recovery")
                    self.setup_driver()
                    # Retry navigation after driver recovery
                    return self.get_page(url)
                raise

    def _is_driver_alive(self) -> bool:
        """Check if the WebDriver is still responsive."""
        if not self.driver:
            return False
        
        try:
            self.driver.execute_script("return true")
            return True
        except (WebDriverException, NoSuchWindowException):
            return False

    def _is_error_page(self) -> bool:
        """Detect common error pages."""
        try:
            page_source = self.driver.page_source.lower()
            error_indicators = [
                'access denied',
                '403 forbidden',
                '404 not found',
                '500 internal server error',
                'something went wrong',
                'page not available',
                'temporarily unavailable'
            ]
            return any(indicator in page_source for indicator in error_indicators)
        except:
            return False

    @transaction.atomic
    def mark_url_as_crawled(self, url: str, url_type: str) -> None:
        """Enhanced URL tracking with database transaction safety."""
        try:
            url_hash = self.get_url_hash(url)
            crawled_url, created = CrawledURL.objects.get_or_create(
                url_hash=url_hash,
                defaults={
                    'url': url,
                    'crawler_type': url_type,
                    'times_crawled': 1
                }
            )
            
            if not created:
                crawled_url.times_crawled += 1
                crawled_url.last_crawled = timezone.now()
                crawled_url.save(update_fields=['times_crawled', 'last_crawled'])
                
            logger.debug(f"🔖 Marked URL as crawled: {url} (crawled {crawled_url.times_crawled} times)")
                
        except DatabaseError as e:
            logger.error(f"❌ Database error marking URL as crawled: {str(e)}")
            # Don't fail the scraping for database issues
        except Exception as e:
            logger.error(f"❌ Error marking URL as crawled: {str(e)}")

    def should_stop(self) -> bool:
        """Check if crawler should stop."""
        # Check session status
        if self.session:
            try:
                self.session.refresh_from_db()
                if self.session.status in ['STOPPED', 'FAILED']:
                    logger.info(f"🛑 Stopping crawler due to session status: {self.session.status}")
                    return True
            except:
                pass
        
        # Check health
        if not self.health_monitor.is_healthy():
            logger.warning("🚨 Scraper health check indicates we should stop")
            return True
        
        # Check circuit breaker
        if self.circuit_breaker.state == 'OPEN':
            logger.warning("⚡ Circuit breaker is open, stopping scraper")
            return True
        
        return False

    def get_url_hash(self, url: str) -> str:
        """Generate consistent hash for URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    def handle_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Enhanced error handling with classification."""
        error_message = f"Error in {self.__class__.__name__}: {str(error)}"
        logger.error(error_message, extra=context, exc_info=True)
        
        # Classify error
        if isinstance(error, (TimeoutException, WebDriverException)):
            error_type = "temporary"
        else:
            error_type = "permanent"
        
        # Update session if available
        if self.session:
            try:
                current_log = self.session.error_log or ""
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                new_entry = f"[{timestamp}] [{error_type}] {error_message}\n"
                new_entry += f"Context: {json.dumps(context)}\n"
                new_entry += f"Traceback: {traceback.format_exc()}\n"
                new_entry += "-" * 80 + "\n"
                
                self.session.error_log = (current_log + new_entry)[-10000:]  # Keep last 10k chars
                self.session.save(update_fields=['error_log', 'updated_at'])
            except Exception as e:
                logger.error(f"❌ Error updating session error log: {str(e)}")
        
        # Take debug screenshot if enabled
        if self.settings.get('SCREENSHOT_ON_ERROR', False) and self.driver:
            try:
                filename = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(filename)
                logger.info(f"📸 Error screenshot saved: {filename}")
            except:
                pass

    @abstractmethod
    def scrape(self) -> None:
        """
        Abstract method to be implemented by specific scrapers.
        
        Each scraper type must implement its own scraping logic.
        """
        pass

    def run(self) -> None:
        """Enhanced scraper execution with comprehensive error handling."""
        start_time = time.time()
        
        try:
            logger.info(f"🚀 Starting {self.__class__.__name__}")
            
            # Update session status
            if self.session:
                self.session.status = 'RUNNING'
                self.session.started_at = timezone.now()
                self.session.save()
                logger.info(f"📊 Session {self.session.id} status updated to RUNNING")
            
            # Setup driver with recovery
            logger.info("🔧 Setting up WebDriver...")
            self.setup_driver()
            
            # CRITICAL DEBUG: Verify driver is ready
            if not self.driver:
                raise PermanentError("Driver setup completed but driver is None")
            
            logger.info("✅ WebDriver setup complete, starting scrape process...")
            
            # Run the actual scraping
            logger.info("🔍 Calling scrape() method...")
            self.scrape()
            logger.info("✅ Scrape method completed successfully")
            
            # Success - update session
            if self.session:
                self.session.status = 'COMPLETED'
                self.session.completed_at = timezone.now()
                self.session.save()
                logger.info(f"📊 Session {self.session.id} marked as COMPLETED")
            
            # Log final stats
            runtime = time.time() - start_time
            logger.info(
                f"🎉 Completed {self.__class__.__name__} - "
                f"Runtime: {runtime:.2f}s, "
                f"Processed: {len(self.processed_urls)}, "
                f"Failed: {len(self.failed_urls)}, "
                f"Health stats: {self.health_monitor.get_stats()}"
            )
            
        except PermanentError as e:
            logger.error(f"🚨 Permanent error in {self.__class__.__name__}: {str(e)}")
            if self.session:
                self.session.status = 'FAILED'
                self.session.completed_at = timezone.now()
                self.session.save()
            raise
            
        except Exception as e:
            logger.error(f"💥 Fatal error in {self.__class__.__name__}: {str(e)}", exc_info=True)
            
            # Update session status
            if self.session:
                self.session.status = 'FAILED'
                self.session.completed_at = timezone.now()
                self.session.metadata = getattr(self.session, 'metadata', {}) or {}
                self.session.metadata['fatal_error'] = {
                    'error': str(e),
                    'type': type(e).__name__,
                    'traceback': traceback.format_exc()
                }
                self.session.save()
                logger.info(f"📊 Session {self.session.id} marked as FAILED")
            
            raise
            
        finally:
            # Always cleanup
            logger.info("🧹 Starting cleanup...")
            self.teardown_driver()
            
            # Log final health report
            if hasattr(self, 'health_monitor'):
                logger.info(f"📊 Final health report: {self.health_monitor.get_stats()}")