"""
Enhanced WebDriver management for ASDA scraper with fixed configuration.

File: asda_scraper/scrapers/webdriver_manager.py
"""

import logging
import os
import random
from typing import Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from .config import SELENIUM_CONFIG
from .exceptions import DriverSetupException

logger = logging.getLogger(__name__)


class WebDriverManager:
    """
    Enhanced WebDriver manager with proper configuration handling.
    """
    
    def __init__(self, headless: bool = False):
        """
        Initialize WebDriver manager.
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.driver = None
        self.wait = None
        
    def setup_driver(self) -> webdriver.Chrome:
        """
        Set up Chrome WebDriver with improved Windows compatibility and config handling.
        
        Returns:
            webdriver.Chrome: Configured Chrome driver instance
            
        Raises:
            DriverSetupException: If driver setup fails
        """
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
                        logger.info("WebDriver setup successful")
                        return self.driver
                except Exception as e:
                    logger.warning(f"Setup method failed: {e}")
                    continue
            
            raise DriverSetupException("All WebDriver setup methods failed")
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {e}")
            raise DriverSetupException(f"WebDriver setup failed: {e}")
    
    def _get_chrome_options(self) -> Options:
        """
        Get Chrome options configuration with proper config handling.
        
        Returns:
            Options: Configured Chrome options
        """
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--disable-gpu")
            
            # Get window size - handle both old and new config formats
            window_size = self._get_window_size()
            
            # Get user agent - handle both old and new config formats  
            user_agent = self._get_user_agent()
            
            # Essential options for web scraping
            options_list = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--disable-web-security",
                "--allow-running-insecure-content",
                "--disable-features=VizDisplayCompositor",
                "--disable-ipc-flooding-protection",
                f"--window-size={window_size}",
                f"--user-agent={user_agent}"
            ]
            
            for option in options_list:
                chrome_options.add_argument(option)
            
            # Experimental options to avoid detection
            experimental_options = SELENIUM_CONFIG.get('experimental_options', {})
            for key, value in experimental_options.items():
                chrome_options.add_experimental_option(key, value)
            
            # Additional stealth options
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            logger.debug(f"Chrome options configured with window size: {window_size}")
            return chrome_options
            
        except Exception as e:
            logger.error(f"Error configuring Chrome options: {e}")
            # Fallback to basic options
            return self._get_fallback_chrome_options()
    
    def _get_window_size(self) -> str:
        """
        Get window size from config with fallback handling.
        
        Returns:
            str: Window size in format "width,height"
        """
        try:
            # Try new config format first (window_sizes list)
            if 'window_sizes' in SELENIUM_CONFIG:
                window_sizes = SELENIUM_CONFIG['window_sizes']
                if isinstance(window_sizes, list) and window_sizes:
                    # Randomly select a window size for variety
                    return random.choice(window_sizes)
            
            # Try old config format (single window_size)
            if 'window_size' in SELENIUM_CONFIG:
                return SELENIUM_CONFIG['window_size']
            
            # Default fallback
            return "1920,1080"
            
        except Exception as e:
            logger.warning(f"Error getting window size from config: {e}")
            return "1920,1080"
    
    def _get_user_agent(self) -> str:
        """
        Get user agent from config with fallback handling.
        
        Returns:
            str: User agent string
        """
        try:
            # Try new config format first (user_agents list)
            if 'user_agents' in SELENIUM_CONFIG:
                user_agents = SELENIUM_CONFIG['user_agents']
                if isinstance(user_agents, list) and user_agents:
                    # Randomly select a user agent for variety
                    return random.choice(user_agents)
            
            # Try old config format (single user_agent)
            if 'user_agent' in SELENIUM_CONFIG:
                return SELENIUM_CONFIG['user_agent']
            
            # Default fallback
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
        except Exception as e:
            logger.warning(f"Error getting user agent from config: {e}")
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def _get_fallback_chrome_options(self) -> Options:
        """
        Get minimal Chrome options as fallback.
        
        Returns:
            Options: Basic Chrome options
        """
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        # Essential minimal options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        logger.info("Using fallback Chrome options")
        return chrome_options
    
    def _setup_with_chrome_driver_manager(self, chrome_options: Options) -> webdriver.Chrome:
        """
        Setup driver using ChromeDriverManager auto-download.
        
        Args:
            chrome_options: Chrome options configuration
            
        Returns:
            webdriver.Chrome: Chrome driver instance
        """
        logger.info("Attempting ChromeDriverManager auto-download...")
        try:
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.error(f"ChromeDriverManager setup failed: {e}")
            raise
    
    def _setup_with_system_chrome(self, chrome_options: Options) -> webdriver.Chrome:
        """
        Setup driver using system Chrome installation.
        
        Args:
            chrome_options: Chrome options configuration
            
        Returns:
            webdriver.Chrome: Chrome driver instance
        """
        logger.info("Attempting system Chrome setup...")
        try:
            return webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error(f"System Chrome setup failed: {e}")
            raise
    
    def _setup_with_manual_paths(self, chrome_options: Options) -> webdriver.Chrome:
        """
        Setup driver using manual chromedriver paths.
        
        Args:
            chrome_options: Chrome options configuration
            
        Returns:
            webdriver.Chrome: Chrome driver instance
            
        Raises:
            Exception: If no valid chromedriver path found
        """
        possible_paths = [
            r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
            r"C:\chromedriver\chromedriver.exe",
            r"C:\WebDriver\bin\chromedriver.exe",
            "./chromedriver.exe",
            "chromedriver.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Trying manual path: {path}")
                try:
                    service = Service(path)
                    return webdriver.Chrome(service=service, options=chrome_options)
                except Exception as e:
                    logger.warning(f"Manual path {path} failed: {e}")
                    continue
        
        raise Exception("No valid chromedriver path found")
    
    def _configure_driver(self) -> None:
        """
        Configure driver after setup with proper timeout handling.
        """
        try:
            # Set timeouts with fallback values
            page_load_timeout = SELENIUM_CONFIG.get('page_load_timeout', 30)
            implicit_wait = SELENIUM_CONFIG.get('implicit_wait', 5)
            default_timeout = SELENIUM_CONFIG.get('default_timeout', 15)
            
            self.driver.set_page_load_timeout(page_load_timeout)
            self.driver.implicitly_wait(implicit_wait)
            
            # Set up WebDriverWait
            self.wait = WebDriverWait(self.driver, default_timeout)
            
            # Remove navigator.webdriver flag to avoid detection
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            # Test the driver
            self.driver.get("about:blank")
            logger.info("WebDriver test successful")
            
        except Exception as e:
            logger.error(f"Error configuring WebDriver: {e}")
            raise
    
    def cleanup(self) -> None:
        """
        Clean up WebDriver resources.
        """
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver cleanup complete")
            except Exception as e:
                logger.error(f"Error during WebDriver cleanup: {e}")
    
    def get_wait(self) -> WebDriverWait:
        """
        Get the WebDriverWait instance.
        
        Returns:
            WebDriverWait: WebDriverWait instance for explicit waits
        """
        return self.wait if self.wait else WebDriverWait(self.driver, 10)