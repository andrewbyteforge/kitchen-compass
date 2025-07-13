"""
Simple dual crawler using existing WebDriverManager.
Fallback solution for browser setup issues.

File: asda_scraper/scrapers/simple_dual_crawler.py
"""

import logging
import time
import threading
import queue
from typing import Dict, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db.models import Q
from django.utils import timezone

from asda_scraper.models import AsdaProduct, CrawlSession
from .stealth_webdriver_manager import StealthWebDriverManager
from .nutrition_extractor import NutritionExtractor
from .enhanced_popup_handler import EnhancedPopupHandler

logger = logging.getLogger(__name__)


class SimpleDualCrawler:
    """
    Simple dual crawler using existing WebDriverManager.
    More reliable fallback for browser setup issues.
    """
    
    def __init__(self):
        """Initialize the simple dual crawler."""
        self.drivers = {}
        self.extractors = {}
        self.popup_handlers = {}
        self.stats = {
            'products': {'processed': 0, 'found': 0, 'errors': 0},
            'nutrition': {'processed': 0, 'found': 0, 'errors': 0}
        }
        self.stop_event = threading.Event()
    
    def setup_browsers(self) -> bool:
        """
        Set up both browser instances using existing WebDriverManager.
        
        Returns:
            bool: True if setup successful
        """
        try:
            logger.info("🔧 Setting up browsers using StealthWebDriverManager...")
            
            # Setup Product Browser
            product_manager = StealthWebDriverManager(headless=False)
            self.drivers['product'] = product_manager.setup_stealth_driver()
            
            # Setup Nutrition Browser  
            nutrition_manager = StealthWebDriverManager(headless=False)
            self.drivers['nutrition'] = nutrition_manager.setup_stealth_driver()
            
            # Position windows side by side
            self._position_browsers()
            
            # Initialize extractors and handlers
            self.extractors['nutrition'] = NutritionExtractor(self.drivers['nutrition'])
            self.popup_handlers['product'] = EnhancedPopupHandler(self.drivers['product'])
            self.popup_handlers['nutrition'] = EnhancedPopupHandler(self.drivers['nutrition'])
            
            # Set browser titles
            self.drivers['product'].execute_script(
                "document.title = '🛒 Product Crawler - KitchenCompass';"
            )
            self.drivers['nutrition'].execute_script(
                "document.title = '🔬 Nutrition Crawler - KitchenCompass';"
            )
            
            logger.info("✅ Simple dual browser setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup browsers: {e}")
            self.cleanup()
            return False
    
    def _position_browsers(self):
        """Position browsers side by side."""
        try:
            # Position product browser on left
            self.drivers['product'].set_window_position(50, 50)
            self.drivers['product'].set_window_size(800, 900)
            
            # Position nutrition browser on right
            self.drivers['nutrition'].set_window_position(900, 50)
            self.drivers['nutrition'].set_window_size(800, 900)
            
            logger.info("🖥️  Browsers positioned side by side")
            
        except Exception as e:
            logger.warning(f"⚠️  Could not position browsers: {e}")
    
    def start_simple_crawl(
        self,
        max_products: int = 50,
        max_nutrition: int = 30,
        delay: float = 2.0
    ) -> Dict[str, Dict[str, int]]:
        """
        Start simple dual crawling.
        
        Args:
            max_products: Max products to find (demonstration)
            max_nutrition: Max nutrition items to process
            delay: Delay between requests
            
        Returns:
            Dict: Statistics from both crawlers
        """
        try:
            logger.info("🚀 Starting simple dual crawl")
            
            # Start both crawlers
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit tasks
                product_future = executor.submit(
                    self._demonstrate_product_crawler, 
                    max_products, 
                    delay
                )
                
                nutrition_future = executor.submit(
                    self._run_nutrition_crawler,
                    max_nutrition,
                    delay
                )
                
                # Wait for completion
                for future in as_completed([product_future, nutrition_future]):
                    try:
                        result = future.result()
                        logger.info(f"Crawler completed: {result}")
                    except Exception as e:
                        logger.error(f"Crawler failed: {e}")
            
            self._log_final_stats()
            return self.stats
            
        except Exception as e:
            logger.error(f"❌ Simple dual crawl failed: {e}")
            raise
        finally:
            self.cleanup()
    
    def _demonstrate_product_crawler(
        self, 
        max_products: int, 
        delay: float
    ) -> Dict[str, int]:
        """
        Demonstrate product crawler by navigating ASDA site.
        
        Args:
            max_products: Maximum products to simulate finding
            delay: Delay between actions
            
        Returns:
            Dict: Product crawler stats
        """
        try:
            logger.info("🛒 Starting product crawler demonstration")
            
            driver = self.drivers['product']
            
            # Navigate to ASDA
            logger.info("🛒 Navigating to ASDA groceries...")
            driver.get("https://groceries.asda.com/")
            time.sleep(3)
            
            # Handle popups
            self.popup_handlers['product'].handle_all_popups(max_attempts=3, timeout=10.0)
            
            # Show some activity by browsing categories
            self._browse_categories(driver, max_products, delay)
            
            logger.info(f"🛒 Product crawler demo completed")
            return self.stats['products']
            
        except Exception as e:
            logger.error(f"🛒 Product crawler failed: {e}")
            self.stats['products']['errors'] += 1
            return self.stats['products']
    
    def _browse_categories(self, driver, max_products: int, delay: float):
        """
        Browse ASDA categories to demonstrate product finding.
        
        Args:
            driver: WebDriver instance
            max_products: Max products to simulate
            delay: Delay between actions
        """
        try:
            # Look for category links
            category_selectors = [
                "a[href*='department']",
                "a[href*='category']", 
                ".category-link",
                "[data-testid*='category']"
            ]
            
            categories_found = 0
            
            for selector in category_selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    
                    for element in elements[:3]:  # Limit to 3 categories
                        if self.stop_event.is_set():
                            break
                            
                        try:
                            category_name = element.text or "Unknown Category"
                            logger.info(f"🛒 Found category: {category_name[:30]}")
                            
                            # Simulate finding products in this category
                            products_in_category = min(5, max_products - self.stats['products']['found'])
                            
                            for i in range(products_in_category):
                                self.stats['products']['found'] += 1
                                logger.info(f"🛒 Simulated product {self.stats['products']['found']}: Product-{self.stats['products']['found']}")
                                time.sleep(delay / 2)  # Faster for demo
                                
                                if self.stats['products']['found'] >= max_products:
                                    break
                            
                            categories_found += 1
                            self.stats['products']['processed'] = categories_found
                            
                            time.sleep(delay)
                            
                            if self.stats['products']['found'] >= max_products:
                                break
                                
                        except Exception as e:
                            logger.debug(f"🛒 Error with category element: {e}")
                            continue
                    
                    if self.stats['products']['found'] >= max_products:
                        break
                        
                except Exception as e:
                    logger.debug(f"🛒 Selector {selector} failed: {e}")
                    continue
            
            logger.info(f"🛒 Browsed {categories_found} categories, found {self.stats['products']['found']} products")
            
        except Exception as e:
            logger.error(f"🛒 Category browsing failed: {e}")
            self.stats['products']['errors'] += 1
    
    def _run_nutrition_crawler(
        self, 
        max_nutrition: int, 
        delay: float
    ) -> Dict[str, int]:
        """
        Run actual nutrition crawler on existing products.
        
        Args:
            max_nutrition: Max nutrition items to process
            delay: Delay between requests
            
        Returns:
            Dict: Nutrition crawler stats
        """
        try:
            logger.info("🔬 Starting nutrition crawler")
            
            # Get products that need nutrition data
            products = AsdaProduct.objects.filter(
                Q(nutritional_info__isnull=True) | Q(nutritional_info={}),
                product_url__isnull=False
            ).exclude(product_url='')[:max_nutrition]
            
            total_products = len(products)
            logger.info(f"🔬 Found {total_products} products needing nutrition")
            
            if total_products == 0:
                logger.info("🔬 No products need nutrition data")
                return self.stats['nutrition']
            
            for i, product in enumerate(products, 1):
                if self.stop_event.is_set():
                    break
                    
                try:
                    logger.info(f"🔬 [{i}/{total_products}] Processing: {product.name[:30]}")
                    
                    # Extract nutrition
                    nutrition_data = self.extractors['nutrition'].extract_from_url(
                        product.nutrition_url
                    )
                    
                    if nutrition_data:
                        # Save nutrition data
                        product.nutrition_data = nutrition_data
                        product.nutrition_last_updated = timezone.now()
                        product.save()
                        
                        self.stats['nutrition']['found'] += 1
                        logger.info(f"🔬 ✅ Nutrition found: {product.name[:30]}")
                    else:
                        logger.info(f"🔬 ❌ No nutrition: {product.name[:30]}")
                    
                    self.stats['nutrition']['processed'] += 1
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"🔬 Error processing {product.name}: {e}")
                    self.stats['nutrition']['errors'] += 1
                    continue
            
            logger.info(f"🔬 Nutrition crawler completed")
            return self.stats['nutrition']
            
        except Exception as e:
            logger.error(f"🔬 Nutrition crawler failed: {e}")
            self.stats['nutrition']['errors'] += 1
            return self.stats['nutrition']
    
    def _log_final_stats(self):
        """Log final statistics."""
        logger.info("="*60)
        logger.info("🏁 SIMPLE DUAL CRAWL COMPLETE")
        logger.info("="*60)
        
        product_stats = self.stats['products']
        logger.info(f"🛒 PRODUCTS: found={product_stats['found']}, errors={product_stats['errors']}")
        
        nutrition_stats = self.stats['nutrition']
        logger.info(f"🔬 NUTRITION: processed={nutrition_stats['processed']}, found={nutrition_stats['found']}, errors={nutrition_stats['errors']}")
    
    def cleanup(self):
        """Clean up browser resources."""
        try:
            for name, driver in self.drivers.items():
                if driver:
                    driver.quit()
                    logger.info(f"🧹 {name.capitalize()} browser closed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def run_simple_dual_crawl(
    max_products: int = 50,
    max_nutrition: int = 30,
    delay: float = 2.0
) -> Dict[str, Dict[str, int]]:
    """
    Run the simple dual crawler.
    
    Args:
        max_products: Max products to simulate
        max_nutrition: Max nutrition to process
        delay: Delay between requests
        
    Returns:
        Dict: Combined statistics
    """
    crawler = SimpleDualCrawler()
    
    try:
        if not crawler.setup_browsers():
            raise Exception("Failed to setup browsers")
        
        return crawler.start_simple_crawl(
            max_products=max_products,
            max_nutrition=max_nutrition,
            delay=delay
        )
    finally:
        crawler.cleanup()