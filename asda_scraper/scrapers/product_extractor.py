"""
Enhanced Product extraction functionality for ASDA scraper with fixed nutrition saving.

File: asda_scraper/scrapers/product_extractor.py
"""

import logging
import time
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from django.db.models import F
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading

from asda_scraper.models import AsdaCategory, AsdaProduct, CrawlSession
from .models import ProductData
from .popup_handler import PopupHandler
from .config import SCRAPER_SETTINGS

logger = logging.getLogger(__name__)


class ProductExtractor:
    """
    Product extractor that supports both PRODUCT and BOTH crawl types.
    
    - PRODUCT mode: Fast product and price extraction only
    - BOTH mode: Products + conditional nutrition extraction
    """
    
    def __init__(self, driver: webdriver.Chrome, session: CrawlSession):
        """
        Initialize product extractor with crawl type awareness.
        
        Args:
            driver: Selenium WebDriver instance
            session: Current crawl session
        """
        self.driver = driver
        self.session = session
        self.base_url = "https://groceries.asda.com"
        self._parent_scraper = None
        self._nutrition_extractor = None
        self._executor = ThreadPoolExecutor(max_workers=1)  # For timeout handling
        
        # Log initialization mode
        if session.crawl_type == 'BOTH':
            logger.info("ProductExtractor initialized for BOTH mode (products + nutrition)")
        else:
            logger.info("ProductExtractor initialized for PRODUCT mode (fast, no nutrition)")
        
        logger.info(f"Crawl type: {session.crawl_type}")
        logger.info(f"Session ID: {session.pk}")
    
    def __del__(self):
        """Cleanup executor on deletion."""
        if hasattr(self, '_executor') and self._executor:
            self._executor.shutdown(wait=False)
    
    def extract_products_from_category(self, category: AsdaCategory) -> int:
        """
        Extract products from a specific category.
        
        Args:
            category: AsdaCategory to extract products from
            
        Returns:
            int: Number of products extracted
        """
        try:
            from .category_manager import CategoryManager
            category_manager = CategoryManager(self.driver, self.session)
            category_url = category_manager.get_category_url(category)
            
            if not category_url:
                logger.error(f"No URL found for category: {category.name}")
                return 0
            
            logger.info(f"Crawling category: {category.name}")
            logger.info(f"URL: {category_url}")
            
            self.driver.get(category_url)
            time.sleep(3)
            
            popup_handler = PopupHandler(self.driver)
            popup_handler.handle_popups()
            
            return self._extract_products_from_current_page(category)
            
        except Exception as e:
            logger.error(f"Error crawling category {category.name}: {e}")
            return 0
    
    def _extract_products_from_current_page(self, category: AsdaCategory) -> int:
        """
        Extract products from the current page with pagination support.
        
        Args:
            category: AsdaCategory instance
            
        Returns:
            int: Total number of products extracted
        """
        total_products = 0
        page_num = 1
        
        try:
            while True:
                logger.info(f"Extracting products from {category.name} page {page_num}")
                
                # Extract products from current page
                products_found = self._extract_products_from_page(category, page_num)
                total_products += products_found
                
                if products_found == 0:
                    logger.info("No products found on page, finishing")
                    break
                
                # Check for next page
                if not self._navigate_to_next_page():
                    logger.info("No more pages available")
                    break
                
                page_num += 1
                time.sleep(2)  # Delay between pages
                
            return total_products
            
        except Exception as e:
            logger.error(f"Error during pagination: {e}")
            return total_products
    
    def _save_product_data(self, product_data: ProductData, category: AsdaCategory) -> bool:
        """
        Save product data to database with CONDITIONAL nutrition extraction.
        
        Args:
            product_data: ProductData instance
            category: AsdaCategory instance
            
        Returns:
            bool: True if saved successfully
        """
        try:
            if not product_data.validate():
                logger.warning("Invalid product data")
                return False
            
            product, created = AsdaProduct.objects.get_or_create(
                asda_id=product_data.asda_id,
                defaults={
                    'name': product_data.name,
                    'price': product_data.price,
                    'was_price': product_data.was_price,
                    'unit': product_data.unit,
                    'description': product_data.description,
                    'image_url': product_data.image_url,
                    'product_url': product_data.product_url,
                    'category': category,
                    'in_stock': product_data.in_stock,
                    'special_offer': product_data.special_offer,
                    'rating': product_data.rating,
                    'review_count': product_data.review_count,
                    'price_per_unit': product_data.price_per_unit,
                }
            )
            
            if created:
                self.session.products_found += 1
                logger.info(f"Created: {product.name[:50]} - £{product.price}")
            else:
                # Update existing product
                price_changed = False
                if product.price != product_data.price:
                    old_price = product.price
                    price_changed = True
                    logger.info(f"Price change: {product.name[:40]} £{old_price} → £{product_data.price}")
                
                # Update all fields
                for field in ['name', 'price', 'was_price', 'unit', 'description', 
                             'image_url', 'product_url', 'in_stock', 'special_offer',
                             'rating', 'review_count', 'price_per_unit']:
                    value = getattr(product_data, field)
                    if value is not None:
                        setattr(product, field, value)
                
                product.category = category
                product.save()
                self.session.products_updated += 1
                logger.info(f"Updated: {product.name[:50]} - £{product.price}")
            
            # CONDITIONAL NUTRITION EXTRACTION FOR "BOTH" CRAWL TYPE
            if (self.session.crawl_type == 'BOTH' and 
                product.product_url and 
                not self._has_recent_nutrition(product) and
                self._should_extract_nutrition(product)):
                
                logger.info(f"Extracting nutrition for: {product.name[:50]}...")
                nutrition_success = self._extract_and_save_nutrition_fast(product)
                
                if nutrition_success:
                    self.session.products_with_nutrition += 1
                    logger.info(f"Nutrition added for: {product.name[:50]}")
                else:
                    self.session.nutrition_errors += 1
                    logger.debug(f"No nutrition data for: {product.name[:50]}")
            
            self.session.save()
            
            # Update category product count
            category.product_count = category.products.count()
            category.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving product {product_data.name}: {e}")
            return False
    
    def _should_extract_nutrition(self, product) -> bool:
        """
        Check if we should attempt nutrition extraction for this product.
        
        Args:
            product: AsdaProduct instance
            
        Returns:
            bool: True if should extract nutrition
        """
        # Skip fresh produce (unlikely to have nutrition labels)
        fresh_keywords = ['fruit', 'vegetable', 'fresh', 'flower', 'plant', 'strawberr']
        category_name = product.category.name.lower()
        product_name = product.name.lower()
        
        if any(keyword in category_name for keyword in fresh_keywords):
            logger.debug(f"Skipping nutrition for fresh produce: {product.name[:30]}")
            return False
        
        if any(keyword in product_name for keyword in fresh_keywords):
            logger.debug(f"Skipping nutrition for fresh produce: {product.name[:30]}")
            return False
        
        # Focus on processed foods that likely have nutrition labels
        processed_keywords = ['bakery', 'bread', 'chilled', 'frozen', 'cupboard', 'snack', 'cereal', 'biscuit']
        if any(keyword in category_name for keyword in processed_keywords):
            return True
        
        # Default to not extracting for performance
        return False
    
    def _has_recent_nutrition(self, product) -> bool:
        """
        Check if product has recent nutritional information.
        
        Args:
            product: AsdaProduct instance
            
        Returns:
            bool: True if has recent nutrition data
        """
        if not product.nutritional_info:
            return False
        
        if not isinstance(product.nutritional_info, dict):
            return False
        
        # Check if has actual nutrition data
        if 'nutrition' not in product.nutritional_info:
            return False
        
        nutrition_data = product.nutritional_info.get('nutrition', {})
        if not nutrition_data:
            return False
        
        # Check if updated recently (within 7 days for BOTH crawl type)
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        return product.updated_at and product.updated_at > seven_days_ago
    
    def _extract_and_save_nutrition_fast(self, product) -> bool:
        """
        FAST nutrition extraction with proper timeout handling for Windows.
        
        Args:
            product: AsdaProduct instance
            
        Returns:
            bool: True if nutrition data was successfully extracted and saved
        """
        try:
            # Initialize nutrition extractor if not already available
            if not hasattr(self, '_nutrition_extractor') or self._nutrition_extractor is None:
                from .nutrition_extractor import NutritionExtractor
                self._nutrition_extractor = NutritionExtractor(self.driver)
                self._nutrition_extractor.debug_mode = False  # Disable debug for speed
                logger.info("Initialized FAST nutrition extractor for BOTH crawl type")
            
            # Store current URL
            current_url = self.driver.current_url
            
            # Extract nutrition data with timeout using ThreadPoolExecutor
            start_time = time.time()
            nutrition_data = None
            
            try:
                # Create a future for the extraction
                future = self._executor.submit(
                    self._nutrition_extractor.extract_from_url,
                    product.product_url
                )
                
                # Wait with timeout
                nutrition_data = future.result(timeout=15)  # 15 second timeout
                
            except FutureTimeoutError:
                logger.debug(f"Nutrition extraction timeout for: {product.name[:30]}")
                # Try to cancel the operation
                future.cancel()
                # Navigate back to original URL
                try:
                    self.driver.get(current_url)
                    time.sleep(1)
                except:
                    pass
                return False
            except Exception as e:
                logger.debug(f"Nutrition extraction error for {product.name[:30]}: {e}")
                # Navigate back to original URL
                try:
                    self.driver.get(current_url)
                    time.sleep(1)
                except:
                    pass
                return False
            
            extract_time = time.time() - start_time
            
            if nutrition_data and len(nutrition_data) > 0:
                # Create enhanced nutrition data with metadata
                enhanced_data = {
                    'nutrition': nutrition_data,
                    'extracted_at': timezone.now().isoformat(),
                    'extraction_method': 'both_crawl_fast',
                    'data_count': len(nutrition_data),
                    'extract_time': round(extract_time, 2)
                }
                
                # Save to product
                product.nutritional_info = enhanced_data
                product.save(update_fields=['nutritional_info', 'updated_at'])
                
                logger.info(f"Saved {len(nutrition_data)} nutrition values for {product.name[:30]} (took {extract_time:.1f}s)")
                return True
            else:
                logger.debug(f"No nutrition data found for {product.name[:30]} (took {extract_time:.1f}s)")
                return False
                
        except Exception as e:
            logger.error(f"Error extracting nutrition for {product.name}: {e}")
            return False
    
    def _extract_products_from_page(self, category: AsdaCategory, page_num: int) -> int:
        """
        Extract products from the current page.
        
        Args:
            category: AsdaCategory instance
            page_num: Current page number
            
        Returns:
            int: Number of products extracted
        """
        try:
            logger.info(f"Processing page {page_num} of {category.name}")
            
            # Wait for products to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.co-product"))
            )
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Find all product containers
            product_containers = soup.find_all('div', class_='co-product')
            logger.info(f"Found {len(product_containers)} product containers")
            
            products_saved = 0
            
            for container in product_containers:
                try:
                    product_data = self._extract_product_data(container)
                    if product_data and self._save_product_data(product_data, category):
                        products_saved += 1
                except Exception as e:
                    logger.error(f"Error extracting product: {e}")
                    continue
            
            logger.info(f"Saved {products_saved} products from page {page_num}")
            return products_saved
            
        except TimeoutException:
            logger.warning(f"Timeout waiting for products on page {page_num}")
            return 0
        except Exception as e:
            logger.error(f"Error extracting products from page: {e}")
            return 0
    
    def _extract_product_data(self, container) -> Optional[ProductData]:
        """
        Extract product data from a container element.
        
        Args:
            container: BeautifulSoup element containing product data
            
        Returns:
            Optional[ProductData]: Extracted product data or None
        """
        try:
            # Extract basic product information
            name = self._extract_name(container)
            if not name:
                return None
            
            asda_id = self._extract_asda_id(container)
            if not asda_id:
                return None
            
            price = self._extract_price(container)
            if price is None:
                return None
            
            # Create product data
            product_data = ProductData(
                asda_id=asda_id,
                name=name,
                price=price,
                was_price=self._extract_was_price(container),
                unit=self._extract_unit(container),
                description="",  # Will be filled from detail page if needed
                image_url=self._extract_image_url(container),
                product_url=self._extract_product_url(container),
                in_stock=True,  # Assume in stock if displayed
                special_offer=bool(container.select_one('.co-product__promo-pill')),
            )
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error extracting product data: {e}")
            return None
    
    def _extract_name(self, container) -> Optional[str]:
        """Extract product name."""
        name_element = container.select_one('h3.co-product__title, a.co-product__anchor')
        return name_element.get_text(strip=True) if name_element else None
    
    def _extract_asda_id(self, container) -> Optional[str]:
        """Extract ASDA product ID."""
        link_element = container.select_one('a.co-product__anchor')
        if link_element and link_element.get('href'):
            match = re.search(r'/(\d+)$', link_element['href'])
            if match:
                return match.group(1)
        return None
    
    def _extract_price(self, container) -> Optional[float]:
        """Extract current price."""
        price_element = container.select_one('.co-product__price')
        if price_element:
            price_text = price_element.get_text()
            match = re.search(r'£(\d+\.?\d*)', price_text)
            if match:
                return float(match.group(1))
        return None
    
    def _extract_was_price(self, container) -> Optional[float]:
        """Extract was price if available."""
        was_price_element = container.select_one('span.co-product__was-price')
        if was_price_element:
            was_price_match = re.search(r'£(\d+\.?\d*)', was_price_element.get_text())
            if was_price_match:
                return float(was_price_match.group(1))
        return None
    
    def _extract_unit(self, container) -> str:
        """Extract unit information."""
        unit_element = container.select_one('span.co-product__volume')
        return unit_element.get_text(strip=True) if unit_element else 'each'
    
    def _extract_image_url(self, container) -> str:
        """Extract product image URL."""
        img_element = container.select_one('img.asda-img')
        return img_element.get('src', '') if img_element else ''
    
    def _extract_product_url(self, container) -> Optional[str]:
        """Extract product detail page URL."""
        link_element = container.select_one('a.co-product__anchor')
        if link_element and link_element.get('href'):
            return urljoin(self.base_url, link_element['href'])
        return None
    
    def _navigate_to_next_page(self) -> bool:
        """
        Navigate to the next page of products if pagination exists.
        
        Returns:
            bool: True if successfully navigated to next page
        """
        try:
            # Look for next page button
            next_button = self.driver.find_element(
                By.CSS_SELECTOR, 
                "button[aria-label*='next' i], a[aria-label*='next' i]"
            )
            
            if next_button.is_enabled():
                self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(1)
                next_button.click()
                time.sleep(2)  # Wait for page to load
                return True
            
            return False
            
        except NoSuchElementException:
            logger.debug("No next page button found")
            return False
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False