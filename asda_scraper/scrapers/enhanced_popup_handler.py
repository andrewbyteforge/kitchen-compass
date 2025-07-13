"""
Enhanced popup handler specifically for ASDA privacy and cookie popups.

File: asda_scraper/scrapers/enhanced_popup_handler.py
"""

import logging
import time
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    TimeoutException, 
    ElementNotInteractableException,
    ElementClickInterceptedException
)

logger = logging.getLogger(__name__)


class EnhancedPopupHandler:
    """
    Enhanced popup handler specifically designed for ASDA's privacy and cookie popups.
    Addresses common issues with privacy popups blocking interactions.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize enhanced popup handler.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.handled_popups = set()  # Track handled popup types
        self.last_popup_check = 0
        self.popup_check_interval = 1.0  # Minimum time between checks
        
        # ASDA-specific popup selectors (prioritized by frequency and reliability)
        self.asda_popup_selectors = [
            # Primary ASDA privacy/cookie selectors
            "button#onetrust-accept-btn-handler",  # Most common OneTrust cookie button
            "button[id*='onetrust-accept']",
            "#accept-recommended-btn-handler",
            "button.ot-sdk-row .save-preference-btn-handler",
            
            # Alternative ASDA cookie selectors
            "button[class*='cookie'][class*='accept']",
            "button[aria-label*='Accept all cookies']",
            "button[data-testid*='accept-cookies']",
            ".privacy-prompt__button--accept",
            "[data-auto-id='privacy-accept-all']",
            
            # Generic cookie consent selectors
            "button[id*='accept'][id*='cookie']",
            "button[class*='accept'][class*='cookie']",
            ".cookie-banner button[class*='accept']",
            "#cookie-consent button[class*='accept']",
            
            # Modal and overlay close buttons
            "button[aria-label*='Close']",
            "button[aria-label*='close']",
            ".modal-close",
            ".overlay-close",
            "[data-testid*='close-modal']",
            
            # Newsletter/marketing popups
            ".newsletter-popup .close",
            ".marketing-modal .close-btn",
            "button[class*='no-thanks']",
            
            # General dismiss buttons
            "button[class*='dismiss']",
            "button[data-dismiss]",
            ".popup-dismiss"
        ]
        
        # Text patterns that indicate accept/continue buttons
        self.accept_text_patterns = [
            'accept all', 'accept all cookies', 'accept', 'allow all',
            'continue', 'ok', 'i agree', 'got it', 'close', 'dismiss',
            'no thanks', 'not now'
        ]
    
    def handle_all_popups(self, max_attempts: int = 3, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Comprehensive popup handling with multiple strategies.
        
        Args:
            max_attempts: Maximum number of attempts to clear popups
            timeout: Maximum time to spend on popup handling
            
        Returns:
            Dict: Results of popup handling
        """
        start_time = time.time()
        results = {
            'popups_handled': 0,
            'attempts': 0,
            'time_taken': 0,
            'success': False,
            'popup_types': []
        }
        
        try:
            # Check if we recently handled popups for this page
            current_url = self.driver.current_url
            if current_url in self.handled_popups and (time.time() - self.last_popup_check) < self.popup_check_interval:
                logger.debug("Popups recently handled for this page, skipping")
                results['success'] = True
                return results
            
            logger.info("🚫 Checking for privacy and cookie popups...")
            
            for attempt in range(max_attempts):
                results['attempts'] = attempt + 1
                
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"⏰ Popup handling timeout after {timeout}s")
                    break
                
                # Strategy 1: Handle known ASDA popups
                popup_count = self._handle_asda_popups()
                if popup_count > 0:
                    results['popups_handled'] += popup_count
                    results['popup_types'].append('asda_privacy')
                    logger.info(f"✅ Handled {popup_count} ASDA popups")
                
                # Strategy 2: Handle by text content
                text_popups = self._handle_popups_by_text()
                if text_popups > 0:
                    results['popups_handled'] += text_popups
                    results['popup_types'].append('text_based')
                    logger.info(f"✅ Handled {text_popups} text-based popups")
                
                # Strategy 3: Handle iframe popups (OneTrust etc.)
                iframe_popups = self._handle_iframe_popups()
                if iframe_popups > 0:
                    results['popups_handled'] += iframe_popups
                    results['popup_types'].append('iframe')
                    logger.info(f"✅ Handled {iframe_popups} iframe popups")
                
                # Strategy 4: JavaScript popup dismissal
                js_popups = self._dismiss_popups_with_javascript()
                if js_popups > 0:
                    results['popups_handled'] += js_popups
                    results['popup_types'].append('javascript')
                    logger.info(f"✅ Dismissed {js_popups} popups with JavaScript")
                
                # Brief pause to let page settle
                time.sleep(0.5)
                
                # Check if more popups appeared
                if not self._has_visible_popups():
                    logger.info("🎉 No more popups detected")
                    break
                    
                logger.info(f"🔄 Attempt {attempt + 1}: Found more popups, continuing...")
            
            # Update tracking
            if results['popups_handled'] > 0:
                self.handled_popups.add(current_url)
            self.last_popup_check = time.time()
            
            results['time_taken'] = time.time() - start_time
            results['success'] = True
            
            logger.info(f"🏁 Popup handling complete: {results['popups_handled']} popups in {results['time_taken']:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Error in popup handling: {e}")
            results['time_taken'] = time.time() - start_time
        
        return results
    
    def _handle_asda_popups(self) -> int:
        """
        Handle known ASDA popup selectors.
        
        Returns:
            int: Number of popups handled
        """
        popups_handled = 0
        
        for selector in self.asda_popup_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    if self._is_element_interactable(element):
                        if self._click_element_safely(element, selector):
                            popups_handled += 1
                            logger.debug(f"Clicked popup with selector: {selector}")
                            time.sleep(0.3)  # Brief pause after click
                            break  # Move to next selector
                
                if popups_handled > 0:
                    break  # Stop after first successful popup handling
                    
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return popups_handled
    
    def _handle_popups_by_text(self) -> int:
        """
        Handle popups by searching for specific text content.
        
        Returns:
            int: Number of popups handled
        """
        popups_handled = 0
        
        try:
            # Find all clickable elements (buttons, links, etc.)
            clickable_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "button, a, [role='button'], input[type='button'], input[type='submit']"
            )
            
            for element in clickable_elements:
                try:
                    if not self._is_element_interactable(element):
                        continue
                    
                    # Check element text
                    element_text = (element.text or element.get_attribute('value') or '').lower().strip()
                    aria_label = (element.get_attribute('aria-label') or '').lower().strip()
                    title = (element.get_attribute('title') or '').lower().strip()
                    
                    # Check if text matches accept patterns
                    all_text = f"{element_text} {aria_label} {title}"
                    
                    for pattern in self.accept_text_patterns:
                        if pattern in all_text:
                            if self._click_element_safely(element, f"text='{pattern}'"):
                                popups_handled += 1
                                logger.debug(f"Clicked popup button with text: {element_text}")
                                time.sleep(0.3)
                                break
                    
                    if popups_handled > 0:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error checking element text: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"Error in text-based popup handling: {e}")
        
        return popups_handled
    
    def _handle_iframe_popups(self) -> int:
        """
        Handle popups that appear within iframes (like OneTrust).
        
        Returns:
            int: Number of popups handled
        """
        popups_handled = 0
        original_window = self.driver.current_window_handle
        
        try:
            # Find all iframes
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            
            for iframe in iframes:
                try:
                    # Switch to iframe
                    self.driver.switch_to.frame(iframe)
                    
                    # Try ASDA selectors within iframe
                    for selector in self.asda_popup_selectors[:5]:  # Try top 5 selectors
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            
                            for element in elements:
                                if self._is_element_interactable(element):
                                    if self._click_element_safely(element, f"iframe:{selector}"):
                                        popups_handled += 1
                                        logger.debug(f"Clicked iframe popup: {selector}")
                                        time.sleep(0.3)
                                        break
                            
                            if popups_handled > 0:
                                break
                                
                        except Exception as e:
                            logger.debug(f"Iframe selector {selector} failed: {e}")
                            continue
                    
                    # Switch back to main content
                    self.driver.switch_to.default_content()
                    
                    if popups_handled > 0:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error handling iframe popup: {e}")
                    # Ensure we're back in main content
                    try:
                        self.driver.switch_to.default_content()
                    except:
                        pass
                    continue
        
        except Exception as e:
            logger.debug(f"Error in iframe popup handling: {e}")
        
        # Ensure we're back in the original window
        try:
            self.driver.switch_to.window(original_window)
        except:
            pass
        
        return popups_handled
    
    def _dismiss_popups_with_javascript(self) -> int:
        """
        Use JavaScript to dismiss stubborn popups.
        
        Returns:
            int: Number of popups dismissed
        """
        try:
            # JavaScript to remove common popup elements
            js_script = """
            let removed = 0;
            
            // Remove OneTrust cookie banner
            const oneTrust = document.querySelector('#onetrust-banner-sdk');
            if (oneTrust) {
                oneTrust.remove();
                removed++;
            }
            
            // Remove cookie consent overlays
            const overlays = document.querySelectorAll('[class*="cookie"], [class*="consent"], [class*="privacy"]');
            overlays.forEach(overlay => {
                if (overlay.style.position === 'fixed' || overlay.style.position === 'absolute') {
                    overlay.remove();
                    removed++;
                }
            });
            
            // Remove modal backdrops
            const backdrops = document.querySelectorAll('.modal-backdrop, .overlay, [class*="backdrop"]');
            backdrops.forEach(backdrop => {
                backdrop.remove();
                removed++;
            });
            
            // Reset body scroll
            document.body.style.overflow = '';
            document.documentElement.style.overflow = '';
            
            return removed;
            """
            
            removed_count = self.driver.execute_script(js_script)
            
            if removed_count > 0:
                logger.debug(f"JavaScript removed {removed_count} popup elements")
                time.sleep(0.5)  # Let page settle
            
            return removed_count
            
        except Exception as e:
            logger.debug(f"JavaScript popup removal failed: {e}")
            return 0
    
    def _has_visible_popups(self) -> bool:
        """
        Check if there are still visible popups on the page.
        
        Returns:
            bool: True if popups are still visible
        """
        try:
            # Check for common popup indicators
            popup_indicators = [
                "[class*='modal'][style*='block']",
                "[class*='popup'][style*='block']",
                "[class*='overlay'][style*='visible']",
                "#onetrust-banner-sdk",
                ".cookie-banner",
                "[role='dialog']",
                "[aria-modal='true']"
            ]
            
            for indicator in popup_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    for element in elements:
                        if element.is_displayed():
                            return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking for visible popups: {e}")
            return False
    
    def _is_element_interactable(self, element) -> bool:
        """
        Check if element is interactable (visible, enabled, and clickable).
        
        Args:
            element: WebElement to check
            
        Returns:
            bool: True if element is interactable
        """
        try:
            return (
                element.is_displayed() and 
                element.is_enabled() and
                element.size.get('height', 0) > 5 and
                element.size.get('width', 0) > 5
            )
        except Exception:
            return False
    
    def _click_element_safely(self, element, identifier: str = "") -> bool:
        """
        Safely click an element with multiple fallback methods.
        
        Args:
            element: WebElement to click
            identifier: String identifier for logging
            
        Returns:
            bool: True if click was successful
        """
        try:
            # Method 1: Standard click
            element.click()
            logger.debug(f"Standard click successful: {identifier}")
            return True
            
        except ElementClickInterceptedException:
            try:
                # Method 2: JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
                logger.debug(f"JavaScript click successful: {identifier}")
                return True
            except Exception as e:
                logger.debug(f"JavaScript click failed for {identifier}: {e}")
                return False
                
        except ElementNotInteractableException:
            try:
                # Method 3: Force JavaScript click
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true}));", 
                    element
                )
                logger.debug(f"Force click successful: {identifier}")
                return True
            except Exception as e:
                logger.debug(f"Force click failed for {identifier}: {e}")
                return False
                
        except Exception as e:
            logger.debug(f"All click methods failed for {identifier}: {e}")
            return False
    
    def clear_cache(self):
        """Clear the popup handling cache."""
        self.handled_popups.clear()
        self.last_popup_check = 0
        logger.debug("🧹 Popup handler cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get popup handler statistics.
        
        Returns:
            Dict: Handler statistics
        """
        return {
            'cached_pages': len(self.handled_popups),
            'last_check': self.last_popup_check,
            'check_interval': self.popup_check_interval
        }