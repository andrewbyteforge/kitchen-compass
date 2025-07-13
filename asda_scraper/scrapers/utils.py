"""
Utility functions for ASDA scrapers.

Contains common functionality used across different scraper types,
including popup handling, data parsing, and validation.
"""

import logging
import time
from typing import Optional, Dict, Any
from decimal import Decimal
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)


def handle_cookie_consent(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    """
    Handle cookie consent popup if present.
    
    This function checks for and handles the ASDA cookie consent popup
    that appears on first visit to the site.
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        
    Returns:
        bool: True if popup was handled, False if not found
    """
    try:
        logger.debug("Checking for cookie consent popup")
        
        # Try multiple possible selectors for the accept button
        accept_selectors = [
            (By.XPATH, "//button[contains(text(), 'Accept')]"),
            (By.XPATH, "//button[contains(text(), 'I Accept')]"),
            (By.CSS_SELECTOR, "button[class*='accept']"),
            (By.ID, "onetrust-accept-btn-handler"),
            (By.CSS_SELECTOR, "[data-testid='cookie-accept']"),
            (By.XPATH, "//button[contains(@class, 'onetrust-close-btn-handler')]"),
        ]
        
        for selector_type, selector_value in accept_selectors:
            try:
                # Wait a short time for each selector
                accept_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((selector_type, selector_value))
                )
                
                # Scroll to button if needed
                driver.execute_script(
                    "arguments[0].scrollIntoView(true);", 
                    accept_button
                )
                
                # Click the button
                accept_button.click()
                logger.info("Cookie consent accepted")
                
                # Wait for popup to disappear
                time.sleep(2)
                
                return True
                
            except TimeoutException:
                continue
                
        logger.debug("No cookie consent popup found")
        return False
        
    except Exception as e:
        logger.error(f"Error handling cookie consent: {str(e)}")
        return False


def handle_privacy_popup(driver: webdriver.Chrome, wait: WebDriverWait) -> bool:
    """
    Handle privacy/data processing popup if present.
    
    This handles the "Your privacy is important to us" popup that
    may appear on ASDA pages.
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        
    Returns:
        bool: True if popup was handled, False if not found
    """
    try:
        logger.debug("Checking for privacy popup")
        
        # Check if the privacy popup is present
        privacy_selectors = [
            (By.XPATH, "//h2[contains(text(), 'Your privacy is important to us')]"),
            (By.XPATH, "//div[contains(text(), 'We and our partners process data')]"),
        ]
        
        popup_found = False
        for selector_type, selector_value in privacy_selectors:
            try:
                driver.find_element(selector_type, selector_value)
                popup_found = True
                break
            except NoSuchElementException:
                continue
                
        if not popup_found:
            logger.debug("No privacy popup found")
            return False
            
        # Look for action buttons
        button_selectors = [
            (By.XPATH, "//button[contains(text(), 'I Accept')]"),
            (By.XPATH, "//button[contains(text(), 'Accept')]"),
            (By.XPATH, "//button[contains(text(), 'Reject All')]"),
            (By.XPATH, "//button[contains(text(), 'Show Purposes')]"),
            (By.CSS_SELECTOR, "button[class*='accept']"),
        ]
        
        for selector_type, selector_value in button_selectors:
            try:
                button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((selector_type, selector_value))
                )
                
                # Click the accept button if found
                if "accept" in button.text.lower():
                    button.click()
                    logger.info("Privacy popup accepted")
                    time.sleep(2)
                    return True
                    
            except TimeoutException:
                continue
                
        logger.warning("Privacy popup found but no suitable button to click")
        return False
        
    except Exception as e:
        logger.error(f"Error handling privacy popup: {str(e)}")
        return False


