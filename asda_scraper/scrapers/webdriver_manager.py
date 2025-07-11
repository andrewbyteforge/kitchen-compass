"""
WebDriver management for ASDA scraper.

File: asda_scraper/scrapers/webdriver_manager.py
"""

import logging
import os
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
    Manages WebDriver setup and configuration.
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
        Set up Chrome WebDriver with improved Windows compatibility.
        
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
        Get Chrome options configuration.
        
        Returns:
            Options: Configured Chrome options
        """
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
            f"--window-size={SELENIUM_CONFIG['window_size']}",
            f"--user-agent={SELENIUM_CONFIG['user_agent']}"
        ]
        
        for option in options_list:
            chrome_options.add_argument(option)
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
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
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    
    def _setup_with_system_chrome(self, chrome_options: Options) -> webdriver.Chrome:
        """
        Setup driver using system Chrome installation.
        
        Args:
            chrome_options: Chrome options configuration
            
        Returns:
            webdriver.Chrome: Chrome driver instance
        """
        logger.info("Attempting system Chrome setup...")
        return webdriver.Chrome(options=chrome_options)
    
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
            "./chromedriver.exe",
            "chromedriver.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Trying manual path: {path}")
                service = Service(path)
                return webdriver.Chrome(service=service, options=chrome_options)
        
        raise Exception("No valid chromedriver path found")
    
    def _configure_driver(self) -> None:
        """
        Configure driver after setup.
        """
        # Set timeouts
        self.driver.set_page_load_timeout(SELENIUM_CONFIG['page_load_timeout'])
        self.driver.implicitly_wait(SELENIUM_CONFIG['implicit_wait'])
        
        # Set up WebDriverWait
        self.wait = WebDriverWait(self.driver, SELENIUM_CONFIG['default_timeout'])
        
        # Remove navigator.webdriver flag
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        # Test the driver
        self.driver.get("about:blank")
        logger.info("WebDriver test successful")
    
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