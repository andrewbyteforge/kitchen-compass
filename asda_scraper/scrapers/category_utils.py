"""
Utility functions for category and subcategory navigation.

Handles discovery and processing of category hierarchies on ASDA website.
"""

import logging
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from ..models import Category, CrawlQueue

logger = logging.getLogger(__name__)


class CategoryNavigator:
    """
    Handles navigation and discovery of category hierarchies.
    
    Discovers subcategories, department links, and category refinements.
    """
    
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait):
        """
        Initialize the category navigator.
        
        Args:
            driver: Selenium WebDriver instance
            wait: WebDriverWait instance
        """
        self.driver = driver
        self.wait = wait
        self.discovered_urls: Set[str] = set()
        
    def discover_subcategories(self) -> List[Dict[str, str]]:
        """
        Discover all subcategory links on the current page.
        
        Returns:
            List of dictionaries containing subcategory information
        """
        subcategories = []
        
        # Multiple selectors for finding subcategory links
        selectors = [
            # Taxonomy explore links (as shown in your example)
            "a.taxonomy-explore__item[data-auto-id='linkTaxonomyExplore']",
            "a.asda-btn--light.taxonomy-explore__item",
            
            # Department navigation links
            "a.department-nav__link",
            "a[data-auto-id='linkDepartment']",
            
            # Category refinement links
            "a.category-filter__link",
            "a.refinement-link",
            
            # Sidebar navigation
            "nav.category-nav a",
            "aside.category-sidebar a",
            
            # Breadcrumb style navigation
            "div.category-list a",
            "ul.category-menu a"
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        href = element.get_attribute('href')
                        text = element.text.strip()
                        
                        if href and text and self._is_valid_category_url(href):
                            # Normalize URL
                            full_url = self._normalize_url(href)
                            
                            if full_url not in self.discovered_urls:
                                self.discovered_urls.add(full_url)
                                
                                subcategory = {
                                    'name': text,
                                    'url': full_url,
                                    'selector': selector,
                                    'element_class': element.get_attribute('class'),
                                    'data_auto_id': element.get_attribute('data-auto-id')
                                }
                                
                                subcategories.append(subcategory)
                                logger.debug(f"Found subcategory: {text} - {full_url}")
                                
                    except Exception as e:
                        logger.debug(f"Error processing element: {str(e)}")
                        continue
                        
            except NoSuchElementException:
                continue
                
        # Also check for "Explore departments" or similar sections
        subcategories.extend(self._find_explore_sections())
        
        logger.info(f"Discovered {len(subcategories)} subcategories on page")
        return subcategories
    
    def _find_explore_sections(self) -> List[Dict[str, str]]:
        """
        Find links in "Explore departments" or similar sections.
        
        Returns:
            List of subcategory dictionaries
        """
        explore_categories = []
        
        try:
            # Look for explore sections
            explore_selectors = [
                "section[data-auto-id='taxonomyExplore'] a",
                "div.explore-departments a",
                "div.department-explorer a",
                "[class*='explore'] a[href*='/dept/']",
                "[class*='explore'] a[href*='/cat/']"
            ]
            
            for selector in explore_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        href = element.get_attribute('href')
                        text = element.text.strip()
                        
                        if href and text and self._is_valid_category_url(href):
                            full_url = self._normalize_url(href)
                            
                            if full_url not in self.discovered_urls:
                                self.discovered_urls.add(full_url)
                                
                                explore_categories.append({
                                    'name': text,
                                    'url': full_url,
                                    'selector': selector,
                                    'type': 'explore_section'
                                })
                                
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.debug(f"Error finding explore sections: {str(e)}")
            
        return explore_categories
    
    def _is_valid_category_url(self, url: str) -> bool:
        """
        Check if URL is a valid category/department URL.
        
        Args:
            url: URL to validate
            
        Returns:
            bool: True if valid category URL
        """
        if not url:
            return False
            
        # Category URL patterns
        valid_patterns = [
            '/dept/',
            '/cat/',
            '/category/',
            'taxonomy',
            'department'
        ]
        
        # Invalid patterns (product pages, etc.)
        invalid_patterns = [
            '/product/',
            '/search',
            '#',
            'javascript:',
            '.pdf',
            'login',
            'register',
            'basket',
            'checkout'
        ]
        
        url_lower = url.lower()
        
        # Check for invalid patterns
        if any(pattern in url_lower for pattern in invalid_patterns):
            return False
            
        # Check for valid patterns
        return any(pattern in url_lower for pattern in valid_patterns)
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to full absolute URL.
        
        Args:
            url: URL to normalize
            
        Returns:
            str: Normalized URL
        """
        if url.startswith('http'):
            return url
            
        # Get current page URL for base
        current_url = self.driver.current_url
        return urljoin(current_url, url)
    
    def save_subcategories_to_queue(
        self, 
        subcategories: List[Dict[str, str]], 
        parent_category: Optional[Category] = None,
        priority: int = 5
    ) -> int:
        """
        Save discovered subcategories to the crawl queue.
        
        Args:
            subcategories: List of subcategory dictionaries
            parent_category: Parent category if applicable
            priority: Queue priority (lower number = higher priority)
            
        Returns:
            int: Number of subcategories added to queue
        """
        added_count = 0
        
        for subcat in subcategories:
            try:
                # Create or get category record
                category, created = Category.objects.get_or_create(
                    url=subcat['url'],
                    defaults={
                        'name': subcat['name'],
                        'parent': parent_category,
                        'level': parent_category.level + 1 if parent_category else 1,
                        'is_active': True
                    }
                )
                
                # Add to crawl queue if not already processed
                from .base_scraper import BaseScraper
                url_hash = BaseScraper.get_url_hash(None, subcat['url'])
                
                queue_item, created = CrawlQueue.objects.get_or_create(
                    url_hash=url_hash,
                    queue_type='PRODUCT_LIST',
                    defaults={
                        'url': subcat['url'],
                        'priority': priority,
                        'category': category,
                        'metadata': {
                            'category_name': subcat['name'],
                            'discovery_type': subcat.get('type', 'subcategory'),
                            'parent_category': parent_category.name if parent_category else None
                        }
                    }
                )
                
                if created:
                    added_count += 1
                    logger.info(f"Added subcategory to queue: {subcat['name']}")
                    
            except Exception as e:
                logger.error(f"Error saving subcategory {subcat['name']}: {str(e)}")
                
        return added_count
    
    def check_for_pagination_categories(self) -> bool:
        """
        Check if there are additional category pages (pagination).
        
        Returns:
            bool: True if more category pages exist
        """
        pagination_selectors = [
            "a.pagination__next:not(.disabled)",
            "button.load-more-categories",
            "a[aria-label='Next page categories']"
        ]
        
        for selector in pagination_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.is_enabled():
                    return True
            except NoSuchElementException:
                continue
                
        return False
    
    def get_category_breadcrumbs(self) -> List[Dict[str, str]]:
        """
        Extract category hierarchy from breadcrumbs.
        
        Returns:
            List of breadcrumb items with name and URL
        """
        breadcrumbs = []
        
        breadcrumb_selectors = [
            "nav.breadcrumb a",
            "ol.breadcrumb li a",
            "[data-auto-id='breadcrumb'] a",
            ".breadcrumb-item a"
        ]
        
        for selector in breadcrumb_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    for element in elements:
                        href = element.get_attribute('href')
                        text = element.text.strip()
                        
                        if href and text:
                            breadcrumbs.append({
                                'name': text,
                                'url': self._normalize_url(href)
                            })
                    break
            except NoSuchElementException:
                continue
                
        return breadcrumbs
    
    def get_category_info(self) -> Dict[str, any]:
        """
        Extract current category information from the page.
        
        Returns:
            Dictionary containing category details
        """
        info = {
            'name': None,
            'description': None,
            'product_count': None,
            'breadcrumbs': []
        }
        
        # Try to get category name
        name_selectors = [
            "h1.category-title",
            "h1[data-auto-id='categoryTitle']",
            ".category-header h1",
            "h1"
        ]
        
        for selector in name_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.text.strip():
                    info['name'] = element.text.strip()
                    break
            except NoSuchElementException:
                continue
        
        # Try to get product count
        count_selectors = [
            "[data-auto-id='productCount']",
            ".product-count",
            ".results-count"
        ]
        
        for selector in count_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text
                # Extract number from text like "324 products"
                import re
                match = re.search(r'(\d+)', text)
                if match:
                    info['product_count'] = int(match.group(1))
                    break
            except NoSuchElementException:
                continue
        
        # Get breadcrumbs
        info['breadcrumbs'] = self.get_category_breadcrumbs()
        
        return info