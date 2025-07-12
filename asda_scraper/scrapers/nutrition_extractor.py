"""
Enhanced nutritional information extraction for ASDA scraper with fixed navigation.

File: asda_scraper/scrapers/nutrition_extractor.py
"""

import logging
import time
import re
import json
from typing import Dict, Optional, List, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class NutritionExtractor:
    """
    Enhanced extractor for nutritional information from ASDA product pages.
    Optimized for speed and reliability with better navigation handling.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize nutrition extractor.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.debug_mode = False  # Disabled by default for speed
        self._nutrition_cache = {}  # Cache results
        
        # Modern CSS selectors for ASDA's current website
        self.nutrition_selectors = [
            # Primary ASDA nutrition selectors
            "[data-testid*='nutrition']",
            "[data-auto-id*='nutrition']",
            "section[aria-label*='nutrition' i]",
            
            # Table-based selectors
            "table[class*='nutrition' i]",
            "div[class*='nutrition-table' i]",
            
            # General nutrition containers
            "div[class*='nutrition' i]",
            ".nutrition-information",
            ".product-nutrition",
            ".pdp__nutritional-information",
            
            # Accordion sections
            "details[class*='nutrition' i]",
            "button[aria-controls*='nutrition' i] + *",
        ]
        
        # Keywords to identify nutrition content
        self.nutrition_keywords = [
            'energy', 'kcal', 'kj', 'calories',
            'fat', 'saturated', 'saturates',
            'carbohydrate', 'carbs', 'sugar',
            'protein', 'salt', 'sodium',
            'fibre', 'fiber'
        ]
    
    def extract_from_url(self, product_url: str) -> Optional[Dict[str, str]]:
        """
        Extract nutritional information from a product detail page.
        Optimized for speed with minimal navigation.
        
        Args:
            product_url: URL of the product page
            
        Returns:
            Dict[str, str]: Nutritional information or None if not found
        """
        try:
            # Check cache first
            if product_url in self._nutrition_cache:
                logger.debug(f"Using cached nutrition data for: {product_url}")
                return self._nutrition_cache[product_url]
            
            if self.debug_mode:
                logger.info(f"Starting nutrition extraction for: {product_url}")
            
            # Navigate to product page
            self.driver.get(product_url)
            
            # Quick wait for basic page load
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except TimeoutException:
                logger.warning("Page load timeout")
                return None
            
            # Minimal delay for dynamic content
            time.sleep(1.5)
            
            # Try to expand nutrition sections quickly
            self._expand_nutrition_sections_fast()
            
            # Extract nutrition data
            nutrition_data = self._extract_nutrition_data()
            
            # Cache the result
            if nutrition_data:
                self._nutrition_cache[product_url] = nutrition_data
                logger.info(f"Successfully extracted {len(nutrition_data)} nutritional values")
            else:
                logger.debug("No nutrition data found")
            
            return nutrition_data if nutrition_data else None
            
        except Exception as e:
            logger.error(f"Error extracting nutritional info: {e}")
            return None
    
    def _expand_nutrition_sections_fast(self):
        """
        Try to expand any collapsed nutrition sections quickly.
        """
        try:
            # Common expand button patterns
            expand_selectors = [
                "button[aria-expanded='false'][aria-label*='nutrition' i]",
                "button[aria-expanded='false'][aria-controls*='nutrition' i]",
                "details[class*='nutrition' i]:not([open])",
                ".accordion-button[aria-expanded='false']",
                "button:contains('Nutrition')"
            ]
            
            for selector in expand_selectors[:3]:  # Only try first few
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # Click first expandable element
                        elements[0].click()
                        time.sleep(0.5)
                        logger.debug(f"Expanded nutrition section: {selector}")
                        return
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error expanding sections: {e}")
    
    def _extract_nutrition_data(self) -> Dict[str, str]:
        """
        Extract nutrition data using multiple strategies.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        # Try primary extraction method
        nutrition_data = self._extract_using_selectors()
        
        if nutrition_data:
            return nutrition_data
        
        # Try table extraction
        nutrition_data = self._extract_from_nutrition_tables()
        
        if nutrition_data:
            return nutrition_data
        
        # Last resort: text parsing
        return self._extract_from_page_text()
    
    def _extract_using_selectors(self) -> Dict[str, str]:
        """
        Extract nutrition using CSS selectors.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        nutrition_data = {}
        
        for selector in self.nutrition_selectors[:5]:  # Limit selectors tried
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if not elements:
                    continue
                
                for element in elements[:2]:  # Only check first 2 elements
                    try:
                        # Quick keyword check
                        element_text = element.text.lower()
                        if not any(keyword in element_text for keyword in ['energy', 'fat', 'carbo', 'protein']):
                            continue
                        
                        logger.debug(f"Found nutrition element with selector: {selector}")
                        
                        # Try structured extraction
                        data = self._extract_structured_nutrition(element)
                        if data:
                            return data
                        
                        # Try text parsing
                        data = self._parse_nutrition_text(element.text)
                        if data:
                            return data
                            
                    except Exception as e:
                        logger.debug(f"Error processing element: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return nutrition_data
    
    def _extract_from_nutrition_tables(self) -> Dict[str, str]:
        """
        Extract nutrition from tables.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        try:
            # Find tables with nutrition keywords
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            
            for table in tables[:3]:  # Check first 3 tables only
                table_text = table.text.lower()
                if any(keyword in table_text for keyword in ['energy', 'fat', 'protein']):
                    logger.debug("Found table with nutrition content")
                    data = self._extract_structured_nutrition(table)
                    if data:
                        return data
                        
        except Exception as e:
            logger.debug(f"Error extracting from tables: {e}")
        
        return {}
    
    def _extract_from_page_text(self) -> Dict[str, str]:
        """
        Extract nutrition from page text as last resort.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        try:
            # Get page source and parse
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Find nutrition section
            lines = text.split('\n')
            nutrition_data = {}
            
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                
                # Look for nutrition section markers
                if any(marker in line_lower for marker in ['nutritional values', 'nutrition information', 'typical values']):
                    # Parse next 20 lines for nutrition data
                    for j in range(i + 1, min(i + 20, len(lines))):
                        data = self._parse_nutrition_line(lines[j])
                        if data:
                            nutrition_data.update(data)
                    
                    if nutrition_data:
                        return nutrition_data
            
            return nutrition_data
            
        except Exception as e:
            logger.debug(f"Error in text extraction: {e}")
            return {}
    
    def _extract_structured_nutrition(self, element) -> Dict[str, str]:
        """
        Extract nutrition from structured element.
        
        Args:
            element: WebElement containing nutrition data
            
        Returns:
            Dict[str, str]: Nutrition data
        """
        nutrition_data = {}
        
        try:
            # Try to find rows in the element
            rows = element.find_elements(By.CSS_SELECTOR, "tr, div[class*='row'], li")
            
            for row in rows[:15]:  # Limit rows processed
                try:
                    row_text = row.text.strip()
                    if not row_text:
                        continue
                    
                    # Parse the row
                    data = self._parse_nutrition_line(row_text)
                    if data:
                        nutrition_data.update(data)
                        
                except Exception:
                    continue
            
            # Also try direct text parsing if no rows found
            if not nutrition_data and element.text:
                lines = element.text.split('\n')
                for line in lines[:20]:  # Limit lines processed
                    data = self._parse_nutrition_line(line)
                    if data:
                        nutrition_data.update(data)
            
            return nutrition_data
            
        except Exception as e:
            logger.debug(f"Error in structured extraction: {e}")
            return {}
    
    def _parse_nutrition_line(self, text: str) -> Dict[str, str]:
        """
        Parse a single line of nutrition text.
        
        Args:
            text: Line of text to parse
            
        Returns:
            Dict[str, str]: Parsed nutrition data
        """
        if not text:
            return {}
        
        text = text.strip()
        
        # Common nutrition patterns
        patterns = [
            # Pattern: "Energy 1466kJ/350kcal"
            (r'(Energy)\s*(\d+\.?\d*)\s*(kJ|kcal)', lambda m: {f"{m.group(1)} ({m.group(3)})": m.group(2)}),
            
            # Pattern: "Fat 12.5g"
            (r'(Fat|Saturates|Carbohydrate|Sugars|Fibre|Protein|Salt)\s*(\d+\.?\d*)\s*g', 
             lambda m: {m.group(1): f"{m.group(2)}g"}),
            
            # Pattern: "Sodium 0.48g"
            (r'(Sodium)\s*(\d+\.?\d*)\s*g', lambda m: {m.group(1): f"{m.group(2)}g"}),
            
            # Pattern with colon: "Fat: 12.5g"
            (r'([\w\s]+):\s*(\d+\.?\d*)\s*(g|mg|kJ|kcal)', 
             lambda m: {m.group(1).strip(): f"{m.group(2)}{m.group(3)}"}),
        ]
        
        for pattern, handler in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return handler(match)
        
        return {}
    
    def _parse_nutrition_text(self, text: str) -> Dict[str, str]:
        """
        Parse nutrition from unstructured text.
        
        Args:
            text: Text containing nutrition information
            
        Returns:
            Dict[str, str]: Parsed nutrition data
        """
        if not text:
            return {}
        
        nutrition_data = {}
        lines = text.split('\n')
        
        for line in lines:
            data = self._parse_nutrition_line(line)
            if data:
                nutrition_data.update(data)
        
        return nutrition_data
    
    def clear_cache(self):
        """Clear the nutrition cache."""
        self._nutrition_cache.clear()
        logger.debug("Cleared nutrition cache")