"""
Base scraper class for ASDA website scraping.

Provides common functionality for all scraper types including
Selenium setup, stealth configuration, and error handling.
"""

import logging
import random
import time
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)
from selenium_stealth import stealth

from ..models import CrawlSession, CrawledURL, CrawlQueue

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for ASDA scrapers.

    Provides common functionality for web scraping including:
    - Selenium WebDriver management
    - Stealth mode configuration
    - Error handling and retries
    - Session management
    - URL tracking
    """

    def __init__(self, session: Optional[CrawlSession] = None) -> None:
        """
        Initialize the base scraper.

        Args:
            session: Optional CrawlSession instance for tracking progress
        """
        self.settings = settings.ASDA_SCRAPER_SETTINGS
        self.session = session
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.processed_urls: set = set()
        self.failed_urls: set = set()

    def setup_driver(self) -> None:
        """
        Set up Chrome WebDriver with stealth mode.

        Configures Chrome options for stealth browsing to avoid detection.
        """
        try:
            logger.info("Setting up Chrome WebDriver with stealth mode")

            options = Options()

            # Stealth mode options
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option(
                "excludeSwitches",
                ["enable-automation"]
            )
            options.add_experimental_option(
                'useAutomationExtension',
                False
            )

            # Performance options - modified for visibility
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-notifications')
            
            # Remove problematic options that might hide the window
            # options.add_argument('--disable-gpu')  # Commented out - can hide window
            # options.add_argument('--disable-web-security')  # Commented out
            # options.add_argument('--disable-features=VizDisplayCompositor')  # Commented out

            # Headless mode if configured
            headless_mode = self.settings.get('HEADLESS', True)
            if headless_mode:
                options.add_argument('--headless=new')
                logger.info("Running in headless mode")
            else:
                logger.info("Running with visible browser window")
                
                # Additional options for visible mode
                options.add_argument('--start-maximized')  # Start with maximized window
                # options.add_argument('--disable-background-timer-throttling')
                # options.add_argument('--disable-renderer-backgrounding')
                # options.add_argument('--disable-backgrounding-occluded-windows')

            # Window size configuration
            window_sizes = [
                (1366, 768), (1920, 1080), (1440, 900),
                (1536, 864), (1280, 720)
            ]
            width, height = random.choice(window_sizes)
            
            if not headless_mode:
                # For visible mode, use a fixed larger size for better visibility
                width, height = 1920, 1080
                
            options.add_argument(f'--window-size={width},{height}')
            logger.info(f"Setting window size to {width}x{height}")

            # Random user agent
            user_agents = self.settings.get('USER_AGENTS', [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ])
            user_agent = random.choice(user_agents)
            options.add_argument(f'user-agent={user_agent}')
            logger.info(f"Using user agent: {user_agent[:50]}...")

            # Initialize driver
            logger.info("Initializing Chrome WebDriver...")
            self.driver = webdriver.Chrome(options=options)

            # Apply stealth mode
            logger.info("Applying stealth mode...")
            stealth(
                self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

            # Set timeouts
            timeout_value = self.settings.get('TIMEOUT', 30)
            self.driver.set_page_load_timeout(timeout_value)
            self.wait = WebDriverWait(self.driver, timeout_value)
            
            # For visible mode, ensure window is brought to front
            if not headless_mode:
                try:
                    self.driver.maximize_window()
                    logger.info("Browser window maximized and brought to front")
                except Exception as e:
                    logger.warning(f"Could not maximize window: {str(e)}")

            logger.info("Chrome WebDriver setup completed successfully")

        except Exception as e:
            logger.error(f"Failed to setup Chrome WebDriver: {str(e)}")
            raise




    def teardown_driver(self) -> None:
        """Clean up WebDriver resources."""
        try:
            if self.driver:
                logger.info("Closing Chrome WebDriver")
                self.driver.quit()
                self.driver = None
                self.wait = None
        except Exception as e:
            logger.error(f"Error closing Chrome WebDriver: {str(e)}")

    def get_page(self, url: str, retry_count: int = 0) -> bool:
        """
        Navigate to a URL with retry logic.

        Args:
            url: The URL to navigate to
            retry_count: Current retry attempt number

        Returns:
            bool: True if page loaded successfully, False otherwise
        """
        max_retries = self.settings.get('MAX_RETRIES', 3)

        try:
            logger.info(f"Navigating to: {url}")
            self.driver.get(url)

            # Wait for page to be ready
            self.wait.until(
                lambda driver: driver.execute_script(
                    "return document.readyState"
                ) == "complete"
            )

            # Random delay to appear more human
            min_delay, max_delay = self.settings.get('REQUEST_DELAY', (2, 5))
            delay = random.uniform(min_delay, max_delay)
            logger.debug(f"Waiting {delay:.2f} seconds")
            time.sleep(delay)

            return True

        except TimeoutException:
            logger.warning(f"Timeout loading page: {url}")
            if retry_count < max_retries:
                logger.info(f"Retrying ({retry_count + 1}/{max_retries})")
                return self.get_page(url, retry_count + 1)
            return False

        except Exception as e:
            logger.error(f"Error loading page {url}: {str(e)}")
            if retry_count < max_retries:
                logger.info(f"Retrying ({retry_count + 1}/{max_retries})")
                return self.get_page(url, retry_count + 1)
            return False

    def is_valid_url(self, url: str) -> bool:
        """
        Check if URL is valid and from allowed domains.

        Args:
            url: URL to validate

        Returns:
            bool: True if URL is valid, False otherwise
        """
        try:
            parsed = urlparse(url)
            allowed_domains = self.settings.get('ALLOWED_DOMAINS', [])

            # Check if domain is allowed
            if not any(domain in parsed.netloc for domain in allowed_domains):
                logger.warning(f"URL not from allowed domain: {url}")
                return False

            # Check for blocked extensions
            blocked_extensions = self.settings.get('BLOCKED_EXTENSIONS', [])
            if any(url.lower().endswith(ext) for ext in blocked_extensions):
                logger.debug(f"URL has blocked extension: {url}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating URL {url}: {str(e)}")
            return False

    def get_url_hash(self, url: str) -> str:
        """
        Generate SHA256 hash of URL.

        Args:
            url: URL to hash

        Returns:
            str: SHA256 hash of the URL
        """
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def mark_url_as_crawled(self, url: str, crawler_type: str) -> None:
        """
        Mark URL as crawled in the database.

        Args:
            url: The URL that was crawled
            crawler_type: Type of crawler that processed the URL
        """
        try:
            url_hash = self.get_url_hash(url)
            CrawledURL.objects.update_or_create(
                url_hash=url_hash,
                defaults={
                    'url': url,
                    'crawler_type': crawler_type,
                    'last_crawled': timezone.now(),
                    'times_crawled': CrawledURL.objects.filter(
                        url_hash=url_hash
                    ).values_list('times_crawled', flat=True).first() or 0 + 1
                }
            )
            logger.debug(f"Marked URL as crawled: {url}")
        except Exception as e:
            logger.error(f"Error marking URL as crawled: {str(e)}")

    def update_session_stats(
        self,
        processed: int = 0,
        failed: int = 0
    ) -> None:
        """
        Update crawl session statistics.

        Args:
            processed: Number of items processed
            failed: Number of items failed
        """
        if self.session:
            try:
                self.session.processed_items += processed
                self.session.failed_items += failed
                
                # Only update the fields that actually exist in the model
                self.session.save(update_fields=[
                    'processed_items',
                    'failed_items'
                ])
                
                logger.debug(f"Updated session stats: +{processed} processed, +{failed} failed")
                
            except Exception as e:
                logger.error(f"Error updating session stats: {str(e)}")
                # Fallback: try saving without update_fields
                try:
                    self.session.save()
                    logger.debug("Session stats updated with fallback save")
                except Exception as fallback_error:
                    logger.error(f"Fallback save also failed: {str(fallback_error)}")

    def should_stop(self) -> bool:
        """
        Check if the crawler should stop processing.

        Returns:
            bool: True if crawler should stop, False otherwise
        """
        if not self.session:
            return False

        try:
            # Refresh session from database to get latest status
            self.session.refresh_from_db()
            return self.session.status in ['STOPPED', 'FAILED']
        except Exception as e:
            logger.error(f"Error checking session status: {str(e)}")
            return False

    def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> None:
        """
        Handle and log errors with context.

        Args:
            error: The exception that occurred
            context: Additional context about the error
        """
        error_message = f"Error in {self.__class__.__name__}: {str(error)}"
        logger.error(error_message, extra=context, exc_info=True)

        if self.session:
            try:
                # Append to error log
                current_log = self.session.error_log or ""
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                new_entry = f"[{timestamp}] {error_message}\n"
                self.session.error_log = current_log + new_entry
                self.session.save(update_fields=['error_log', 'updated_at'])
            except Exception as e:
                logger.error(f"Error updating session error log: {str(e)}")

    @abstractmethod
    def scrape(self) -> None:
        """
        Abstract method to be implemented by specific scrapers.

        Each scraper type must implement its own scraping logic.
        """
        pass

    def run(self) -> None:
        """
        Run the scraper with proper setup and teardown.

        Handles the complete scraping lifecycle including:
        - Driver setup
        - Scraping execution
        - Error handling
        - Cleanup
        """
        try:
            logger.info(f"Starting {self.__class__.__name__}")

            # Update session status
            if self.session:
                self.session.status = 'RUNNING'
                self.session.save()

            # Setup driver
            self.setup_driver()

            # Run the actual scraping
            self.scrape()

            # Update session status
            if self.session:
                self.session.status = 'COMPLETED'
                self.session.completed_at = timezone.now()
                self.session.save()

            logger.info(
                f"Completed {self.__class__.__name__} - "
                f"Processed: {len(self.processed_urls)}, "
                f"Failed: {len(self.failed_urls)}"
            )

        except Exception as e:
            logger.error(f"Fatal error in {self.__class__.__name__}: {str(e)}")

            # Update session status
            if self.session:
                self.session.status = 'FAILED'
                self.session.completed_at = timezone.now()
                self.session.save()

            raise

        finally:
            # Always cleanup
            self.teardown_driver()
