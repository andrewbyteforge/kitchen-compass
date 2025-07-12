"""
Main Selenium scraper for ASDA.

File: asda_scraper/scrapers/selenium_scraper.py
"""

import logging
import time
from typing import Optional
from django.utils import timezone

from asda_scraper.models import AsdaCategory, CrawlSession
from .webdriver_manager import WebDriverManager
from .category_manager import CategoryManager
from .product_extractor import ProductExtractor
from .nutrition_extractor import NutritionExtractor
from .popup_handler import PopupHandler
from .delay_manager import DelayManager
from .models import ScrapingResult
from .exceptions import ScraperException, DriverSetupException
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SeleniumAsdaScraper:
    """
    Production-ready Selenium-based ASDA scraper.
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
        
        try:
            self.driver_manager = WebDriverManager(headless=headless)
            self.driver = self.driver_manager.setup_driver()
            
            # Initialize extractors
            self.product_extractor = ProductExtractor(self.driver, crawl_session)
            self.product_extractor._parent_scraper = self
            
            self.nutrition_extractor = NutritionExtractor(self.driver)
            self.popup_handler = PopupHandler(self.driver)
            
        except DriverSetupException as e:
            logger.error(f"Failed to initialize scraper: {e}")
            raise
    
    def start_crawl(self) -> ScrapingResult:
        """
        Start the crawling process using Selenium.
        
        Returns:
            ScrapingResult: Results of the crawling session
        """
        start_time = time.time()
        result = ScrapingResult()
        
        try:
            logger.info(f"Starting Selenium crawl session {self.session.pk}")
            
            self.session.status = 'RUNNING'
            self.session.save()
            
            if self._should_discover_categories():
                category_manager = CategoryManager(self.driver, self.session)
                if not category_manager.discover_categories():
                    raise ScraperException("Category discovery failed")
            
            result = self._crawl_all_products()
            
            self.session.mark_completed()
            result.duration = time.time() - start_time
            
            logger.info(f"Crawl completed successfully in {result.duration:.2f} seconds")
            return result
            
        except Exception as e:
            logger.error(f"Error in Selenium crawl session {self.session.pk}: {e}")
            self.session.mark_failed(str(e))
            result.errors.append(str(e))
            result.duration = time.time() - start_time
            return result
        finally:
            self._cleanup()
    
    def _should_discover_categories(self) -> bool:
        """
        Determine if category discovery is needed.
        
        Returns:
            bool: True if categories should be discovered
        """
        active_categories = AsdaCategory.objects.filter(is_active=True).count()
        return active_categories == 0
    
    def _crawl_all_products(self) -> ScrapingResult:
        """
        Crawl products for all active categories with intelligent delays.
        
        Returns:
            ScrapingResult: Results of product crawling
        """
        result = ScrapingResult()
        
        try:
            active_categories = AsdaCategory.objects.filter(is_active=True)
            total_categories = active_categories.count()
            
            logger.info(f"Crawling products for {total_categories} categories")
            
            # Initialize link crawler if available
            link_crawler = None
            try:
                from asda_scraper.asda_link_crawler import AsdaLinkCrawler
                link_crawler = AsdaLinkCrawler(self)
                # FIXED: Set proper references to both the main scraper and product extractor
                link_crawler.main_scraper = self  # Reference to the main SeleniumAsdaScraper
                link_crawler.scraper = self.product_extractor  # Keep for backward compatibility
                link_crawler.delay_manager = self.delay_manager
                logger.info("Link crawler initialized - Will discover and follow subcategory links")
                logger.info("✅ Product extractor properly linked for product extraction")
            except ImportError:
                logger.warning("Link crawler not available")
            except Exception as e:
                logger.error(f"Error initializing link crawler: {e}")
                link_crawler = None
            
            logger.info("="*80)
            logger.info("STARTING CATEGORY CRAWLING")
            logger.info("DELAY STRATEGY: 60 seconds between main categories")
            logger.info("="*80)
            
            for i, category in enumerate(active_categories, 1):
                try:
                    logger.info(f"\n{'='*80}")
                    logger.info(f"PROCESSING MAIN CATEGORY {i}/{total_categories}: {category.name}")
                    logger.info(f"{'='*80}")
                    
                    self.session.categories_crawled = i
                    self.session.save()
                    
                    # Extract products from main category
                    main_page_products = self.product_extractor.extract_products_from_category(category)
                    result.products_found += main_page_products
                    logger.info(f"Found {main_page_products} products on main category page")
                    
                    # Delay after extraction
                    self.delay_manager.wait('after_product_extraction')
                    
                    # Discover and crawl subcategories if link crawler available
                    if link_crawler:
                        from .category_manager import CategoryManager
                        category_manager = CategoryManager(self.driver, self.session)
                        category_url = category_manager.get_category_url(category)
                        
                        if category_url:
                            logger.info(f"Discovering subcategory links...")
                            discovered_links = link_crawler.discover_page_links(category_url)
                            
                            subcategory_links = discovered_links.get('subcategories', [])
                            if subcategory_links:
                                logger.info(f"Found {len(subcategory_links)} subcategory links to explore")
                                link_crawler.crawl_discovered_links(discovered_links, max_depth=2, current_depth=0)
                            else:
                                logger.warning(f"No subcategory links found on {category.name} page")
                    
                    # Update category timestamp
                    category.last_crawled = timezone.now()
                    category.save()
                    
                    # Reset delay multiplier after successful category
                    self.delay_manager.reset_delay()
                    
                    # Apply delay between main categories (except for last one)
                    if i < total_categories:
                        logger.info(f"[DELAY] Applying 60-second delay before next main category...")
                        self.delay_manager.wait('between_categories')
                    
                except Exception as e:
                    error_msg = f"Error crawling category {category.name}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    
                    # Increase delay after error
                    self.delay_manager.increase_delay()
                    self.delay_manager.wait('after_navigation_error')
                    continue
            
            # Update final counts
            result.categories_processed = total_categories
            result.products_saved = self.session.products_found
            
            # Keep browser open for inspection if not headless
            if not self.headless:
                logger.info("\n" + "="*80)
                logger.info("CRAWLING COMPLETE - Browser window will remain open")
                logger.info("Close the browser window manually when done inspecting")
                logger.info("="*80)
                
                # Wait for user to close browser
                input("\nPress Enter to close the browser and complete cleanup...")
            
        except Exception as e:
            logger.error(f"Error crawling products: {e}")
            result.errors.append(str(e))
        
        return result
    
    def scrape_nutritional_info(self, product_url: str, session: CrawlSession) -> Dict[str, Any]:
        """
        Scrape nutritional information from a product page.
        
        Args:
            product_url: URL of the product page
            session: Current crawl session
            
        Returns:
            Dict[str, Any]: Nutritional information or empty dict if not found
        """
        return self.nutrition_extractor.extract_from_url(product_url) or {}
    
    def _cleanup(self) -> None:
        """
        Clean up resources and close the browser.
        """
        try:
            if hasattr(self, 'driver') and self.driver:
                try:
                    # Close all windows
                    for handle in self.driver.window_handles:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                except Exception as e:
                    logger.debug(f"Error closing windows: {str(e)}")
                
                try:
                    # Quit the driver
                    self.driver.quit()
                    logger.info("WebDriver closed successfully")
                except Exception as e:
                    logger.error(f"Error quitting driver: {str(e)}")
                
                self.driver = None
            
            # Clean up driver manager if exists
            if hasattr(self, 'driver_manager') and self.driver_manager:
                try:
                    self.driver_manager.cleanup()
                    logger.info("Driver manager cleanup complete")
                except Exception as e:
                    logger.error(f"Error cleaning up driver manager: {str(e)}")
                
                self.driver_manager = None
            
            logger.info("Selenium scraper cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during selenium scraper cleanup: {str(e)}")
            # Don't re-raise - cleanup should always complete


def create_selenium_scraper(crawl_session: CrawlSession, headless: bool = False) -> SeleniumAsdaScraper:
    """
    Factory function to create a Selenium scraper instance.
    
    Args:
        crawl_session: CrawlSession instance
        headless: Whether to run browser in headless mode
        
    Returns:
        SeleniumAsdaScraper: Configured scraper instance
    """
    return SeleniumAsdaScraper(crawl_session, headless)