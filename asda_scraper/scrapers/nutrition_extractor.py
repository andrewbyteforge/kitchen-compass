"""
Nutritional information extraction for ASDA scraper.

File: asda_scraper/scrapers/nutrition_extractor.py
"""

import logging
import time
import re
from typing import Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from .popup_handler import PopupHandler

logger = logging.getLogger(__name__)


class NutritionExtractor:
    """
    Extracts nutritional information from ASDA product pages.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize nutrition extractor.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self._current_url = None
    
    def extract_from_url(self, product_url: str) -> Optional[Dict[str, str]]:
        """
        Extract nutritional information from a product detail page.
        
        Args:
            product_url: URL of the product page
            
        Returns:
            Dict[str, str]: Nutritional information or None if not found
        """
        try:
            # Store current URL to return to later
            self._current_url = self.driver.current_url
            
            # Navigate to product page
            logger.info(f"Navigating to product page for nutrition: {product_url}")
            self.driver.get(product_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Small delay to ensure content loads
            time.sleep(2)
            
            # Handle popups if any
            popup_handler = PopupHandler(self.driver)
            popup_handler.handle_popups()
            
            # Extract nutrition data
            nutrition_data = self._extract_nutrition_data()
            
            # Navigate back to previous page
            if self._current_url:
                self.driver.get(self._current_url)
                time.sleep(2)
            
            if nutrition_data:
                logger.info(f"Extracted {len(nutrition_data)} nutritional values")
            
            return nutrition_data if nutrition_data else None
            
        except Exception as e:
            logger.error(f"Error extracting nutritional info: {e}")
            # Try to navigate back on error
            if self._current_url:
                try:
                    self.driver.get(self._current_url)
                except:
                    pass
            return None
    
    def _extract_nutrition_data(self) -> Dict[str, str]:
        """
        Extract nutrition data from the current page.
        
        Returns:
            Dict[str, str]: Nutrition data
        """
        nutrition_data = {}
        
        # Try different selectors for ASDA's nutrition table
        nutrition_selectors = [
            "table[class*='nutrition']",
            "div[class*='nutrition-table']",
            "div[class*='nutritional']",
            "[data-testid*='nutrition']",
            "section[aria-label*='Nutrition']",
            "div.pdp__nutritional-information",
            "div[class*='nutritional-information']",
            "[class*='nutrition']"
        ]
        
        nutrition_element = None
        for selector in nutrition_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Look for the one with actual nutrition content
                    for elem in elements:
                        text = elem.text.lower()
                        if any(keyword in text for keyword in ['energy', 'fat', 'protein', 'carbohydrate', 'kcal']):
                            nutrition_element = elem
                            logger.info(f"Found nutrition element with selector: {selector}")
                            break
                    if nutrition_element:
                        break
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        if nutrition_element:
            # Try structured extraction first
            nutrition_data = self._extract_structured_nutrition(nutrition_element)
            
            # Fall back to text parsing if needed
            if not nutrition_data:
                nutrition_text = nutrition_element.text
                nutrition_data = self._parse_nutrition_text(nutrition_text)
        else:
            logger.warning("No nutrition element found on product page")
        
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
            
            # Look for table rows
            rows = soup.find_all('tr')
            if rows:
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        nutrient_name = cells[0].get_text(strip=True)
                        nutrient_value = cells[1].get_text(strip=True)
                        
                        if nutrient_name and nutrient_value and nutrient_name.lower() != 'typical values':
                            standardized_name = self._standardize_nutrient_name(nutrient_name)
                            if standardized_name:
                                nutrition_data[standardized_name] = nutrient_value
                                logger.debug(f"Extracted: {standardized_name} = {nutrient_value}")
            
            # Also try to extract from text layout
            if not nutrition_data:
                lines = element.text.strip().split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    
                    # Check if this is a nutrient name
                    if line in ['Energy', 'Fat', 'Saturates', 'Sugars', 'Salt', 'Protein', 'Carbohydrate', 'Fibre']:
                        nutrient_name = line
                        
                        # Get the value(s) from next line(s)
                        if i + 1 < len(lines):
                            value = lines[i + 1].strip()
                            
                            # Handle energy which has both kJ and kcal
                            if nutrient_name == 'Energy' and i + 2 < len(lines):
                                kj_value = value
                                kcal_value = lines[i + 2].strip()
                                nutrition_data['Energy (kJ)'] = kj_value
                                nutrition_data['Energy (kcal)'] = kcal_value
                                i += 2
                            else:
                                nutrition_data[nutrient_name] = value
                                i += 1
                    i += 1
                    
        except Exception as e:
            logger.error(f"Error parsing nutrition structure: {e}")
        
        return nutrition_data
    
    def _standardize_nutrient_name(self, name: str) -> str:
        """
        Standardize nutrient names for consistent storage.
        
        Args:
            name: Raw nutrient name
            
        Returns:
            str: Standardized nutrient name
        """
        # Remove common suffixes and clean up
        name = name.lower().strip()
        name = name.replace('per 100g', '').replace('per serving', '')
        name = name.replace('of which', '').replace('- of which', '')
        name = name.strip(' -:')
        
        # Map to standard names
        nutrient_mapping = {
            'energy': 'calories',
            'energy (kcal)': 'calories',
            'kcal': 'calories',
            'total fat': 'fat',
            'fat': 'fat',
            'saturated fat': 'saturated_fat',
            'saturates': 'saturated_fat',
            'carbohydrate': 'carbohydrates',
            'carbs': 'carbohydrates',
            'total sugars': 'sugars',
            'sugars': 'sugars',
            'protein': 'protein',
            'salt': 'salt',
            'sodium': 'sodium',
            'fibre': 'fiber',
            'dietary fiber': 'fiber',
        }
        
        return nutrient_mapping.get(name, name.replace(' ', '_'))
    
    def _parse_nutrition_text(self, text: str) -> Dict[str, str]:
        """
        Parse nutritional information from unstructured text.
        
        Args:
            text: Raw text containing nutritional information
            
        Returns:
            Dict[str, str]: Parsed nutritional information
        """
        nutritional_info = {}
        
        # Common nutrition patterns
        patterns = {
            'calories': r'(?:energy|calories|kcal)[:\s]*(\d+(?:\.\d+)?)\s*(?:kcal)?',
            'fat': r'(?:total\s)?fat[:\s]*(\d+(?:\.\d+)?)\s*g',
            'saturated_fat': r'saturate[ds]?(?:\s+fat)?[:\s]*(\d+(?:\.\d+)?)\s*g',
            'carbohydrates': r'carbohydrate[s]?[:\s]*(\d+(?:\.\d+)?)\s*g',
            'sugars': r'(?:total\s)?sugars?[:\s]*(\d+(?:\.\d+)?)\s*g',
            'protein': r'protein[:\s]*(\d+(?:\.\d+)?)\s*g',
            'salt': r'salt[:\s]*(\d+(?:\.\d+)?)\s*g',
            'fiber': r'(?:dietary\s)?fib(?:re|er)[:\s]*(\d+(?:\.\d+)?)\s*g',
        }
        
        text_lower = text.lower()
        for nutrient, pattern in patterns.items():
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                nutritional_info[nutrient] = match.group(1) + ('g' if nutrient != 'calories' else '')
        
        return nutritional_info