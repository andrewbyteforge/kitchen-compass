"""
Enhanced Category management for ASDA scraper with robust validation.

File: asda_scraper/scrapers/category_manager.py
"""

import logging
import time
from typing import Dict, Optional, List, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from django.utils import timezone
from django.db import transaction

from asda_scraper.models import AsdaCategory, CrawlSession
from .config import ASDA_CATEGORY_MAPPINGS, SCRAPER_SETTINGS, validate_category_mapping, get_category_info

logger = logging.getLogger(__name__)


class CategoryValidationError(Exception):
    """
    Exception raised when category validation fails.
    """
    pass


class CategoryManager:
    """
    Enhanced ASDA category discovery and validation manager.
    
    Handles category discovery, validation, URL generation,
    and maintenance with comprehensive error handling.
    """
    
    def __init__(self, driver: webdriver.Chrome, session: CrawlSession):
        """
        Initialize category manager.
        
        Args:
            driver: Selenium WebDriver instance
            session: Current crawl session
        """
        self.driver = driver
        self.session = session
        self._category_cache = {}
        self.base_url = "https://groceries.asda.com"
        self.validation_enabled = SCRAPER_SETTINGS.get('category_validation_enabled', True)
        self.require_active_categories = SCRAPER_SETTINGS.get('require_active_categories', True)
        
        logger.info(f"CategoryManager initialized with validation: {self.validation_enabled}")
    
    def discover_categories(self) -> bool:
        """
        Create categories using ASDA's actual category structure with enhanced validation.
        
        Returns:
            bool: True if categories discovered successfully
            
        Raises:
            CategoryValidationError: If category discovery fails critically
        """
        try:
            logger.info("Starting ASDA category discovery with enhanced validation")
            
            # Get crawl settings
            max_categories = self.session.crawl_settings.get('max_categories', 10)
            include_priority = self.session.crawl_settings.get('category_priority', 2)
            
            logger.info(f"Discovery settings - Max categories: {max_categories}, Priority: {include_priority}")
            
            categories_created = 0
            categories_failed = 0
            
            # Process categories by priority
            sorted_categories = sorted(
                ASDA_CATEGORY_MAPPINGS.items(),
                key=lambda x: x[1]['priority']
            )
            
            with transaction.atomic():
                for url_code, cat_info in sorted_categories:
                    # Skip if priority too high
                    if cat_info['priority'] > include_priority:
                        logger.debug(f"Skipping {cat_info['name']} - priority {cat_info['priority']} > {include_priority}")
                        continue
                        
                    # Stop if we've reached max categories
                    if categories_created >= max_categories:
                        logger.info(f"Reached maximum categories limit: {max_categories}")
                        break
                    
                    try:
                        success = self._create_or_update_category(url_code, cat_info)
                        if success:
                            categories_created += 1
                            logger.info(f"✓ Category {categories_created}/{max_categories}: {cat_info['name']}")
                        else:
                            categories_failed += 1
                            logger.warning(f"✗ Failed to create category: {cat_info['name']}")
                            
                    except Exception as e:
                        categories_failed += 1
                        logger.error(f"Error processing category {cat_info['name']}: {e}")
                        continue
            
            # Clean up promotional/invalid categories
            self._deactivate_promotional_categories()
            
            # Final validation
            active_categories = AsdaCategory.objects.filter(is_active=True).count()
            
            logger.info(f"Category discovery complete:")
            logger.info(f"  ✓ Created/Updated: {categories_created}")
            logger.info(f"  ✗ Failed: {categories_failed}")
            logger.info(f"  📊 Total Active: {active_categories}")
            
            # Check if we have minimum required categories
            if self.require_active_categories and active_categories == 0:
                raise CategoryValidationError("No active categories found after discovery")
            
            return active_categories > 0
            
        except CategoryValidationError:
            raise
        except Exception as e:
            logger.error(f"Critical error in category discovery: {e}")
            return False
    
    def _create_or_update_category(self, url_code: str, cat_info: Dict) -> bool:
        """
        Create or update a single category with enhanced validation.
        
        Args:
            url_code: Category URL code
            cat_info: Category information dictionary
            
        Returns:
            bool: True if category created/updated successfully
        """
        try:
            category_name = cat_info['name']
            logger.info(f"Processing category: {category_name} ({url_code})")
            
            # Validate URL code exists in mappings
            if not validate_category_mapping(url_code):
                logger.error(f"Category {url_code} not found in ASDA_CATEGORY_MAPPINGS")
                return False
            
            # Generate test URL
            test_url = self._build_category_url(url_code, cat_info)
            if not test_url:
                logger.error(f"Could not build URL for category {category_name}")
                return False
            
            logger.debug(f"Testing URL: {test_url}")
            
            # Test category page if validation enabled
            if self.validation_enabled:
                is_valid = self._validate_category_page(test_url)
                if not is_valid:
                    logger.warning(f"Category page validation failed for {category_name}")
                    if SCRAPER_SETTINGS.get('skip_invalid_categories', True):
                        return False
            
            # Create or update category in database
            category, created = AsdaCategory.objects.get_or_create(
                url_code=url_code,
                defaults={
                    'name': category_name,
                    'is_active': True,
                    'last_crawled': None
                }
            )
            
            # Update category name if it changed
            if category.name != category_name:
                category.name = category_name
                category.save(update_fields=['name'])
            
            # Ensure category is active
            if not category.is_active:
                category.is_active = True
                category.save(update_fields=['is_active'])
            
            action = "Created" if created else "Updated"
            logger.info(f"✓ {action} category: {category.name}")
            
            # Cache the category
            self._category_cache[url_code] = category
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing category {cat_info.get('name', 'Unknown')}: {e}")
            return False
    
    def _validate_category_page(self, url: str) -> bool:
        """
        Validate that a category page is accessible and contains products.
        
        Args:
            url: Category URL to validate
            
        Returns:
            bool: True if page is valid
        """
        try:
            logger.debug(f"Validating category page: {url}")
            
            # Navigate to category page
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check page title and URL for errors
            page_title = self.driver.title.lower()
            current_url = self.driver.current_url.lower()
            
            # Check for error indicators
            error_indicators = ['404', 'error', 'not found', 'page not found']
            if any(indicator in page_title for indicator in error_indicators):
                logger.warning(f"Error indicator in page title: {page_title}")
                return False
            
            # Verify we're still on ASDA groceries site
            if 'groceries.asda.com' not in current_url:
                logger.warning(f"Redirected away from ASDA site: {current_url}")
                return False
            
            # Optional: Check for products on page (light validation)
            try:
                from .config import PRODUCT_EXTRACTION_CONFIG
                product_selectors = PRODUCT_EXTRACTION_CONFIG['selectors']['product_grid']
                
                for selector in product_selectors:
                    products = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if products:
                        logger.debug(f"Found {len(products)} products using selector: {selector}")
                        break
                else:
                    logger.debug("No products found on category page (might be empty category)")
                    
            except Exception as e:
                logger.debug(f"Product validation failed (non-critical): {e}")
            
            logger.debug(f"✓ Category page validation passed: {url}")
            return True
            
        except TimeoutException:
            logger.warning(f"Timeout while validating category page: {url}")
            return False
        except WebDriverException as e:
            logger.warning(f"WebDriver error validating category page {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating category page {url}: {e}")
            return False
    
    def _build_category_url(self, url_code: str, cat_info: Dict) -> Optional[str]:
        """
        Build full category URL from code and info.
        
        Args:
            url_code: Category URL code
            cat_info: Category information dictionary
            
        Returns:
            Optional[str]: Full category URL or None if build fails
        """
        try:
            slug = cat_info.get('slug')
            if not slug:
                logger.error(f"No slug found for category {cat_info.get('name', 'Unknown')}")
                return None
            
            # Handle nested slugs (e.g., 'bakery/bagels')
            if '/' in slug:
                # For nested categories, use the full path
                url = f"{self.base_url}/cat/{slug}/{url_code}"
            else:
                # For top-level categories
                url = f"{self.base_url}/cat/{slug}/{url_code}"
            
            logger.debug(f"Built URL: {url}")
            return url
            
        except Exception as e:
            logger.error(f"Error building category URL for {url_code}: {e}")
            return None
    
    def _deactivate_promotional_categories(self) -> None:
        """
        Deactivate old/promotional categories with enhanced logging.
        """
        try:
            promotional_codes = ['rollback', 'summer', 'events-inspiration', 'christmas', 'easter']
            deactivated_count = 0
            
            for promo in promotional_codes:
                updated = AsdaCategory.objects.filter(
                    url_code__icontains=promo,
                    is_active=True
                ).update(is_active=False)
                
                if updated > 0:
                    deactivated_count += updated
                    logger.info(f"Deactivated {updated} promotional categories containing '{promo}'")
            
            if deactivated_count > 0:
                logger.info(f"Total promotional categories deactivated: {deactivated_count}")
            else:
                logger.debug("No promotional categories found to deactivate")
                
        except Exception as e:
            logger.error(f"Error deactivating promotional categories: {e}")
    
    def get_category_url(self, category: AsdaCategory) -> Optional[str]:
        """
        Get the full URL for a category with enhanced error handling.
        
        Args:
            category: AsdaCategory instance
            
        Returns:
            Optional[str]: Category URL or None if not found
        """
        try:
            # Check cache first
            if category.url_code in self._category_cache:
                cached_cat = self._category_cache[category.url_code]
                if cached_cat.pk == category.pk:
                    logger.debug(f"Using cached URL for {category.name}")
            
            # Look up category in mappings
            cat_info = get_category_info(category.url_code)
            if not cat_info:
                logger.warning(f"No URL slug found for category {category.name} ({category.url_code})")
                return None
            
            # Build URL
            url = self._build_category_url(category.url_code, cat_info)
            if url:
                logger.debug(f"Generated URL for {category.name}: {url}")
                return url
            else:
                logger.error(f"Failed to build URL for category {category.name}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting category URL for {category.name}: {e}")
            return None
    
    def get_active_categories(self) -> List[AsdaCategory]:
        """
        Get all active categories with validation.
        
        Returns:
            List[AsdaCategory]: List of active categories
        """
        try:
            active_categories = AsdaCategory.objects.filter(is_active=True).order_by('name')
            logger.info(f"Retrieved {active_categories.count()} active categories")
            return list(active_categories)
            
        except Exception as e:
            logger.error(f"Error retrieving active categories: {e}")
            return []
    
    def validate_all_categories(self) -> Tuple[int, int]:
        """
        Validate all active categories and deactivate invalid ones.
        
        Returns:
            Tuple[int, int]: (valid_count, invalid_count)
        """
        try:
            if not self.validation_enabled:
                logger.info("Category validation is disabled")
                return 0, 0
            
            logger.info("Starting validation of all active categories")
            
            active_categories = self.get_active_categories()
            valid_count = 0
            invalid_count = 0
            
            for category in active_categories:
                try:
                    url = self.get_category_url(category)
                    if url and self._validate_category_page(url):
                        valid_count += 1
                        logger.debug(f"✓ Valid: {category.name}")
                    else:
                        invalid_count += 1
                        category.is_active = False
                        category.save(update_fields=['is_active'])
                        logger.warning(f"✗ Deactivated invalid category: {category.name}")
                        
                except Exception as e:
                    invalid_count += 1
                    logger.error(f"Error validating category {category.name}: {e}")
            
            logger.info(f"Category validation complete - Valid: {valid_count}, Invalid: {invalid_count}")
            return valid_count, invalid_count
            
        except Exception as e:
            logger.error(f"Error in category validation: {e}")
            return 0, 0