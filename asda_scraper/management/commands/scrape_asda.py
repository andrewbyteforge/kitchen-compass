"""
Management command to scrape Asda grocery products and prices.

This command handles the complete scraping process including:
- Cookie acceptance
- Category navigation
- Product extraction
- Price information
- Database storage

File: auth_hub/management/commands/scrape_asda.py
"""

import logging
import time
import json
from typing import Dict, List, Optional, Tuple
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException,
    StaleElementReferenceException
)

from auth_hub.models import AsdaProduct, AsdaCategory

# Set up logging
logger = logging.getLogger(__name__)


class AsdaScraper:
    """
    Handles scraping of Asda grocery website for products and prices.
    
    This class manages the entire scraping process including:
    - Browser initialization with proper configuration
    - Cookie handling and consent management
    - Category navigation and extraction
    - Product data extraction and cleaning
    - Database persistence with error handling
    """
    
    def __init__(self, headless: bool = False, timeout: int = 10):
        """
        Initialize the Asda scraper.
        
        Args:
            headless: Run browser in headless mode
            timeout: Default timeout for web element waits
        """
        self.timeout = timeout
        self.headless = headless
        self.driver = None
        self.base_url = "https://groceries.asda.com/"
        self.products_scraped = 0
        self.categories_scraped = 0
        
    def setup_driver(self) -> None:
        """
        Set up Chrome WebDriver with optimal configuration for scraping.
        
        Raises:
            WebDriverException: If driver setup fails
        """
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless=new")
            
            # Essential Chrome options for stable scraping
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # User agent to avoid detection
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Performance optimizations
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.managed_default_content_settings.media_stream": 2,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(5)
            
            logger.info("Chrome WebDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {str(e)}")
            raise WebDriverException(f"Driver setup failed: {str(e)}")
    
    def accept_cookies(self) -> bool:
        """
        Handle cookie consent popup on Asda website.
        
        Returns:
            bool: True if cookies accepted successfully, False otherwise
        """
        try:
            logger.info("Attempting to accept cookies...")
            
            # Wait for and click the accept cookies button
            cookie_selectors = [
                "button[data-testid='accept-all-cookies']",
                "button[id*='cookie'][id*='accept']",
                "button[class*='cookie'][class*='accept']",
                ".cookie-banner button[data-qa='accept-all']",
                "#acceptAllCookiesButton",
                "button:contains('Accept all cookies')",
                "button:contains('Accept All')"
            ]
            
            for selector in cookie_selectors:
                try:
                    if selector.startswith("button:contains"):
                        # Use XPath for text-based selection
                        text = selector.split("'")[1]
                        button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{text}')]"))
                        )
                    else:
                        button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    
                    button.click()
                    logger.info(f"Successfully clicked cookie button with selector: {selector}")
                    time.sleep(2)  # Wait for cookie banner to disappear
                    return True
                    
                except TimeoutException:
                    continue
                except Exception as e:
                    logger.debug(f"Failed with selector {selector}: {str(e)}")
                    continue
            
            logger.warning("Could not find cookie acceptance button")
            return False
            
        except Exception as e:
            logger.error(f"Error accepting cookies: {str(e)}")
            return False
    
    def navigate_to_groceries(self) -> bool:
        """
        Navigate to the groceries section of Asda website.
        
        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            logger.info("Navigating to groceries section...")
            
            # Look for groceries navigation link
            groceries_selectors = [
                "a[href*='groceries']",
                "nav a:contains('Groceries')",
                ".navigation a[data-qa='groceries']",
                "a[data-testid='groceries-link']"
            ]
            
            for selector in groceries_selectors:
                try:
                    if selector.startswith("nav a:contains"):
                        text = selector.split("'")[1]
                        link = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//nav//a[contains(text(), '{text}')]"))
                        )
                    else:
                        link = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    
                    link.click()
                    logger.info("Successfully navigated to groceries section")
                    time.sleep(3)  # Wait for page to load
                    return True
                    
                except TimeoutException:
                    continue
                except Exception as e:
                    logger.debug(f"Failed with groceries selector {selector}: {str(e)}")
                    continue
            
            logger.warning("Could not find groceries navigation link")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to groceries: {str(e)}")
            return False
    
    def extract_categories(self) -> List[Dict]:
        """
        Extract category hierarchy from Asda groceries page.
        
        Returns:
            List[Dict]: List of category dictionaries with hierarchy information
        """
        categories = []
        
        try:
            logger.info("Extracting category hierarchy...")
            
            # Wait for categories to load
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "nav, .navigation, .categories"))
            )
            
            # Look for main category containers
            category_selectors = [
                ".navigation-categories li",
                ".category-navigation li", 
                "nav li[data-qa*='category']",
                ".categories-menu li",
                ".main-navigation li"
            ]
            
            for selector in category_selectors:
                try:
                    category_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if category_elements:
                        logger.info(f"Found {len(category_elements)} categories with selector: {selector}")
                        break
                except:
                    continue
            else:
                logger.error("No category elements found")
                return categories
            
            # Extract category information with hover interaction
            for i, category_element in enumerate(category_elements[:10]):  # Limit for testing
                try:
                    # Get category text and link
                    category_link = category_element.find_element(By.TAG_NAME, "a")
                    category_name = category_link.get_attribute("textContent").strip()
                    category_url = category_link.get_attribute("href")
                    
                    if not category_name or category_name.lower() in ['home', 'about', 'contact']:
                        continue
                    
                    logger.info(f"Processing category: {category_name}")
                    
                    # Hover over category to reveal subcategories
                    ActionChains(self.driver).move_to_element(category_element).perform()
                    time.sleep(1)  # Wait for dropdown to appear
                    
                    # Look for subcategories
                    subcategories = self._extract_subcategories(category_element)
                    
                    category_data = {
                        'name': category_name,
                        'url': category_url,
                        'level': 1,
                        'parent': None,
                        'subcategories': subcategories
                    }
                    
                    categories.append(category_data)
                    self.categories_scraped += 1
                    
                    logger.info(f"Extracted category: {category_name} with {len(subcategories)} subcategories")
                    
                except StaleElementReferenceException:
                    logger.warning(f"Stale element reference for category {i}")
                    continue
                except Exception as e:
                    logger.error(f"Error extracting category {i}: {str(e)}")
                    continue
            
            logger.info(f"Successfully extracted {len(categories)} main categories")
            return categories
            
        except Exception as e:
            logger.error(f"Error extracting categories: {str(e)}")
            return categories
    
    def _extract_subcategories(self, parent_element) -> List[Dict]:
        """
        Extract subcategories from a parent category element.
        
        Args:
            parent_element: WebElement of the parent category
            
        Returns:
            List[Dict]: List of subcategory dictionaries
        """
        subcategories = []
        
        try:
            # Look for subcategory containers
            subcategory_selectors = [
                ".dropdown-menu a",
                ".submenu a",
                ".category-dropdown a",
                "ul ul a",
                ".level-2 a"
            ]
            
            for selector in subcategory_selectors:
                try:
                    subcat_elements = parent_element.find_elements(By.CSS_SELECTOR, selector)
                    if subcat_elements:
                        break
                except:
                    continue
            else:
                return subcategories
            
            for subcat_element in subcat_elements[:5]:  # Limit subcategories
                try:
                    subcat_name = subcat_element.get_attribute("textContent").strip()
                    subcat_url = subcat_element.get_attribute("href")
                    
                    if subcat_name and subcat_url:
                        subcategories.append({
                            'name': subcat_name,
                            'url': subcat_url,
                            'level': 2
                        })
                        
                except Exception as e:
                    logger.debug(f"Error extracting subcategory: {str(e)}")
                    continue
            
        except Exception as e:
            logger.debug(f"Error in _extract_subcategories: {str(e)}")
        
        return subcategories
    
    def scrape_category_products(self, category_url: str, category_name: str, max_products: int = 50) -> List[Dict]:
        """
        Scrape products from a specific category page.
        
        Args:
            category_url: URL of the category page
            category_name: Name of the category
            max_products: Maximum number of products to scrape
            
        Returns:
            List[Dict]: List of product dictionaries
        """
        products = []
        
        try:
            logger.info(f"Scraping products from category: {category_name}")
            self.driver.get(category_url)
            
            # Wait for products to load
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".product, .item, [data-qa*='product']"))
            )
            
            # Find product elements
            product_selectors = [
                ".product-item",
                ".product-tile",
                "[data-qa*='product-tile']",
                ".product-card",
                ".item"
            ]
            
            product_elements = []
            for selector in product_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        product_elements = elements
                        logger.info(f"Found {len(elements)} products with selector: {selector}")
                        break
                except:
                    continue
            
            if not product_elements:
                logger.warning(f"No products found for category: {category_name}")
                return products
            
            # Extract product information
            for i, product_element in enumerate(product_elements[:max_products]):
                try:
                    product_data = self._extract_product_data(product_element, category_name)
                    if product_data:
                        products.append(product_data)
                        self.products_scraped += 1
                        
                except Exception as e:
                    logger.error(f"Error extracting product {i}: {str(e)}")
                    continue
            
            logger.info(f"Scraped {len(products)} products from {category_name}")
            
        except Exception as e:
            logger.error(f"Error scraping category {category_name}: {str(e)}")
        
        return products
    
    def _extract_product_data(self, product_element, category_name: str) -> Optional[Dict]:
        """
        Extract data from a single product element.
        
        Args:
            product_element: WebElement containing product information
            category_name: Name of the category this product belongs to
            
        Returns:
            Optional[Dict]: Product data dictionary or None if extraction fails
        """
        try:
            # Extract product name
            name_selectors = [
                ".product-name",
                ".product-title", 
                "h3",
                "h2",
                "[data-qa*='product-name']",
                ".title"
            ]
            
            product_name = None
            for selector in name_selectors:
                try:
                    name_element = product_element.find_element(By.CSS_SELECTOR, selector)
                    product_name = name_element.get_attribute("textContent").strip()
                    if product_name:
                        break
                except:
                    continue
            
            if not product_name:
                return None
            
            # Extract price
            price_selectors = [
                ".price",
                ".product-price",
                "[data-qa*='price']",
                ".current-price",
                ".price-current"
            ]
            
            price_text = None
            for selector in price_selectors:
                try:
                    price_element = product_element.find_element(By.CSS_SELECTOR, selector)
                    price_text = price_element.get_attribute("textContent").strip()
                    if price_text:
                        break
                except:
                    continue
            
            # Parse price
            price = self._parse_price(price_text) if price_text else None
            
            # Extract product URL
            product_url = None
            try:
                link_element = product_element.find_element(By.TAG_NAME, "a")
                product_url = link_element.get_attribute("href")
            except:
                pass
            
            # Extract image URL
            image_url = None
            try:
                img_element = product_element.find_element(By.TAG_NAME, "img")
                image_url = img_element.get_attribute("src") or img_element.get_attribute("data-src")
            except:
                pass
            
            return {
                'name': product_name,
                'price': price,
                'price_text': price_text,
                'category': category_name,
                'url': product_url,
                'image_url': image_url,
                'scraped_at': time.time()
            }
            
        except Exception as e:
            logger.error(f"Error extracting product data: {str(e)}")
            return None
    
    def _parse_price(self, price_text: str) -> Optional[Decimal]:
        """
        Parse price from text string.
        
        Args:
            price_text: Raw price text from website
            
        Returns:
            Optional[Decimal]: Parsed price or None if parsing fails
        """
        if not price_text:
            return None
        
        try:
            # Remove currency symbols and extra whitespace
            clean_price = price_text.replace('£', '').replace('$', '').replace(',', '').strip()
            
            # Extract numeric part
            import re
            price_match = re.search(r'(\d+\.?\d*)', clean_price)
            if price_match:
                return Decimal(price_match.group(1))
            
        except (InvalidOperation, ValueError) as e:
            logger.debug(f"Could not parse price '{price_text}': {str(e)}")
        
        return None
    
    def save_to_database(self, categories: List[Dict], products: List[Dict]) -> None:
        """
        Save scraped data to database.
        
        Args:
            categories: List of category dictionaries
            products: List of product dictionaries
        """
        try:
            logger.info("Saving scraped data to database...")
            
            # Save categories
            for category_data in categories:
                category, created = AsdaCategory.objects.get_or_create(
                    name=category_data['name'],
                    defaults={
                        'url': category_data.get('url'),
                        'level': category_data.get('level', 1),
                        'is_active': True
                    }
                )
                
                if created:
                    logger.info(f"Created new category: {category.name}")
                
                # Save subcategories
                for subcat_data in category_data.get('subcategories', []):
                    subcategory, sub_created = AsdaCategory.objects.get_or_create(
                        name=subcat_data['name'],
                        defaults={
                            'url': subcat_data.get('url'),
                            'level': subcat_data.get('level', 2),
                            'parent': category,
                            'is_active': True
                        }
                    )
                    
                    if sub_created:
                        logger.info(f"Created new subcategory: {subcategory.name}")
            
            # Save products
            for product_data in products:
                try:
                    category = AsdaCategory.objects.filter(name=product_data['category']).first()
                    
                    product, created = AsdaProduct.objects.update_or_create(
                        name=product_data['name'],
                        category=category,
                        defaults={
                            'price': product_data.get('price'),
                            'price_text': product_data.get('price_text'),
                            'url': product_data.get('url'),
                            'image_url': product_data.get('image_url'),
                            'is_available': True
                        }
                    )
                    
                    if created:
                        logger.info(f"Created new product: {product.name}")
                    else:
                        logger.info(f"Updated product: {product.name}")
                        
                except Exception as e:
                    logger.error(f"Error saving product {product_data.get('name')}: {str(e)}")
                    continue
            
            logger.info(f"Successfully saved {len(categories)} categories and {len(products)} products")
            
        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
    
    def run_scrape(self, max_categories: int = 5, max_products_per_category: int = 20) -> Dict:
        """
        Run the complete scraping process.
        
        Args:
            max_categories: Maximum number of categories to scrape
            max_products_per_category: Maximum products per category
            
        Returns:
            Dict: Summary of scraping results
        """
        results = {
            'success': False,
            'categories_found': 0,
            'products_found': 0,
            'errors': []
        }
        
        try:
            # Setup browser
            self.setup_driver()
            
            # Navigate to Asda
            logger.info(f"Navigating to {self.base_url}")
            self.driver.get(self.base_url)
            
            # Accept cookies
            if not self.accept_cookies():
                results['errors'].append("Failed to accept cookies")
            
            # Navigate to groceries
            if not self.navigate_to_groceries():
                results['errors'].append("Failed to navigate to groceries section")
                return results
            
            # Extract categories
            categories = self.extract_categories()
            if not categories:
                results['errors'].append("No categories found")
                return results
            
            results['categories_found'] = len(categories)
            
            # Scrape products from categories
            all_products = []
            for category in categories[:max_categories]:
                if category.get('url'):
                    products = self.scrape_category_products(
                        category['url'], 
                        category['name'], 
                        max_products_per_category
                    )
                    all_products.extend(products)
            
            results['products_found'] = len(all_products)
            
            # Save to database
            self.save_to_database(categories, all_products)
            
            results['success'] = True
            logger.info(f"Scraping completed successfully. Found {len(categories)} categories and {len(all_products)} products")
            
        except Exception as e:
            error_msg = f"Scraping failed: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")
        
        return results


class Command(BaseCommand):
    """Django management command to scrape Asda grocery data."""
    
    help = 'Scrape Asda grocery products and prices'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Run browser in headless mode',
        )
        parser.add_argument(
            '--max-categories',
            type=int,
            default=5,
            help='Maximum number of categories to scrape (default: 5)',
        )
        parser.add_argument(
            '--max-products',
            type=int,
            default=20,
            help='Maximum products per category (default: 20)',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=10,
            help='Timeout for web elements (default: 10 seconds)',
        )
    
    def handle(self, *args, **options):
        """Execute the scraping command."""
        try:
            self.stdout.write(
                self.style.SUCCESS('Starting Asda grocery scraping...')
            )
            
            # Initialize scraper
            scraper = AsdaScraper(
                headless=options['headless'],
                timeout=options['timeout']
            )
            
            # Run scraping
            results = scraper.run_scrape(
                max_categories=options['max_categories'],
                max_products_per_category=options['max_products']
            )
            
            # Display results
            if results['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Scraping completed successfully!\n"
                        f"Categories found: {results['categories_found']}\n"
                        f"Products found: {results['products_found']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Scraping failed!\n"
                        f"Errors: {', '.join(results['errors'])}"
                    )
                )
                
                raise CommandError("Scraping process failed")
            
        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            raise CommandError(f"Failed to execute scraping: {str(e)}")