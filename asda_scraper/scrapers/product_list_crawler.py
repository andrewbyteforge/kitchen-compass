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

from .base_scraper import BaseScraper
from ..models import Product, Category, CrawlQueue
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

            # Process all pages
            page_num = 1
            while True:
                logger.info(f"Processing page {page_num} of {url}")

                # Extract products from current page
                products = self._extract_products_from_page()

                if not products:
                    logger.info("No products found on page")
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
            # Wait for products to load
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='product-tile']")
                )
            )

            # Find all product tiles
            product_tiles = self.driver.find_elements(
                By.CSS_SELECTOR,
                "[data-testid='product-tile']"
            )

            logger.info(f"Found {len(product_tiles)} product tiles")

            for tile in product_tiles:
                try:
                    product_data = self._extract_product_data(tile)
                    if product_data:
                        products.append(product_data)
                except Exception as e:
                    logger.warning(f"Error extracting product data: {str(e)}")
                    continue

        except TimeoutException:
            logger.warning("No products found on page (timeout)")
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

            # Extract product link and ID
            link_element = tile_element.find_element(
                By.CSS_SELECTOR,
                "a[data-testid='product-tile-link']"
            )
            product_url = link_element.get_attribute('href')

            if not product_url:
                return None

            # Extract ASDA ID from URL
            asda_id_match = re.search(r'/product/[^/]+/(\d+)', product_url)
            if asda_id_match:
                product_data['asda_id'] = asda_id_match.group(1)
            else:
                # Try to get from data attribute
                product_data['asda_id'] = tile_element.get_attribute('data-product-id')

            if not product_data.get('asda_id'):
                logger.warning("Could not extract ASDA ID")
                return None

            product_data['url'] = product_url

            # Extract product name
            try:
                name_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-tile-title']"
                )
                product_data['name'] = name_element.text.strip()
            except NoSuchElementException:
                logger.warning("Could not find product name")
                return None

            # Extract brand (if present)
            try:
                brand_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-tile-brand']"
                )
                product_data['brand'] = brand_element.text.strip()
            except NoSuchElementException:
                product_data['brand'] = None

            # Extract price
            price_data = self._extract_price_data(tile_element)
            product_data.update(price_data)

            # Extract image URL
            try:
                img_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    "img[data-testid='product-tile-image']"
                )
                product_data['image_url'] = img_element.get_attribute('src')
            except NoSuchElementException:
                product_data['image_url'] = None

            # Extract description (if present)
            try:
                desc_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-tile-description']"
                )
                product_data['description'] = desc_element.text.strip()
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
            Dict: Price-related data
        """
        price_data = {
            'price': None,
            'price_per_unit': None,
            'on_offer': False,
            'offer_text': None
        }

        try:
            # Check for offer price first
            try:
                offer_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-tile-offer-price']"
                )
                price_text = offer_element.text.strip()
                price_data['on_offer'] = True

                # Get offer text
                try:
                    offer_text_element = tile_element.find_element(
                        By.CSS_SELECTOR,
                        "[data-testid='product-tile-offer-text']"
                    )
                    price_data['offer_text'] = offer_text_element.text.strip()
                except NoSuchElementException:
                    pass

            except NoSuchElementException:
                # No offer, get regular price
                price_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-tile-price']"
                )
                price_text = price_element.text.strip()

            # Parse price
            price_match = re.search(r'£(\d+\.?\d*)', price_text)
            if price_match:
                price_data['price'] = Decimal(price_match.group(1))

            # Extract price per unit
            try:
                unit_price_element = tile_element.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-tile-unit-price']"
                )
                price_data['price_per_unit'] = unit_price_element.text.strip()
            except NoSuchElementException:
                pass

        except Exception as e:
            logger.warning(f"Error extracting price data: {str(e)}")

        return price_data

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
            # Look for next page button
            next_button = self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-testid='pagination-next']:not([disabled])"
            )

            # Scroll to button
            self.driver.execute_script(
                "arguments[0].scrollIntoView(true);",
                next_button
            )
            time.sleep(1)

            # Click next page
            next_button.click()

            # Wait for page to load
            time.sleep(3)  # Give time for products to load

            return True

        except NoSuchElementException:
            logger.debug("No next page button found")
            return False
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
