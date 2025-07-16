"""
Enhanced base scraper class for ASDA website scraping.

Provides improved error handling, resilience patterns, and monitoring
for stable and reliable web scraping operations.
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
                        current_delay = min(current_delay * backoff, 30)  # Cap at 30 seconds
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            raise last_exception
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Enhanced circuit breaker pattern implementation.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception_types: tuple = (Exception,)
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception_types: Tuple of exceptions that trigger the breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception_types = expected_exception_types
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.success_count = 0
        self.last_exception = None
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        """
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                time_remaining = self.recovery_timeout - (time.time() - self.last_failure_time)
                raise ScraperException(
                    f"Circuit breaker is OPEN. Failure count: {self.failure_count}. "
                    f"Retry in {time_remaining:.0f}s. Last error: {self.last_exception}"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception_types as e:
            self._on_failure(e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful function call."""
        self.success_count += 1
        
        # In HALF_OPEN state, close circuit after sufficient successes
        if self.state == 'HALF_OPEN' and self.success_count >= 3:
            self.failure_count = 0
            self.state = 'CLOSED'
            self.last_exception = None
            logger.info("Circuit breaker reset to CLOSED state")
        elif self.state == 'CLOSED':
            self.failure_count = max(0, self.failure_count - 1)  # Decay failure count
    
    def _on_failure(self, exception: Exception) -> None:
        """Handle failed function call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.last_exception = str(exception)
        self.success_count = 0
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures. "
                f"Last error: {self.last_exception}"
            )


class RateLimiter:
    """
    Enhanced token bucket rate limiter with burst support.
    """
    
    def __init__(
        self,
        max_requests: int = 60,
        time_window: int = 60,
        burst_size: int = 10
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
            burst_size: Maximum burst size allowed
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_size = burst_size
        self.requests = deque()
        self.tokens = burst_size
        self.last_refill = time.time()
        self.refill_rate = max_requests / time_window
    
    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        current_time = time.time()
        
        # Refill tokens based on time passed
        time_passed = current_time - self.last_refill
        self.tokens = min(
            self.burst_size,
            self.tokens + (time_passed * self.refill_rate)
        )
        self.last_refill = current_time
        
        # Remove old requests outside time window
        while self.requests and current_time - self.requests[0] > self.time_window:
            self.requests.popleft()
        
        # Check if we need to wait
        if self.tokens < 1:
            # Calculate wait time
            wait_time = (1 - self.tokens) / self.refill_rate
            logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s")
            time.sleep(wait_time)
            self.tokens = 1
        
        # Consume a token and record request
        self.tokens -= 1
        self.requests.append(current_time)


class HealthMonitor:
    """
    Monitor scraper health and performance metrics.
    """
    
    def __init__(self, error_threshold: float = 0.1):
        """
        Initialize health monitor.
        
        Args:
            error_threshold: Maximum acceptable error rate
        """
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
            'recent_errors': list(self.recent_errors)[-10:],  # Last 10 errors
        }


class BaseScraper(ABC):
    """
    Enhanced abstract base class for ASDA scrapers with improved stability.
    """

    def __init__(self, session: Optional[CrawlSession] = None) -> None:
        """
        Initialize the enhanced base scraper.

        Args:
            session: Optional CrawlSession instance for tracking progress
        """
        self.settings = settings.ASDA_SCRAPER_SETTINGS
        self.session = session
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.processed_urls: set = set()
        self.failed_urls: set = set()
        
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
        
        logger.info("Enhanced scraper initialized with resilience components")

    @contextmanager
    def error_tracking(self, context: str):
        """
        Context manager for consistent error tracking.
        
        Args:
            context: Description of the operation being performed
        """
        start_time = time.time()
        try:
            yield
            duration = time.time() - start_time
            self.health_monitor.record_request(True, duration)
        except Exception as e:
            duration = time.time() - start_time
            self.health_monitor.record_request(False, duration, e)
            logger.error(f"Error in {context}: {str(e)}", exc_info=True)
            
            # Check if we should continue
            if not self.health_monitor.is_healthy():
                logger.critical(
                    f"Health check failed. Error rate too high: "
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
        """
        Enhanced Chrome WebDriver setup with better error recovery.
        """
        with self.error_tracking("driver_setup"):
            try:
                # Clean up any existing driver
                if self.driver:
                    self.teardown_driver()
                
                logger.info("Setting up Chrome WebDriver with enhanced stealth mode")

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
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                ]
                options.add_argument(f'user-agent={random.choice(user_agents)}')
                
                # Headless mode control
                if self.settings.get('HEADLESS_MODE', False):
                    options.add_argument('--headless=new')  # New headless mode
                
                # Create driver
                self.driver = webdriver.Chrome(options=options)
                
                # Apply stealth settings
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
                self.driver.set_page_load_timeout(timeout_value)
                self.driver.implicitly_wait(10)  # Add implicit wait
                self.wait = WebDriverWait(self.driver, timeout_value)
                
                # Test driver is working
                self.driver.execute_script("return navigator.userAgent")
                
                logger.info("Chrome WebDriver setup completed successfully")
                
            except Exception as e:
                logger.error(f"Failed to setup Chrome WebDriver: {str(e)}")
                self.driver_restarts += 1
                if self.driver_restarts > self.max_driver_restarts:
                    raise PermanentError(f"Driver setup failed after {self.max_driver_restarts} attempts")
                raise TemporaryError(str(e))

    def teardown_driver(self) -> None:
        """Enhanced cleanup of WebDriver resources."""
        try:
            if self.driver:
                logger.info("Closing Chrome WebDriver")
                # Take screenshot before closing if in debug mode
                if self.settings.get('DEBUG_MODE', False):
                    try:
                        self.driver.save_screenshot(
                            f"debug_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        )
                    except:
                        pass
                
                self.driver.quit()
                self.driver = None
                self.wait = None
        except Exception as e:
            logger.error(f"Error closing Chrome WebDriver: {str(e)}")
            # Force cleanup
            self.driver = None
            self.wait = None

    @with_retry(max_attempts=3, exceptions=(TimeoutException, WebDriverException))
    def get_page(self, url: str) -> bool:
        """
        Enhanced page navigation with better error handling.
        
        Args:
            url: The URL to navigate to
            
        Returns:
            bool: True if page loaded successfully, False otherwise
        """
        with self.error_tracking(f"get_page:{url}"):
            try:
                # Rate limiting
                self.rate_limiter.wait_if_needed()
                
                # Circuit breaker check
                def navigate():
                    logger.info(f"Navigating to: {url}")
                    self.driver.get(url)
                    
                    # Wait for page to be interactive
                    self.wait.until(
                        lambda driver: driver.execute_script(
                            "return document.readyState"
                        ) in ["interactive", "complete"]
                    )
                    
                    # Check for common error pages
                    if self._is_error_page():
                        raise TemporaryError("Error page detected")
                    
                    return True
                
                result = self.circuit_breaker.call(navigate)
                
                # Human-like delay
                min_delay, max_delay = self.settings.get('REQUEST_DELAY', (2, 5))
                delay = random.uniform(min_delay, max_delay)
                logger.debug(f"Waiting {delay:.2f} seconds")
                time.sleep(delay)
                
                return result
                
            except Exception as e:
                # Check if driver is still alive
                if not self._is_driver_alive():
                    logger.warning("Driver appears to be dead, attempting recovery")
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
        """
        Enhanced URL tracking with database transaction safety.
        
        Args:
            url: The URL that was crawled
            url_type: Type of URL (CATEGORY, PRODUCT_LIST, etc.)
        """
        try:
            url_hash = self.get_url_hash(url)
            
            CrawledURL.objects.update_or_create(
                url_hash=url_hash,
                defaults={
                    'url': url,
                    'url_type': url_type,
                    'crawled_at': timezone.now(),
                    'session': self.session,
                }
            )
            self.processed_urls.add(url)
            logger.debug(f"Marked as crawled: {url}")
            
        except DatabaseError as e:
            logger.error(f"Database error marking URL as crawled: {str(e)}")
            # Don't fail the entire operation for tracking issues
        except Exception as e:
            logger.error(f"Error marking URL as crawled: {str(e)}")

    def update_session_stats(self, processed: int = 0, failed: int = 0) -> None:
        """
        Enhanced session statistics update with safety checks.
        
        Args:
            processed: Number of items processed
            failed: Number of items failed
        """
        if not self.session:
            return
            
        try:
            with transaction.atomic():
                # Refresh from DB to avoid race conditions
                self.session.refresh_from_db()
                self.session.processed_items += processed
                self.session.failed_items += failed
                
                # Update health stats
                stats = self.health_monitor.get_stats()
                self.session.metadata = self.session.metadata or {}
                self.session.metadata['health_stats'] = stats
                
                self.session.save(update_fields=[
                    'processed_items',
                    'failed_items',
                    'metadata',
                    'updated_at'
                ])
                
        except Exception as e:
            logger.error(f"Error updating session stats: {str(e)}")

    def should_stop(self) -> bool:
        """
        Enhanced stop condition checking.
        
        Returns:
            bool: True if crawler should stop, False otherwise
        """
        # Check session status
        if self.session:
            try:
                self.session.refresh_from_db()
                if self.session.status in ['STOPPED', 'FAILED']:
                    return True
            except:
                pass
        
        # Check health
        if not self.health_monitor.is_healthy():
            logger.warning("Scraper health check indicates we should stop")
            return True
        
        # Check circuit breaker
        if self.circuit_breaker.state == 'OPEN':
            logger.warning("Circuit breaker is open, stopping scraper")
            return True
        
        return False

    def get_url_hash(self, url: str) -> str:
        """Generate consistent hash for URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    def handle_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Enhanced error handling with classification.
        
        Args:
            error: The exception that occurred
            context: Additional context about the error
        """
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
                logger.error(f"Error updating session error log: {str(e)}")
        
        # Take debug screenshot if enabled
        if self.settings.get('SCREENSHOT_ON_ERROR', False) and self.driver:
            try:
                filename = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(filename)
                logger.info(f"Error screenshot saved: {filename}")
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
        """
        Enhanced scraper execution with comprehensive error handling.
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting {self.__class__.__name__}")
            
            # Update session status
            if self.session:
                self.session.status = 'RUNNING'
                self.session.started_at = timezone.now()
                self.session.save()
            
            # Setup driver with recovery
            self.setup_driver()
            
            # Run the actual scraping
            self.scrape()
            
            # Success - update session
            if self.session:
                self.session.status = 'COMPLETED'
                self.session.completed_at = timezone.now()
                self.session.save()
            
            # Log final stats
            runtime = time.time() - start_time
            logger.info(
                f"Completed {self.__class__.__name__} - "
                f"Runtime: {runtime:.2f}s, "
                f"Processed: {len(self.processed_urls)}, "
                f"Failed: {len(self.failed_urls)}, "
                f"Health stats: {self.health_monitor.get_stats()}"
            )
            
        except PermanentError as e:
            logger.error(f"Permanent error in {self.__class__.__name__}: {str(e)}")
            if self.session:
                self.session.status = 'FAILED'
                self.session.completed_at = timezone.now()
                self.session.save()
            raise
            
        except Exception as e:
            logger.error(f"Fatal error in {self.__class__.__name__}: {str(e)}", exc_info=True)
            
            # Update session status
            if self.session:
                self.session.status = 'FAILED'
                self.session.completed_at = timezone.now()
                self.session.metadata = self.session.metadata or {}
                self.session.metadata['fatal_error'] = {
                    'error': str(e),
                    'type': type(e).__name__,
                    'traceback': traceback.format_exc()
                }
                self.session.save()
            
            raise
            
        finally:
            # Always cleanup
            self.teardown_driver()
            
            # Log final health report
            if hasattr(self, 'health_monitor'):
                logger.info(f"Final health report: {self.health_monitor.get_stats()}")