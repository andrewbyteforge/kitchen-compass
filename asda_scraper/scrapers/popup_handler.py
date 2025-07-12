"""
Optimized popup and cookie banner handler for ASDA scraper.

File: asda_scraper/scrapers/popup_handler.py
"""

import logging
import time
from typing import List, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException

logger = logging.getLogger(__name__)


class PopupHandler:
    """
    Handles cookie banners and other popups on ASDA website.
    Optimized with reduced timeout and faster detection.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize popup handler.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.max_timeout = 3  # Reduced from 8 seconds
        self.quick_timeout = 0.5  # Reduced from 2 seconds
        self._popup_handled_cache = set()  # Cache handled popup URLs
    
    def handle_popups(self, timeout: int = None) -> int:
        """
        Handle cookie banners and other popups with optimized detection.
        
        Args:
            timeout: Maximum time to spend handling popups (default: 3 seconds)
        
        Returns:
            int: Number of popups handled
        """
        timeout = timeout or self.max_timeout
        start_time = time.time()
        current_url = self.driver.current_url
        
        try:
            # Check cache first
            if current_url in self._popup_handled_cache:
                logger.debug("Popups already handled for this URL")
                return 0
            
            logger.debug("Checking for popups and cookie banners")
            
            # Quick initial check - if page title indicates error, skip
            if self._is_error_page():
                logger.info("Error page detected, skipping popup handling")
                return 0
            
            popups_handled = 0
            
            # Phase 1: Quick common popup check
            popups_handled += self._handle_common_popups_fast()
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.debug(f"Popup handling timeout ({timeout}s) reached")
                return popups_handled
            
            # Phase 2: Only if no popups found and time remaining
            if popups_handled == 0 and (timeout - elapsed) > 0.5:
                remaining_timeout = timeout - elapsed
                popups_handled += self._handle_additional_popups(remaining_timeout)
            
            # Cache URL if popups were handled
            if popups_handled > 0:
                self._popup_handled_cache.add(current_url)
                logger.info(f"Handled {popups_handled} popups in {elapsed:.1f}s")
            else:
                logger.debug(f"No popups found (checked in {elapsed:.1f}s)")
            
            return popups_handled
                
        except Exception as e:
            elapsed = time.time() - start_time
            logger.debug(f"Error handling popups after {elapsed:.1f}s: {e}")
            return 0
    
    def _is_error_page(self) -> bool:
        """
        Quick check if current page is an error page.
        
        Returns:
            bool: True if error page detected
        """
        try:
            title = self.driver.title.lower()
            error_indicators = ['404', 'error', 'not found', 'access denied', 'blocked']
            return any(indicator in title for indicator in error_indicators)
        except:
            return False
    
    def _handle_common_popups_fast(self) -> int:
        """
        Handle the most common popups quickly with minimal waiting.
        
        Returns:
            int: Number of popups handled
        """
        try:
            # Most common ASDA popup selectors (prioritized by frequency)
            common_selectors = [
                "button#onetrust-accept-btn-handler",  # Most common ASDA cookie button
                "button[id*='accept']",
                "button[class*='accept']",
                "#accept-cookies",
                "button.privacy-prompt__button--accept",
                "[data-auto-id='privacy-accept-all']",
                "button[aria-label*='Accept all']"
            ]
            
            for selector in common_selectors:
                try:
                    # Very quick check with minimal wait
                    element = WebDriverWait(self.driver, self.quick_timeout).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    if self._click_element_safely(element):
                        logger.info(f"Clicked common popup: {selector}")
                        time.sleep(0.2)  # Very brief pause
                        return 1
                        
                except (TimeoutException, NoSuchElementException):
                    continue
                except Exception as e:
                    logger.debug(f"Common popup selector {selector} failed: {e}")
                    continue
            
            return 0
            
        except Exception as e:
            logger.debug(f"Error in common popup handling: {e}")
            return 0
    
    def _handle_additional_popups(self, remaining_timeout: float) -> int:
        """
        Handle less common popups if time permits.
        
        Args:
            remaining_timeout: Time remaining for popup handling
        
        Returns:
            int: Number of popups handled
        """
        if remaining_timeout < 0.5:
            return 0
        
        try:
            start_time = time.time()
            popup_selectors = self._get_additional_popup_selectors()
            popups_handled = 0
            
            for selector in popup_selectors:
                # Check timeout
                if time.time() - start_time > remaining_timeout:
                    break
                
                try:
                    elements = self._find_elements_quickly(selector)
                    
                    for element in elements[:1]:  # Only try first element
                        if self._is_element_clickable_fast(element):
                            if self._click_element_safely(element):
                                logger.info(f"Clicked popup with selector: {selector}")
                                popups_handled += 1
                                return popups_handled
                    
                except Exception as e:
                    logger.debug(f"Popup selector {selector} failed: {e}")
                    continue
            
            return popups_handled
            
        except Exception as e:
            logger.debug(f"Error in additional popup handling: {e}")
            return 0
    
    def _get_additional_popup_selectors(self) -> List[str]:
        """
        Get list of additional popup selectors.
        
        Returns:
            List[str]: CSS selectors for less common popups
        """
        return [
            # Close buttons
            "button[aria-label*='close' i]",
            ".modal-close",
            ".popup-close",
            "[data-testid*='close']",
            
            # Banner buttons
            ".notification-banner button",
            ".banner-close",
            ".consent-banner button",
        ]
    
    def _find_elements_quickly(self, selector: str) -> List:
        """
        Find elements quickly without waiting.
        
        Args:
            selector: CSS selector string
            
        Returns:
            List: Found elements
        """
        try:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            return []
    
    def _is_element_clickable_fast(self, element) -> bool:
        """
        Quick check if element is clickable.
        
        Args:
            element: WebElement to check
            
        Returns:
            bool: True if element appears clickable
        """
        try:
            # Quick checks only
            return (element.is_displayed() and 
                   element.is_enabled() and 
                   element.size.get('height', 0) > 10 and 
                   element.size.get('width', 0) > 10)
        except Exception:
            return False
    
    def _click_element_safely(self, element) -> bool:
        """
        Attempt to click element with fallback methods.
        
        Args:
            element: WebElement to click
            
        Returns:
            bool: True if click successful
        """
        try:
            # Method 1: Standard click
            element.click()
            return True
        except ElementNotInteractableException:
            try:
                # Method 2: JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False
        except Exception:
            try:
                # Fallback to JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False
    
    def clear_cache(self):
        """Clear the popup handled cache."""
        self._popup_handled_cache.clear()
        logger.debug("Cleared popup handler cache")