"""
Category management for ASDA scraper.

File: asda_scraper/scrapers/category_manager.py
"""

import logging
import time
from typing import Dict, Optional
from selenium import webdriver
from django.utils import timezone

from asda_scraper.models import AsdaCategory, CrawlSession
from .config import ASDA_CATEGORY_MAPPINGS

logger = logging.getLogger(__name__)


class CategoryManager:
    """
    Manages ASDA category discovery and validation.
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
    
    def discover_categories(self) -> bool:
        """
        Create categories using ASDA's actual category structure with real codes.
        
        Returns:
            bool: True if categories discovered successfully
        """
        try:
            logger.info("Setting up ASDA categories using real category structure")
            
            max_categories = self.session.crawl_settings.get('max_categories', 10)
            include_priority = self.session.crawl_settings.get('category_priority', 2)
            
            categories_created = 0
            
            for url_code, cat_info in ASDA_CATEGORY_MAPPINGS.items():
                if cat_info['priority'] > include_priority:
                    continue
                    
                if categories_created >= max_categories:
                    break
                
                if self._create_or_update_category(url_code, cat_info):
                    categories_created += 1
            
            self._deactivate_promotional_categories()
            
            active_categories = AsdaCategory.objects.filter(is_active=True).count()
            logger.info(f"Category setup complete. Active categories: {active_categories}")
            
            return active_categories > 0
            
        except Exception as e:
            logger.error(f"Critical error in category discovery: {e}")
            return False
    
    def _create_or_update_category(self, url_code: str, cat_info: Dict) -> bool:
        """
        Create or update a single category.
        
        Args:
            url_code: Category URL code
            cat_info: Category information dictionary
            
        Returns:
            bool: True if category created/updated successfully
        """
        try:
            test_url = f"https://groceries.asda.com/cat/{cat_info['slug']}/{url_code}"
            logger.info(f"Testing category: {cat_info['name']} - {test_url}")
            
            self.driver.get(test_url)
            time.sleep(2)
            
            if self._is_valid_category_page():
                category, created = AsdaCategory.objects.get_or_create(
                    url_code=url_code,
                    defaults={
                        'name': cat_info['name'],
                        'is_active': True
                    }
                )
                
                if category.name != cat_info['name']:
                    category.name = cat_info['name']
                    category.save()
                
                action = "Created" if created else "Updated"
                logger.info(f"{action} category: {category.name}")
                
                return True
            else:
                logger.warning(f"Invalid category URL: {cat_info['name']}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing category {cat_info['name']}: {e}")
            return False
    
    def _is_valid_category_page(self) -> bool:
        """
        Check if current page is a valid category page.
        
        Returns:
            bool: True if valid category page
        """
        page_title = self.driver.title.lower()
        current_url = self.driver.current_url
        
        return ('404' not in page_title and 
                'error' not in page_title and 
                'not found' not in page_title and
                'groceries.asda.com' in current_url)
    
    def _deactivate_promotional_categories(self) -> None:
        """
        Deactivate old/promotional categories.
        """
        promotional_codes = ['rollback', 'summer', 'events-inspiration']
        for promo in promotional_codes:
            AsdaCategory.objects.filter(
                url_code__icontains=promo
            ).update(is_active=False)
            logger.info(f"Deactivated promotional category: {promo}")
    
    def get_category_url(self, category: AsdaCategory) -> Optional[str]:
        """
        Get the full URL for a category.
        
        Args:
            category: AsdaCategory instance
            
        Returns:
            Optional[str]: Category URL or None if not found
        """
        for url_code, cat_info in ASDA_CATEGORY_MAPPINGS.items():
            if url_code == category.url_code:
                return f"https://groceries.asda.com/cat/{cat_info['slug']}/{category.url_code}"
        
        logger.warning(f"No URL slug found for category {category.name} ({category.url_code})")
        return None