"""
Enhanced nutritional information extraction for ASDA scraper.

This version includes modern CSS selectors, enhanced debugging, and multiple
extraction strategies to handle ASDA's current website structure.

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

from .popup_handler import PopupHandler

logger = logging.getLogger(__name__)


class NutritionExtractor:
    """
    Enhanced extractor for nutritional information from ASDA product pages.
    
    Features:
    - Modern CSS selectors for current ASDA website
    - Multiple extraction strategies
    - Enhanced debugging and logging
    - Fallback text parsing
    - Comprehensive error handling
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize nutrition extractor.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self._current_url = None
        self.debug_mode = True  # Enable detailed logging
        
        # Modern CSS selectors for ASDA's current website (2024/2025)
        self.nutrition_selectors = [
            # Updated ASDA specific selectors
            "[data-testid*='nutrition']",
            "[data-testid*='nutritional']",
            "[data-auto-id*='nutrition']",
            "section[aria-label*='nutrition' i]",
            "section[aria-label*='nutritional' i]",
            
            # Table-based selectors
            "table[class*='nutrition' i]",
            "table[id*='nutrition' i]",
            "div[class*='nutrition-table' i]",
            "div[class*='nutritional-table' i]",
            
            # General nutrition containers
            "div[class*='nutrition' i]",
            "div[class*='nutritional' i]",
            ".nutrition-information",
            ".nutritional-information",
            ".product-nutrition",
            ".pdp-nutrition",
            ".pdp__nutritional-information",
            
            # Accordion/expandable sections
            "details[class*='nutrition' i]",
            "button[aria-controls*='nutrition' i] + *",
            
            # Fallback generic selectors
            "*[class*='nutrition' i]",
            "*[id*='nutrition' i]"
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
        
        Args:
            product_url: URL of the product page
            
        Returns:
            Dict[str, str]: Nutritional information or None if not found
        """
        try:
            if self.debug_mode:
                logger.info(f"🔍 Starting nutrition extraction for: {product_url}")
            
            # Store current URL to return to later
            self._current_url = self.driver.current_url
            
            # Navigate to product page
            logger.info(f"📱 Navigating to product page: {product_url}")
            self.driver.get(product_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Extended delay to ensure dynamic content loads
            time.sleep(3)
            
            # Handle popups if any
            popup_handler = PopupHandler(self.driver)
            popup_handler.handle_popups()
            
            # Try to expand nutrition sections
            self._expand_nutrition_sections()
            
            # Extract nutrition data using multiple strategies
            nutrition_data = self._extract_nutrition_data()
            
            # Log results
            if nutrition_data:
                logger.info(f"✅ Successfully extracted {len(nutrition_data)} nutritional values")
                if self.debug_mode:
                    for key, value in nutrition_data.items():
                        logger.debug(f"   • {key}: {value}")
            else:
                logger.warning("❌ No nutrition data found")
                if self.debug_mode:
                    self._debug_page_content()
            
            # Navigate back to previous page
            if self._current_url:
                self.driver.get(self._current_url)
                time.sleep(1)
            
            return nutrition_data if nutrition_data else None
            
        except Exception as e:
            logger.error(f"💥 Error extracting nutritional info: {e}")
            if self.debug_mode:
                logger.error(f"   URL: {product_url}")
                logger.error(f"   Current URL: {self.driver.current_url}")
            
            # Try to navigate back on error
            if self._current_url:
                try:
                    self.driver.get(self._current_url)
                except Exception as nav_error:
                    logger.error(f"Failed to navigate back: {nav_error}")
            
            return None
    
    def _expand_nutrition_sections(self):
        """
        Try to expand any collapsed nutrition sections or accordions.
        """
        try:
            # Look for expandable nutrition sections
            expandable_selectors = [
                "button[aria-expanded='false'][aria-controls*='nutrition' i]",
                "details[class*='nutrition' i]:not([open])",
                ".accordion-trigger[data-target*='nutrition' i]",
                "button[class*='nutrition' i][aria-expanded='false']",
                "[data-testid*='nutrition'] button[aria-expanded='false']"
            ]
            
            for selector in expandable_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            logger.info(f"🔽 Expanding nutrition section: {selector}")
                            element.click()
                            time.sleep(1)  # Allow content to load
                            break
                except Exception as e:
                    logger.debug(f"Could not expand with selector {selector}: {e}")
                    
        except Exception as e:
            logger.debug(f"Error expanding sections: {e}")
    
    def _extract_nutrition_data(self) -> Dict[str, str]:
        """
        Extract nutrition data using multiple strategies.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        # Strategy 1: Find nutrition elements with modern selectors
        nutrition_data = self._extract_from_modern_selectors()
        if nutrition_data:
            logger.info("✅ Extracted nutrition using modern selectors")
            return nutrition_data
        
        # Strategy 2: Search for tables containing nutrition keywords
        nutrition_data = self._extract_from_nutrition_tables()
        if nutrition_data:
            logger.info("✅ Extracted nutrition from tables")
            return nutrition_data
        
        # Strategy 3: Full page text search
        nutrition_data = self._extract_from_page_text()
        if nutrition_data:
            logger.info("✅ Extracted nutrition from page text")
            return nutrition_data
        
        # Strategy 4: JSON-LD structured data
        nutrition_data = self._extract_from_structured_data()
        if nutrition_data:
            logger.info("✅ Extracted nutrition from structured data")
            return nutrition_data
        
        logger.warning("❌ All extraction strategies failed")
        return {}
    
    def _extract_from_modern_selectors(self) -> Dict[str, str]:
        """
        Extract nutrition using modern CSS selectors.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        nutrition_data = {}
        
        for selector in self.nutrition_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if not elements:
                    continue
                
                for element in elements:
                    try:
                        # Check if element contains nutrition keywords
                        element_text = element.text.lower()
                        if not any(keyword in element_text for keyword in self.nutrition_keywords):
                            continue
                        
                        logger.info(f"🎯 Found nutrition element with selector: {selector}")
                        
                        # Try structured extraction first
                        data = self._extract_structured_nutrition(element)
                        if data:
                            nutrition_data.update(data)
                        
                        # Try text parsing as fallback
                        if not data:
                            data = self._parse_nutrition_text(element.text)
                            if data:
                                nutrition_data.update(data)
                        
                        if nutrition_data:
                            return nutrition_data
                            
                    except Exception as e:
                        logger.debug(f"Error processing element: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        return nutrition_data
    
    def _extract_from_nutrition_tables(self) -> Dict[str, str]:
        """
        Extract nutrition from any tables that contain nutrition keywords.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        nutrition_data = {}
        
        try:
            # Find all tables on the page
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            
            for table in tables:
                table_text = table.text.lower()
                if any(keyword in table_text for keyword in self.nutrition_keywords):
                    logger.info("🔍 Found table with nutrition content")
                    data = self._extract_structured_nutrition(table)
                    if data:
                        nutrition_data.update(data)
                        return nutrition_data
                        
        except Exception as e:
            logger.debug(f"Error extracting from tables: {e}")
        
        return nutrition_data
    
    def _extract_from_page_text(self) -> Dict[str, str]:
        """
        Extract nutrition from full page text search.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        try:
            # Get all text from the page
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Look for nutrition sections in the text
            lines = page_text.split('\n')
            nutrition_section = []
            in_nutrition_section = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if we're entering a nutrition section
                if any(keyword in line.lower() for keyword in ['nutrition', 'typical values', 'per 100g']):
                    in_nutrition_section = True
                    nutrition_section = [line]
                    continue
                
                if in_nutrition_section:
                    # Check if we're still in nutrition section
                    if any(keyword in line.lower() for keyword in self.nutrition_keywords):
                        nutrition_section.append(line)
                    else:
                        # We've probably left the nutrition section
                        if len(nutrition_section) > 3:  # Only process if we have enough data
                            break
                        else:
                            in_nutrition_section = False
                            nutrition_section = []
            
            if nutrition_section:
                logger.info(f"🔍 Found nutrition section in page text ({len(nutrition_section)} lines)")
                nutrition_text = '\n'.join(nutrition_section)
                return self._parse_nutrition_text(nutrition_text)
                
        except Exception as e:
            logger.debug(f"Error extracting from page text: {e}")
        
        return {}
    
    def _extract_from_structured_data(self) -> Dict[str, str]:
        """
        Extract nutrition from JSON-LD structured data.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        try:
            # Look for JSON-LD structured data
            json_scripts = self.driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]')
            
            for script in json_scripts:
                try:
                    json_content = script.get_attribute('innerHTML')
                    data = json.loads(json_content)
                    
                    # Look for nutrition information in the structured data
                    nutrition_info = self._extract_nutrition_from_json(data)
                    if nutrition_info:
                        logger.info("✅ Found nutrition in structured data")
                        return nutrition_info
                        
                except Exception as e:
                    logger.debug(f"Error parsing JSON-LD: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error extracting structured data: {e}")
        
        return {}
    
    def _extract_nutrition_from_json(self, data: Any) -> Dict[str, str]:
        """
        Recursively search for nutrition data in JSON structure.
        
        Args:
            data: JSON data to search
            
        Returns:
            Dict[str, str]: Nutrition data
        """
        if isinstance(data, dict):
            # Look for nutrition-related keys
            for key, value in data.items():
                if 'nutrition' in key.lower():
                    if isinstance(value, dict):
                        return self._parse_nutrition_json(value)
                
                # Recurse into nested objects
                result = self._extract_nutrition_from_json(value)
                if result:
                    return result
                    
        elif isinstance(data, list):
            for item in data:
                result = self._extract_nutrition_from_json(item)
                if result:
                    return result
        
        return {}
    
    def _parse_nutrition_json(self, nutrition_json: Dict) -> Dict[str, str]:
        """
        Parse nutrition data from JSON format.
        
        Args:
            nutrition_json: JSON nutrition data
            
        Returns:
            Dict[str, str]: Parsed nutrition data
        """
        nutrition_data = {}
        
        # Common JSON nutrition field mappings
        field_mappings = {
            'calories': 'Energy (kcal)',
            'energy': 'Energy (kcal)',
            'fatContent': 'Fat',
            'saturatedFatContent': 'Saturates',
            'carbohydrateContent': 'Carbohydrate',
            'sugarContent': 'Sugars',
            'proteinContent': 'Protein',
            'sodiumContent': 'Salt',
            'fiberContent': 'Fibre'
        }
        
        for json_key, display_name in field_mappings.items():
            if json_key in nutrition_json:
                value = nutrition_json[json_key]
                if isinstance(value, (int, float)):
                    nutrition_data[display_name] = f"{value}g"
                elif isinstance(value, str):
                    nutrition_data[display_name] = value
        
        return nutrition_data
    
    def _extract_structured_nutrition(self, element) -> Dict[str, str]:
        """
        Extract nutrition from structured table format.
        
        Args:
            element: WebElement containing nutrition data
            
        Returns:
            Dict[str, str]: Extracted nutrition data
        """
        nutrition_data = {}
        
        try:
            # Get the HTML and parse with BeautifulSoup
            nutrition_html = element.get_attribute('innerHTML')
            soup = BeautifulSoup(nutrition_html, 'html.parser')
            
            # Try different table structures
            rows = soup.find_all('tr')
            if rows:
                nutrition_data = self._parse_table_rows(rows)
            
            # Try list-based structure
            if not nutrition_data:
                list_items = soup.find_all(['li', 'div'])
                nutrition_data = self._parse_list_items(list_items)
            
            # Try definition list structure
            if not nutrition_data:
                dt_elements = soup.find_all('dt')
                dd_elements = soup.find_all('dd')
                if len(dt_elements) == len(dd_elements):
                    for dt, dd in zip(dt_elements, dd_elements):
                        nutrient_name = self._standardize_nutrient_name(dt.get_text(strip=True))
                        nutrient_value = dd.get_text(strip=True)
                        if nutrient_name and nutrient_value:
                            nutrition_data[nutrient_name] = nutrient_value
                            
        except Exception as e:
            logger.error(f"Error parsing nutrition structure: {e}")
        
        return nutrition_data
    
    def _parse_table_rows(self, rows: List) -> Dict[str, str]:
        """
        Parse nutrition data from table rows.
        
        Args:
            rows: List of table row elements
            
        Returns:
            Dict[str, str]: Nutrition data
        """
        nutrition_data = {}
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                nutrient_name = cells[0].get_text(strip=True)
                nutrient_value = cells[1].get_text(strip=True)
                
                # Skip header rows
                if nutrient_name.lower() in ['nutrient', 'typical values', 'per 100g']:
                    continue
                
                standardized_name = self._standardize_nutrient_name(nutrient_name)
                if standardized_name and nutrient_value:
                    nutrition_data[standardized_name] = nutrient_value
                    logger.debug(f"   Extracted: {standardized_name} = {nutrient_value}")
        
        return nutrition_data
    
    def _parse_list_items(self, items: List) -> Dict[str, str]:
        """
        Parse nutrition data from list items.
        
        Args:
            items: List of list item elements
            
        Returns:
            Dict[str, str]: Nutrition data
        """
        nutrition_data = {}
        
        for item in items:
            text = item.get_text(strip=True)
            if ':' in text:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    nutrient_name = self._standardize_nutrient_name(parts[0].strip())
                    nutrient_value = parts[1].strip()
                    if nutrient_name and nutrient_value:
                        nutrition_data[nutrient_name] = nutrient_value
        
        return nutrition_data
    
    def _standardize_nutrient_name(self, name: str) -> Optional[str]:
        """
        Standardize nutrient names for consistent storage.
        
        Args:
            name: Raw nutrient name
            
        Returns:
            str: Standardized nutrient name or None if not recognized
        """
        if not name:
            return None
        
        # Clean the name
        name = name.lower().strip()
        name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
        name = name.replace('per 100g', '').replace('typical values', '')
        name = name.replace('of which', '').replace('- of which', '')
        name = name.strip(' -:')
        
        # Mapping to standard names
        nutrient_mapping = {
            'energy': 'Energy (kcal)',
            'energy (kcal)': 'Energy (kcal)',
            'energy kcal': 'Energy (kcal)',
            'kcal': 'Energy (kcal)',
            'calories': 'Energy (kcal)',
            'energy (kj)': 'Energy (kJ)',
            'energy kj': 'Energy (kJ)',
            'kj': 'Energy (kJ)',
            
            'fat': 'Fat',
            'total fat': 'Fat',
            'fat content': 'Fat',
            
            'saturated fat': 'Saturates',
            'saturates': 'Saturates',
            'saturated': 'Saturates',
            'sat fat': 'Saturates',
            
            'carbohydrate': 'Carbohydrate',
            'carbohydrates': 'Carbohydrate',
            'carbs': 'Carbohydrate',
            'total carbohydrate': 'Carbohydrate',
            
            'sugar': 'Sugars',
            'sugars': 'Sugars',
            'total sugars': 'Sugars',
            
            'protein': 'Protein',
            'total protein': 'Protein',
            
            'salt': 'Salt',
            'sodium': 'Salt',  # Convert sodium to salt for consistency
            
            'fibre': 'Fibre',
            'fiber': 'Fibre',
            'dietary fibre': 'Fibre',
            'dietary fiber': 'Fibre',
        }
        
        standardized = nutrient_mapping.get(name)
        if standardized:
            return standardized
        
        # If not in mapping, check if it contains key nutrition words
        if any(keyword in name for keyword in self.nutrition_keywords):
            # Capitalize first letter of each word
            return ' '.join(word.capitalize() for word in name.split())
        
        return None
    
    def _parse_nutrition_text(self, text: str) -> Dict[str, str]:
        """
        Parse nutritional information from unstructured text.
        
        Args:
            text: Raw text containing nutritional information
            
        Returns:
            Dict[str, str]: Parsed nutritional information
        """
        nutrition_data = {}
        
        if not text:
            return nutrition_data
        
        logger.debug(f"🔍 Parsing nutrition text: {text[:200]}...")
        
        # Enhanced nutrition patterns with more flexible matching
        patterns = {
            'Energy (kcal)': [
                r'(?:energy|calories|kcal)[:\s]*(\d+(?:\.\d+)?)\s*(?:kcal|cal)?',
                r'(\d+(?:\.\d+)?)\s*kcal',
                r'energy[:\s]*(\d+(?:\.\d+)?)'
            ],
            'Energy (kJ)': [
                r'(?:energy|kilojoules|kj)[:\s]*(\d+(?:\.\d+)?)\s*(?:kj)?',
                r'(\d+(?:\.\d+)?)\s*kj'
            ],
            'Fat': [
                r'(?:total\s+)?fat[:\s]*(\d+(?:\.\d+)?)\s*g',
                r'fat\s+content[:\s]*(\d+(?:\.\d+)?)\s*g'
            ],
            'Saturates': [
                r'saturate[ds]?(?:\s+fat)?[:\s]*(\d+(?:\.\d+)?)\s*g',
                r'(?:of\s+which\s+)?saturate[ds]?[:\s]*(\d+(?:\.\d+)?)\s*g'
            ],
            'Carbohydrate': [
                r'carbohydrate[s]?[:\s]*(\d+(?:\.\d+)?)\s*g',
                r'carbs[:\s]*(\d+(?:\.\d+)?)\s*g',
                r'total\s+carbohydrate[s]?[:\s]*(\d+(?:\.\d+)?)\s*g'
            ],
            'Sugars': [
                r'(?:total\s+)?sugars?[:\s]*(\d+(?:\.\d+)?)\s*g',
                r'(?:of\s+which\s+)?sugars?[:\s]*(\d+(?:\.\d+)?)\s*g'
            ],
            'Protein': [
                r'protein[:\s]*(\d+(?:\.\d+)?)\s*g',
                r'total\s+protein[:\s]*(\d+(?:\.\d+)?)\s*g'
            ],
            'Salt': [
                r'salt[:\s]*(\d+(?:\.\d+)?)\s*g',
                r'sodium[:\s]*(\d+(?:\.\d+)?)\s*g'
            ],
            'Fibre': [
                r'(?:dietary\s+)?fib(?:re|er)[:\s]*(\d+(?:\.\d+)?)\s*g'
            ]
        }
        
        text_lower = text.lower()
        
        for nutrient, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text_lower, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    # Add unit if not calories/energy
                    if 'energy' in nutrient.lower() or 'kcal' in nutrient.lower():
                        nutrition_data[nutrient] = f"{value}"
                    else:
                        nutrition_data[nutrient] = f"{value}g"
                    logger.debug(f"   Matched {nutrient}: {nutrition_data[nutrient]}")
                    break  # Stop after first match for this nutrient
        
        return nutrition_data
    
    def _debug_page_content(self):
        """
        Debug method to log page content for troubleshooting.
        """
        try:
            logger.debug("🔍 DEBUG: Page content analysis")
            
            # Log page title
            title = self.driver.title
            logger.debug(f"   Page title: {title}")
            
            # Log if any nutrition-related text exists
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            found_keywords = [kw for kw in self.nutrition_keywords if kw in body_text]
            logger.debug(f"   Found nutrition keywords: {found_keywords}")
            
            # Log all elements with nutrition-related attributes
            for selector in self.nutrition_selectors[:5]:  # Check first 5 selectors
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.debug(f"   Found {len(elements)} elements with selector: {selector}")
                except Exception:
                    pass
            
            # Look for common nutrition section headers
            headers = self.driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")
            nutrition_headers = [h.text for h in headers if 'nutrition' in h.text.lower()]
            if nutrition_headers:
                logger.debug(f"   Found nutrition headers: {nutrition_headers}")
            
        except Exception as e:
            logger.debug(f"   Debug failed: {e}")