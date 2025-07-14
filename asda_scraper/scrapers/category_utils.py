"""
Utility functions for category and subcategory navigation.

Handles discovery and processing of category hierarchies on ASDA website.
"""

import logging
import re
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

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
        
    def discover_all_links(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Discover all types of category links on the current page.
        
        Returns:
            Dictionary with categorized links:
            - 'subcategories': Regular subcategory links
            - 'explore_sections': Explore aisle/department links
            - 'refinements': Category refinement links
            - 'navigation': Navigation menu links
        """
        all_links = {
            'subcategories': [],
            'explore_sections': [],
            'refinements': [],
            'navigation': []
        }
        
        # Discover regular subcategories
        all_links['subcategories'] = self.discover_subcategories()
        
        # Discover explore sections
        all_links['explore_sections'] = self._find_explore_sections()
        
        # Discover refinement links
        all_links['refinements'] = self._find_refinement_links()
        
        # Discover navigation menu links
        all_links['navigation'] = self._find_navigation_links()
        
        # Log summary
        total_links = sum(len(links) for links in all_links.values())
        logger.info(f"Total links discovered: {total_links}")
        for link_type, links in all_links.items():
            if links:
                logger.info(f"  - {link_type}: {len(links)} links")
        
        return all_links
        
    def discover_subcategories(self) -> List[Dict[str, str]]:
        """
        Discover all subcategory links on the current page.
        
        Returns:
            List of dictionaries containing subcategory information
        """
        subcategories = []
        
        # Enhanced selectors for finding subcategory links
        selectors = [
            # Taxonomy explore links - PRIMARY TARGET
            "a.taxonomy-explore__item[data-auto-id='linkTaxonomyExplore']",
            "a.asda-btn--light.taxonomy-explore__item",
            "button.taxonomy-explore__item",
            
            # Department cards and tiles
            "a.department-tile__link",
            "a.category-tile__link",
            "[data-testid='department-card'] a",
            "[data-testid='category-card'] a",
            
            # Department navigation links
            "a.department-nav__link",
            "a[data-auto-id='linkDepartment']",
            "a[data-auto-id='linkCategory']",
            
            # Category refinement links
            "a.category-filter__link",
            "a.refinement-link",
            "[data-testid='refinement'] a",
            
            # Sidebar navigation
            "nav.category-nav a",
            "aside.category-sidebar a",
            ".sidebar-categories a",
            
            # Category lists
            "div.category-list a",
            "ul.category-menu a",
            ".category-grid a",
            
            # Generic patterns
            "a[href*='/dept/']:not([href*='product'])",
            "a[href*='/cat/']:not([href*='product'])",
            "[class*='category'] a[href*='asda.com']",
            "[class*='department'] a[href*='asda.com']"
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        # Handle both <a> tags and other clickable elements
                        if element.tag_name == 'a':
                            href = element.get_attribute('href')
                        else:
                            # For buttons or other elements, try data attributes
                            href = (element.get_attribute('data-href') or 
                                   element.get_attribute('data-url') or
                                   element.get_attribute('onclick'))
                            
                            # Extract URL from onclick if present
                            if href and 'location.href' in href:
                                match = re.search(r"'([^']+)'", href)
                                if match:
                                    href = match.group(1)
                        
                        text = element.text.strip()
                        
                        # Skip if no text or href
                        if not href or not text:
                            continue
                            
                        # Skip if text is too short or generic
                        if len(text) < 3 or text.lower() in ['shop', 'view', 'more']:
                            continue
                        
                        if self._is_valid_category_url(href):
                            # Normalize URL
                            full_url = self._normalize_url(href)
                            
                            if full_url not in self.discovered_urls:
                                self.discovered_urls.add(full_url)
                                
                                subcategory = {
                                    'name': text,
                                    'url': full_url,
                                    'selector': selector,
                                    'element_class': element.get_attribute('class') or '',
                                    'data_auto_id': element.get_attribute('data-auto-id') or '',
                                    'type': 'subcategory'
                                }
                                
                                subcategories.append(subcategory)
                                logger.debug(f"Found subcategory: {text} - {full_url}")
                                
                    except Exception as e:
                        logger.debug(f"Error processing element: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {str(e)}")
                continue
        
        logger.info(f"Discovered {len(subcategories)} subcategories on page")
        return subcategories
    
    def _find_explore_sections(self) -> List[Dict[str, str]]:
        """
        Find links in "Explore Aisle" and "Explore Department" sections.
        
        Returns:
            List of subcategory dictionaries
        """
        explore_categories = []
        
        try:
            # Enhanced selectors for explore sections
            explore_selectors = [
                # Primary explore section selectors
                "section[data-auto-id='taxonomyExplore'] a",
                "section.taxonomy-explore a",
                "[class*='explore'] [class*='item']",
                
                # Explore containers
                "div.explore-departments a",
                "div.explore-aisles a",
                "div.department-explorer a",
                ".explore-section a",
                
                # Specific explore patterns
                "[class*='explore'] a[href*='/dept/']",
                "[class*='explore'] a[href*='/cat/']",
                "[data-testid*='explore'] a",
                
                # Button-style explore links
                "button[class*='explore'][onclick]",
                "[role='button'][class*='explore']"
            ]
            
            # Check for explore section headers
            explore_headers = [
                "h2:contains('Explore')",
                "h3:contains('Explore')",
                "[class*='heading']:contains('Explore')",
                "[class*='title']:contains('Explore')"
            ]
            
            # Look for sections with explore headers
            for header_selector in explore_headers:
                try:
                    # Use XPath for contains() functionality
                    xpath = header_selector.replace(':contains', '[contains(., ')
                    if xpath != header_selector:
                        xpath = xpath.replace('(', '(., ').replace(')', ')]')
                        headers = self.driver.find_elements(By.XPATH, f"//{xpath}")
                        
                        for header in headers:
                            # Find parent section and get all links
                            parent = header.find_element(By.XPATH, "./..")
                            links = parent.find_elements(By.TAG_NAME, "a")
                            
                            for link in links:
                                href = link.get_attribute('href')
                                text = link.text.strip()
                                
                                if href and text and self._is_valid_category_url(href):
                                    full_url = self._normalize_url(href)
                                    
                                    if full_url not in self.discovered_urls:
                                        self.discovered_urls.add(full_url)
                                        
                                        explore_categories.append({
                                            'name': text,
                                            'url': full_url,
                                            'selector': 'explore_section_under_header',
                                            'type': 'explore_section'
                                        })
                except Exception:
                    continue
            
            # Use specific selectors
            for selector in explore_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        # Get href from various sources
                        href = (element.get_attribute('href') or
                               element.get_attribute('data-href') or
                               element.get_attribute('data-url'))
                        
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
                                
                                logger.debug(f"Found explore link: {text} - {full_url}")
                                
                    except Exception:
                        continue
                        
        except Exception as e:
            logger.debug(f"Error finding explore sections: {str(e)}")
        
        if explore_categories:
            logger.info(f"Found {len(explore_categories)} explore section links")
            
        return explore_categories
    
    def _find_refinement_links(self) -> List[Dict[str, str]]:
        """
        Find category refinement links (filters, facets).
        
        Returns:
            List of refinement link dictionaries
        """
        refinements = []
        
        refinement_selectors = [
            # Facet filters
            "[data-testid='facet'] a",
            ".facet-list a",
            ".filter-options a",
            
            # Refinement panels
            ".refinement-panel a",
            "[class*='refinement'] a",
            
            # Category filters
            ".category-filters a",
            "[data-auto-id*='filter'] a"
        ]
        
        for selector in refinement_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    href = element.get_attribute('href')
                    text = element.text.strip()
                    
                    if href and text and self._is_valid_category_url(href):
                        full_url = self._normalize_url(href)
                        
                        if full_url not in self.discovered_urls:
                            self.discovered_urls.add(full_url)
                            
                            refinements.append({
                                'name': text,
                                'url': full_url,
                                'selector': selector,
                                'type': 'refinement'
                            })
            except Exception:
                continue
                
        return refinements
    
    def _find_navigation_links(self) -> List[Dict[str, str]]:
        """
        Find links in navigation menus.
        
        Returns:
            List of navigation link dictionaries
        """
        nav_links = []
        
        nav_selectors = [
            # Main navigation
            "nav.main-nav a",
            "[role='navigation'] a",
            
            # Dropdown menus
            ".dropdown-menu a",
            "[class*='menu'] [class*='item'] a",
            
            # Mobile navigation
            ".mobile-nav a",
            "[data-testid='mobile-menu'] a"
        ]
        
        for selector in nav_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    href = element.get_attribute('href')
                    text = element.text.strip()
                    
                    if href and text and self._is_valid_category_url(href):
                        full_url = self._normalize_url(href)
                        
                        if full_url not in self.discovered_urls:
                            self.discovered_urls.add(full_url)
                            
                            nav_links.append({
                                'name': text,
                                'url': full_url,
                                'selector': selector,
                                'type': 'navigation'
                            })
            except Exception:
                continue
                
        return nav_links
    
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
            'department',
            '/aisle/',
            '/shop/'
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
            'checkout',
            'account',
            'help',
            'store-locator'
        ]
        
        url_lower = url.lower()
        
        # Check for invalid patterns
        if any(pattern in url_lower for pattern in invalid_patterns):
            return False
            
        # Must be ASDA domain
        if 'asda.com' not in url_lower and not url.startswith('/'):
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
            
        # Handle protocol-relative URLs
        if url.startswith('//'):
            return 'https:' + url
            
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
                # Determine category level
                if parent_category:
                    level = parent_category.level + 1
                else:
                    # Estimate level from URL structure
                    url_parts = subcat['url'].split('/')
                    dept_count = url_parts.count('dept')
                    cat_count = url_parts.count('cat')
                    level = dept_count + cat_count
                
                # Create or get category record
                category, created = Category.objects.get_or_create(
                    url=subcat['url'],
                    defaults={
                        'name': subcat['name'],
                        'parent': parent_category,
                        'level': level,
                        'is_active': True
                    }
                )
                
                # Add to crawl queue if not already processed
                from .base_scraper import BaseScraper
                url_hash = BaseScraper.get_url_hash(None, subcat['url'])
                
                # Adjust priority based on type
                adjusted_priority = priority
                if subcat.get('type') == 'explore_section':
                    adjusted_priority -= 2  # Higher priority for explore sections
                elif subcat.get('type') == 'refinement':
                    adjusted_priority += 2  # Lower priority for refinements
                
                queue_item, queue_created = CrawlQueue.objects.get_or_create(
                    url_hash=url_hash,
                    queue_type='PRODUCT_LIST',
                    defaults={
                        'url': subcat['url'],
                        'priority': adjusted_priority,
                        'category': category,
                        'metadata': {
                            'category_name': subcat['name'],
                            'discovery_type': subcat.get('type', 'subcategory'),
                            'parent_category': parent_category.name if parent_category else None,
                            'selector_used': subcat.get('selector', 'unknown')
                        }
                    }
                )
                
                if queue_created:
                    added_count += 1
                    logger.info(
                        f"Added {subcat.get('type', 'subcategory')} to queue: "
                        f"{subcat['name']} (Priority: {adjusted_priority})"
                    )
                    
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
            "a[aria-label='Next page categories']",
            "[data-testid='pagination-next']",
            ".category-pagination .next"
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
            "[data-testid='breadcrumb'] a",
            "[data-auto-id='breadcrumb'] a",
            ".breadcrumb-item a",
            "[aria-label='breadcrumb'] a"
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
            'breadcrumbs': [],
            'has_products': False,
            'has_subcategories': False
        }
        
        # Try to get category name
        name_selectors = [
            "h1.category-title",
            "h1[data-auto-id='categoryTitle']",
            ".category-header h1",
            "[data-testid='category-name']",
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
            "[data-testid='product-count']",
            ".product-count",
            ".results-count",
            "[class*='result'][class*='count']"
        ]
        
        for selector in count_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text
                # Extract number from text like "324 products" or "Showing 1-24 of 156"
                match = re.search(r'(?:of\s+)?(\d+)(?:\s+products?)?', text, re.IGNORECASE)
                if match:
                    info['product_count'] = int(match.group(1))
                    info['has_products'] = True
                    break
            except NoSuchElementException:
                continue
        
        # Check for products on page
        product_selectors = [
            "[data-testid='product-tile']",
            "[class*='product-tile']",
            "[class*='product-card']",
            "article[class*='product']"
        ]
        
        for selector in product_selectors:
            try:
                products = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if products:
                    info['has_products'] = True
                    if not info['product_count']:
                        info['product_count'] = len(products)
                    break
            except NoSuchElementException:
                continue
        
        # Check for subcategories
        if self.discover_subcategories():
            info['has_subcategories'] = True
        
        # Get breadcrumbs
        info['breadcrumbs'] = self.get_category_breadcrumbs()
        
        return info
    
    def handle_dynamic_content(self) -> None:
        """
        Handle dynamic content loading (infinite scroll, lazy loading).
        """
        try:
            # Scroll to bottom to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content
            import time
            time.sleep(2)
            
            # Check for "Load More" buttons
            load_more_selectors = [
                "button[class*='load-more']",
                "[data-testid='load-more']",
                "button:contains('Show more')",
                "a.show-more"
            ]
            
            for selector in load_more_selectors:
                try:
                    button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        time.sleep(2)
                        logger.info("Clicked 'Load More' button")
                except NoSuchElementException:
                    continue
                    
        except Exception as e:
            logger.debug(f"Error handling dynamic content: {str(e)}")