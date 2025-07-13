"""
Optimized nutrition extractor with faster processing and better caching.

File: asda_scraper/scrapers/optimized_nutrition_extractor.py
"""

import logging
import time
import re
import json
from typing import Dict, Optional, List, Set
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class OptimizedNutritionExtractor:
    """
    Optimized nutrition extractor with improved speed and caching.
    Focuses on speed while maintaining accuracy.
    """
    
    def __init__(self, driver: webdriver.Chrome):
        """
        Initialize optimized nutrition extractor.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.nutrition_cache = {}  # Cache for processed URLs
        self.failed_urls = set()   # Track failed URLs to avoid retries
        self.current_domain = None
        
        # Optimized selectors based on ASDA's current structure
        self.fast_selectors = [
            # Most common ASDA nutrition selectors (try these first)
            "[data-testid='pdp-product-nutrition']",
            "[data-testid='nutrition-table']",
            ".nutrition-information table",
            ".product-nutrition-info",
            
            # Fallback selectors
            "table[class*='nutrition']",
            "div[class*='nutrition'] table",
            "[aria-label*='nutrition' i] table",
            ".pdp__nutritional-information",
        ]
        
        # Common nutrition nutrients to extract (prioritized)
        self.priority_nutrients = [
            'energy', 'kcal', 'kj', 'calories',
            'fat', 'saturated', 'saturates',
            'carbohydrate', 'carbs', 'sugar', 'sugars',
            'protein', 'salt', 'fibre', 'fiber'
        ]
        
        # Pre-compiled regex patterns for faster matching
        self.nutrition_patterns = {
            'energy_kcal': re.compile(r'(\d+(?:\.\d+)?)\s*kcal', re.IGNORECASE),
            'energy_kj': re.compile(r'(\d+(?:\.\d+)?)\s*kj', re.IGNORECASE),
            'fat': re.compile(r'fat.*?(\d+(?:\.\d+)?)\s*g', re.IGNORECASE),
            'saturated': re.compile(r'saturated.*?(\d+(?:\.\d+)?)\s*g', re.IGNORECASE),
            'carbs': re.compile(r'carb.*?(\d+(?:\.\d+)?)\s*g', re.IGNORECASE),
            'sugar': re.compile(r'sugar.*?(\d+(?:\.\d+)?)\s*g', re.IGNORECASE),
            'protein': re.compile(r'protein.*?(\d+(?:\.\d+)?)\s*g', re.IGNORECASE),
            'salt': re.compile(r'salt.*?(\d+(?:\.\d+)?)\s*g', re.IGNORECASE),
            'fibre': re.compile(r'fi[bv]re.*?(\d+(?:\.\d+)?)\s*g', re.IGNORECASE),
        }
    
    def extract_from_url(self, nutrition_url: str, timeout: int = 10) -> Optional[Dict[str, str]]:
        """
        Extract nutritional information from URL with optimizations.
        
        Args:
            nutrition_url: URL to extract nutrition from
            timeout: Maximum time to wait for page load
            
        Returns:
            Optional[Dict[str, str]]: Nutrition data or None if extraction fails
        """
        if not nutrition_url or nutrition_url in self.failed_urls:
            return None
        
        # Check cache first
        if nutrition_url in self.nutrition_cache:
            logger.debug(f"🔬 ⚡ Cache hit for: {nutrition_url}")
            return self.nutrition_cache[nutrition_url]
        
        try:
            start_time = time.time()
            logger.info(f"🔬 Extracting nutrition from: {nutrition_url}")
            
            # Navigate to URL with timeout
            self.driver.set_page_load_timeout(timeout)
            self.driver.get(nutrition_url)
            
            # Quick wait for basic page structure
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Fast extraction using multiple strategies
            nutrition_data = self._fast_extract_nutrition()
            
            # Cache result (even if None to avoid re-processing)
            self.nutrition_cache[nutrition_url] = nutrition_data
            
            if not nutrition_data:
                self.failed_urls.add(nutrition_url)
                logger.warning(f"🔬 ❌ No nutrition found: {nutrition_url}")
            else:
                extraction_time = time.time() - start_time
                logger.info(f"🔬 ✅ Nutrition extracted in {extraction_time:.2f}s")
            
            return nutrition_data
            
        except TimeoutException:
            logger.warning(f"🔬 ⏰ Timeout extracting from: {nutrition_url}")
            self.failed_urls.add(nutrition_url)
            return None
            
        except Exception as e:
            logger.error(f"🔬 ❌ Error extracting nutrition: {e}")
            self.failed_urls.add(nutrition_url)
            return None
    
    def _fast_extract_nutrition(self) -> Optional[Dict[str, str]]:
        """
        Fast nutrition extraction using optimized strategies.
        
        Returns:
            Optional[Dict[str, str]]: Extracted nutrition data
        """
        # Strategy 1: Fast selector search
        nutrition_data = self._extract_using_fast_selectors()
        if nutrition_data:
            return nutrition_data
        
        # Strategy 2: Regex extraction from page text
        nutrition_data = self._extract_using_regex()
        if nutrition_data:
            return nutrition_data
        
        # Strategy 3: Table-based extraction (fallback)
        nutrition_data = self._extract_from_tables()
        if nutrition_data:
            return nutrition_data
        
        return None
    
    def _extract_using_fast_selectors(self) -> Optional[Dict[str, str]]:
        """
        Extract nutrition using optimized CSS selectors.
        
        Returns:
            Optional[Dict[str, str]]: Nutrition data
        """
        try:
            for selector in self.fast_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        # Get text content quickly
                        text_content = element.get_attribute('textContent') or element.text
                        
                        if not text_content:
                            continue
                        
                        # Check if this looks like nutrition content
                        if self._is_nutrition_content(text_content):
                            nutrition_data = self._parse_nutrition_text(text_content)
                            if nutrition_data:
                                logger.debug(f"🔬 ⚡ Fast selector success: {selector}")
                                return nutrition_data
                
                except NoSuchElementException:
                    continue
                except Exception as e:
                    logger.debug(f"🔬 Selector {selector} failed: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"🔬 Fast selector extraction failed: {e}")
            return None
    
    def _extract_using_regex(self) -> Optional[Dict[str, str]]:
        """
        Extract nutrition using regex patterns on page text.
        
        Returns:
            Optional[Dict[str, str]]: Nutrition data
        """
        try:
            # Get page text quickly
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            if not page_text or len(page_text) < 100:
                return None
            
            # Apply regex patterns
            nutrition_data = {}
            
            for nutrient, pattern in self.nutrition_patterns.items():
                matches = pattern.findall(page_text)
                if matches:
                    # Take first match and format appropriately
                    value = matches[0]
                    if nutrient.startswith('energy'):
                        nutrition_data[f"Energy ({nutrient.split('_')[1].upper()})"] = f"{value}"
                    else:
                        nutrition_data[nutrient.capitalize()] = f"{value}g"
            
            if len(nutrition_data) >= 3:  # Require at least 3 nutrients
                logger.debug("🔬 ⚡ Regex extraction successful")
                return nutrition_data
            
            return None
            
        except Exception as e:
            logger.error(f"🔬 Regex extraction failed: {e}")
            return None
    
    def _extract_from_tables(self) -> Optional[Dict[str, str]]:
        """
        Extract nutrition from HTML tables (fallback method).
        
        Returns:
            Optional[Dict[str, str]]: Nutrition data
        """
        try:
            # Find all tables
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            
            for table in tables:
                try:
                    # Get table HTML and parse with BeautifulSoup for speed
                    table_html = table.get_attribute('outerHTML')
                    soup = BeautifulSoup(table_html, 'html.parser')
                    
                    nutrition_data = self._parse_nutrition_table(soup)
                    if nutrition_data:
                        logger.debug("🔬 ⚡ Table extraction successful")
                        return nutrition_data
                
                except Exception as e:
                    logger.debug(f"🔬 Table processing failed: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"🔬 Table extraction failed: {e}")
            return None
    
    def _is_nutrition_content(self, text: str) -> bool:
        """
        Check if text content appears to contain nutrition information.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text appears to contain nutrition info
        """
        if not text or len(text) < 20:
            return False
        
        text_lower = text.lower()
        
        # Count nutrition keywords
        keyword_count = sum(1 for keyword in self.priority_nutrients 
                          if keyword in text_lower)
        
        # Check for numeric values with units
        has_values = bool(re.search(r'\d+(?:\.\d+)?\s*[gk]', text))
        
        return keyword_count >= 2 and has_values
    
    def _parse_nutrition_text(self, text: str) -> Optional[Dict[str, str]]:
        """
        Parse nutrition information from text content.
        
        Args:
            text: Text containing nutrition information
            
        Returns:
            Optional[Dict[str, str]]: Parsed nutrition data
        """
        try:
            nutrition_data = {}
            
            # Split text into lines for easier processing
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            for line in lines:
                # Look for patterns like "Protein: 5.2g" or "Energy 120kcal"
                for nutrient in self.priority_nutrients:
                    pattern = rf'{nutrient}[:\s]*(\d+(?:\.\d+)?)\s*([gkm]?[cj]?[al]?[ls]?)'
                    match = re.search(pattern, line, re.IGNORECASE)
                    
                    if match:
                        value = match.group(1)
                        unit = match.group(2) or 'g'
                        
                        # Standardize nutrient names
                        key = self._standardize_nutrient_name(nutrient)
                        nutrition_data[key] = f"{value}{unit}"
                        break
            
            return nutrition_data if len(nutrition_data) >= 2 else None
            
        except Exception as e:
            logger.error(f"🔬 Text parsing failed: {e}")
            return None
    
    def _parse_nutrition_table(self, soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Parse nutrition table using BeautifulSoup.
        
        Args:
            soup: BeautifulSoup table element
            
        Returns:
            Optional[Dict[str, str]]: Nutrition data
        """
        try:
            nutrition_data = {}
            rows = soup.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) >= 2:
                    nutrient = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    
                    # Check if this looks like a nutrition row
                    if any(keyword in nutrient.lower() for keyword in self.priority_nutrients):
                        # Clean and standardize
                        key = self._standardize_nutrient_name(nutrient)
                        nutrition_data[key] = value
            
            return nutrition_data if len(nutrition_data) >= 2 else None
            
        except Exception as e:
            logger.error(f"🔬 Table parsing failed: {e}")
            return None
    
    def _standardize_nutrient_name(self, nutrient: str) -> str:
        """
        Standardize nutrient names for consistency.
        
        Args:
            nutrient: Raw nutrient name
            
        Returns:
            str: Standardized nutrient name
        """
        nutrient_lower = nutrient.lower().strip()
        
        # Map common variations to standard names
        mappings = {
            'energy': 'Energy',
            'kcal': 'Energy (kcal)',
            'kj': 'Energy (kJ)',
            'calories': 'Energy (kcal)',
            'fat': 'Fat',
            'saturated': 'Saturates',
            'saturates': 'Saturates',
            'carbohydrate': 'Carbohydrate',
            'carbs': 'Carbohydrate',
            'sugar': 'Sugars',
            'sugars': 'Sugars',
            'protein': 'Protein',
            'salt': 'Salt',
            'fibre': 'Fibre',
            'fiber': 'Fibre',
        }
        
        for key, standard_name in mappings.items():
            if key in nutrient_lower:
                return standard_name
        
        # Return capitalized version if no mapping found
        return nutrient.capitalize()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about the nutrition cache.
        
        Returns:
            Dict[str, int]: Cache statistics
        """
        return {
            'cached_urls': len(self.nutrition_cache),
            'failed_urls': len(self.failed_urls),
            'success_rate': len([v for v in self.nutrition_cache.values() if v]) / 
                          max(len(self.nutrition_cache), 1) * 100
        }
    
    def clear_cache(self):
        """Clear the nutrition cache and failed URLs."""
        self.nutrition_cache.clear()
        self.failed_urls.clear()
        logger.info("🔬 🧹 Nutrition cache cleared")