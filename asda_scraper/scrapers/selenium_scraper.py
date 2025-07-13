"""
Enhanced Selenium scraper for ASDA with nutrition-only crawling support.

File: asda_scraper/scrapers/selenium_scraper.py
"""

import logging
import time
from typing import Optional, List
from django.utils import timezone
from django.db.models import Q

from asda_scraper.models import AsdaCategory, AsdaProduct, CrawlSession
from .webdriver_manager import WebDriverManager
from .category_manager import CategoryManager
from .product_extractor import ProductExtractor
from .nutrition_extractor import NutritionExtractor
from .popup_handler import PopupHandler
from .delay_manager import DelayManager
from .models import ScrapingResult
from .exceptions import ScraperException, DriverSetupException

logger = logging.getLogger(__name__)


class SeleniumAsdaScraper:
    """
    Production-ready Selenium-based ASDA scraper with nutrition-only support.
    """
    
    def __init__(self, crawl_session: CrawlSession, headless: bool = True):
        """
        Initialize Selenium ASDA scraper.
        
        Args:
            crawl_session: CrawlSession instance
            headless: Whether to run browser in headless mode
        """
        self.session = crawl_session
        self.headless = headless
        self.driver_manager = None
        self.driver = None
        self.base_url = "https://groceries.asda.com"
        
        # Initialize components
        self.product_extractor = None
        self.nutrition_extractor = None
        self.popup_handler = None
        self.delay_manager = DelayManager()
        
        logger.info(f"Selenium ASDA Scraper initialized for session {self.session.pk}")
        logger.info(f"Crawl type: {self.session.crawl_type}")
        
        try:
            self.driver_manager = WebDriverManager(headless=headless)
            self.driver = self.driver_manager.setup_driver()
            
            # Initialize extractors based on crawl type
            if self.session.crawl_type in ['PRODUCT', 'BOTH']:
                self.product_extractor = ProductExtractor(self.driver, crawl_session)
                self.product_extractor._parent_scraper = self
            
            if self.session.crawl_type in ['NUTRITION', 'BOTH']:
                self.nutrition_extractor = NutritionExtractor(self.driver)
                
            self.popup_handler = PopupHandler(self.driver)
            
        except DriverSetupException as e:
            logger.error(f"Failed to initialize scraper: {e}")
            raise
    
    def start_crawl(self) -> ScrapingResult:
        """
        Start the crawling process using Selenium.
        Routes to appropriate crawler based on crawl_type.
        
        Returns:
            ScrapingResult: Result of the scraping operation
        """
        try:
            logger.info(f"Starting {self.session.crawl_type} crawl for session {self.session.pk}")
            
            # Route based on crawl type
            if self.session.crawl_type == 'NUTRITION':
                return self._crawl_nutrition_only()
            elif self.session.crawl_type == 'PRODUCT':
                return self._crawl_products_only()
            elif self.session.crawl_type == 'BOTH':
                return self._crawl_products_and_nutrition()
            else:
                raise ScraperException(f"Unknown crawl type: {self.session.crawl_type}")
                
        except Exception as e:
            logger.error(f"Crawl failed: {e}")
            self.session.mark_failed(str(e))
            return ScrapingResult(
                products_found=self.session.products_found,
                products_saved=self.session.products_found,
                categories_processed=0,
                errors=[]
            )
        finally:
            if self.driver:
                self.driver.quit()
    
    def _crawl_nutrition_only(self) -> ScrapingResult:
        """
        Crawl only nutritional information for existing products.
        
        Returns:
            ScrapingResult: Result of nutrition crawling
        """
        try:
            logger.info("Starting nutrition-only crawl")
            
            # Get products that need nutrition data
            products = self._get_products_for_nutrition()
            total_products = len(products)
            
            if total_products == 0:
                logger.info("No products found that need nutrition data")
                self.session.mark_completed()
                return ScrapingResult(
                    products_found=0,
                    products_saved=0,
                    categories_processed=0
                )
            
            logger.info(f"Found {total_products} products needing nutrition data")
            
            success_count = 0
            error_count = 0
            
            for i, product in enumerate(products, 1):
                try:
                    # Update session progress
                    self.session.products_found = i
                    self.session.save()
                    
                    logger.info(f"[{i}/{total_products}] Processing: {product.name[:50]}...")
                    
                    # Skip if already has recent nutrition
                    if self._has_recent_nutrition(product):
                        logger.info(f"Skipping {product.name[:30]} - already has recent nutrition")
                        continue
                    
                    # Extract nutrition
                    nutrition_data = self._extract_nutrition_for_product(product)
                    
                    if nutrition_data:
                        # Save nutrition data
                        self._save_nutrition_data(product, nutrition_data)
                        success_count += 1
                        self.session.products_with_nutrition += 1
                        logger.info(f"Successfully extracted nutrition for: {product.name[:30]}")
                    else:
                        error_count += 1
                        self.session.nutrition_errors += 1
                        logger.warning(f"No nutrition data found for: {product.name[:30]}")
                    
                    # Save session updates
                    self.session.save()
                    
                    # Delay between products
                    delay = self.session.crawl_settings.get('delay', 2.0)
                    if i < total_products:
                        time.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"Error processing product {product.name}: {e}")
                    error_count += 1
                    self.session.nutrition_errors += 1
                    self.session.save()
                    continue
            
            # Mark session as completed
            self.session.mark_completed()
            
            return ScrapingResult(
                products_found=success_count,
                products_saved=success_count,
                categories_processed=0,
                errors=[f"Nutrition extraction complete: {success_count} successful, {error_count} errors"]
            )
            
        except Exception as e:
            logger.error(f"Nutrition crawl failed: {e}")
            raise
    
    def _crawl_products_only(self) -> ScrapingResult:
        """
        Crawl only product information (no nutrition).
        
        Returns:
            ScrapingResult: Result of product crawling
        """
        try:
            logger.info("Starting product-only crawl")
            
            # Navigate to ASDA homepage
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # Handle popups
            self.popup_handler.handle_popups()
            
            # Get categories to crawl
            category_manager = CategoryManager(self.driver, self.session)
            categories = self._get_categories_to_crawl()
            
            total_products = 0
            
            for category in categories:
                try:
                    logger.info(f"Crawling category: {category.name}")
                    products_found = self.product_extractor.extract_products_from_category(category)
                    total_products += products_found
                    
                    # Update session
                    self.session.categories_crawled += 1
                    self.session.save()
                    
                    # Delay between categories
                    self.delay_manager.wait('between_categories')
                    
                except Exception as e:
                    logger.error(f"Error crawling category {category.name}: {e}")
                    continue
            
            # Mark session as completed
            self.session.mark_completed()
            
            return ScrapingResult(
                products_found=total_products,
                products_saved=total_products,
                categories_processed=self.session.categories_crawled
            )
            
        except Exception as e:
            logger.error(f"Product crawl failed: {e}")
            raise
    
    def _crawl_products_and_nutrition(self) -> ScrapingResult:
        """
        Crawl both products and nutrition (existing behavior).
        
        Returns:
            ScrapingResult: Result of combined crawling
        """
        # This uses the existing product extractor which handles BOTH mode
        return self._crawl_products_only()
    
    def _get_products_for_nutrition(self) -> List[AsdaProduct]:
        """
        Get products that need nutritional information.
        
        Returns:
            List[AsdaProduct]: Products needing nutrition data
        """
        # Get max products from settings
        max_products = self.session.crawl_settings.get('max_products', 100)
        
        # Base query - products with URLs but no nutrition data
        query = AsdaProduct.objects.filter(
            product_url__isnull=False,
            product_url__gt=''
        ).exclude(
            product_url=''
        )
        
        # Filter by category if specified
        category_filter = self.session.crawl_settings.get('category_filter')
        if category_filter:
            query = query.filter(category__name__icontains=category_filter)
        
        # Exclude fresh produce categories
        if self.session.crawl_settings.get('exclude_fresh', True):
            fresh_keywords = ['fruit', 'vegetable', 'fresh', 'flower', 'plant', 'strawberr']
            for keyword in fresh_keywords:
                query = query.exclude(
                    Q(category__name__icontains=keyword) | 
                    Q(name__icontains=keyword)
                )
        
        # Priority categories (more likely to have nutrition)
        if self.session.crawl_settings.get('priority_categories', True):
            priority_keywords = ['bakery', 'bread', 'cereal', 'biscuit', 'snack', 'frozen', 'chilled']
            priority_q = Q()
            for keyword in priority_keywords:
                priority_q |= Q(category__name__icontains=keyword)
            
            # Get priority products first
            priority_products = list(query.filter(priority_q)[:max_products//2])
            remaining_needed = max_products - len(priority_products)
            
            if remaining_needed > 0:
                other_products = list(query.exclude(priority_q)[:remaining_needed])
                return priority_products + other_products
            
            return priority_products
        
        # Get products without recent nutrition
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        query = query.filter(
            Q(nutritional_info__isnull=True) | 
            Q(nutritional_info__exact={}) |
            Q(nutritional_info={}) |
            Q(updated_at__lt=three_days_ago)
        )
        
        # Order by creation date (newer products first)
        return list(query.order_by('-created_at')[:max_products])
    
    def _has_recent_nutrition(self, product: AsdaProduct) -> bool:
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
        nutrition_data = product.nutritional_info.get('nutrition', {})
        if not nutrition_data:
            return False
        
        # Check if updated recently (within 3 days)
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        return product.updated_at and product.updated_at > three_days_ago
    
    def _extract_nutrition_for_product(self, product: AsdaProduct) -> Optional[dict]:
        """
        Extract nutrition data for a single product.
        
        Args:
            product: AsdaProduct instance
            
        Returns:
            Optional[dict]: Nutrition data or None
        """
        try:
            if not product.product_url:
                logger.warning(f"No URL for product: {product.name}")
                return None
            
            # Extract nutrition using the nutrition extractor
            nutrition_data = self.nutrition_extractor.extract_from_url(product.product_url)
            
            return nutrition_data
            
        except Exception as e:
            logger.error(f"Error extracting nutrition for {product.name}: {e}")
            return None
    
    def _save_nutrition_data(self, product: AsdaProduct, nutrition_data: dict):
        """
        Save nutrition data to product.
        
        Args:
            product: AsdaProduct instance
            nutrition_data: Dictionary of nutrition data
        """
        try:
            # Create enhanced nutrition data with metadata
            enhanced_data = {
                'nutrition': nutrition_data,
                'extracted_at': timezone.now().isoformat(),
                'extraction_method': 'selenium_nutrition_crawler',
                'session_id': self.session.pk,
                'data_count': len(nutrition_data)
            }
            
            product.nutritional_info = enhanced_data
            product.save(update_fields=['nutritional_info', 'updated_at'])
            
            logger.info(f"Saved {len(nutrition_data)} nutrition values for {product.name[:30]}")
            
        except Exception as e:
            logger.error(f"Error saving nutrition data: {e}")
            raise
    
    def _get_categories_to_crawl(self) -> List[AsdaCategory]:
        """
        Get categories to crawl based on session settings.
        
        Returns:
            List[AsdaCategory]: Categories to crawl
        """
        # Get selected categories from session settings
        selected_ids = self.session.crawl_settings.get('selected_categories', [])
        
        if selected_ids:
            return list(AsdaCategory.objects.filter(id__in=selected_ids))
        else:
            # Default to all active categories
            return list(AsdaCategory.objects.filter(is_active=True))
    
    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
    
    def _cleanup(self):
        """Alias for cleanup method for compatibility."""
        self.cleanup()


def create_selenium_scraper(crawl_session: CrawlSession, headless: bool = True) -> SeleniumAsdaScraper:
    """
    Factory function to create a Selenium scraper instance.
    
    Args:
        crawl_session: CrawlSession instance
        headless: Whether to run browser in headless mode
        
    Returns:
        SeleniumAsdaScraper: Configured scraper instance
    """
    return SeleniumAsdaScraper(crawl_session, headless)