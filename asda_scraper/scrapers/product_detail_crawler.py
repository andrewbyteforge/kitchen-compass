"""
Product Detail crawler for ASDA website.

Crawls individual product pages to extract detailed information,
particularly nutrition data and additional product details.
"""

import logging
import re
from typing import Dict, Optional, Any, List
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .base_scraper import BaseScraper
from ..models import Product, NutritionInfo, CrawlQueue
from .utils import handle_all_popups
import time

logger = logging.getLogger(__name__)


class ProductDetailCrawler(BaseScraper):
    """
    Crawler for extracting detailed product information from ASDA.

    This crawler:
    1. Takes product URLs from the detail queue
    2. Navigates to individual product pages
    3. Extracts nutrition information
    4. Updates product records with additional details
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the product detail crawler."""
        super().__init__(*args, **kwargs)
        self.nutrition_extracted: int = 0
        self.batch_size: int = 10  # Configurable batch size
        self.batch_delay: int = 2  # Delay between batches in seconds

    def scrape(self) -> None:
        """
        Main scraping method for product details.

        Processes ALL URLs from the PRODUCT_DETAIL queue until empty.
        """
        try:
            logger.info("Starting product detail crawling")
            batch_size = 10  # Process 10 at a time for better memory management
            total_processed = 0
            
            while True:
                # Get next batch of pending URLs from queue
                queue_items = CrawlQueue.objects.filter(
                    queue_type='PRODUCT_DETAIL',
                    status='PENDING'
                ).order_by('-priority', 'created_at')[:batch_size]

                if not queue_items:
                    logger.info("No more pending URLs in product detail queue")
                    break

                logger.info(f"Processing batch of {len(queue_items)} products")
                
                for queue_item in queue_items:
                    try:
                        # Check if we should stop (for graceful shutdown)
                        if self.session and self.session.status == 'STOPPED':
                            logger.info("Crawler stopped by user")
                            return
                        
                        # Mark as processing
                        queue_item.status = 'PROCESSING'
                        queue_item.save()

                        # Process the product
                        self._process_product_page(queue_item)

                        # Mark as completed
                        queue_item.status = 'COMPLETED'
                        queue_item.processed_at = timezone.now()
                        queue_item.save()
                        
                        total_processed += 1
                        
                        # Log progress every 10 products
                        if total_processed % 10 == 0:
                            remaining = CrawlQueue.objects.filter(
                                queue_type='PRODUCT_DETAIL',
                                status='PENDING'
                            ).count()
                            logger.info(
                                f"Progress: Processed {total_processed} products, "
                                f"{remaining} remaining in queue"
                            )

                    except Exception as e:
                        logger.error(
                            f"Error processing queue item {queue_item.id}: {str(e)}"
                        )
                        self._handle_queue_failure(queue_item, e)
                        
                # Small delay between batches to avoid overwhelming the server
                time.sleep(2)

            logger.info(
                f"Product detail crawling completed. "
                f"Total processed: {total_processed}, "
                f"Extracted nutrition for {self.nutrition_extracted} products"
            )

        except Exception as e:
            logger.error(f"Fatal error in product detail crawling: {str(e)}")
            self.handle_error(e, {'stage': 'product_detail_crawling'})
            raise










    def _process_product_page(self, queue_item: CrawlQueue) -> None:
        """
        Process a single product page.

        Args:
            queue_item: The queue item being processed
        """
        try:
            url = queue_item.url
            product = queue_item.product

            if not product:
                logger.error(f"No product associated with queue item {queue_item.id}")
                return

            logger.info(f"Processing product: {product.name}")

            # Navigate to product page
            if not self.get_page(url):
                raise Exception(f"Failed to load product page: {url}")

            # Handle any popups that might appear
            handle_all_popups(self.driver, self.wait)

            # Check if product is still available
            if self._is_product_unavailable():
                logger.warning(f"Product unavailable: {product.name}")
                product.is_available = False
                product.save()
                return

            # Extract detailed information
            details = self._extract_product_details()

            # Update product with any additional details
            if details:
                self._update_product_details(product, details)

            # Extract nutrition information
            nutrition_data = self._extract_nutrition_info()

            if nutrition_data:
                self._save_nutrition_info(product, nutrition_data)
                self.nutrition_extracted += 1
            else:
                logger.warning(f"No nutrition data found for: {product.name}")

            # Mark URL as crawled
            self.mark_url_as_crawled(url, 'PRODUCT_DETAIL')

            # Update session stats
            self.update_session_stats(processed=1)

        except Exception as e:
            logger.error(f"Error processing product page: {str(e)}")
            self.update_session_stats(failed=1)
            raise

    def _is_product_unavailable(self) -> bool:
        """
        Check if product is unavailable.

        Returns:
            bool: True if product is unavailable
        """
        try:
            # Check for out of stock message
            self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-testid='product-unavailable-message']"
            )
            return True
        except NoSuchElementException:
            pass

        try:
            # Check for 404 or error page
            error_element = self.driver.find_element(
                By.CSS_SELECTOR,
                ".error-page, .not-found"
            )
            return True
        except NoSuchElementException:
            pass

        return False

    def _extract_product_details(self) -> Dict[str, Any]:
        """
        Extract additional product details from the page.

        Returns:
            Dict: Additional product details
        """
        details = {}

        try:
            # Extract full description
            try:
                desc_element = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-description']"
                )
                details['description'] = desc_element.text.strip()
            except NoSuchElementException:
                pass

            # Extract ingredients
            try:
                ingredients_element = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-ingredients']"
                )
                details['ingredients'] = ingredients_element.text.strip()
            except NoSuchElementException:
                pass

            # Extract storage instructions
            try:
                storage_element = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "[data-testid='product-storage']"
                )
                details['storage'] = storage_element.text.strip()
            except NoSuchElementException:
                pass

        except Exception as e:
            logger.warning(f"Error extracting product details: {str(e)}")

        return details
    


    def _parse_nutrition_value(self, value_text: str) -> Optional[Decimal]:
        """
        Parse nutrition value from text.

        Args:
            value_text: Text containing the value (e.g., "1.8g", "<0.5g", "131")

        Returns:
            Optional[Decimal]: Parsed value or None
        """
        try:
            # Remove whitespace
            value_text = value_text.strip()
            
            # Handle "less than" values (e.g., "<0.5g")
            if value_text.startswith('<'):
                # Extract the number after '<'
                match = re.search(r'<(\d+\.?\d*)', value_text)
                if match:
                    # Return half of the "less than" value as approximation
                    return Decimal(match.group(1)) / 2
            
            # Extract numeric value
            match = re.search(r'(\d+\.?\d*)', value_text)
            if match:
                return Decimal(match.group(1))
                
            return None
            
        except Exception as e:
            logger.debug(f"Error parsing nutrition value '{value_text}': {str(e)}")
            return None





    def _extract_nutrition_info(self) -> Optional[Dict[str, Any]]:
        """
        Extract nutrition information from product page.

        Returns:
            Optional[Dict]: Nutrition data or None if not found
        """
        try:
            # Wait a bit for page to fully load
            time.sleep(2)
            
            # Find nutrition container using the actual class names from the HTML
            nutrition_container = self._find_nutrition_container()

            if not nutrition_container:
                return None

            # Extract nutrition values
            nutrition_data = {
                'energy_kj': None,
                'energy_kcal': None,
                'fat': None,
                'saturated_fat': None,
                'carbohydrates': None,
                'sugars': None,
                'fibre': None,
                'protein': None,
                'salt': None,
                'other_nutrients': {},
                'serving_size': None,
                'servings_per_pack': None,
                'raw_nutrition_text': nutrition_container.text
            }

            # Find all nutrition rows
            nutrition_rows = nutrition_container.find_elements(
                By.CSS_SELECTOR,
                ".pdp-description-reviews__nutrition-row--details"
            )

            for row in nutrition_rows:
                try:
                    # Get cells in the row
                    cells = row.find_elements(
                        By.CSS_SELECTOR,
                        ".pdp-description-reviews__nutrition-cell"
                    )
                    
                    if len(cells) >= 2:
                        nutrient_name = cells[0].text.strip()
                        value_text = cells[1].text.strip()
                        
                        # Parse the value
                        value = self._parse_nutrition_value(value_text)
                        
                        if nutrient_name and value is not None:
                            # Map to our database fields
                            mapped_field = self._map_nutrient_name(nutrient_name)
                            
                            if mapped_field in nutrition_data:
                                nutrition_data[mapped_field] = value
                            else:
                                # Store in other_nutrients
                                nutrition_data['other_nutrients'][nutrient_name] = float(value)

                except Exception as e:
                    logger.debug(f"Error parsing nutrition row: {str(e)}")
                    continue

            # Extract serving information from header if present
            serving_info = self._extract_serving_info(nutrition_container)
            nutrition_data.update(serving_info)

            return nutrition_data

        except Exception as e:
            logger.error(f"Error extracting nutrition info: {str(e)}")
            return None



    def _navigate_to_nutrition_section(self) -> None:
        """Navigate to the nutrition section of the product page."""
        try:
            # Look for nutrition tab/button
            nutrition_tab = self.driver.find_element(
                By.CSS_SELECTOR,
                "[data-testid='product-nutrition-tab'], "
                "[aria-label*='nutrition' i], "
                "button:contains('Nutrition')"
            )

            # Click to expand nutrition section
            self.driver.execute_script(
                "arguments[0].scrollIntoView(true);",
                nutrition_tab
            )
            nutrition_tab.click()

            # Wait for nutrition content to load
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".nutrition-table, .nutrition-content")
                )
            )

        except NoSuchElementException:
            logger.debug("No nutrition tab found, checking if already visible")
        except Exception as e:
            logger.warning(f"Error navigating to nutrition section: {str(e)}")

    def _find_nutrition_container(self) -> Optional[Any]:
        """
        Find the container element with nutrition information.

        Returns:
            Optional[WebElement]: Nutrition container or None
        """
        # Selectors based on the actual HTML structure
        selectors = [
            ".pdp-description-reviews__nutrition-table-cntr",
            "[data-auto-id='nutritionTable']",
            "div:has(.pdp-description-reviews__nutrition-row)",
            ".pdp-description-reviews__product-details-content",
        ]

        for selector in selectors:
            try:
                # For :has selector, use XPath equivalent
                if ":has(" in selector:
                    # Convert :has selector to XPath
                    container = self.driver.find_element(
                        By.XPATH,
                        "//div[.//div[contains(@class, 'pdp-description-reviews__nutrition-row')]]"
                    )
                else:
                    container = self.driver.find_element(By.CSS_SELECTOR, selector)
                
                # Check if it contains nutrition keywords
                text = container.text.lower()
                if any(keyword in text for keyword in ['nutrition', 'energy', 'kcal', 'protein', 'typical values']):
                    logger.debug(f"Found nutrition container with selector: {selector}")
                    return container
            except NoSuchElementException:
                continue

        # Try finding by text content
        try:
            # Look for "Nutritional Values" heading
            heading = self.driver.find_element(
                By.XPATH,
                "//div[contains(text(), 'Nutritional Values')]"
            )
            # Get the parent container
            container = heading.find_element(By.XPATH, "./..")
            if container:
                logger.debug("Found nutrition container via heading text")
                return container
        except NoSuchElementException:
            pass

        logger.warning("No nutrition container found")
        return None




    def _parse_nutrition_row(self, row_element) -> tuple[Optional[str], Optional[Decimal]]:
        """
        Parse a nutrition table row.

        Args:
            row_element: WebElement containing nutrition data

        Returns:
            Tuple of (nutrient_name, value) or (None, None)
        """
        try:
            text = row_element.text.strip()

            # Common patterns for nutrition rows
            patterns = [
                r'([A-Za-z\s\-]+)\s+(\d+\.?\d*)\s*(g|mg|kJ|kcal)',
                r'([A-Za-z\s\-]+):\s*(\d+\.?\d*)\s*(g|mg|kJ|kcal)',
                r'([A-Za-z\s\-]+)\s+(\d+\.?\d*)',
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    nutrient_name = match.group(1).strip().lower()
                    value = Decimal(match.group(2))
                    return nutrient_name, value

            return None, None

        except Exception as e:
            logger.debug(f"Error parsing nutrition row: {str(e)}")
            return None, None





    def _map_nutrient_name(self, nutrient_name: str) -> str:
        """
        Map nutrient names to database fields.

        Args:
            nutrient_name: Raw nutrient name from webpage

        Returns:
            str: Database field name
        """
        # Clean the name first
        clean_name = nutrient_name.lower().strip()
        
        # Remove "of which" prefix
        clean_name = clean_name.replace('of which ', '')
        
        nutrient_map = {
            'energy kj': 'energy_kj',
            'energy kcal': 'energy_kcal',
            'fat': 'fat',
            'saturates': 'saturated_fat',
            'saturated fat': 'saturated_fat',
            'carbohydrate': 'carbohydrates',
            'carbohydrates': 'carbohydrates',
            'sugars': 'sugars',
            'sugar': 'sugars',
            'fibre': 'fibre',
            'fiber': 'fibre',
            'protein': 'protein',
            'salt': 'salt',
        }

        return nutrient_map.get(clean_name, clean_name)





    def _extract_serving_info(self, nutrition_container) -> Dict[str, Any]:
        """
        Extract serving size information from nutrition table header.

        Args:
            nutrition_container: Container element with nutrition info

        Returns:
            Dict: Serving information
        """
        serving_info = {
            'serving_size': None,
            'servings_per_pack': None
        }

        try:
            # Look for header row with serving info
            header_cells = nutrition_container.find_elements(
                By.CSS_SELECTOR,
                ".pdp-description-reviews__nutrition-cell--title"
            )
            
            for cell in header_cells:
                text = cell.text.strip()
                
                # Extract serving size (e.g., "Per 100g", "(pan-fried) Per 100g")
                serving_match = re.search(r'Per\s+(\d+\s*\w+)', text, re.IGNORECASE)
                if serving_match:
                    serving_info['serving_size'] = serving_match.group(1)
                    logger.debug(f"Found serving size: {serving_info['serving_size']}")
                    
        except Exception as e:
            logger.debug(f"Error extracting serving info: {str(e)}")

        return serving_info








    def _save_nutrition_info(
        self,
        product: Product,
        nutrition_data: Dict[str, Any]
    ) -> None:
        """
        Save nutrition information to database.

        Args:
            product: Product instance
            nutrition_data: Nutrition data dictionary
        """
        try:
            with transaction.atomic():
                # Create or update nutrition info
                nutrition, created = NutritionInfo.objects.update_or_create(
                    product=product,
                    defaults={
                        'energy_kj': nutrition_data.get('energy_kj'),
                        'energy_kcal': nutrition_data.get('energy_kcal'),
                        'fat': nutrition_data.get('fat'),
                        'saturated_fat': nutrition_data.get('saturated_fat'),
                        'carbohydrates': nutrition_data.get('carbohydrates'),
                        'sugars': nutrition_data.get('sugars'),
                        'fibre': nutrition_data.get('fibre'),
                        'protein': nutrition_data.get('protein'),
                        'salt': nutrition_data.get('salt'),
                        'other_nutrients': nutrition_data.get('other_nutrients', {}),
                        'serving_size': nutrition_data.get('serving_size'),
                        'servings_per_pack': nutrition_data.get('servings_per_pack'),
                        'raw_nutrition_text': nutrition_data.get('raw_nutrition_text')
                    }
                )

                # Update product nutrition status
                product.nutrition_scraped = True
                product.save(update_fields=['nutrition_scraped', 'updated_at'])

                if created:
                    logger.info(f"Created nutrition info for: {product.name}")
                else:
                    logger.info(f"Updated nutrition info for: {product.name}")

        except Exception as e:
            logger.error(f"Error saving nutrition info: {str(e)}")
            raise

    def _update_product_details(
        self,
        product: Product,
        details: Dict[str, Any]
    ) -> None:
        """
        Update product with additional details.

        Args:
            product: Product instance
            details: Additional details dictionary
        """
        try:
            updated_fields = []

            if details.get('description') and len(details['description']) > len(product.description or ''):
                product.description = details['description']
                updated_fields.append('description')

            # Could add more fields here as needed

            if updated_fields:
                updated_fields.append('updated_at')
                product.save(update_fields=updated_fields)
                logger.debug(f"Updated product details for: {product.name}")

        except Exception as e:
            logger.error(f"Error updating product details: {str(e)}")

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
