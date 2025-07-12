"""
Optimized Product extraction functionality for ASDA scraper - PRODUCT/PRICE ONLY.

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

from asda_scraper.models import AsdaCategory, AsdaProduct, CrawlSession
from .models import ProductData
from .popup_handler import PopupHandler
from .config import SCRAPER_SETTINGS

logger = logging.getLogger(__name__)


class ProductExtractor:
    """
    OPTIMIZED: Extracts ONLY product data and pricing from ASDA category pages.
    
    This version SKIPS nutritional information extraction for maximum speed and reliability.
    Use the separate NutritionCrawler for nutritional data.
    """
    
    def __init__(self, driver: webdriver.Chrome, session: CrawlSession):
        """
        Initialize product extractor.
        
        Args:
            driver: Selenium WebDriver instance
            session: Current crawl session
        """
        self.driver = driver
        self.session = session
        self.base_url = "https://groceries.asda.com"
        self._parent_scraper = None  # Reference to parent scraper
    
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
            category: AsdaCategory being processed
            
        Returns:
            int: Number of products extracted
        """
        try:
            products_found = 0
            max_products = self.session.crawl_settings.get('max_products_per_category', 100)
            
            logger.info(f"Extracting products from {category.name} page")
            
            if not self._wait_for_products_to_load():
                logger.warning(f"Timeout waiting for products to load on {category.name}")
                return 0
            
            page_num = 1
            max_pages = SCRAPER_SETTINGS.get('max_pages_per_category', 5)
            
            while page_num <= max_pages and products_found < max_products:
                logger.info(f"Processing page {page_num} of {category.name}")
                
                page_products = self._extract_products_from_page(category)
                products_found += page_products
                
                logger.info(f"Page {page_num}: {page_products} products extracted")
                
                if page_products > 0 and products_found < max_products:
                    if not self._navigate_to_next_page():
                        logger.info(f"No more pages available for {category.name}")
                        break
                    page_num += 1
                    time.sleep(2)
                else:
                    break
            
            logger.info(f"Total products extracted from {category.name}: {products_found}")
            return products_found
            
        except Exception as e:
            logger.error(f"Error extracting products from {category.name}: {e}")
            return 0
    
    def _wait_for_products_to_load(self, timeout: int = 10) -> bool:
        """
        Wait for products to load on the page.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            bool: True if products loaded
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    'div.co-product, div[class*="co-product"], div[class*="product-tile"]'
                ))
            )
            return True
        except TimeoutException:
            return False
    
    def _extract_products_from_page(self, category: AsdaCategory) -> int:
        """
        Extract products from the current page.
        
        Args:
            category: AsdaCategory being processed
            
        Returns:
            int: Number of products saved
        """
        try:
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            product_containers = self._find_product_containers(soup)
            
            if not product_containers:
                logger.warning(f"No product containers found on {category.name}")
                return 0
            
            logger.info(f"Found {len(product_containers)} product containers")
            
            products_saved = 0
            for container in product_containers:
                try:
                    product_data = self._extract_product_data(container, category)
                    
                    if product_data:
                        if self._save_product_data(product_data, category):
                            products_saved += 1
                            logger.debug(f"Saved product: {product_data.name[:50]}...")
                
                except Exception as e:
                    logger.error(f"Error extracting product data: {e}")
                    continue
            
            return products_saved
            
        except Exception as e:
            logger.error(f"Error extracting products from page: {e}")
            return 0
    
    def _find_product_containers(self, soup: BeautifulSoup) -> List:
        """
        Find product containers using multiple selectors.
        
        Args:
            soup: BeautifulSoup parsed page
            
        Returns:
            List: Product container elements
        """
        selectors = [
            'div.co-product',
            'div[class*="co-product"]',
            'div[class*="product-tile"]',
            'div[class*="product-item"]',
            'article[class*="product"]',
            '[data-testid*="product"]'
        ]
        
        for selector in selectors:
            containers = soup.select(selector)
            if containers:
                logger.info(f"Found {len(containers)} products using selector: {selector}")
                return containers
        
        logger.warning("No product containers found with any selector")
        return []
    
    def _extract_product_data(self, container, category: AsdaCategory) -> Optional[ProductData]:
        """
        Extract product data from container.
        
        Args:
            container: BeautifulSoup element containing product
            category: AsdaCategory being processed
            
        Returns:
            Optional[ProductData]: Extracted product data or None
        """
        try:
            # Find product link and name
            title_link = container.select_one('a.co-product__anchor, a[href*="/product/"]')
            if not title_link:
                return None
            
            name = title_link.get_text(strip=True)
            product_url = urljoin(self.base_url, title_link.get('href', ''))
            
            # Find price
            price_element = container.select_one('strong.co-product__price, .price strong')
            if not price_element:
                return None
            
            price_text = price_element.get_text(strip=True)
            price_match = re.search(r'£(\d+\.?\d*)', price_text)
            if not price_match:
                return None
            
            price = float(price_match.group(1))
            
            # Extract ASDA ID
            asda_id_match = re.search(r'/(\d+)$', product_url)
            asda_id = (asda_id_match.group(1) if asda_id_match 
                      else f"{category.url_code}_{hash(name) % 100000}")
            
            # Extract optional fields
            was_price = self._extract_was_price(container)
            unit = self._extract_unit(container)
            image_url = self._extract_image_url(container)
            
            return ProductData(
                name=name,
                price=price,
                was_price=was_price,
                unit=unit,
                description=name,
                image_url=image_url,
                product_url=product_url,
                asda_id=asda_id,
                in_stock=True,
                special_offer='',
                rating=None,
                review_count='',
                price_per_unit='',
            )
            
        except Exception as e:
            logger.error(f"Error extracting product data: {e}")
            return None
    
    def _extract_was_price(self, container) -> Optional[float]:
        """
        Extract was price if product is on sale.
        
        Args:
            container: Product container element
            
        Returns:
            Optional[float]: Was price or None
        """
        was_price_element = container.select_one('span.co-product__was-price')
        if was_price_element:
            was_price_match = re.search(r'£(\d+\.?\d*)', was_price_element.get_text())
            if was_price_match:
                return float(was_price_match.group(1))
        return None
    
    def _extract_unit(self, container) -> str:
        """
        Extract unit information.
        
        Args:
            container: Product container element
            
        Returns:
            str: Unit information
        """
        unit_element = container.select_one('span.co-product__volume')
        return unit_element.get_text(strip=True) if unit_element else 'each'
    
    def _extract_image_url(self, container) -> str:
        """
        Extract product image URL.
        
        Args:
            container: Product container element
            
        Returns:
            str: Image URL
        """
        img_element = container.select_one('img.asda-img')
        return img_element.get('src', '') if img_element else ''
    
    def _save_product_data(self, product_data: ProductData, category: AsdaCategory) -> bool:
        """
        OPTIMIZED: Save product data to database WITHOUT nutrition extraction.
        
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
                logger.info(f"Created: {product.name} in {category.name}")
            else:
                # Update existing product - CHECK FOR PRICE CHANGES
                price_changed = False
                if product.price != product_data.price:
                    old_price = product.price
                    price_changed = True
                    logger.info(f"Price change for {product.name}: £{old_price} → £{product_data.price}")
                
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
                logger.info(f"Updated: {product.name} in {category.name}")
            
            # ✅ NUTRITION EXTRACTION REMOVED FOR SPEED
            # Nutrition data will be handled by separate NutritionCrawler
            
            self.session.save()
            
            # Update category product count
            category.product_count = category.products.count()
            category.save()
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving product {product_data.name}: {e}")
            return False
    
    def _navigate_to_next_page(self) -> bool:
        """
        Navigate to the next page of products if pagination exists.
        
        Returns:
            bool: True if navigation successful
        """
        try:
            next_selectors = [
                'a[aria-label="Next"]',
                'a.pagination-next',
                'a[class*="next"]',
                'button[aria-label="Next"]',
                'button.pagination-next',
                'button[class*="next"]'
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if next_button.is_enabled() and next_button.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(1)
                        next_button.click()
                        time.sleep(3)
                        logger.debug(f"Navigated to next page using selector: {selector}")
                        return True
                        
                except (NoSuchElementException, Exception):
                    continue
            
            logger.debug("No next page button found or enabled")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False