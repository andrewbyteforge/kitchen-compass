"""
Product List crawler for ASDA website.

Crawls category pages to extract product listings and basic information
including names, prices, and product URLs.
"""

import logging
import json
import re
from typing import List, Dict, Optional, Any
from decimal import Decimal
from urllib.parse import urljoin, urlparse
from django.utils import timezone

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from django.db import transaction
from .category_utils import CategoryNavigator

from .base_scraper import BaseScraper
from ..models import Product, Category, CrawlQueue
import time
from .base_scraper import BaseScraper
from ..models import Product, Category, CrawlQueue
from .utils import handle_all_popups, parse_price, parse_unit_price, extract_product_id_from_url
import time

logger = logging.getLogger(__name__)


class ProductListCrawler(BaseScraper):
    """
    Crawler for extracting product listings from ASDA category pages.

    This crawler:
    1. Takes category URLs from the queue
    2. Navigates through paginated product listings
    3. Extracts basic product information
    4. Saves products to database
    5. Adds product URLs to detail crawler queue
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the product list crawler."""
        super().__init__(*args, **kwargs)
        self.current_category: Optional[Category] = None
        self.products_found: int = 0

    def scrape(self) -> None:
        """
        Main scraping method for product listings.

        Processes URLs from the PRODUCT_LIST queue.
        """
        try:
            logger.info("Starting product list crawling")

            # Get pending URLs from queue
            queue_items = CrawlQueue.objects.filter(
                queue_type='PRODUCT_LIST',
                status='PENDING'
            ).order_by('-priority', 'created_at')[:10]  # Process 10 at a time

            if not queue_items:
                logger.info("No pending URLs in product list queue")
                return

            for queue_item in queue_items:
                try:
                    # Mark as processing
                    queue_item.status = 'PROCESSING'
                    queue_item.save()

                    # Process the category
                    self._process_category_page(queue_item)

                    # Mark as completed
                    queue_item.status = 'COMPLETED'
                    queue_item.processed_at = timezone.now()
                    queue_item.save()

                except Exception as e:
                    logger.error(
                        f"Error processing queue item {queue_item.id}: {str(e)}"
                    )
                    self._handle_queue_failure(queue_item, e)

            logger.info(
                f"Product list crawling completed. "
                f"Found {self.products_found} products"
            )

        except Exception as e:
            logger.error(f"Fatal error in product list crawling: {str(e)}")
            self.handle_error(e, {'stage': 'product_list_crawling'})
            raise



    # Then update the _process_category_page method:
    def _process_category_page(self, queue_item: CrawlQueue) -> None:
        """
        Process a single category page and all its paginations.

        Args:
            queue_item: The queue item being processed
        """
        try:
            url = queue_item.url
            self.current_category = queue_item.category

            logger.info(
                f"Processing category: {self.current_category.name if self.current_category else 'Unknown'}"
            )

            # Navigate to first page
            if not self.get_page(url):
                raise Exception(f"Failed to load category page: {url}")

            # Handle any popups that might appear
            handle_all_popups(self.driver, self.wait)
            
            # Initialize category navigator
            navigator = CategoryNavigator(self.driver, self.wait)
            
            # Discover and save subcategories
            subcategories = navigator.discover_subcategories()
            if subcategories:
                added = navigator.save_subcategories_to_queue(
                    subcategories, 
                    parent_category=self.current_category,
                    priority=3  # Higher priority for subcategories
                )
                logger.info(f"Added {added} subcategories to queue")
            
            # Get category info for logging
            category_info = navigator.get_category_info()
            if category_info['product_count']:
                logger.info(f"Category contains {category_info['product_count']} products")

            # Process all pages
            page_num = 1
            while True:
                logger.info(f"Processing page {page_num} of {url}")

                # Extract products from current page
                products = self._extract_products_from_page()

                if not products:
                    logger.info("No products found on page")
                    # Check if this is a category hub page (only subcategories, no products)
                    if page_num == 1 and subcategories:
                        logger.info("This appears to be a category hub page with subcategories only")
                        # Mark as completed since we've discovered subcategories
                        self.update_session_stats(processed=1)
                        return
                    break

                # Save products
                self._save_products(products)

                # Check for next page
                if not self._navigate_to_next_page():
                    logger.info("No more pages to process")
                    break

                page_num += 1

                # Safety limit
                if page_num > 100:
                    logger.warning("Reached page limit, stopping pagination")
                    break

        except Exception as e:
            logger.error(f"Error processing category page: {str(e)}")
            raise




    def _extract_products_from_page(self) -> List[Dict[str, Any]]:
        """
        Extract product information from the current page.

        Returns:
            List[Dict]: List of product data dictionaries
        """
        products = []

        try:
            # Wait for the product grid to load
            time.sleep(2)  # Give page time to fully render
            
            # More specific selector for actual product containers
            # Look for elements that have both product class AND contain a link
            product_selectors = [
                "div.co-product:has(a[href*='/product/'])",
                "article.co-item:has(a[href*='/product/'])",
                "li.co-item:has(a[href*='/product/'])",
                "[class*='product-item']:has(a[href*='/product/'])",
                "div[class*='co-product']:has(h3)",
            ]
            
            product_tiles = []
            for selector in product_selectors:
                try:
                    # Use JavaScript to find elements since :has() might not work with Selenium
                    script = f"""
                    return Array.from(document.querySelectorAll('div.co-product')).filter(el => 
                        el.querySelector('a[href*="/product/"]') !== null
                    );
                    """
                    potential_tiles = self.driver.execute_script(script)
                    if potential_tiles:
                        product_tiles = potential_tiles
                        logger.info(f"Found {len(product_tiles)} product tiles using JavaScript filter")
                        break
                except Exception:
                    try:
                        # Fallback to basic selector
                        tiles = self.driver.find_elements(By.CSS_SELECTOR, "div.co-product")
                        # Filter out non-product elements
                        product_tiles = []
                        for tile in tiles:
                            try:
                                # Check if it has a product link
                                tile.find_element(By.CSS_SELECTOR, "a[href*='/product/']")
                                product_tiles.append(tile)
                            except NoSuchElementException:
                                continue
                        if product_tiles:
                            logger.info(f"Found {len(product_tiles)} valid product tiles after filtering")
                            break
                    except Exception as e:
                        logger.debug(f"Error with selector {selector}: {str(e)}")
                        continue

            if not product_tiles:
                logger.warning("No products found with any known selector")
                return products

            logger.info(f"Processing {len(product_tiles)} product tiles")
            
            for i, tile in enumerate(product_tiles):
                try:
                    product_data = self._extract_product_data(tile)
                    if product_data and product_data.get('name') and product_data.get('asda_id'):
                        products.append(product_data)
                        logger.debug(f"Successfully extracted product {i+1}/{len(product_tiles)}: {product_data['name']}")
                    else:
                        logger.debug(f"Skipped invalid product data at position {i+1}")
                except Exception as e:
                    logger.warning(f"Error extracting product data at position {i+1}: {str(e)}")
                    continue

            logger.info(f"Successfully extracted {len(products)} valid products from {len(product_tiles)} tiles")

        except Exception as e:
            logger.error(f"Error extracting products: {str(e)}")

        return products

    def _extract_product_data(self, tile_element) -> Optional[Dict[str, Any]]:
        """
        Extract data from a single product tile.

        Args:
            tile_element: Selenium WebElement for the product tile

        Returns:
            Optional[Dict]: Product data or None if extraction fails
        """
        try:
            product_data = {}

            # First, get the product link which is most reliable
            try:
                link_element = tile_element.find_element(By.CSS_SELECTOR, "a[href*='/product/']")
                product_url = link_element.get_attribute('href')
                
                if not product_url or '/product/' not in product_url:
                    logger.debug("Invalid product URL")
                    return None
                    
                product_data['url'] = product_url
                
                # Extract ASDA ID from URL - more robust pattern
                # URLs are like: /product/something/1234567890
                url_parts = product_url.rstrip('/').split('/')
                asda_id = None
                for part in reversed(url_parts):
                    if part.isdigit() and len(part) >= 10:
                        asda_id = part
                        break
                
                if not asda_id:
                    logger.debug(f"Could not extract ASDA ID from URL: {product_url}")
                    return None
                    
                product_data['asda_id'] = asda_id
                
            except NoSuchElementException:
                logger.debug("No product link found in tile")
                return None

            # Extract product name - prioritize h3 title
            product_name = None
            
            # Method 1: Look for h3 with class co-product__title
            try:
                title_element = tile_element.find_element(By.CSS_SELECTOR, "h3.co-product__title")
                product_name = title_element.text.strip()
            except NoSuchElementException:
                pass
            
            # Method 2: Look for any h3 inside the tile
            if not product_name:
                try:
                    title_element = tile_element.find_element(By.CSS_SELECTOR, "h3")
                    product_name = title_element.text.strip()
                except NoSuchElementException:
                    pass
            
            # Method 3: Get text from the product link
            if not product_name:
                try:
                    link_element = tile_element.find_element(By.CSS_SELECTOR, "a[href*='/product/']")
                    product_name = link_element.text.strip()
                except NoSuchElementException:
                    pass
            
            # Method 4: Look for image alt text
            if not product_name:
                try:
                    img = tile_element.find_element(By.CSS_SELECTOR, "img[alt]")
                    alt_text = img.get_attribute('alt')
                    if alt_text and len(alt_text) > 3 and not alt_text.lower().startswith('image'):
                        product_name = alt_text
                except NoSuchElementException:
                    pass

            if not product_name or len(product_name) < 3:
                logger.debug(f"Invalid product name: {product_name}")
                return None

            # Filter out non-product text
            invalid_names = [
                'typically fresh for', 'frozen', 'exclusive to asda', 
                'decanter', 'winner', 'days', 'bar-be-quick'
            ]
            if any(invalid in product_name.lower() for invalid in invalid_names):
                logger.debug(f"Filtered out invalid product name: {product_name}")
                return None

            product_data['name'] = product_name

            # Extract brand
            if product_name.upper().startswith('ASDA'):
                product_data['brand'] = 'ASDA'
            else:
                # Try to find brand element
                try:
                    brand_element = tile_element.find_element(By.CSS_SELECTOR, "[class*='brand']")
                    product_data['brand'] = brand_element.text.strip()
                except NoSuchElementException:
                    product_data['brand'] = None

            # Extract price
            price_data = self._extract_price_data(tile_element)
            product_data.update(price_data)

            # Extract image URL
            try:
                img_element = tile_element.find_element(By.CSS_SELECTOR, "img")
                image_url = img_element.get_attribute('src')
                if image_url and 'assets-asda.com' in image_url:
                    product_data['image_url'] = image_url
                else:
                    product_data['image_url'] = None
            except NoSuchElementException:
                product_data['image_url'] = None

            # Extract volume/weight
            try:
                volume_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    ".co-product__volume, .co-item__volume, [class*='volume']"
                )
                volume_text = volume_element.text.strip()
                # Validate it looks like a volume/weight
                if re.search(r'\d+(?:g|kg|ml|l|L|cl|pack|x)', volume_text, re.IGNORECASE):
                    product_data['description'] = volume_text
                else:
                    product_data['description'] = None
            except NoSuchElementException:
                product_data['description'] = None

            return product_data

        except Exception as e:
            logger.error(f"Error extracting product data: {str(e)}")
            return None

    def _extract_price_data(self, tile_element) -> Dict[str, Any]:
        """
        Extract price information from product tile.

        Args:
            tile_element: Product tile element

        Returns:
            Dict containing price information
        """
        price_info = {
            'price': None,
            'price_per_unit': None,
            'on_offer': False,
            'offer_text': None
        }

        try:
            # Price selectors
            price_selectors = [
                ".co-product__price",
                ".co-item__price",
                "[data-auto-id='productPrice']",
                "[class*='price-now']",
                ".price-single",
                "strong[class*='price']"
            ]

            for selector in price_selectors:
                try:
                    price_element = tile_element.find_element(By.CSS_SELECTOR, selector)
                    price_text = price_element.text.strip()
                    if price_text:
                        price = parse_price(price_text)
                        if price:
                            price_info['price'] = price
                            break
                except NoSuchElementException:
                    continue

            # Check for offer/was price
            try:
                was_price_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    ".co-product__price-was, .price-was, [class*='was-price']"
                )
                if was_price_element:
                    price_info['on_offer'] = True
                    price_info['offer_text'] = was_price_element.text.strip()
            except NoSuchElementException:
                pass

            # Extract unit price
            try:
                unit_price_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    ".co-product__price-per-uom, .price-per-unit, [class*='price-per']"
                )
                unit_text = unit_price_element.text.strip()
                if unit_text:
                    unit_data = parse_unit_price(unit_text)
                    if unit_data:
                        price_info['price_per_unit'] = unit_data['price']
            except NoSuchElementException:
                pass

        except Exception as e:
            logger.error(f"Error extracting price data: {str(e)}")

        return price_info

    def _save_products(self, products: List[Dict[str, Any]]) -> None:
        """
        Save products to database and add to detail queue.

        Args:
            products: List of product data dictionaries
        """
        try:
            with transaction.atomic():
                for product_data in products:
                    try:
                        # Create or update product
                        product, created = Product.objects.update_or_create(
                            asda_id=product_data['asda_id'],
                            defaults={
                                'name': product_data['name'],
                                'brand': product_data.get('brand'),
                                'description': product_data.get('description'),
                                'url': product_data['url'],
                                'image_url': product_data.get('image_url'),
                                'price': product_data.get('price'),
                                'price_per_unit': product_data.get('price_per_unit'),
                                'on_offer': product_data.get('on_offer', False),
                                'offer_text': product_data.get('offer_text'),
                                'is_available': True,
                                'last_scraped': timezone.now()
                            }
                        )

                        # Add category relationship
                        if self.current_category:
                            product.categories.add(self.current_category)

                        # Add to detail queue if nutrition not scraped
                        if not product.nutrition_scraped:
                            self._add_to_detail_queue(product)

                        self.products_found += 1

                        if created:
                            logger.info(f"Created product: {product.name}")
                        else:
                            logger.debug(f"Updated product: {product.name}")

                        # Update session stats
                        self.update_session_stats(processed=1)

                    except Exception as e:
                        logger.error(f"Error saving product: {str(e)}")
                        self.update_session_stats(failed=1)

        except Exception as e:
            logger.error(f"Error in save_products transaction: {str(e)}")
            raise

    def _add_to_detail_queue(self, product: Product) -> None:
        """
        Add product URL to detail crawler queue.

        Args:
            product: Product instance to queue
        """
        try:
            url_hash = self.get_url_hash(product.url)

            # Check if already in queue
            existing = CrawlQueue.objects.filter(
                url_hash=url_hash,
                queue_type='PRODUCT_DETAIL'
            ).exists()

            if not existing:
                CrawlQueue.objects.create(
                    url=product.url,
                    url_hash=url_hash,
                    queue_type='PRODUCT_DETAIL',
                    priority=0,  # Default priority
                    product=product,
                    metadata={
                        'product_name': product.name,
                        'product_id': product.asda_id
                    }
                )
                logger.debug(f"Added to detail queue: {product.name}")

        except Exception as e:
            logger.error(f"Error adding product to detail queue: {str(e)}")

    def _navigate_to_next_page(self) -> bool:
        """
        Navigate to the next page of products if available.

        Returns:
            bool: True if navigated to next page, False if no next page
        """
        try:
            # Multiple possible selectors for next button
            next_button_selectors = [
                "[data-testid='pagination-next']:not([disabled])",
                "a.co-pagination__next:not(.co-pagination__next--disabled)",
                "button.pagination-next:not([disabled])",
                "[aria-label='Next page']:not([disabled])",
                "a[rel='next']",
                ".asda-pagination__next:not(.disabled)"
            ]

            next_button = None
            for selector in next_button_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if next_button:
                        break
                except NoSuchElementException:
                    continue

            if not next_button:
                logger.debug("No next page button found")
                return False

            # Check if button is actually clickable
            if next_button.get_attribute('disabled') or 'disabled' in next_button.get_attribute('class', ''):
                logger.debug("Next page button is disabled")
                return False

            # Scroll to button
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                next_button
            )
            time.sleep(1)

            # Click next page
            try:
                next_button.click()
            except Exception:
                # Try JavaScript click as fallback
                self.driver.execute_script("arguments[0].click();", next_button)

            # Wait for page to load
            time.sleep(3)
            
            # Handle any popups that might appear after navigation
            from .utils import handle_all_popups
            handle_all_popups(self.driver, self.wait)

            return True

        except Exception as e:
            logger.warning(f"Error navigating to next page: {str(e)}")
            return False

    def _handle_queue_failure(
        self,
        queue_item: CrawlQueue,
        error: Exception
    ) -> None:
        """
        Handle failure of a queue item.

        Args:
            queue_item: The failed queue item
            error: The exception that occurred
        """
        try:
            queue_item.attempts += 1
            queue_item.error_message = str(error)

            if queue_item.attempts >= queue_item.max_attempts:
                queue_item.status = 'FAILED'
                logger.error(
                    f"Queue item {queue_item.id} failed after "
                    f"{queue_item.max_attempts} attempts"
                )
            else:
                queue_item.status = 'PENDING'  # Reset to pending for retry
                logger.info(
                    f"Queue item {queue_item.id} will be retried "
                    f"({queue_item.attempts}/{queue_item.max_attempts})"
                )

            queue_item.save()
            self.update_session_stats(failed=1)

        except Exception as e:
            logger.error(f"Error handling queue failure: {str(e)}")
