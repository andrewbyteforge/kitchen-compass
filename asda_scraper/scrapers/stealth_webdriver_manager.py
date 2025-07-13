"""
Stealth WebDriver Manager to avoid bot detection.

File: asda_scraper/scrapers/stealth_webdriver_manager.py
"""

import logging
import time
import random
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)


class StealthWebDriverManager:
    """
    WebDriver manager designed to avoid bot detection by mimicking real browser behavior.
    """
    
    def __init__(self, headless: bool = False):
        """
        Initialize stealth WebDriver manager.
        
        Args:
            headless: Whether to run in headless mode
        """
        self.headless = headless
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
    
    def setup_stealth_driver(self) -> webdriver.Chrome:
        """
        Set up Chrome driver with anti-detection measures.
        
        Returns:
            webdriver.Chrome: Configured stealth Chrome driver
        """
        try:
            logger.info("🥷 Setting up stealth Chrome driver...")
            
            options = Options()
            
            # Basic stealth options
            if self.headless:
                options.add_argument("--headless")
            
            # Anti-detection arguments
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Realistic browser behavior
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-features=TranslateUI")
            
            # Realistic window size
            options.add_argument("--window-size=1366,768")
            
            # Random user agent
            user_agent = random.choice(self.user_agents)
            options.add_argument(f"--user-agent={user_agent}")
            logger.info(f"🎭 Using user agent: {user_agent[:50]}...")
            
            # Language and locale
            options.add_argument("--lang=en-GB")
            options.add_argument("--accept-lang=en-GB,en;q=0.9")
            
            # Preferences to look more human
            prefs = {
                "profile.default_content_setting_values": {
                    "notifications": 2,
                    "popups": 2,
                    "media_stream": 2,
                    "geolocation": 2
                },
                "profile.managed_default_content_settings": {
                    "images": 1  # Allow images
                },
                "profile.default_content_settings": {
                    "popups": 0
                }
            }
            options.add_experimental_option("prefs", prefs)
            
            # Create driver
            driver = webdriver.Chrome(options=options)
            
            # Execute stealth JavaScript to remove automation indicators
            self._execute_stealth_scripts(driver)
            
            # Set realistic timeouts
            driver.implicitly_wait(10)
            driver.set_page_load_timeout(30)
            
            logger.info("✅ Stealth driver setup complete")
            return driver
            
        except Exception as e:
            logger.error(f"❌ Failed to setup stealth driver: {e}")
            raise
    
    def _execute_stealth_scripts(self, driver: webdriver.Chrome):
        """
        Execute JavaScript to make the browser appear more human.
        
        Args:
            driver: Chrome WebDriver instance
        """
        try:
            # Remove webdriver property
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Mock plugins
            driver.execute_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            
            # Mock languages
            driver.execute_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-GB', 'en', 'en-US'],
                });
            """)
            
            # Mock permissions
            driver.execute_script("""
                const originalQuery = window.navigator.permissions.query;
                return window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
            # Mock chrome runtime
            driver.execute_script("""
                window.chrome = {
                    runtime: {}
                };
            """)
            
            logger.debug("🥷 Stealth scripts executed")
            
        except Exception as e:
            logger.warning(f"⚠️  Stealth script execution failed: {e}")
    
    def navigate_like_human(self, driver: webdriver.Chrome, url: str) -> bool:
        """
        Navigate to URL with human-like behavior.
        
        Args:
            driver: Chrome WebDriver instance
            url: URL to navigate to
            
        Returns:
            bool: True if navigation successful
        """
        try:
            logger.info(f"🌐 Navigating like human to: {url}")
            
            # Random delay before navigation
            time.sleep(random.uniform(1.0, 3.0))
            
            # Navigate to URL
            driver.get(url)
            
            # Wait for initial load
            time.sleep(random.uniform(2.0, 4.0))
            
            # Check if page loaded
            if self._is_page_loaded(driver):
                logger.info("✅ Page loaded successfully")
                
                # Human-like behavior: scroll a bit
                self._simulate_human_behavior(driver)
                
                return True
            else:
                logger.warning("⚠️  Page may not have loaded completely")
                return False
                
        except Exception as e:
            logger.error(f"❌ Navigation failed: {e}")
            return False
    
    def _is_page_loaded(self, driver: webdriver.Chrome) -> bool:
        """
        Check if page has loaded completely.
        
        Args:
            driver: Chrome WebDriver instance
            
        Returns:
            bool: True if page appears loaded
        """
        try:
            # Check if body exists and has content
            body = driver.find_element(By.TAG_NAME, "body")
            body_text = body.text.strip()
            
            # Check page title
            title = driver.title
            
            # Basic checks
            if len(body_text) > 100 and title and "asda" in driver.current_url.lower():
                return True
            
            # Check for loading indicators
            loading_selectors = [
                "[class*='loading']",
                "[class*='spinner']",
                ".loader"
            ]
            
            for selector in loading_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if any(el.is_displayed() for el in elements):
                        logger.info("🔄 Loading indicators still visible")
                        return False
                except:
                    continue
            
            return len(body_text) > 50  # Minimal content check
            
        except Exception as e:
            logger.debug(f"Error checking page load: {e}")
            return False
    
    def _simulate_human_behavior(self, driver: webdriver.Chrome):
        """
        Simulate human-like behavior on the page.
        
        Args:
            driver: Chrome WebDriver instance
        """
        try:
            # Random scroll
            scroll_amount = random.randint(200, 800)
            driver.execute_script(f"window.scrollTo(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))
            
            # Scroll back up a bit
            scroll_back = random.randint(50, 200)
            driver.execute_script(f"window.scrollTo(0, {scroll_amount - scroll_back});")
            time.sleep(random.uniform(0.5, 1.0))
            
            logger.debug("🤖 Simulated human scrolling behavior")
            
        except Exception as e:
            logger.debug(f"Human behavior simulation failed: {e}")
    
    def handle_access_denied(self, driver: webdriver.Chrome) -> bool:
        """
        Handle access denied or bot detection pages.
        
        Args:
            driver: Chrome WebDriver instance
            
        Returns:
            bool: True if handled successfully
        """
        try:
            page_title = driver.title.lower()
            page_source = driver.page_source.lower()
            
            # Check for common access denied indicators
            access_denied_indicators = [
                "access denied", "blocked", "forbidden", "403", "bot detected",
                "security check", "cloudflare", "please verify", "captcha"
            ]
            
            is_blocked = any(
                indicator in page_title or indicator in page_source 
                for indicator in access_denied_indicators
            )
            
            if is_blocked:
                logger.warning("🚫 Access denied or bot detection detected")
                logger.info("💡 Try:")
                logger.info("   • Using VPN with UK IP")
                logger.info("   • Increasing delays between requests")
                logger.info("   • Running in non-headless mode")
                logger.info("   • Using different user agent")
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking access: {e}")
            return True