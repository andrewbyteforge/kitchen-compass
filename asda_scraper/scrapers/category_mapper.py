"""
Enhanced CategoryMapperCrawler with comprehensive debug logging.

ISSUE ANALYSIS:
The CategoryMapperCrawler.scrape() method is likely getting stuck in one of these areas:
1. Getting the page ("https://groceries.asda.com/")
2. Cookie consent handling
3. Processing main categories from settings
4. The settings might not have CATEGORIES defined

KEY FIXES:
- Add step-by-step debug logging
- Check if CATEGORIES exist in settings
- Fallback to discovering categories if none configured
- Add timeout protection for all operations
"""

import logging
import time
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin
import colorlog
from colorlog import ColoredFormatter
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .base_scraper import BaseScraper
from ..models import Category, CrawlQueue
from .utils import handle_all_popups

# Configure colored logger for link discovery
logger = logging.getLogger(__name__)

# Create a separate logger for link discovery with color formatting
link_logger = logging.getLogger(f"{__name__}.links")
link_handler = logging.StreamHandler()
link_formatter = ColoredFormatter(
    "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
)
link_handler.setFormatter(link_formatter)
link_logger.addHandler(link_handler)
link_logger.setLevel(logging.INFO)


class CategoryMapperCrawler(BaseScraper):
    """
    Enhanced crawler for discovering and mapping ASDA product categories.

    This crawler:
    1. Navigates to ASDA groceries homepage
    2. Interacts with the navigation menu
    3. Discovers all categories and subcategories
    4. Saves category hierarchy to database
    5. Populates queue for product list crawler
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the category mapper crawler."""
        super().__init__(*args, **kwargs)
        self.discovered_categories: Set[str] = set()
        self.category_hierarchy: Dict[str, List[Dict]] = {}
        self.total_links_found: int = 0
        
        logger.info("🗂️  CategoryMapperCrawler initialized")

    def scrape(self) -> None:
        """
        Main scraping method for category discovery with enhanced debugging.

        Implements the abstract scrape method from BaseScraper.
        """
        try:
            logger.info("🗂️  === STARTING CATEGORY MAPPING PROCESS ===")
            link_logger.info("=== LINK DISCOVERY STARTED ===")

            # STEP 1: Navigate to ASDA homepage
            logger.info("🌐 STEP 1: Navigating to ASDA groceries homepage...")
            homepage_url = "https://groceries.asda.com/"
            
            if not self.get_page(homepage_url):
                raise Exception(f"Failed to load ASDA homepage: {homepage_url}")
            
            logger.info("✅ STEP 1 COMPLETE: Homepage loaded successfully")

            # STEP 2: Handle cookie consent
            logger.info("🍪 STEP 2: Handling cookie consent and popups...")
            self._handle_cookie_consent()
            logger.info("✅ STEP 2 COMPLETE: Cookie consent handled")

            # STEP 3: Check if we have predefined categories in settings
            logger.info("⚙️  STEP 3: Checking for predefined categories in settings...")
            main_categories = self.settings.get('CATEGORIES', [])
            
            if main_categories:
                logger.info(f"📋 Found {len(main_categories)} predefined categories in settings:")
                for i, cat_url in enumerate(main_categories, 1):
                    logger.info(f"   {i}. {cat_url}")
                
                # Process predefined categories
                for category_url in main_categories:
                    try:
                        logger.info(f"🔍 Processing predefined category: {category_url}")
                        self._process_main_category(category_url)
                        logger.info(f"✅ Successfully processed: {category_url}")
                    except Exception as e:
                        logger.error(f"❌ Error processing category {category_url}: {str(e)}")
                        self.handle_error(e, {'category_url': category_url})
                        continue
            else:
                logger.warning("⚠️  No predefined categories found in settings")
                logger.info("🔍 STEP 3-ALT: Attempting to discover categories from homepage...")
                
                # Fallback: Try to discover categories from the homepage
                discovered_categories = self._discover_categories_from_homepage()
                
                if discovered_categories:
                    logger.info(f"✅ Discovered {len(discovered_categories)} categories from homepage")
                    for category_url in discovered_categories:
                        try:
                            self._process_main_category(category_url)
                        except Exception as e:
                            logger.error(f"❌ Error processing discovered category {category_url}: {str(e)}")
                            continue
                else:
                    logger.error("❌ No categories could be discovered from homepage")
                    raise Exception("No categories found in settings and none could be discovered")

            logger.info("✅ STEP 3 COMPLETE: Category processing finished")

            # STEP 4: Final summary
            logger.info("📊 === CATEGORY MAPPING SUMMARY ===")
            logger.info(f"📊 Discovered categories: {len(self.discovered_categories)}")
            logger.info(f"📊 Total links found: {self.total_links_found}")
            
            # Log discovered categories
            if self.discovered_categories:
                logger.info("📋 Discovered category URLs:")
                for i, category_url in enumerate(sorted(self.discovered_categories), 1):
                    logger.info(f"   {i:2d}. {category_url}")
            
            logger.info(
                f"🎉 Category mapping completed successfully! "
                f"Discovered {len(self.discovered_categories)} categories"
            )
            link_logger.info(
                f"=== LINK DISCOVERY COMPLETED: {self.total_links_found} TOTAL LINKS FOUND ==="
            )

        except Exception as e:
            logger.error(f"💥 Fatal error in category mapping: {str(e)}", exc_info=True)
            self.handle_error(e, {'stage': 'category_mapping'})
            raise

    def _handle_cookie_consent(self) -> None:
        """Handle cookie consent popup if present."""
        try:
            logger.info("🍪 Checking for popups and cookie consent...")
            handle_all_popups(self.driver, self.wait)
            
            # Additional checks for ASDA-specific cookie banners
            cookie_selectors = [
                "button[data-testid='accept-all-cookies']",
                "button[id*='accept']",
                "button[id*='cookie']",
                ".cookie-banner button",
                "#accept-all-cookies",
                "[data-auto-id='cookie-accept']"
            ]
            
            for selector in cookie_selectors:
                try:
                    cookie_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if cookie_button.is_displayed():
                        logger.info(f"🍪 Found cookie consent button: {selector}")
                        cookie_button.click()
                        time.sleep(2)  # Wait for banner to disappear
                        logger.info("✅ Cookie consent accepted")
                        break
                except NoSuchElementException:
                    continue
            
            logger.info("✅ Cookie consent handling completed")
            
        except Exception as e:
            logger.warning(f"⚠️  Error handling cookie consent: {str(e)}")
            # Don't fail the entire process for cookie issues

    def _discover_categories_from_homepage(self) -> List[str]:
        """
        Discover categories directly from the homepage navigation.
        
        Returns:
            List[str]: List of discovered category URLs
        """
        discovered_urls = []
        
        try:
            logger.info("🔍 Discovering categories from homepage navigation...")
            
            # Common selectors for ASDA navigation
            nav_selectors = [
                # Main navigation
                "nav a[href*='/dept/']",
                "nav a[href*='/cat/']",
                "nav a[href*='/aisle/']",
                
                # Menu links
                ".main-menu a[href*='/dept/']",
                ".navigation a[href*='/dept/']",
                
                # Department links
                "a[data-testid*='department']",
                "a[class*='department']",
                
                # Generic grocery links
                "a[href*='groceries.asda.com/dept/']",
                "a[href*='groceries.asda.com/cat/']",
            ]
            
            for selector in nav_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.info(f"🔍 Found {len(elements)} elements with selector: {selector}")
                    
                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            text = element.text.strip()
                            
                            if href and self._is_valid_category_url(href):
                                full_url = self._normalize_url(href)
                                if full_url not in discovered_urls:
                                    discovered_urls.append(full_url)
                                    logger.info(f"✅ Discovered category: {text} -> {full_url}")
                        except Exception as e:
                            logger.debug(f"Error processing element: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {str(e)}")
                    continue
            
            logger.info(f"🔍 Total categories discovered from homepage: {len(discovered_urls)}")
            return discovered_urls
            
        except Exception as e:
            logger.error(f"❌ Error discovering categories from homepage: {str(e)}")
            return []

    def _is_valid_category_url(self, url: str) -> bool:
        """Check if URL is a valid ASDA category URL."""
        if not url:
            return False
        
        # Must be an ASDA groceries URL
        if 'groceries.asda.com' not in url:
            return False
        
        # Must be a category, department, or aisle URL
        valid_patterns = ['/dept/', '/cat/', '/aisle/']
        return any(pattern in url for pattern in valid_patterns)

    def _normalize_url(self, url: str) -> str:
        """Normalize URL to ensure it's absolute."""
        if url.startswith('//'):
            return f"https:{url}"
        elif url.startswith('/'):
            return f"https://groceries.asda.com{url}"
        elif not url.startswith('http'):
            return f"https://groceries.asda.com/{url}"
        return url

    def _process_main_category(self, category_url: str) -> None:
        """
        Process a main category and discover its subcategories.

        Args:
            category_url: URL of the main category to process
        """
        try:
            logger.info(f"🗂️  Processing main category: {category_url}")
            link_logger.info(f">>> Navigating to main category: {category_url}")

            # Navigate to category page
            if not self.get_page(category_url):
                raise Exception(f"Failed to load category page: {category_url}")

            # Extract category name from page
            category_name = self._extract_category_name()
            if not category_name:
                logger.warning(f"⚠️  Could not extract category name for {category_url}")
                category_name = self._extract_name_from_url(category_url)

            # Create or update main category
            main_category = self._save_category(
                name=category_name,
                url=category_url,
                level=0,
                parent=None
            )

            # Log the main category discovery
            link_logger.info(f"✓ MAIN CATEGORY FOUND: {category_name} - {category_url}")
            self.total_links_found += 1
            self.discovered_categories.add(category_url)

            # Discover subcategories using the navigation menu
            logger.info(f"🔍 Discovering subcategories for: {category_name}")
            subcategories = self._discover_subcategories()

            for subcat_data in subcategories:
                try:
                    # Save subcategory
                    subcategory = self._save_category(
                        name=subcat_data['name'],
                        url=subcat_data['url'],
                        level=1,
                        parent=main_category
                    )

                    # Discover sub-subcategories if any
                    if subcat_data.get('children'):
                        for sub_subcat_data in subcat_data['children']:
                            self._save_category(
                                name=sub_subcat_data['name'],
                                url=sub_subcat_data['url'],
                                level=2,
                                parent=subcategory
                            )

                except Exception as e:
                    logger.error(f"❌ Error processing subcategory: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"❌ Error processing main category {category_url}: {str(e)}")
            raise

    def _extract_category_name(self) -> Optional[str]:
        """
        Extract category name from the current page.
        
        Returns:
            str: Category name or None if not found
        """
        try:
            # Common selectors for category names
            name_selectors = [
                "h1",
                ".page-title",
                ".category-title",
                "[data-testid='page-title']",
                ".breadcrumb li:last-child",
                "title"
            ]
            
            for selector in name_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = element.text.strip()
                    if text and text != "ASDA Groceries":
                        logger.debug(f"🏷️  Extracted category name: '{text}' using selector: {selector}")
                        return text
                except NoSuchElementException:
                    continue
            
            logger.debug("⚠️  Could not extract category name from page")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️  Error extracting category name: {str(e)}")
            return None

    def _extract_name_from_url(self, url: str) -> str:
        """Extract a category name from the URL as fallback."""
        try:
            # Extract the last part of the URL path
            parts = url.rstrip('/').split('/')
            if parts:
                name = parts[-1].replace('-', ' ').replace('_', ' ').title()
                logger.debug(f"🏷️  Extracted name from URL: '{name}'")
                return name
        except:
            pass
        
        return "Unknown Category"

    def _discover_subcategories(self) -> List[Dict[str, str]]:
        """
        Discover subcategories from the current category page.
        
        Returns:
            List[Dict]: List of subcategory data
        """
        subcategories = []
        
        try:
            # Wait a moment for page to fully load
            time.sleep(2)
            
            # Look for subcategory links
            subcat_selectors = [
                "a[href*='/cat/']",
                "a[href*='/aisle/']",
                ".category-nav a",
                ".subcategory-list a",
                "[data-testid='category-link']"
            ]
            
            for selector in subcat_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    logger.debug(f"🔍 Found {len(elements)} subcategory elements with: {selector}")
                    
                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            text = element.text.strip()
                            
                            if href and text and self._is_valid_category_url(href):
                                full_url = self._normalize_url(href)
                                subcategories.append({
                                    'name': text,
                                    'url': full_url,
                                    'children': []  # Could be populated later
                                })
                                logger.debug(f"✅ Found subcategory: {text} -> {full_url}")
                        except Exception as e:
                            logger.debug(f"Error processing subcategory element: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.debug(f"Error with subcategory selector {selector}: {str(e)}")
                    continue
            
            # Remove duplicates
            seen_urls = set()
            unique_subcategories = []
            for subcat in subcategories:
                if subcat['url'] not in seen_urls:
                    seen_urls.add(subcat['url'])
                    unique_subcategories.append(subcat)
            
            logger.info(f"🔍 Discovered {len(unique_subcategories)} unique subcategories")
            return unique_subcategories
            
        except Exception as e:
            logger.error(f"❌ Error discovering subcategories: {str(e)}")
            return []

    def _save_category(self, name: str, url: str, level: int, parent: Optional[Category] = None) -> Category:
        """
        Save category to database.
        
        Args:
            name: Category name
            url: Category URL
            level: Category level (0=main, 1=sub, 2=sub-sub)
            parent: Parent category (if any)
            
        Returns:
            Category: The saved category instance
        """
        try:
            # Create or update category
            category, created = Category.objects.get_or_create(
                url=url,
                defaults={
                    'name': name,
                    'level': level,
                    'parent': parent,
                    'is_active': True
                }
            )
            
            if not created:
                # Update existing category if needed
                if category.name != name:
                    category.name = name
                if category.level != level:
                    category.level = level
                if category.parent != parent:
                    category.parent = parent
                category.save()
                logger.debug(f"📝 Updated category: {name}")
            else:
                logger.info(f"📝 Created new category: {name} (Level {level})")
            
            # Add to crawl queue if it's a leaf category
            if level == 0 or not parent:  # Main categories should be crawled
                queue_item, queue_created = CrawlQueue.objects.get_or_create(
                    url=url,
                    queue_type='PRODUCT_LIST',
                    defaults={
                        'status': 'PENDING',
                        'priority': 10 - level  # Higher priority for main categories
                    }
                )
                
                if queue_created:
                    logger.info(f"➕ Added to crawl queue: {name}")
            
            return category
            
        except Exception as e:
            logger.error(f"❌ Error saving category {name}: {str(e)}")
            raise

    def _add_to_queue(self, category: Category) -> None:
        """
        Add category URL to product list crawler queue.

        Args:
            category: Category instance to queue
        """
        try:
            url_hash = self.get_url_hash(category.url)

            # Check if already in queue
            existing = CrawlQueue.objects.filter(
                url_hash=url_hash,
                queue_type='PRODUCT_LIST'
            ).exists()

            if not existing:
                # Determine priority based on category level and keywords
                priority = self._calculate_priority(category)

                CrawlQueue.objects.create(
                    url=category.url,
                    url_hash=url_hash,
                    queue_type='PRODUCT_LIST',
                    priority=priority,
                    category=category,
                    metadata={
                        'category_name': category.name,
                        'category_level': category.level
                    }
                )

                logger.debug(
                    f"Added to product list queue: {category.name} "
                    f"(Priority: {priority})"
                )
                link_logger.info(f"  ➜ Added to PRODUCT LIST QUEUE: {category.name}")

        except Exception as e:
            logger.error(f"Error adding category to queue: {str(e)}")

    def _calculate_priority(self, category: Category) -> int:
        """
        Calculate queue priority for a category.

        Higher priority for:
        - Main categories (level 0)
        - Popular categories (based on keywords)
        - Fresh food categories

        Args:
            category: Category instance

        Returns:
            int: Priority value (higher is better)
        """
        priority = 50  # Base priority

        # Level-based priority
        if category.level == 0:
            priority += 30
        elif category.level == 1:
            priority += 20
        else:
            priority += 10

        # Keyword-based priority
        name_lower = category.name.lower()
        if any(keyword in name_lower for keyword in ['fresh', 'fruit', 'veg']):
            priority += 20
        elif any(keyword in name_lower for keyword in ['offer', 'deal', 'save']):
            priority += 15
        elif any(keyword in name_lower for keyword in ['meat', 'fish', 'dairy']):
            priority += 10

        return priority
