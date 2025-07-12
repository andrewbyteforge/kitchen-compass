"""
Standalone nutrition crawler that works independently of the main scraper.

File: asda_scraper/scrapers/standalone_nutrition_crawler.py
"""

import logging
import time
from typing import Dict, Optional, List
from django.utils import timezone
from django.db.models import Q
from selenium import webdriver

from asda_scraper.models import AsdaProduct, CrawlSession
from .webdriver_manager import WebDriverManager
from .nutrition_extractor import NutritionExtractor
from .popup_handler import PopupHandler

logger = logging.getLogger(__name__)


class StandaloneNutritionCrawler:
    """
    Standalone nutrition crawler that can run independently.
    Designed for simplicity and reliability.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the nutrition crawler.
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.driver = None
        self.nutrition_extractor = None
        self.popup_handler = None
        self.stats = {
            'products_processed': 0,
            'nutrition_found': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def setup(self):
        """Set up the crawler components."""
        try:
            logger.info("Setting up standalone nutrition crawler...")
            
            # Setup WebDriver
            driver_manager = WebDriverManager(headless=self.headless)
            self.driver = driver_manager.setup_driver()
            
            # Initialize extractors
            self.nutrition_extractor = NutritionExtractor(self.driver)
            self.popup_handler = PopupHandler(self.driver)
            
            logger.info("Nutrition crawler setup complete")
            
        except Exception as e:
            logger.error(f"Failed to setup nutrition crawler: {e}")
            self.cleanup()
            raise
    
    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
    
    def crawl_nutrition(
        self, 
        max_products: int = 100,
        category_filter: Optional[str] = None,
        exclude_fresh: bool = True,
        priority_categories: bool = True,
        delay: float = 2.0,
        force_recrawl: bool = False
    ) -> Dict[str, int]:
        """
        Crawl nutrition information for products.
        
        Args:
            max_products: Maximum number of products to process
            category_filter: Optional category name filter
            exclude_fresh: Whether to exclude fresh produce
            priority_categories: Whether to prioritize certain categories
            delay: Delay between products in seconds
            force_recrawl: Whether to recrawl products with existing nutrition
            
        Returns:
            Dict[str, int]: Statistics about the crawl
        """
        try:
            # Setup if not already done
            if not self.driver:
                self.setup()
            
            # Get products to process
            products = self._get_products_for_nutrition(
                max_products=max_products,
                category_filter=category_filter,
                exclude_fresh=exclude_fresh,
                priority_categories=priority_categories,
                force_recrawl=force_recrawl
            )
            
            if not products:
                logger.info("No products found that need nutrition data")
                return self.stats
            
            logger.info(f"Found {len(products)} products to process")
            
            # Process each product
            for i, product in enumerate(products, 1):
                try:
                    logger.info(f"[{i}/{len(products)}] Processing: {product.name[:50]}...")
                    
                    # Check if already has nutrition (unless force recrawl)
                    if not force_recrawl and self._has_recent_nutrition(product):
                        logger.info(f"Skipping - already has recent nutrition data")
                        self.stats['skipped'] += 1
                        continue
                    
                    # Extract nutrition
                    nutrition_data = self._extract_nutrition_for_product(product)
                    
                    if nutrition_data:
                        # Save nutrition data
                        self._save_nutrition_data(product, nutrition_data)
                        self.stats['nutrition_found'] += 1
                        logger.info(f"Successfully extracted {len(nutrition_data)} nutrition values")
                    else:
                        self.stats['errors'] += 1
                        logger.warning(f"No nutrition data found")
                    
                    self.stats['products_processed'] += 1
                    
                    # Delay between products (except for last one)
                    if i < len(products):
                        time.sleep(delay)
                        
                except KeyboardInterrupt:
                    logger.warning("Interrupted by user")
                    break
                except Exception as e:
                    logger.error(f"Error processing product {product.name}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            # Log final statistics
            self._log_statistics()
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Nutrition crawl failed: {e}")
            raise
        finally:
            self.cleanup()
    
    def _get_products_for_nutrition(
        self,
        max_products: int,
        category_filter: Optional[str],
        exclude_fresh: bool,
        priority_categories: bool,
        force_recrawl: bool
    ) -> List[AsdaProduct]:
        """
        Get products that need nutritional information.
        
        Returns:
            List[AsdaProduct]: Products needing nutrition data
        """
        # Base query - products with URLs
        query = AsdaProduct.objects.filter(
            product_url__isnull=False,
            product_url__gt=''
        ).exclude(
            product_url=''
        )
        
        # Filter by category if specified
        if category_filter:
            query = query.filter(category__name__icontains=category_filter)
        
        # Exclude fresh produce
        if exclude_fresh:
            fresh_keywords = ['fruit', 'vegetable', 'fresh', 'flower', 'plant', 'strawberr']
            for keyword in fresh_keywords:
                query = query.exclude(
                    Q(category__name__icontains=keyword) | 
                    Q(name__icontains=keyword)
                )
        
        # Only get products without nutrition (unless force recrawl)
        if not force_recrawl:
            three_days_ago = timezone.now() - timezone.timedelta(days=3)
            query = query.filter(
                Q(nutritional_info__isnull=True) | 
                Q(nutritional_info__exact={}) |
                Q(updated_at__lt=three_days_ago)
            )
        
        # Handle priority categories
        if priority_categories:
            priority_keywords = ['bakery', 'bread', 'cereal', 'biscuit', 'snack', 'frozen', 'chilled']
            priority_q = Q()
            for keyword in priority_keywords:
                priority_q |= Q(category__name__icontains=keyword)
            
            # Get priority products first
            priority_products = list(query.filter(priority_q)[:max_products//2])
            remaining_needed = max_products - len(priority_products)
            
            if remaining_needed > 0:
                other_products = list(query.exclude(priority_q)[:remaining_needed])
                products = priority_products + other_products
            else:
                products = priority_products
        else:
            # Just get newest products
            products = list(query.order_by('-created_at')[:max_products])
        
        # Log category breakdown
        from collections import Counter
        category_counts = Counter(p.category.name for p in products)
        logger.info("Products by category:")
        for category, count in category_counts.most_common():
            logger.info(f"  {category}: {count} products")
        
        return products
    
    def _has_recent_nutrition(self, product: AsdaProduct) -> bool:
        """Check if product has recent nutritional information."""
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
    
    def _extract_nutrition_for_product(self, product: AsdaProduct) -> Optional[Dict[str, str]]:
        """Extract nutrition data for a single product."""
        try:
            if not product.product_url:
                logger.warning(f"No URL for product: {product.name}")
                return None
            
            # Extract nutrition
            nutrition_data = self.nutrition_extractor.extract_from_url(product.product_url)
            
            return nutrition_data
            
        except Exception as e:
            logger.error(f"Error extracting nutrition: {e}")
            return None
    
    def _save_nutrition_data(self, product: AsdaProduct, nutrition_data: Dict[str, str]):
        """Save nutrition data to product."""
        try:
            # Create enhanced nutrition data with metadata
            enhanced_data = {
                'nutrition': nutrition_data,
                'extracted_at': timezone.now().isoformat(),
                'extraction_method': 'standalone_nutrition_crawler',
                'data_count': len(nutrition_data)
            }
            
            product.nutritional_info = enhanced_data
            product.save(update_fields=['nutritional_info', 'updated_at'])
            
            logger.debug(f"Saved {len(nutrition_data)} nutrition values")
            
        except Exception as e:
            logger.error(f"Error saving nutrition data: {e}")
            raise
    
    def _log_statistics(self):
        """Log final crawl statistics."""
        logger.info("="*60)
        logger.info("NUTRITION CRAWL COMPLETE")
        logger.info("="*60)
        logger.info(f"Products processed: {self.stats['products_processed']}")
        logger.info(f"Nutrition found: {self.stats['nutrition_found']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Skipped: {self.stats['skipped']}")
        
        success_rate = 0
        if self.stats['products_processed'] > 0:
            success_rate = (self.stats['nutrition_found'] / self.stats['products_processed']) * 100
        logger.info(f"Success rate: {success_rate:.1f}%")


def run_nutrition_crawler(
    max_products: int = 100,
    category_filter: Optional[str] = None,
    exclude_fresh: bool = True,
    priority_categories: bool = True,
    delay: float = 2.0,
    force_recrawl: bool = False,
    headless: bool = True
) -> Dict[str, int]:
    """
    Convenience function to run the nutrition crawler.
    
    Args:
        max_products: Maximum number of products to process
        category_filter: Optional category name filter
        exclude_fresh: Whether to exclude fresh produce
        priority_categories: Whether to prioritize certain categories
        delay: Delay between products in seconds
        force_recrawl: Whether to recrawl products with existing nutrition
        headless: Whether to run browser in headless mode
        
    Returns:
        Dict[str, int]: Statistics about the crawl
    """
    crawler = StandaloneNutritionCrawler(headless=headless)
    try:
        return crawler.crawl_nutrition(
            max_products=max_products,
            category_filter=category_filter,
            exclude_fresh=exclude_fresh,
            priority_categories=priority_categories,
            delay=delay,
            force_recrawl=force_recrawl
        )
    finally:
        crawler.cleanup()