def handle_all_popups(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    """
    Handle all possible popups that might appear on ASDA pages.
    
    This is a convenience function that calls all popup handlers
    in sequence.
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
    """
    try:
        # Handle cookie consent first
        handle_cookie_consent(driver, wait)
        
        # Handle privacy popup
        handle_privacy_popup(driver, wait)
        
        # Add more popup handlers here as needed
        
    except Exception as e:
        logger.error(f"Error in handle_all_popups: {str(e)}")


def parse_price(price_text: str) -> Optional[Decimal]:
    """
    Parse price from text string.
    
    Handles various price formats like:
    - £1.50
    - £1.50 was £2.00
    - 2 for £3.00
    
    Args:
        price_text: Raw price text
        
    Returns:
        Decimal: Parsed price or None if parsing fails
    """
    try:
        if not price_text:
            return None
            
        # Remove whitespace
        price_text = price_text.strip()
        
        # Extract price using regex
        price_match = re.search(r'£(\d+\.?\d*)', price_text)
        if price_match:
            return Decimal(price_match.group(1))
            
        return None
        
    except Exception as e:
        logger.error(f"Error parsing price '{price_text}': {str(e)}")
        return None


def parse_unit_price(unit_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse unit price from text.
    
    Handles formats like:
    - £1.50/kg
    - 50p/100g
    - £2.00 per litre
    
    Args:
        unit_text: Raw unit price text
        
    Returns:
        dict: Contains 'price' and 'unit' keys, or None if parsing fails
    """
    try:
        if not unit_text:
            return None
            
        unit_text = unit_text.strip()
        
        # Match patterns like "£1.50/kg" or "50p/100g"
        match = re.search(
            r'(?:£(\d+\.?\d*)|(\d+)p)[\s/]*(per\s+)?(\w+)',
            unit_text,
            re.IGNORECASE
        )
        
        if match:
            if match.group(1):  # Pounds
                price = Decimal(match.group(1))
            elif match.group(2):  # Pence
                price = Decimal(match.group(2)) / 100
            else:
                return None
                
            unit = match.group(4)
            
            return {
                'price': price,
                'unit': unit
            }
            
        return None
        
    except Exception as e:
        logger.error(f"Error parsing unit price '{unit_text}': {str(e)}")
        return None


def extract_product_id_from_url(url: str) -> Optional[str]:
    """
    Extract ASDA product ID from URL.
    
    ASDA URLs typically contain the product ID at the end:
    https://groceries.asda.com/product/cheese/asda-mature-cheddar/1000000012345
    
    Args:
        url: Product URL
        
    Returns:
        str: Product ID or None if not found
    """
    try:
        if not url:
            return None
            
        # Extract ID from end of URL
        parts = url.rstrip('/').split('/')
        if parts:
            last_part = parts[-1]
            # Check if it's a numeric ID
            if last_part.isdigit():
                return last_part
                
        return None
        
    except Exception as e:
        logger.error(f"Error extracting product ID from '{url}': {str(e)}")
        return None


def is_valid_asda_url(url: str) -> bool:
    """
    Validate if URL is a valid ASDA groceries URL.
    
    Args:
        url: URL to validate
        
    Returns:
        bool: True if valid ASDA URL, False otherwise
    """
    try:
        if not url:
            return False
            
        return 'groceries.asda.com' in url.lower()
        
    except Exception:
        return False


def scroll_to_element(driver: webdriver.Chrome, element) -> None:
    """
    Scroll element into view.
    
    Args:
        driver: Selenium WebDriver instance
        element: WebElement to scroll to
    """
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
            element
        )
        time.sleep(0.5)  # Allow time for smooth scroll
        
    except Exception as e:
        logger.error(f"Error scrolling to element: {str(e)}")


def wait_for_page_load(driver: webdriver.Chrome, timeout: int = 30) -> bool:
    """
    Wait for page to fully load.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait in seconds
        
    Returns:
        bool: True if page loaded, False if timeout
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
        
    except TimeoutException:
        logger.warning("Timeout waiting for page load")
        return False
        
    except Exception as e:
        logger.error(f"Error waiting for page load: {str(e)}")
        return False