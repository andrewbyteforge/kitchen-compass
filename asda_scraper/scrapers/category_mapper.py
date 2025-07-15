"""
Category Mapper crawler for ASDA website.

Discovers and maps all product categories and subcategories
by navigating through the ASDA groceries navigation menu.
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
    Crawler for discovering and mapping ASDA product categories.

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

    def scrape(self) -> None:
        """
        Main scraping method for category discovery.

        Implements the abstract scrape method from BaseScraper.
        """
        try:
            logger.info("Starting category mapping process")
            link_logger.info("=== LINK DISCOVERY STARTED ===")

            # Navigate to ASDA groceries homepage
            if not self.get_page("https://groceries.asda.com/"):
                raise Exception("Failed to load ASDA homepage")

            # Accept cookies if present
            self._handle_cookie_consent()

            # Get main categories from configuration
            main_categories = self.settings.get('CATEGORIES', [])

            for category_url in main_categories:
                try:
                    self._process_main_category(category_url)
                except Exception as e:
                    logger.error(f"Error processing category {category_url}: {str(e)}")
                    self.handle_error(e, {'category_url': category_url})
                    continue

            logger.info(
                f"Category mapping completed. "
                f"Discovered {len(self.discovered_categories)} categories"
            )
            link_logger.info(
                f"=== LINK DISCOVERY COMPLETED: {self.total_links_found} TOTAL LINKS FOUND ==="
            )

        except Exception as e:
            logger.error(f"Fatal error in category mapping: {str(e)}")
            self.handle_error(e, {'stage': 'category_mapping'})
            raise

    def _handle_cookie_consent(self) -> None:
        """Handle cookie consent popup if present."""
        handle_all_popups(self.driver, self.wait)

    def _process_main_category(self, category_url: str) -> None:
        """
        Process a main category and discover its subcategories.

        Args:
            category_url: URL of the main category to process
        """
        try:
            logger.info(f"Processing main category: {category_url}")
            link_logger.info(f">>> Navigating to main category: {category_url}")

            # Navigate to category page
            if not self.get_page(category_url):
                raise Exception(f"Failed to load category page: {category_url}")

            # Extract category name from page
            category_name = self._extract_category_name()
            if not category_name:
                logger.warning(f"Could not extract category name for {category_url}")
                category_name = "Unknown Category"

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

            # Discover subcategories using the navigation menu
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
                    logger.error(f"Error processing subcategory: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error processing main category {category_url}: {str(e)}")
            raise

    def _extract_category_name(self) -> Optional[str]:
        """
        Extract category name from the current page.

        Returns:
            Optional[str]: Category name if found, None otherwise
        """
        try:
            # Try to find category name in breadcrumb
            breadcrumb = self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-testid='breadcrumb'] li:last-child"
            )
            return breadcrumb.text.strip()
        except NoSuchElementException:
            pass

        try:
            # Try to find category name in page title
            title_element = self.driver.find_element(
                By.CSS_SELECTOR,
                "h1"
            )
            return title_element.text.strip()
        except NoSuchElementException:
            pass

        return None

    def _discover_subcategories(self) -> List[Dict]:
        """
        Discover subcategories from the navigation menu.

        Returns:
            List[Dict]: List of subcategory data with names, URLs, and children
        """
        subcategories = []

        try:
            # Find navigation menu sections
            # ASDA uses different class names for different category sections
            nav_sections = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[class*='-taxo'] a, .category-navigation a, [data-testid*='category'] a"
            )

            link_logger.info(f"  → Scanning for subcategory links... Found {len(nav_sections)} potential links")

            for nav_link in nav_sections:
                try:
                    # Get link text and URL
                    name = nav_link.text.strip()
                    url = nav_link.get_attribute('href')

                    if name and url and self.is_valid_url(url):
                        # Check if already discovered
                        if url not in self.discovered_categories:
                            self.discovered_categories.add(url)

                            subcategory_data = {
                                'name': name,
                                'url': url,
                                'children': []
                            }

                            subcategories.append(subcategory_data)

                            # Log each discovered subcategory link in green
                            link_logger.info(f"  ✓ SUBCATEGORY LINK FOUND: {name} - {url}")
                            self.total_links_found += 1
                            logger.debug(f"Discovered subcategory: {name} - {url}")

                except Exception as e:
                    logger.warning(f"Error processing navigation link: {str(e)}")
                    continue

            link_logger.info(f"  → Found {len(subcategories)} new subcategories on this page")

        except Exception as e:
            logger.error(f"Error discovering subcategories: {str(e)}")

        return subcategories

    def _save_category(
        self,
        name: str,
        url: str,
        level: int,
        parent: Optional[Category] = None
    ) -> Category:
        """
        Save category to database and add to queue.

        Args:
            name: Category name
            url: Category URL
            level: Category level (0=main, 1=sub, 2=sub-sub)
            parent: Parent category if applicable

        Returns:
            Category: The saved category instance
        """
        try:
            # Create or update category
            category, created = Category.objects.update_or_create(
                url=url,
                defaults={
                    'name': name,
                    'level': level,
                    'parent': parent,
                    'is_active': True
                }
            )

            if created:
                logger.info(f"Created category: {name} (Level {level})")
                link_logger.info(f"  ★ NEW CATEGORY SAVED TO DATABASE: {name}")
            else:
                logger.debug(f"Updated category: {name} (Level {level})")

            # Add to product list queue
            self._add_to_queue(category)

            # Mark URL as crawled
            self.mark_url_as_crawled(url, 'CATEGORY')

            # Update session stats
            self.update_session_stats(processed=1)

            return category

        except Exception as e:
            logger.error(f"Error saving category {name}: {str(e)}")
            self.update_session_stats(failed=1)
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
