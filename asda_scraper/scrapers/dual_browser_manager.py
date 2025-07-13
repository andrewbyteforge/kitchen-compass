"""
Dual Browser Crawler Manager for ASDA Scraper.
Runs both product and nutrition crawlers simultaneously with visible browsers.

File: asda_scraper/scrapers/dual_browser_manager.py
"""

import logging
import time
import threading
import queue
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from django.db.models import Q, F
from django.utils import timezone

from asda_scraper.models import AsdaProduct, CrawlSession
from .webdriver_manager import WebDriverManager
from .nutrition_extractor import NutritionExtractor
from .popup_handler import PopupHandler

logger = logging.getLogger(__name__)


class DualBrowserCrawlerManager:
    """
    Manages dual browser crawling for products and nutrition data.
    Provides visual monitoring and improved performance through concurrency.
    """
    
    def __init__(self):
        """Initialize the dual browser crawler manager."""
        self.product_driver = None
        self.nutrition_driver = None
        self.nutrition_extractor = None
        self.popup_handlers = {}
        self.crawl_stats = {
            'products': {
                'processed': 0,
                'found': 0,
                'errors': 0,
                'start_time': None
            },
            'nutrition': {
                'processed': 0,
                'found': 0,
                'errors': 0,
                'start_time': None
            }
        }
        self.nutrition_queue = queue.Queue()
        self.stop_event = threading.Event()
        
    def setup_browsers(self) -> bool:
        """
        Set up both browser instances with visible windows.
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            logger.info("Setting up dual browser instances...")
            
            # Setup Product Browser (left side)
            self.product_driver = self._create_visible_driver(
                window_position=(50, 50),
                window_size=(800, 900),
                user_data_dir="product_browser"
            )
            
            # Setup Nutrition Browser (right side)
            self.nutrition_driver = self._create_visible_driver(
                window_position=(900, 50),
                window_size=(800, 900),
                user_data_dir="nutrition_browser"
            )
            
            # Initialize nutrition extractor
            self.nutrition_extractor = NutritionExtractor(self.nutrition_driver)
            
            # Initialize popup handlers
            self.popup_handlers['product'] = PopupHandler(self.product_driver)
            self.popup_handlers['nutrition'] = PopupHandler(self.nutrition_driver)
            
            # Set browser titles for identification
            self.product_driver.execute_script(
                "document.title = '🛒 ASDA Product Crawler - KitchenCompass';"
            )
            self.nutrition_driver.execute_script(
                "document.title = '🔬 ASDA Nutrition Crawler - KitchenCompass';"
            )
            
            logger.info("✅ Dual browser setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup dual browsers: {e}")
            self.cleanup()
            return False
    
    def _create_visible_driver(
        self, 
        window_position: Tuple[int, int],
        window_size: Tuple[int, int],
        user_data_dir: str
    ) -> webdriver.Chrome:
        """
        Create a visible Chrome driver with specific positioning.
        
        Args:
            window_position: (x, y) position for browser window
            window_size: (width, height) for browser window
            user_data_dir: Directory for browser user data
            
        Returns:
            webdriver.Chrome: Configured Chrome driver
        """
        import os
        import tempfile
        
        options = Options()
        
        # Create unique temp directory for each browser instance
        temp_dir = os.path.join(tempfile.gettempdir(), f"chrome_{user_data_dir}_{int(time.time())}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Visible browser configuration with fixed DevTools issues
        options.add_argument(f"--window-position={window_position[0]},{window_position[1]}")
        options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
        options.add_argument(f"--user-data-dir={temp_dir}")
        
        # Fix DevTools and port issues
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--remote-debugging-port=0")  # Let Chrome choose port
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")  # Speed up loading
        options.add_argument("--disable-javascript")  # We'll enable when needed
        
        # Disable unnecessary features for speed
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("detach", True)
        
        # Disable notifications and popups
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "popups": 2,
                "media_stream": 2,
                "geolocation": 2
            },
            "profile.managed_default_content_settings": {
                "images": 2  # Block images for speed
            }
        }
        options.add_experimental_option("prefs", prefs)
        
        try:
            # Create driver with error handling
            driver = webdriver.Chrome(options=options)
            
            # Set timeouts
            driver.implicitly_wait(5)
            driver.set_page_load_timeout(30)
            
            # Position window after creation (more reliable)
            driver.set_window_position(window_position[0], window_position[1])
            driver.set_window_size(window_size[0], window_size[1])
            
            # Disable webdriver detection
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)
            
            logger.info(f"✅ Browser created successfully: {user_data_dir}")
            return driver
            
        except Exception as e:
            logger.error(f"❌ Failed to create {user_data_dir} browser: {e}")
            # Clean up temp directory on failure
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            raise
    
    def start_dual_crawl(
        self,
        max_products: int = 100,
        max_nutrition: int = 50,
        product_delay: float = 1.0,
        nutrition_delay: float = 2.0,
        category_filter: Optional[str] = None
    ) -> Dict[str, Dict[str, int]]:
        """
        Start dual crawling with both browsers running simultaneously.
        
        Args:
            max_products: Maximum products to crawl
            max_nutrition: Maximum nutrition items to process
            product_delay: Delay between product requests
            nutrition_delay: Delay between nutrition requests
            category_filter: Optional category filter
            
        Returns:
            Dict: Combined statistics from both crawlers
        """
        try:
            logger.info("🚀 Starting dual browser crawl")
            
            # Record start times
            self.crawl_stats['products']['start_time'] = datetime.now()
            self.crawl_stats['nutrition']['start_time'] = datetime.now()
            
            # Start both crawlers in separate threads
            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both crawling tasks
                product_future = executor.submit(
                    self._run_product_crawler,
                    max_products,
                    product_delay,
                    category_filter
                )
                
                nutrition_future = executor.submit(
                    self._run_nutrition_crawler,
                    max_nutrition,
                    nutrition_delay
                )
                
                # Wait for both to complete
                for future in as_completed([product_future, nutrition_future]):
                    try:
                        result = future.result()
                        logger.info(f"Crawler completed: {result}")
                    except Exception as e:
                        logger.error(f"Crawler failed: {e}")
            
            # Calculate final statistics
            self._log_final_stats()
            return self.crawl_stats
            
        except Exception as e:
            logger.error(f"❌ Dual crawl failed: {e}")
            raise
        finally:
            self.cleanup()
    
    def _run_product_crawler(
        self,
        max_products: int,
        delay: float,
        category_filter: Optional[str]
    ) -> Dict[str, int]:
        """
        Run the product crawler in a separate thread.
        
        Args:
            max_products: Maximum products to crawl
            delay: Delay between requests
            category_filter: Optional category filter
            
        Returns:
            Dict: Product crawler statistics
        """
        try:
            logger.info("🛒 Starting product crawler thread")
            
            # Navigate to ASDA groceries page
            self.product_driver.get("https://groceries.asda.com/")
            time.sleep(3)
            
            # Handle initial popups
            self.popup_handlers['product'].handle_popups()
            
            products_found = 0
            categories_processed = 0
            
            # Example: Navigate through categories
            # This would be replaced with your actual product crawling logic
            category_links = self._find_category_links()
            
            for category_link in category_links[:5]:  # Limit for demo
                if self.stop_event.is_set():
                    break
                    
                try:
                    logger.info(f"🛒 Processing category: {category_link.text}")
                    
                    # Click category
                    category_link.click()
                    time.sleep(delay)
                    
                    # Process products in category
                    category_products = self._extract_products_from_page()
                    
                    for product_data in category_products:
                        if products_found >= max_products:
                            break
                            
                        # Save product and add to nutrition queue if it has a product URL
                        saved_product = self._save_product(product_data)
                        if saved_product and saved_product.product_url:
                            self.nutrition_queue.put(saved_product)
                        
                        products_found += 1
                        self.crawl_stats['products']['found'] = products_found
                        
                        logger.info(f"🛒 Found product: {product_data.get('name', 'Unknown')[:30]}")
                        time.sleep(delay)
                    
                    categories_processed += 1
                    self.crawl_stats['products']['processed'] = categories_processed
                    
                except Exception as e:
                    logger.error(f"🛒 Error processing category: {e}")
                    self.crawl_stats['products']['errors'] += 1
            
            logger.info(f"🛒 Product crawler completed: {products_found} products found")
            return self.crawl_stats['products']
            
        except Exception as e:
            logger.error(f"🛒 Product crawler failed: {e}")
            self.crawl_stats['products']['errors'] += 1
            return self.crawl_stats['products']
    
    def _run_nutrition_crawler(
        self,
        max_nutrition: int,
        delay: float
    ) -> Dict[str, int]:
        """
        Run the nutrition crawler in a separate thread.
        
        Args:
            max_nutrition: Maximum nutrition items to process
            delay: Delay between requests
            
        Returns:
            Dict: Nutrition crawler statistics
        """
        try:
            logger.info("🔬 Starting nutrition crawler thread")
            
            # Get existing products that need nutrition data
            products_needing_nutrition = AsdaProduct.objects.filter(
                Q(nutritional_info__isnull=True) | Q(nutritional_info={}),
                product_url__isnull=False
            ).exclude(product_url='')[:max_nutrition]
            
            nutrition_processed = 0
            
            for product in products_needing_nutrition:
                if self.stop_event.is_set() or nutrition_processed >= max_nutrition:
                    break
                
                try:
                    logger.info(f"🔬 Processing nutrition: {product.name[:30]}")
                    
                    # Extract nutrition data
                    nutrition_data = self.nutrition_extractor.extract_from_url(
                        product.product_url
                    )
                    
                    if nutrition_data:
                        # Save nutrition data in correct format
                        enhanced_data = {
                            'nutrition': nutrition_data,
                            'extracted_at': timezone.now().isoformat(),
                            'extraction_method': 'dual_browser_crawler',
                            'data_count': len(nutrition_data)
                        }
                        
                        product.nutritional_info = enhanced_data
                        product.save(update_fields=['nutritional_info', 'updated_at'])
                        
                        self.crawl_stats['nutrition']['found'] += 1
                        logger.info(f"🔬 ✅ Nutrition found for: {product.name[:30]}")
                    else:
                        logger.info(f"🔬 ❌ No nutrition for: {product.name[:30]}")
                    
                    nutrition_processed += 1
                    self.crawl_stats['nutrition']['processed'] = nutrition_processed
                    
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"🔬 Error processing nutrition for {product.name}: {e}")
                    self.crawl_stats['nutrition']['errors'] += 1
                
                # Also check queue for new products from product crawler
                try:
                    while not self.nutrition_queue.empty():
                        queued_product = self.nutrition_queue.get_nowait()
                        # Process queued product nutrition
                        self._process_queued_nutrition(queued_product, delay)
                except queue.Empty:
                    pass
            
            logger.info(f"🔬 Nutrition crawler completed: {nutrition_processed} processed")
            return self.crawl_stats['nutrition']
            
        except Exception as e:
            logger.error(f"🔬 Nutrition crawler failed: {e}")
            self.crawl_stats['nutrition']['errors'] += 1
            return self.crawl_stats['nutrition']
    
    def _process_queued_nutrition(self, product: AsdaProduct, delay: float):
        """
        Process nutrition for a product from the queue.
        
        Args:
            product: Product to process nutrition for
            delay: Delay after processing
        """
        try:
            if not product.product_url:
                return
                
            logger.info(f"🔬 ⚡ Processing queued nutrition: {product.name[:30]}")
            
            nutrition_data = self.nutrition_extractor.extract_from_url(
                product.product_url
            )
            
            if nutrition_data:
                enhanced_data = {
                    'nutrition': nutrition_data,
                    'extracted_at': timezone.now().isoformat(),
                    'extraction_method': 'dual_browser_queued',
                    'data_count': len(nutrition_data)
                }
                
                product.nutritional_info = enhanced_data
                product.save(update_fields=['nutritional_info', 'updated_at'])
                
                self.crawl_stats['nutrition']['found'] += 1
                logger.info(f"🔬 ⚡ ✅ Queued nutrition saved: {product.name[:30]}")
            
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"🔬 ⚡ Error processing queued nutrition: {e}")
            self.crawl_stats['nutrition']['errors'] += 1
    
    def _find_category_links(self) -> List:
        """Find category links on the current page."""
        # This would contain your actual category finding logic
        # Placeholder implementation
        return []
    
    def _extract_products_from_page(self) -> List[Dict]:
        """Extract products from the current page."""
        # This would contain your actual product extraction logic
        # Placeholder implementation
        return []
    
    def _save_product(self, product_data: Dict) -> Optional[AsdaProduct]:
        """Save a product to the database."""
        # This would contain your actual product saving logic
        # Placeholder implementation
        return None
    
    def _log_final_stats(self):
        """Log final crawling statistics."""
        logger.info("="*80)
        logger.info("🏁 DUAL CRAWL COMPLETE")
        logger.info("="*80)
        
        # Product stats
        product_stats = self.crawl_stats['products']
        logger.info(f"🛒 PRODUCT CRAWLER:")
        logger.info(f"   Categories processed: {product_stats['processed']}")
        logger.info(f"   Products found: {product_stats['found']}")
        logger.info(f"   Errors: {product_stats['errors']}")
        
        # Nutrition stats
        nutrition_stats = self.crawl_stats['nutrition']
        logger.info(f"🔬 NUTRITION CRAWLER:")
        logger.info(f"   Products processed: {nutrition_stats['processed']}")
        logger.info(f"   Nutrition found: {nutrition_stats['found']}")
        logger.info(f"   Errors: {nutrition_stats['errors']}")
        
        # Success rates
        if product_stats['processed'] > 0:
            product_success = (product_stats['found'] / product_stats['processed']) * 100
            logger.info(f"🛒 Product success rate: {product_success:.1f}%")
        
        if nutrition_stats['processed'] > 0:
            nutrition_success = (nutrition_stats['found'] / nutrition_stats['processed']) * 100
            logger.info(f"🔬 Nutrition success rate: {nutrition_success:.1f}%")
    
    def stop_crawl(self):
        """Stop both crawlers gracefully."""
        logger.info("🛑 Stopping dual crawl...")
        self.stop_event.set()
    
    def cleanup(self):
        """Clean up browser resources."""
        try:
            if self.product_driver:
                self.product_driver.quit()
                logger.info("🛒 Product browser closed")
                
            if self.nutrition_driver:
                self.nutrition_driver.quit()
                logger.info("🔬 Nutrition browser closed")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def run_dual_browser_crawl(
    max_products: int = 100,
    max_nutrition: int = 50,
    product_delay: float = 1.0,
    nutrition_delay: float = 2.0,
    category_filter: Optional[str] = None
) -> Dict[str, Dict[str, int]]:
    """
    Convenience function to run the dual browser crawler.
    
    Args:
        max_products: Maximum products to crawl
        max_nutrition: Maximum nutrition items to process
        product_delay: Delay between product requests
        nutrition_delay: Delay between nutrition requests
        category_filter: Optional category filter
        
    Returns:
        Dict: Combined statistics from both crawlers
    """
    manager = DualBrowserCrawlerManager()
    
    try:
        if not manager.setup_browsers():
            raise Exception("Failed to setup browsers")
        
        return manager.start_dual_crawl(
            max_products=max_products,
            max_nutrition=max_nutrition,
            product_delay=product_delay,
            nutrition_delay=nutrition_delay,
            category_filter=category_filter
        )
    finally:
        manager.cleanup()