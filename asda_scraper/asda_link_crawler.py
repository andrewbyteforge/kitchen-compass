"""
ASDA Link Crawler Module

This module handles the discovery and crawling of links within ASDA pages,
including subcategories, department navigation, and pagination.
"""

import logging
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from django.utils import timezone
from .models import AsdaCategory, CrawlSession

logger = logging.getLogger(__name__)


class AsdaLinkCrawler:
    """
    Handles discovery and crawling of links within ASDA pages.
    
    This class identifies different types of links (categories, subcategories,
    pagination, etc.) and manages the crawling process.
    """
    
    def __init__(self, selenium_scraper):
        """
        Initialize the link crawler.
        
        Args:
            selenium_scraper: Instance of SeleniumAsdaScraper
        """
        self.scraper = selenium_scraper
        self.driver = selenium_scraper.driver
        self.session = selenium_scraper.session
        self.base_url = selenium_scraper.base_url
        
        # Tracking discovered links
        self.discovered_links = set()
        self.processed_links = set()
        self.failed_links = set()
        
        logger.info("ASDA Link Crawler initialized")
    
    def discover_page_links(self, current_url=None):
        """
        Discover all relevant links on the current page.
        
        Args:
            current_url: Current page URL (if not provided, gets from driver)
            
        Returns:
            dict: Categorized links found on the page
        """
        try:
            if not current_url:
                current_url = self.driver.current_url
            
            logger.info(f"🔍 Discovering links on: {current_url}")
            
            # Get page source and parse
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Categorize links
            categorized_links = {
                'departments': [],
                'categories': [],
                'subcategories': [],
                'products': [],
                'pagination': [],
                'navigation': [],
                'other': []
            }
            
            # Find all links
            all_links = soup.find_all('a', href=True)
            logger.info(f"📊 Found {len(all_links)} total links on page")
            
            for link in all_links:
                try:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # Make absolute URL
                    absolute_url = urljoin(current_url, href)
                    
                    # Skip if not ASDA domain or invalid
                    if not self._is_valid_asda_url(absolute_url):
                        continue
                    
                    # Skip if already processed
                    if absolute_url in self.processed_links:
                        continue
                    
                    # Classify the link
                    link_info = self._classify_link(link, absolute_url)
                    if link_info:
                        link_type = link_info['type']
                        categorized_links[link_type].append(link_info)
                        self.discovered_links.add(absolute_url)
                
                except Exception as e:
                    logger.debug(f"Error processing link: {str(e)}")
                    continue
            
            # Log discovery results
            for link_type, links in categorized_links.items():
                if links:
                    logger.info(f"🎯 Found {len(links)} {link_type} links")
            
            return categorized_links
            
        except Exception as e:
            logger.error(f"❌ Error discovering page links: {str(e)}")
            return {}
    
    def _classify_link(self, link_element, url):
        """
        Classify a link based on its URL, text, and context.
        
        Args:
            link_element: BeautifulSoup link element
            url: Absolute URL of the link
            
        Returns:
            dict: Link information with classification
        """
        try:
            # Extract link information
            text = link_element.get_text(strip=True)
            classes = ' '.join(link_element.get('class', []))
            title = link_element.get('title', '')
            
            # Parse URL to understand structure
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # Initialize link info
            link_info = {
                'url': url,
                'text': text,
                'title': title,
                'classes': classes,
                'type': 'other'
            }
            
            # Classification logic based on URL patterns and content
            
            # Department links (main categories)
            if (('/dept/' in path or '/department/' in path) and 
                any(keyword in classes.lower() for keyword in ['dept', 'department', 'main-cat'])):
                link_info['type'] = 'departments'
                link_info['priority'] = 1
                
            # Category links (like the produce taxonomy in your example)
            elif (('/dept/' in path or '/cat/' in path) and 
                  any(keyword in classes.lower() for keyword in ['taxo', 'category', 'produce'])):
                link_info['type'] = 'categories'
                link_info['priority'] = 2
                
            # Subcategory links
            elif ('/dept/' in path and len(path.split('/')) > 4):
                link_info['type'] = 'subcategories'
                link_info['priority'] = 3
                
            # Product links
            elif '/product/' in path:
                link_info['type'] = 'products'
                link_info['priority'] = 5
                
            # Pagination links
            elif (any(keyword in classes.lower() for keyword in ['page', 'next', 'prev', 'pagination']) or
                  any(keyword in text.lower() for keyword in ['next', 'previous', 'page', 'more'])):
                link_info['type'] = 'pagination'
                link_info['priority'] = 4
                
            # Navigation links
            elif any(keyword in classes.lower() for keyword in ['nav', 'menu', 'breadcrumb']):
                link_info['type'] = 'navigation'
                link_info['priority'] = 6
                
            # Special handling for produce taxonomy buttons (from your example)
            elif 'produce-taxo-btn' in classes:
                link_info['type'] = 'categories'
                link_info['priority'] = 2
                link_info['special'] = 'produce_taxonomy'
                
            # Extract category codes if present
            category_code_match = re.search(r'(\d{13})', url)
            if category_code_match:
                link_info['category_code'] = category_code_match.group(1)
            
            return link_info
            
        except Exception as e:
            logger.debug(f"Error classifying link: {str(e)}")
            return None
    
    def crawl_discovered_links(self, categorized_links, max_depth=3, current_depth=0):
        """
        Crawl discovered links in priority order.
        
        Args:
            categorized_links: Dictionary of categorized links
            max_depth: Maximum crawling depth
            current_depth: Current depth level
            
        Returns:
            int: Number of links successfully crawled
        """
        try:
            if current_depth >= max_depth:
                logger.info(f"🔒 Reached maximum depth ({max_depth}), stopping")
                return 0
            
            crawled_count = 0
            
            # Define crawling priority
            priority_order = ['departments', 'categories', 'subcategories', 'pagination']
            
            for link_type in priority_order:
                links = categorized_links.get(link_type, [])
                if not links:
                    continue
                
                logger.info(f"🚀 Crawling {len(links)} {link_type} links at depth {current_depth}")
                
                for link_info in links:
                    try:
                        if self._should_crawl_link(link_info, current_depth):
                            success = self._crawl_single_link(link_info, current_depth)
                            if success:
                                crawled_count += 1
                            
                            # Add delay between links
                            time.sleep(self.session.crawl_settings.get('delay_between_requests', 2.0))
                        
                    except Exception as e:
                        logger.error(f"❌ Error crawling link {link_info.get('url', 'unknown')}: {str(e)}")
                        continue
            
            logger.info(f"✅ Successfully crawled {crawled_count} links at depth {current_depth}")
            return crawled_count
            
        except Exception as e:
            logger.error(f"❌ Error in link crawling: {str(e)}")
            return 0
    
    def _should_crawl_link(self, link_info, current_depth):
        """
        Determine if a link should be crawled based on various criteria.
        
        Args:
            link_info: Link information dictionary
            current_depth: Current crawling depth
            
        Returns:
            bool: True if link should be crawled
        """
        url = link_info.get('url', '')
        
        # Skip if already processed
        if url in self.processed_links:
            return False
        
        # Skip if previously failed
        if url in self.failed_links:
            return False
        
        # Priority-based filtering
        link_type = link_info.get('type', 'other')
        priority = link_info.get('priority', 10)
        
        # Higher priority at deeper levels
        max_priority_for_depth = {
            0: 3,  # Departments, categories, subcategories
            1: 4,  # + pagination
            2: 5,  # + products
            3: 6   # + navigation
        }
        
        max_allowed_priority = max_priority_for_depth.get(current_depth, 10)
        if priority > max_allowed_priority:
            logger.debug(f"⏭️ Skipping {url} - priority {priority} > max {max_allowed_priority} for depth {current_depth}")
            return False
        
        # Skip certain patterns
        skip_patterns = [
            '/search',
            '/account',
            '/checkout',
            '/login',
            '/logout',
            '/help',
            '/customer-service'
        ]
        
        for pattern in skip_patterns:
            if pattern in url.lower():
                logger.debug(f"⏭️ Skipping {url} - matches skip pattern {pattern}")
                return False
        
        return True
    
    def _crawl_single_link(self, link_info, current_depth):
        """
        Crawl a single link and extract information.
        
        Args:
            link_info: Link information dictionary
            current_depth: Current crawling depth
            
        Returns:
            bool: True if crawl was successful
        """
        url = link_info.get('url', '')
        link_type = link_info.get('type', 'other')
        
        try:
            logger.info(f"🔗 Crawling {link_type}: {url}")
            
            # Navigate to the link
            original_url = self.driver.current_url
            self.driver.get(url)
            time.sleep(2)
            
            # Wait for page load
            self._wait_for_page_load()
            
            # Handle popups
            self.scraper._handle_popups()
            
            # Mark as processed
            self.processed_links.add(url)
            
            # Process based on link type
            success = False
            
            if link_type in ['departments', 'categories', 'subcategories']:
                success = self._process_category_page(link_info, current_depth)
            elif link_type == 'pagination':
                success = self._process_pagination_page(link_info, current_depth)
            elif link_type == 'products':
                success = self._process_product_page(link_info, current_depth)
            else:
                # For other types, just discover more links
                new_links = self.discover_page_links(url)
                success = len(new_links) > 0
            
            # Navigate back if needed
            if self.driver.current_url != original_url:
                self.driver.get(original_url)
                time.sleep(1)
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error crawling single link {url}: {str(e)}")
            self.failed_links.add(url)
            return False
    
    def _process_category_page(self, link_info, current_depth):
        """
        Process a category/department page.
        
        Args:
            link_info: Link information dictionary
            current_depth: Current crawling depth
            
        Returns:
            bool: True if processing was successful
        """
        try:
            url = link_info.get('url', '')
            
            # Try to create/update category if it has a category code
            category_code = link_info.get('category_code')
            if category_code:
                category_name = link_info.get('text', 'Unknown Category')
                self._ensure_category_exists(category_code, category_name)
            
            # Discover and crawl subcategories/products
            page_links = self.discover_page_links(url)
            
            # Process products on this page
            if current_depth < 3:  # Only extract products at reasonable depth
                products_found = self.scraper._extract_products_from_current_page_by_url(url)
                logger.info(f"📦 Found {products_found} products on category page")
            
            # Recursively crawl subcategories
            if current_depth < 2:  # Limit recursion depth
                self.crawl_discovered_links(page_links, max_depth=3, current_depth=current_depth + 1)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing category page: {str(e)}")
            return False
    
    def _process_pagination_page(self, link_info, current_depth):
        """
        Process a pagination link.
        
        Args:
            link_info: Link information dictionary
            current_depth: Current crawling depth
            
        Returns:
            bool: True if processing was successful
        """
        try:
            # Extract products from paginated page
            products_found = self.scraper._extract_products_from_current_page_by_url(link_info.get('url'))
            logger.info(f"📄 Found {products_found} products on paginated page")
            
            # Look for more pagination links
            page_links = self.discover_page_links()
            pagination_links = page_links.get('pagination', [])
            
            # Follow next pagination links (limited depth)
            if current_depth < 2 and pagination_links:
                for page_link in pagination_links[:3]:  # Limit to 3 more pages
                    if 'next' in page_link.get('text', '').lower():
                        self._crawl_single_link(page_link, current_depth + 1)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing pagination page: {str(e)}")
            return False
    
    def _process_product_page(self, link_info, current_depth):
        """
        Process a product detail page.
        
        Args:
            link_info: Link information dictionary
            current_depth: Current crawling depth
            
        Returns:
            bool: True if processing was successful
        """
        try:
            # Extract detailed product information
            # This could be expanded to get more detailed product data
            logger.info(f"🛍️ Processing product page: {link_info.get('text', 'Unknown Product')}")
            
            # For now, just mark as processed
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing product page: {str(e)}")
            return False
    
    def _ensure_category_exists(self, category_code, category_name):
        """
        Ensure a category exists in the database.
        
        Args:
            category_code: Numeric category code
            category_name: Category display name
            
        Returns:
            AsdaCategory: The category object
        """
        try:
            from .models import AsdaCategory
            
            category, created = AsdaCategory.objects.get_or_create(
                url_code=category_code,
                defaults={
                    'name': category_name,
                    'is_active': True
                }
            )
            
            if created:
                logger.info(f"🆕 Created category: {category_name} ({category_code})")
            
            return category
            
        except Exception as e:
            logger.error(f"❌ Error ensuring category exists: {str(e)}")
            return None
    
    def _is_valid_asda_url(self, url):
        """
        Check if URL is a valid ASDA URL for crawling.
        
        Args:
            url: URL to validate
            
        Returns:
            bool: True if URL is valid for crawling
        """
        if not url or not isinstance(url, str):
            return False
        
        # Must be ASDA domain
        if not url.startswith('https://groceries.asda.com'):
            return False
        
        # Skip certain file types and paths
        skip_patterns = [
            '/api/', '/ajax/', '.js', '.css', '.png', '.jpg', '.jpeg', 
            '.gif', '.pdf', '.zip', '/checkout', '/account', '/login',
            '/logout', '/help', '/customer-service', '/search?'
        ]
        
        return not any(pattern in url.lower() for pattern in skip_patterns)
    
    def _wait_for_page_load(self, timeout=10):
        """
        Wait for page to fully load.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            time.sleep(1)  # Additional buffer
        except TimeoutException:
            logger.warning(f"⏰ Page load timeout after {timeout} seconds")
        except Exception as e:
            logger.error(f"❌ Error waiting for page load: {str(e)}")
    
    def get_crawl_statistics(self):
        """
        Get statistics about the link crawling process.
        
        Returns:
            dict: Crawling statistics
        """
        return {
            'discovered_links': len(self.discovered_links),
            'processed_links': len(self.processed_links),
            'failed_links': len(self.failed_links),
            'success_rate': len(self.processed_links) / max(len(self.discovered_links), 1) * 100
        }