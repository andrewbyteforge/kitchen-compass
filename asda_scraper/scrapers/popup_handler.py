"""
Popup and cookie banner handler for ASDA scraper.

File: asda_scraper/scrapers/popup_handler.py
"""

import logging
import time
from typing import List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException

logger = logging.getLogger(__name__)


class PopupHandler:
    """
    Handles cookie banners and other popups on ASDA website.
    Production-ready with timeout protection and efficient detection.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize popup handler.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.max_timeout = 8  # Maximum time to spend on popup handling
        self.quick_timeout = 2  # Quick timeout for individual operations
    
    def handle_popups(self, timeout: int = None) -> int:
        """
        Handle cookie banners and other popups with enhanced detection and timeout protection.
        
        Args:
            timeout: Maximum time to spend handling popups (default: 8 seconds)
        
        Returns:
            int: Number of popups handled
        """
        timeout = timeout or self.max_timeout
        start_time = time.time()
        
        try:
            logger.info("Checking for popups and cookie banners")
            
            # Quick initial check - if page title indicates error, skip popup handling
            if self._is_error_page():
                logger.info("Error page detected, skipping popup handling")
                return 0
            
            popups_handled = 0
            
            # Phase 1: Quick common popup check (2 seconds max)
            popups_handled += self._handle_common_popups()
            
            # Check if we've exceeded timeout
            if time.time() - start_time > timeout:
                logger.warning(f"Popup handling timeout ({timeout}s) exceeded in phase 1")
                return popups_handled
            
            # Phase 2: Comprehensive popup check (remaining time)
            if popups_handled == 0:
                remaining_timeout = timeout - (time.time() - start_time)
                if remaining_timeout > 1:
                    popups_handled += self._handle_comprehensive_popups(remaining_timeout)
            
            elapsed_time = time.time() - start_time
            
            if popups_handled > 0:
                logger.info(f"Successfully handled {popups_handled} popups in {elapsed_time:.1f}s")
            else:
                logger.info(f"No popups found (checked in {elapsed_time:.1f}s)")
            
            return popups_handled
                
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.warning(f"Error handling popups after {elapsed_time:.1f}s: {e}")
            return 0
    
    def _is_error_page(self) -> bool:
        """
        Quick check if current page is an error page.
        
        Returns:
            bool: True if error page detected
        """
        try:
            title = self.driver.title.lower()
            error_indicators = ['404', 'error', 'not found', 'access denied']
            return any(indicator in title for indicator in error_indicators)
        except:
            return False
    
    def _handle_common_popups(self) -> int:
        """
        Handle the most common popups quickly.
        
        Returns:
            int: Number of popups handled
        """
        try:
            # Most common ASDA popup selectors (prioritized)
            common_selectors = [
                "button[id*='accept']",
                "button[class*='accept']",
                "#accept-cookies",
                "button.privacy-prompt__button--accept",
                "[data-auto-id='privacy-accept-all']"
            ]
            
            for selector in common_selectors:
                try:
                    # Quick check with WebDriverWait
                    element = WebDriverWait(self.driver, 1).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    if self._click_element_safely(element):
                        logger.info(f"Clicked common popup: {selector}")
                        time.sleep(0.5)  # Brief pause after click
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
    
    def _handle_comprehensive_popups(self, remaining_timeout: float) -> int:
        """
        Handle less common popups with comprehensive search.
        
        Args:
            remaining_timeout: Time remaining for popup handling
        
        Returns:
            int: Number of popups handled
        """
        try:
            start_time = time.time()
            popup_selectors = self._get_popup_selectors()
            popups_handled = 0
            
            for selector in popup_selectors:
                # Check timeout
                if time.time() - start_time > remaining_timeout:
                    logger.debug("Comprehensive popup timeout reached")
                    break
                
                try:
                    elements = self._find_elements_by_selector(selector)
                    
                    for element in elements:
                        if self._is_element_interactable(element):
                            if self._click_element_safely(element):
                                logger.info(f"Clicked popup with selector: {selector}")
                                popups_handled += 1
                                time.sleep(0.3)  # Reduced delay
                                break
                    
                    if popups_handled >= 2:  # Limit to prevent infinite loops
                        break
                        
                except Exception as e:
                    logger.debug(f"Popup selector {selector} failed: {e}")
                    continue
            
            return popups_handled
            
        except Exception as e:
            logger.debug(f"Error in comprehensive popup handling: {e}")
            return 0
    
    def _get_popup_selectors(self) -> List[str]:
        """
        Get list of popup selectors, ordered by likelihood.
        
        Returns:
            List[str]: CSS selectors for popups
        """
        return [
            # Most common first
            "button[data-testid*='accept']",
            ".cookie-accept",
            "button[aria-label*='Accept cookies']",
            
            # Close buttons
            "button[aria-label*='close']",
            "button[aria-label*='Close']",
            ".modal-close",
            ".popup-close",
            "[data-testid*='close']",
            
            # Banner buttons
            ".notification-banner button",
            ".banner-close",
            ".consent-banner button",
        ]
    
    def _find_elements_by_selector(self, selector: str) -> List:
        """
        Find elements by CSS selector with timeout protection.
        
        Args:
            selector: CSS selector string
            
        Returns:
            List: Found elements
        """
        try:
            if ':contains(' in selector:
                # Handle jQuery-style contains selector
                text = selector.split("'")[1]
                xpath = f"//button[contains(text(), '{text}')]"
                return self.driver.find_elements(By.XPATH, xpath)
            else:
                return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception as e:
            logger.debug(f"Error finding elements with selector {selector}: {e}")
            return []
    
    def _is_element_interactable(self, element) -> bool:
        """
        Check if element is displayable and enabled with timeout protection.
        
        Args:
            element: WebElement to check
            
        Returns:
            bool: True if element can be interacted with
        """
        try:
            # Quick checks with timeout protection
            return (element.is_displayed() and 
                   element.is_enabled() and 
                   element.size['height'] > 0 and 
                   element.size['width'] > 0)
        except Exception:
            return False
    
    def _click_element_safely(self, element) -> bool:
        """
        Attempt to click element with fallback methods and timeout protection.
        
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
                try:
                    # Method 3: Force click with JavaScript
                    self.driver.execute_script("""
                        arguments[0].dispatchEvent(new MouseEvent('click', {
                            view: window,
                            bubbles: true,
                            cancelable: true
                        }));
                    """, element)
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