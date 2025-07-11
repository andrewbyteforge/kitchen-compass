"""
Popup and cookie banner handler for ASDA scraper.

File: asda_scraper/scrapers/popup_handler.py
"""

import logging
import time
from typing import List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

logger = logging.getLogger(__name__)


class PopupHandler:
    """
    Handles cookie banners and other popups on ASDA website.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize popup handler.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
    
    def handle_popups(self) -> int:
        """
        Handle cookie banners and other popups with enhanced detection.
        
        Returns:
            int: Number of popups handled
        """
        try:
            logger.info("Checking for popups and cookie banners")
            time.sleep(2)  # Wait for popups to appear
            
            popup_selectors = self._get_popup_selectors()
            popups_handled = 0
            
            for selector in popup_selectors:
                try:
                    elements = self._find_elements_by_selector(selector)
                    
                    for element in elements:
                        if self._is_element_interactable(element):
                            if self._click_element(element):
                                logger.info(f"Clicked popup with selector: {selector}")
                                popups_handled += 1
                                time.sleep(1)
                                break
                    
                    if popups_handled >= 3:  # Don't handle too many popups
                        break
                        
                except Exception as e:
                    logger.debug(f"Popup selector {selector} failed: {e}")
                    continue
            
            if popups_handled > 0:
                logger.info(f"Successfully handled {popups_handled} popups")
            else:
                logger.info("No popups found to handle")
            
            return popups_handled
                
        except Exception as e:
            logger.warning(f"Error handling popups: {e}")
            return 0
    
    def _get_popup_selectors(self) -> List[str]:
        """
        Get list of popup selectors.
        
        Returns:
            List[str]: CSS selectors for popups
        """
        return [
            # Cookie consent buttons
            "button[id*='accept']",
            "button[class*='accept']", 
            "button[data-testid*='accept']",
            "#accept-cookies",
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
            
            # ASDA specific
            "button.privacy-prompt__button--accept",
            "[data-auto-id='privacy-accept-all']",
        ]
    
    def _find_elements_by_selector(self, selector: str) -> List:
        """
        Find elements by CSS selector or XPath.
        
        Args:
            selector: CSS selector string
            
        Returns:
            List: Found elements
        """
        if ':contains(' in selector:
            # Handle jQuery-style contains selector
            text = selector.split("'")[1]
            xpath = f"//button[contains(text(), '{text}')]"
            return self.driver.find_elements(By.XPATH, xpath)
        else:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
    
    def _is_element_interactable(self, element) -> bool:
        """
        Check if element is displayable and enabled.
        
        Args:
            element: WebElement to check
            
        Returns:
            bool: True if element can be interacted with
        """
        try:
            return element.is_displayed() and element.is_enabled()
        except:
            return False
    
    def _click_element(self, element) -> bool:
        """
        Attempt to click element with fallback methods.
        
        Args:
            element: WebElement to click
            
        Returns:
            bool: True if click successful
        """
        try:
            element.click()
            return True
        except:
            try:
                # Fallback to JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except:
                return False