"""
Update the main SeleniumAsdaScraper to use stealth approach.

File: asda_scraper/scrapers/selenium_scraper_stealth.py
"""

import logging
import time
from typing import Optional, List
from django.utils import timezone
from django.db.models import Q

from asda_scraper.models import AsdaCategory, AsdaProduct, CrawlSession
from .stealth_webdriver_manager import StealthWebDriverManager
from .category_manager import CategoryManager
from .product_extractor import ProductExtractor
from .nutrition_extractor import NutritionExtractor
from .enhanced_popup_handler import EnhancedPopupHandler
from .delay_manager import DelayManager
from .models import ScrapingResult
from .exceptions import ScraperException, DriverSetupException

logger = logging.getLogger(__name__)


class StealthSeleniumAsdaScraper:
    """
    Production-ready Selenium-based ASDA scraper with stealth anti-bot detection.
    """
    
    def __init__(self, crawl_session: CrawlSession, headless: bool = False):
        """
        Initialize Stealth Selenium ASDA scraper.
        
        Args:
            crawl_session: CrawlSession instance
            headless: Whether to run browser in headless mode (not recommended for stealth)
        """
        self.session = crawl_session
        self.headless = headless
        self.stealth_manager = None
        self.driver = None
        self.base_url = "https://groceries.asda.com"
        
        # Initialize components
        self.product_extractor = None
        self.nutrition_extractor = None
        self.popup_handler = None
        self.delay_manager = DelayManager()
        
        logger.info(f"🥷 Stealth Selenium ASDA Scraper initialized for session {self.session.pk}")
        logger.info(f"Crawl type: {self.session.crawl_type}")
        logger.info(f"Headless mode: {headless} (stealth works better in visible mode)")
        
        try:
            self.stealth_manager = StealthWebDriverManager(headless=headless)
            self.driver = self.stealth_manager.setup_stealth_driver()
            
            # Initialize extractors based on crawl type
            if self.session.crawl_type in ['PRODUCT', 'BOTH']:
                self.product_extractor = ProductExtractor(self.driver, crawl_session)
                self.product_extractor._parent_scraper = self
            
            if self.session.crawl_type in ['NUTRITION', 'BOTH']:
                self.nutrition_extractor = NutritionExtractor(self.driver)
                
            self.popup_handler = EnhancedPopupHandler(self.driver)
            
            logger.info("✅ Stealth scraper components initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize stealth scraper: {e}")
            raise DriverSetupException(f"Stealth scraper setup failed: {e}")
    
    def start_crawl(self) -> ScrapingResult:
        """
        Start the crawling process using stealth Selenium.
        Routes to appropriate crawler based on crawl_type.
        
        Returns:
            ScrapingResult: Result of the scraping operation
        """
        try:
            logger.info(f"🚀 Starting {self.session.crawl_type} crawl for session {self.session.pk}")
            
            # Initial navigation with stealth
            logger.info("🌐 Initial stealth navigation to ASDA...")
            if not self.stealth_manager.navigate_like_human(self.driver, self.base_url):
                raise ScraperException("Failed to navigate to ASDA homepage")
            
            # Handle initial popups
            logger.info("🚫 Handling initial popups...")
            popup_results = self.popup_handler.handle_all_popups(max_attempts=3, timeout=15.0)
            if popup_results['popups_handled'] > 0:
                logger.info(f"✅ Handled {popup_results['popups_handled']} initial popups")
            
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
            logger.error(f"❌ Crawl failed: {e}")
            self.session.mark_failed(str(e))
            return ScrapingResult(
                products_found=self.session.products_found,
                products_saved=self.session.products_found,
                categories_processed=0,
                errors=[str(e)]
            )
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🧹 Browser closed")
    
    def _crawl_nutrition_only(self) -> ScrapingResult:
        """
        Crawl only nutritional information for existing products using stealth.
        
        Returns:
            ScrapingResult: Result of nutrition crawling
        """
        try:
            logger.info("🔬 Starting stealth nutrition-only crawl")
            
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
            
            logger.info(f"🔬 Found {total_products} products needing nutrition data")
            
            success_count = 0
            error_count = 0
            
            for i, product in enumerate(products, 1):
                try:
                    # Update session progress
                    self.session.products_found = i
                    self.session.save()
                    
                    logger.info(f"🔬 [{i}/{total_products}] Processing: {product.name[:50]}")
                    
                    # Navigate to product with stealth
                    if self.stealth_manager.navigate_like_human(self.driver, product.product_url):
                        # Handle popups for this page
                        self.popup_handler.handle_all_popups(max_attempts=1, timeout=5.0)
                        
                        # Extract nutrition
                        nutrition_data = self._extract_nutrition_for_product(product)
                        
                        if nutrition_data:
                            # Save nutrition data
                            self._save_nutrition_data(product, nutrition_data)
                            success_count += 1
                            self.session.products_with_nutrition += 1
                            logger.info(f"✅ Successfully extracted nutrition for: {product.name[:30]}")
                        else:
                            error_count += 1
                            self.session.nutrition_errors += 1
                            logger.warning(f"⚠️  No nutrition data found for: {product.name[:30]}")
                    else:
                        logger.warning(f"❌ Failed to navigate to: {product.name[:30]}")
                        error_count += 1
                        self.session.nutrition_errors += 1
                    
                    # Save session updates
                    self.session.save()
                    
                    # Human-like delay between products
                    delay = self.session.crawl_settings.get('delay', 6.0)
                    if i < total_products:
                        logger.debug(f"⏳ Waiting {delay}s before next product...")
                        time.sleep(delay)
                        
                except Exception as e:
                    logger.error(f"❌ Error processing product {product.name}: {e}")
                    error_count += 1
                    self.session.nutrition_errors += 1
                    self.session.save()
                    continue
            
            # Mark session as completed
            self.session.mark_completed()
            
            logger.info(f"🏁 Nutrition crawl complete: {success_count} successful, {error_count} errors")
            
            return ScrapingResult(
                products_found=success_count,
                products_saved=success_count,
                categories_processed=0,
                errors=[f"Nutrition extraction complete: {success_count} successful, {error_count} errors"]
            )
            
        except Exception as e:
            logger.error(f"❌ Nutrition crawl failed: {e}")
            raise
    
    def _crawl_products_only(self) -> ScrapingResult:
        """
        Crawl only product information (no nutrition) using stealth.
        
        Returns:
            ScrapingResult: Result of product crawling
        """
        try:
            logger.info("🛒 Starting stealth product-only crawl")
            
            # This would use the existing ProductExtractor logic
            # but with stealth navigation
            if not self.product_extractor:
                raise ScraperException("Product extractor not initialized")
            
            # Get categories to crawl
            categories = self._get_categories_to_crawl()
            
            if not categories:
                logger.warning("No categories found to crawl")
                self.session.mark_completed()
                return ScrapingResult(
                    products_found=0,
                    products_saved=0,
                    categories_processed=0
                )
            
            total_products = 0
            categories_processed = 0
            
            for category in categories:
                try:
                    logger.info(f"🛒 Processing category: {category.name}")
                    
                    # Extract products from category (using existing logic)
                    products_found = self.product_extractor.extract_products_from_category(category)
                    total_products += products_found
                    categories_processed += 1
                    
                    logger.info(f"✅ Category {category.name}: {products_found} products found")
                    
                    # Update session
                    self.session.products_found = total_products
                    self.session.categories_crawled = categories_processed
                    self.session.save()
                    
                    # Delay between categories
                    category_delay = self.session.crawl_settings.get('category_delay', 3.0)
                    time.sleep(category_delay)
                    
                except Exception as e:
                    logger.error(f"❌ Error processing category {category.name}: {e}")
                    continue
            
            self.session.mark_completed()
            
            return ScrapingResult(
                products_found=total_products,
                products_saved=total_products,
                categories_processed=categories_processed
            )
            
        except Exception as e:
            logger.error(f"❌ Product crawl failed: {e}")
            raise
    
    def _crawl_products_and_nutrition(self) -> ScrapingResult:
        """
        Crawl both products and nutrition data using stealth.
        
        Returns:
            ScrapingResult: Result of combined crawling
        """
        try:
            logger.info("🔬🛒 Starting stealth product + nutrition crawl")
            
            # First crawl products
            product_result = self._crawl_products_only()
            
            # Then crawl nutrition for new products
            nutrition_result = self._crawl_nutrition_only()
            
            # Combine results
            return ScrapingResult(
                products_found=product_result.products_found,
                products_saved=product_result.products_saved,
                categories_processed=product_result.categories_processed,
                errors=product_result.errors + nutrition_result.errors
            )
            
        except Exception as e:
            logger.error(f"❌ Combined crawl failed: {e}")
            raise
    
    def _get_products_for_nutrition(self) -> List[AsdaProduct]:
        """Get products that need nutrition data."""
        # Prioritize processed foods
        max_products = self.session.crawl_settings.get('max_products', 50)
        
        # Categories likely to have nutrition data
        priority_terms = [
            'bakery', 'bread', 'cereal', 'meat', 'fish', 'dairy', 
            'snack', 'crisp', 'chocolate', 'sauce', 'soup', 'frozen'
        ]
        
        # Try priority products first
        products = AsdaProduct.objects.filter(
            product_url__isnull=False
        ).filter(
            Q(nutritional_info__isnull=True) | Q(nutritional_info={})
        ).exclude(product_url='')
        
        # Filter by priority categories
        priority_products = products.filter(
            category__name__iregex='|'.join(priority_terms)
        )[:max_products]
        
        if priority_products.exists():
            return list(priority_products)
        
        # Fallback to any products
        return list(products[:max_products])
    
    def _get_categories_to_crawl(self) -> List[AsdaCategory]:
        """Get categories to crawl based on session settings."""
        try:
            settings = self.session.crawl_settings or {}
            max_categories = settings.get('max_categories', 5)
            
            categories = AsdaCategory.objects.filter(is_active=True)
            
            # Apply any category filters from settings
            category_filter = settings.get('category_filter')
            if category_filter:
                categories = categories.filter(name__icontains=category_filter)
            
            return list(categories[:max_categories])
            
        except Exception as e:
            logger.error(f"Error getting categories to crawl: {e}")
            return []
    
    def _extract_nutrition_for_product(self, product: AsdaProduct) -> Optional[dict]:
        """Extract nutrition data for a single product."""
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
        """Save nutrition data to product."""
        try:
            # Create enhanced nutrition data with metadata
            enhanced_data = {
                'nutrition': nutrition_data,
                'extracted_at': timezone.now().isoformat(),
                'extraction_method': 'stealth_selenium_scraper',
                'session_id': self.session.pk,
                'data_count': len(nutrition_data)
            }
            
            product.nutritional_info = enhanced_data
            product.save(update_fields=['nutritional_info', 'updated_at'])
            
            logger.debug(f"💾 Saved {len(nutrition_data)} nutrition values for {product.name[:30]}")
            
        except Exception as e:
            logger.error(f"Error saving nutrition data: {e}")
            raise