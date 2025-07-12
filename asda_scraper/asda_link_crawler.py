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

"""
Manual logging setup for ASDA scraper
Add this at the top of selenium_scraper.py and asda_link_crawler.py
"""

import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).resolve().parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Configure logging manually for the asda_scraper module
def setup_asda_logging():
    """
    Setup logging for ASDA scraper with console and file handlers.
    
    This function configures logging with proper Unicode handling for Windows.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    
    # Import SafeUnicodeFormatter from logging_config
    from .logging_config import SafeUnicodeFormatter
    
    # Create formatter for console (with emoji replacement on Windows)
    console_formatter = SafeUnicodeFormatter(
        '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create formatter for file (supports full Unicode)
    file_formatter = logging.Formatter(
        '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with SafeUnicodeFormatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)
    
    # File handler with UTF-8 encoding
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'asda_scraper.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'  # Ensure file handler uses UTF-8
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Get the asda_scraper logger and configure it
    asda_logger = logging.getLogger('asda_scraper')
    asda_logger.setLevel(logging.DEBUG)
    asda_logger.handlers.clear()  # Remove any existing handlers
    asda_logger.addHandler(console_handler)
    asda_logger.addHandler(file_handler)
    asda_logger.propagate = False
    
    # Also configure submodule loggers
    for submodule in ['selenium_scraper', 'asda_link_crawler', 'management.commands.run_asda_crawl']:
        sublogger = logging.getLogger(f'asda_scraper.{submodule}')
        sublogger.setLevel(logging.DEBUG)
        sublogger.handlers.clear()
        sublogger.addHandler(console_handler)
        sublogger.addHandler(file_handler)
        sublogger.propagate = False
    
    return asda_logger



# Setup logging when module is imported
logger = setup_asda_logging()
logger.info("ASDA scraper logging configured successfully")

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
        Discover all relevant links on the current page with comprehensive logging.
        
        Args:
            current_url: Current page URL (if not provided, gets from driver)
            
        Returns:
            dict: Categorized links found on the page
        """
        try:
            if not current_url:
                current_url = self.driver.current_url
            
            logger.info("="*80)
            logger.info(f"🔍 LINK DISCOVERY STARTED")
            logger.info(f"📍 Current URL: {current_url}")
            logger.info("="*80)
            
            # Get page source and parse
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Log page title for context
            page_title = soup.find('title')
            if page_title:
                logger.info(f"📄 Page Title: {page_title.text.strip()}")
            
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
            logger.info(f"📊 Found {len(all_links)} total <a> tags with href on page")
            
            # Also specifically look for produce taxonomy buttons
            produce_buttons = soup.find_all('a', class_=re.compile(r'produce-taxo-btn'))
            logger.info(f"🌿 Found {len(produce_buttons)} produce taxonomy buttons specifically")
            
            # Log examples of produce buttons found
            if produce_buttons:
                logger.info("🌿 Produce button examples:")
                for btn in produce_buttons[:5]:  # Log first 5
                    btn_text = btn.get_text(strip=True)
                    btn_href = btn.get('href', 'NO HREF')
                    btn_classes = ' '.join(btn.get('class', []))
                    logger.info(f"   - Text: '{btn_text}' | Classes: '{btn_classes}'")
                    logger.info(f"     URL: {btn_href}")
            
            # Track statistics
            link_stats = {
                'total_processed': 0,
                'invalid_domain': 0,
                'already_processed': 0,
                'no_href': 0,
                'classified': 0,
                'errors': 0
            }
            
            # Process each link
            for idx, link in enumerate(all_links):
                try:
                    href = link.get('href', '')
                    if not href:
                        link_stats['no_href'] += 1
                        continue
                    
                    link_stats['total_processed'] += 1
                    
                    # Make absolute URL
                    absolute_url = urljoin(current_url, href)
                    
                    # Log every 50th link to avoid log spam
                    if idx % 50 == 0 and idx > 0:
                        logger.debug(f"  Progress: Processed {idx}/{len(all_links)} links...")
                    
                    # Skip if not ASDA domain or invalid
                    if not self._is_valid_asda_url(absolute_url):
                        link_stats['invalid_domain'] += 1
                        continue
                    
                    # Skip if already processed
                    if absolute_url in self.processed_links:
                        link_stats['already_processed'] += 1
                        continue
                    
                    # Get link details for logging
                    link_text = link.get_text(strip=True)[:50]  # First 50 chars
                    link_classes = ' '.join(link.get('class', []))
                    
                    # Classify the link
                    link_info = self._classify_link(link, absolute_url)
                    if link_info:
                        link_type = link_info['type']
                        categorized_links[link_type].append(link_info)
                        self.discovered_links.add(absolute_url)
                        link_stats['classified'] += 1
                        
                        # Log important discoveries (categories and subcategories)
                        if link_type in ['categories', 'subcategories']:
                            logger.info(f"🎯 FOUND {link_type.upper()}: '{link_text}' | Classes: '{link_classes}'")
                            logger.info(f"   URL: {absolute_url}")
                            if 'special' in link_info:
                                logger.info(f"   Special Type: {link_info['special']}")
                
                except Exception as e:
                    link_stats['errors'] += 1
                    logger.error(f"❌ Error processing link #{idx}: {str(e)}")
                    continue
            
            # Log comprehensive statistics
            logger.info("-"*80)
            logger.info("📊 LINK DISCOVERY STATISTICS:")
            logger.info(f"  Total <a> tags found: {len(all_links)}")
            logger.info(f"  Links processed: {link_stats['total_processed']}")
            logger.info(f"  Links with no href: {link_stats['no_href']}")
            logger.info(f"  Invalid domain links: {link_stats['invalid_domain']}")
            logger.info(f"  Already processed links: {link_stats['already_processed']}")
            logger.info(f"  Successfully classified: {link_stats['classified']}")
            logger.info(f"  Processing errors: {link_stats['errors']}")
            logger.info("-"*80)
            
            # Log categorized results
            logger.info("🎯 CATEGORIZED LINKS SUMMARY:")
            total_categorized = 0
            for link_type, links in categorized_links.items():
                if links:
                    logger.info(f"  {link_type.upper()}: {len(links)} links")
                    total_categorized += len(links)
                    
                    # Log first 3 examples of each type
                    for i, link in enumerate(links[:3]):
                        logger.info(f"    Example {i+1}: '{link['text'][:40]}...' -> {link['url'][:80]}...")
            
            logger.info(f"  TOTAL CATEGORIZED: {total_categorized} links")
            
            # Special check for category pages without subcategories
            if '/dept/' in current_url and not categorized_links['subcategories']:
                logger.warning("⚠️ WARNING: On a category page but found NO subcategory links!")
                logger.warning("  This might indicate a problem with link detection.")
                
                # Debug: Log some raw HTML to see what's on the page
                logger.debug("  Checking for links containing 'fruit', 'vegetable', etc...")
                for link in all_links[:20]:  # Check first 20 links
                    text = link.get_text(strip=True).lower()
                    if any(word in text for word in ['fruit', 'vegetable', 'salad', 'flower', 'nuts']):
                        logger.debug(f"    Potential subcategory: '{link.get_text(strip=True)}'")
                        logger.debug(f"    Classes: {link.get('class', [])}")
                        logger.debug(f"    Href: {link.get('href', 'NO HREF')}")
            
            logger.info("="*80)
            logger.info("🔍 LINK DISCOVERY COMPLETED")
            logger.info("="*80)
            
            return categorized_links
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in discover_page_links: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {}

    def _classify_link(self, link_element, url):
        """
        Classify a link based on its URL, text, and context with enhanced detection.
        
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
            data_auto_id = link_element.get('data-auto-id', '')
            
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
            
            # Debug logging for classification process
            logger.debug(f"\n[CLASSIFY] Analyzing link:")
            logger.debug(f"  Text: '{text[:50]}...'")
            logger.debug(f"  Classes: '{classes}'")
            logger.debug(f"  data-auto-id: '{data_auto_id}'")
            logger.debug(f"  URL path: '{path}'")
            
            # IMPORTANT: Check for taxonomy exploration links (like the ones you showed)
            if 'linkTaxonomyExplore' in data_auto_id or 'taxonomy-explore' in classes:
                link_info['type'] = 'subcategories'
                link_info['priority'] = 2
                link_info['special'] = 'taxonomy_explore'
                logger.info(f"[FOUND] Taxonomy explore link: '{text}' -> subcategories")
            
            # Check for produce taxonomy buttons
            elif 'produce-taxo-btn' in classes:
                link_info['type'] = 'subcategories'
                link_info['priority'] = 2
                link_info['special'] = 'produce_taxonomy'
                logger.info(f"[FOUND] Produce taxonomy button: '{text}' -> subcategories")
            
            # Product links
            elif '/product/' in path:
                link_info['type'] = 'products'
                link_info['priority'] = 5
                logger.debug(f"  -> Classified as: products (contains '/product/')")
                
            # Pagination links
            elif (any(keyword in classes.lower() for keyword in ['page', 'next', 'prev', 'pagination']) or
                any(keyword in text.lower() for keyword in ['next', 'previous', 'page', 'more'])):
                link_info['type'] = 'pagination'
                link_info['priority'] = 4
                logger.debug(f"  -> Classified as: pagination")
                
            # Navigation links
            elif any(keyword in classes.lower() for keyword in ['nav', 'menu', 'breadcrumb']):
                link_info['type'] = 'navigation'
                link_info['priority'] = 6
                logger.debug(f"  -> Classified as: navigation")
                
            # Department/Category links based on URL structure
            elif '/dept/' in path:
                # Count the number of category codes in the URL (13-digit numbers)
                category_codes = re.findall(r'\d{13}', path)
                logger.debug(f"  Found {len(category_codes)} category codes: {category_codes}")
                
                # Count path segments
                path_segments = [p for p in path.split('/') if p and p != 'dept']
                
                # If it has multiple category codes or deep path, it's likely a subcategory
                if len(category_codes) >= 2 or len(path_segments) >= 3:
                    link_info['type'] = 'subcategories'
                    link_info['priority'] = 3
                    logger.info(f"[FOUND] Subcategory link (by URL structure): '{text}' -> subcategories")
                
                # Check if text suggests it's a subcategory
                elif any(word in text.lower() for word in [
                    'chicken', 'meat', 'fish', 'vegetables', 'chips', 'pizza',
                    'pies', 'ready meals', 'takeaway', 'vegetarian', 'vegan',
                    'desserts', 'ice cream', 'fruit', 'salad', 'flowers', 'nuts'
                ]):
                    link_info['type'] = 'subcategories'
                    link_info['priority'] = 3
                    logger.info(f"[FOUND] Subcategory link (by content): '{text}' -> subcategories")
                
                else:
                    # Default to category for other /dept/ links
                    link_info['type'] = 'categories'
                    link_info['priority'] = 2
                    logger.debug(f"  -> Classified as: categories")
                        
            # Check for category links that might not have /dept/ in them
            elif any(keyword in classes.lower() for keyword in ['category', 'cat-link', 'dept-link']):
                link_info['type'] = 'categories'
                link_info['priority'] = 2
                logger.debug(f"  -> Classified as: categories (by class names)")
            
            # Final classification
            else:
                logger.debug(f"  -> Classified as: other (no matching patterns)")
                
            # Extract category codes if present (for tracking)
            category_code_matches = re.findall(r'(\d{13})', url)
            if category_code_matches:
                link_info['category_codes'] = category_code_matches
                # Use the last category code as the primary one
                link_info['category_code'] = category_code_matches[-1]
                logger.debug(f"  Category codes found: {category_code_matches}")
            
            # Log final classification for important types
            if link_info['type'] in ['subcategories', 'categories']:
                logger.info(f"[CLASSIFIED] {link_info['type'].upper()}: '{text}' (priority: {link_info.get('priority', 'N/A')})")
            
            return link_info
            
        except Exception as e:
            logger.error(f"Error classifying link: {str(e)}")
            logger.debug(f"  Link text: {link_element.get_text(strip=True)[:50]}")
            logger.debug(f"  URL: {url}")
            return None










    def crawl_discovered_links(self, categorized_links, max_depth=3, current_depth=0):
        """
        Crawl discovered links in priority order with detailed logging.
        
        Args:
            categorized_links: Dictionary of categorized links
            max_depth: Maximum crawling depth
            current_depth: Current depth in crawling tree
        """
        try:
            logger.info("="*80)
            logger.info(f"🚀 CRAWL DISCOVERED LINKS STARTED")
            logger.info(f"📊 Current Depth: {current_depth} / Max Depth: {max_depth}")
            logger.info("="*80)
            
            # Count total links to process
            total_links = sum(len(links) for links in categorized_links.values())
            logger.info(f"📦 Total links to potentially crawl: {total_links}")
            
            if current_depth >= max_depth:
                logger.warning(f"⚠️ Maximum depth reached ({current_depth} >= {max_depth}). Stopping recursion.")
                return
            
            # Sort links by priority
            prioritized_links = []
            for link_type, links in categorized_links.items():
                for link in links:
                    link['link_type'] = link_type  # Add type for logging
                    prioritized_links.append(link)
            
            prioritized_links.sort(key=lambda x: x.get('priority', 999))
            
            logger.info(f"🔢 Links sorted by priority. Processing order:")
            for i, link in enumerate(prioritized_links[:10]):  # Show first 10
                logger.info(f"  {i+1}. [{link['link_type']}] Priority {link.get('priority', 999)}: '{link['text'][:40]}...'")
            
            # Process links
            processed_count = 0
            skipped_count = 0
            error_count = 0
            
            for idx, link_info in enumerate(prioritized_links):
                url = link_info.get('url', '')
                link_type = link_info.get('link_type', 'unknown')
                
                # Check if already processed
                if url in self.processed_links:
                    skipped_count += 1
                    logger.debug(f"⏭️ Skipping already processed URL: {url}")
                    continue
                
                # Log what we're about to crawl
                logger.info("-"*60)
                logger.info(f"🔗 CRAWLING LINK {idx+1}/{len(prioritized_links)}")
                logger.info(f"  Type: {link_type}")
                logger.info(f"  Text: '{link_info.get('text', 'NO TEXT')}'")
                logger.info(f"  URL: {url}")
                logger.info(f"  Priority: {link_info.get('priority', 'N/A')}")
                if 'special' in link_info:
                    logger.info(f"  Special: {link_info['special']}")
                logger.info("-"*60)
                
                # Crawl the link
                success = self._crawl_single_link(link_info, current_depth)
                
                if success:
                    processed_count += 1
                    logger.info(f"✅ Successfully crawled link {idx+1}")
                else:
                    error_count += 1
                    logger.error(f"❌ Failed to crawl link {idx+1}")
                
                # Add small delay between crawls
                time.sleep(0.5)
            
            # Summary statistics
            logger.info("="*80)
            logger.info(f"📊 CRAWL SUMMARY FOR DEPTH {current_depth}:")
            logger.info(f"  Total links found: {total_links}")
            logger.info(f"  Links processed: {processed_count}")
            logger.info(f"  Links skipped (already processed): {skipped_count}")
            logger.info(f"  Links failed: {error_count}")
            logger.info("="*80)
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in crawl_discovered_links: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")




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
    
# Update these methods in asda_link_crawler.py

    def _crawl_single_link(self, link_info, current_depth):
        """
        Crawl a single link with comprehensive logging and delays.
        
        Args:
            link_info: Link information dictionary
            current_depth: Current crawling depth
            
        Returns:
            bool: True if crawl was successful
        """
        url = link_info.get('url', '')
        link_type = link_info.get('type', 'other')
        
        try:
            logger.info("*"*60)
            logger.info("[TARGET] NAVIGATING TO LINK")
            logger.info(f"  Type: {link_type}")
            logger.info(f"  URL: {url}")
            logger.info(f"  Depth: {current_depth}")
            logger.info("*"*60)
            
            # Store current URL for navigation back
            original_url = self.driver.current_url
            logger.info(f"[LOCATION] Current location before navigation: {original_url}")
            
            # Navigate to the link
            logger.info(f"[NAV] Navigating to: {url}")
            self.driver.get(url)
            logger.info(f"[OK] Navigation command sent")
            
            # Apply appropriate delay based on link type
            if hasattr(self, 'delay_manager'):
                if link_type == 'subcategories':
                    self.delay_manager.wait('between_subcategories')
                elif link_type == 'pagination':
                    self.delay_manager.wait('between_pages')
                else:
                    self.delay_manager.wait('between_requests')
            else:
                # Fallback delay
                time.sleep(3)
            
            # Wait for page load
            logger.info(f"[WAIT] Waiting for page to load...")
            self._wait_for_page_load()
            logger.info(f"[OK] Page loaded")
            
            # Check for rate limiting
            if hasattr(self, 'delay_manager'):
                if self.delay_manager.check_rate_limit(self.driver.page_source):
                    logger.warning("[RATE LIMIT] Rate limit detected on page")
            
            # Verify we actually navigated
            new_url = self.driver.current_url
            logger.info(f"[LOCATION] New location after navigation: {new_url}")
            
            if new_url == original_url:
                logger.warning(f"[WARNING] URL didn't change after navigation!")
                logger.warning(f"  Expected: {url}")
                logger.warning(f"  Still at: {original_url}")
            
            # Handle popups
            logger.info(f"[CHECK] Checking for popups...")
            from .scrapers.popup_handler import PopupHandler
            popup_handler = PopupHandler(self.driver)
            popup_handler.handle_popups()
            
            # Small delay after popup handling
            if hasattr(self, 'delay_manager'):
                self.delay_manager.wait('after_popup_handling')
            
            # Mark as processed
            self.processed_links.add(url)
            logger.info(f"[OK] Marked URL as processed. Total processed: {len(self.processed_links)}")
            
            # Process based on link type
            success = False
            logger.info(f"[PROCESS] Processing as {link_type} page...")
            
            if link_type in ['departments', 'categories', 'subcategories']:
                success = self._process_category_page(link_info, current_depth)
            elif link_type == 'pagination':
                success = self._process_pagination_page(link_info, current_depth)
            elif link_type == 'products':
                success = self._process_product_page(link_info, current_depth)
            else:
                # For other types, just discover more links
                logger.info(f"[GENERIC] Processing as generic page (type: {link_type})")
                new_links = self.discover_page_links(url)
                success = len(new_links) > 0
                logger.info(f"  Found {sum(len(links) for links in new_links.values())} new links")
            
            # Apply delay after processing
            if hasattr(self, 'delay_manager'):
                self.delay_manager.wait('after_product_extraction')
            
            # Navigate back if needed
            if self.driver.current_url != original_url:
                logger.info(f"[BACK] Navigating back to: {original_url}")
                self.driver.get(original_url)
                time.sleep(2)  # Small delay after navigation
                logger.info(f"[OK] Returned to original page")
            
            logger.info(f"{'[SUCCESS]' if success else '[FAILED]'}: Completed processing {link_type} link")
            return success
            
        except Exception as e:
            logger.error(f"[ERROR] Error crawling single link {url}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.failed_links.add(url)
            
            # Increase delay after error
            if hasattr(self, 'delay_manager'):
                self.delay_manager.increase_delay()
                self.delay_manager.wait('after_navigation_error')
            
            # Try to navigate back on error
            try:
                if 'original_url' in locals() and self.driver.current_url != original_url:
                    logger.info(f"[BACK] Attempting to navigate back after error...")
                    self.driver.get(original_url)
            except:
                logger.error(f"[ERROR] Failed to navigate back after error")
            
            return False
















    # In asda_scraper/asda_link_crawler.py
    # Find the _process_category_page method and replace it with this:

    def _process_category_page(self, link_info, current_depth):
        """
        Process a category page and extract products.
        Enhanced to ensure subcategory links are properly discovered and crawled.
        
        Args:
            link_info: Link information dictionary
            current_depth: Current crawling depth
            
        Returns:
            bool: True if processing was successful
        """
        try:
            url = link_info.get('url', '')
            logger.info(f"📂 Processing category page at depth {current_depth}: {url}")
            
            # Try to create/update category if it has a category code
            category = None
            category_code = link_info.get('category_code')
            if category_code:
                category_name = link_info.get('text', 'Unknown Category')
                category = self._ensure_category_exists(category_code, category_name)
                logger.info(f"✅ Created/updated category: {category_name} ({category_code})")
            
            # Discover links on this category page
            page_links = self.discover_page_links(url)
            
            # Log what we found
            total_links = sum(len(links) for links in page_links.values())
            logger.info(f"📊 Category page analysis complete. Found {total_links} total links:")
            
            # Detailed breakdown
            for link_type, links in page_links.items():
                if links:
                    logger.info(f"  - {link_type}: {len(links)} links")
            
            # Process products on this page (if depth allows and category exists)
            products_found = 0
            if current_depth < 3 and category:  # Only extract products at reasonable depth and if we have a category
                logger.info(f"🛒 Extracting products from category page...")
                
                # FIXED: Access the product extractor correctly
                # The scraper object should be the main SeleniumAsdaScraper, not just the product_extractor
                if hasattr(self, 'main_scraper') and self.main_scraper and hasattr(self.main_scraper, 'product_extractor'):
                    products_found = self.main_scraper.product_extractor._extract_products_from_current_page(category)
                    logger.info(f"📦 Found {products_found} products using main_scraper.product_extractor")
                elif hasattr(self, 'scraper') and hasattr(self.scraper, '_extract_products_from_current_page'):
                    # If scraper is the product_extractor directly
                    products_found = self.scraper._extract_products_from_current_page(category)
                    logger.info(f"📦 Found {products_found} products using direct scraper access")
                else:
                    logger.warning("Product extractor not available - no product extraction performed")
                    logger.debug(f"Available attributes: {[attr for attr in dir(self) if not attr.startswith('_')]}")
                    if hasattr(self, 'scraper'):
                        logger.debug(f"Scraper attributes: {[attr for attr in dir(self.scraper) if not attr.startswith('_')]}")
                    
            else:
                if current_depth >= 3:
                    logger.info(f"⏭️ Skipping product extraction (depth {current_depth} >= 3)")
                if not category:
                    logger.info(f"⏭️ Skipping product extraction (no category object)")
            
            # Recursively crawl discovered links if depth allows
            if current_depth < 2:  # Limit recursion depth
                logger.info(f"🔄 Recursively crawling discovered links (depth {current_depth} < 2)...")
                
                # Prioritize subcategories first
                subcategory_links = page_links.get('subcategories', [])
                if subcategory_links:
                    logger.info(f"🗂️ Processing {len(subcategory_links)} subcategory links...")
                    for subcategory_link in subcategory_links[:5]:  # Limit to prevent too much recursion
                        self._crawl_single_link(subcategory_link, current_depth + 1)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error processing category page: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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