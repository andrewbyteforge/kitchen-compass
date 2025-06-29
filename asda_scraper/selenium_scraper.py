"""
Selenium-based ASDA Scraper

This module uses Selenium WebDriver to scrape ASDA with a visible browser
for debugging and handling JavaScript-rendered content.
"""

import logging
import time
import re
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from django.utils import timezone
from .models import AsdaCategory, AsdaProduct, CrawlSession

logger = logging.getLogger(__name__)


class SeleniumAsdaScraper:
    """
    Selenium-based ASDA scraper with visible browser for debugging.
    
    This scraper opens a Chrome browser window so you can see exactly
    what's happening during the scraping process.
    """
    
    def __init__(self, crawl_session, headless=False):
        """
        Initialize the Selenium scraper.
        
        Args:
            crawl_session: CrawlSession object to track progress
            headless: Whether to run browser in headless mode (default: False for debugging)
        """
        self.session = crawl_session
        self.base_url = "https://groceries.asda.com"
        self.driver = None
        self.headless = headless
        self.wait = None
        
        logger.info(f"Selenium ASDA Scraper initialized for session {self.session.pk}")
        self._setup_driver()
    
    def _setup_driver(self):
        """Set up Chrome WebDriver with improved Windows compatibility."""
        try:
            logger.info("Setting up Chrome WebDriver...")
            
            # Chrome options
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Essential options for web scraping
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set a realistic user agent
            chrome_options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Window size
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Try multiple approaches to setup the driver
            driver_setup_success = False
            
            # Method 1: Try automatic ChromeDriverManager
            try:
                logger.info("Attempting ChromeDriverManager auto-download...")
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                driver_setup_success = True
                logger.info("✅ ChromeDriverManager setup successful")
                
            except Exception as e:
                logger.warning(f"ChromeDriverManager failed: {str(e)}")
                
                # Method 2: Try system Chrome installation
                try:
                    logger.info("Attempting system Chrome setup...")
                    self.driver = webdriver.Chrome(options=chrome_options)
                    driver_setup_success = True
                    logger.info("✅ System Chrome setup successful")
                    
                except Exception as e2:
                    logger.warning(f"System Chrome failed: {str(e2)}")
                    
                    # Method 3: Try manual chromedriver path
                    try:
                        import os
                        possible_paths = [
                            r"C:\Program Files\Google\Chrome\Application\chromedriver.exe",
                            r"C:\Program Files (x86)\Google\Chrome\Application\chromedriver.exe",
                            r"C:\chromedriver\chromedriver.exe",
                            "./chromedriver.exe",
                            "chromedriver.exe"
                        ]
                        
                        for path in possible_paths:
                            if os.path.exists(path):
                                logger.info(f"Trying manual path: {path}")
                                service = Service(path)
                                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                                driver_setup_success = True
                                logger.info(f"✅ Manual path setup successful: {path}")
                                break
                        
                    except Exception as e3:
                        logger.error(f"Manual path setup failed: {str(e3)}")
            
            if not driver_setup_success:
                raise Exception("All WebDriver setup methods failed. Please install Chrome and ChromeDriver manually.")
            
            # Set up WebDriverWait
            self.wait = WebDriverWait(self.driver, 10)
            
            # Remove navigator.webdriver flag
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Test the driver
            self.driver.get("about:blank")
            logger.info("WebDriver test successful")
            
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            raise












    def start_crawl(self):
        """
        Start the crawling process using Selenium.
        """
        try:
            logger.info(f"Starting Selenium crawl session {self.session.pk}")
            
            # Update session status
            self.session.status = 'RUNNING'
            self.session.save()
            
            # Step 1: Discover categories (if needed)
            self.discover_categories()
            
            # Step 2: Crawl products for each active category
            self.crawl_products()
            
            # Mark session as completed
            self.session.mark_completed()
            
        except Exception as e:
            logger.error(f"Error in Selenium crawl session {self.session.pk}: {str(e)}")
            self.session.mark_failed(str(e))
        finally:
            self.cleanup()
    
    def discover_categories(self):
        """
        Create categories using ASDA's actual category structure with real codes.
        """
        try:
            logger.info("🏪 Setting up ASDA categories using real category structure")
            
            # ASDA's actual category structure with real codes
            real_asda_categories = {
                # Core Food Categories (high priority)
                'fruit-veg-flowers': {'name': 'Fruit, Veg & Flowers', 'code': '1215686352935', 'priority': 1},
                'meat-poultry-fish': {'name': 'Meat, Poultry & Fish', 'code': '1215135760597', 'priority': 1},
                'chilled-food': {'name': 'Chilled Food', 'code': '1215660378320', 'priority': 1},
                'frozen-food': {'name': 'Frozen Food', 'code': '1215338621416', 'priority': 1},
                'food-cupboard': {'name': 'Food Cupboard', 'code': '1215337189632', 'priority': 1},
                'bakery': {'name': 'Bakery', 'code': '1215686354843', 'priority': 1},
                'drinks': {'name': 'Drinks', 'code': '1215135760614', 'priority': 1},
                
                # Household & Personal Care (medium priority)
                'toiletries-beauty': {'name': 'Toiletries & Beauty', 'code': '1215135760648', 'priority': 2},
                'laundry-household': {'name': 'Laundry & Household', 'code': '1215135760665', 'priority': 2},
                'health-wellness': {'name': 'Health & Wellness', 'code': '1215686353929', 'priority': 2},
                
                # Specialty Categories (lower priority)
                'sweets-treats-snacks': {'name': 'Sweets, Treats & Snacks', 'code': '1215686356579', 'priority': 3},
                'baby-toddler-kids': {'name': 'Baby, Toddler & Kids', 'code': '1215135760631', 'priority': 3},
                'pet-food-accessories': {'name': 'Pet Food & Accessories', 'code': '1215662103573', 'priority': 3},
                'world-food': {'name': 'World Food', 'code': '1215686351451', 'priority': 3},
                'dietary-lifestyle': {'name': 'Dietary & Lifestyle', 'code': '1215686355606', 'priority': 3},
                
                # Optional Categories (can enable for comprehensive coverage)
                # 'beer-wine-spirits': {'name': 'Beer, Wine & Spirits', 'code': '1215685911554', 'priority': 4},
                # 'home-entertainment': {'name': 'Home & Entertainment', 'code': '1215135760682', 'priority': 4},
            }
            
            # Get crawl settings to determine which categories to include
            max_categories = self.session.crawl_settings.get('max_categories', 10)
            include_priority = self.session.crawl_settings.get('category_priority', 2)  # 1=core food, 2=+household, 3=+specialty
            
            categories_created = 0
            for url_code, cat_info in real_asda_categories.items():
                # Skip lower priority categories if limit reached
                if cat_info['priority'] > include_priority:
                    continue
                    
                if categories_created >= max_categories:
                    break
                    
                try:
                    # Test the category URL to make sure it's valid
                    test_url = f"https://groceries.asda.com/cat/{url_code}/{cat_info['code']}"
                    logger.info(f"🧪 Testing category: {cat_info['name']} → {test_url}")
                    
                    self.driver.get(test_url)
                    time.sleep(2)
                    
                    # Check if page loaded successfully
                    page_title = self.driver.title.lower()
                    current_url = self.driver.current_url
                    
                    if ('404' not in page_title and 
                        'error' not in page_title and 
                        'not found' not in page_title and
                        url_code in current_url):
                        
                        # Valid category - create/update in database
                        category, created = AsdaCategory.objects.get_or_create(
                            url_code=cat_info['code'],  # Use the numeric code as the unique identifier
                            defaults={
                                'name': cat_info['name'],
                                'is_active': True
                            }
                        )
                        
                        # Update name if it changed
                        if category.name != cat_info['name']:
                            category.name = cat_info['name']
                            category.save()
                        
                        if created:
                            logger.info(f"✅ Created category: {category.name}")
                        else:
                            logger.info(f"📝 Updated category: {category.name}")
                        
                        categories_created += 1
                        
                    else:
                        logger.warning(f"❌ Invalid category URL: {cat_info['name']}")
                        
                except Exception as e:
                    logger.error(f"❌ Error testing category {cat_info['name']}: {str(e)}")
                    continue
            
            # Deactivate old/promotional categories
            promotional_codes = ['rollback', 'summer', 'events-inspiration']
            for promo in promotional_codes:
                AsdaCategory.objects.filter(url_code__icontains=promo).update(is_active=False)
                logger.info(f"🚫 Deactivated promotional category: {promo}")
            
            # Log final results
            active_categories = AsdaCategory.objects.filter(is_active=True).count()
            logger.info(f"🏁 Category setup complete. Active categories: {active_categories}")
            
            return active_categories > 0
            
        except Exception as e:
            logger.error(f"❌ Critical error in category discovery: {str(e)}")
            return False














    def _create_default_categories(self):
        """Create default categories if navigation scraping fails."""
        default_categories = [
            {'name': 'Fruit, Veg & Flowers', 'url_code': 'fruit-vegetables'},
            {'name': 'Meat & Poultry', 'url_code': 'meat-poultry'},
            {'name': 'Fresh Food & Dairy', 'url_code': 'fresh-food-dairy'},
            {'name': 'Food Cupboard', 'url_code': 'food-cupboard'},
            {'name': 'Frozen', 'url_code': 'frozen'},
        ]
        
        for cat_data in default_categories:
            category, created = AsdaCategory.objects.get_or_create(
                url_code=cat_data['url_code'],
                defaults={
                    'name': cat_data['name'],
                    'is_active': True
                }
            )
            if created:
                logger.info(f"Created default category: {category.name}")
    
    def crawl_products(self):
        """
        Crawl products for all active categories using Selenium.
        """
        try:
            active_categories = AsdaCategory.objects.filter(is_active=True)
            total_categories = active_categories.count()
            
            logger.info(f"Crawling products for {total_categories} categories")
            
            for i, category in enumerate(active_categories, 1):
                try:
                    logger.info(f"Crawling category {i}/{total_categories}: {category.name}")
                    
                    # Update session progress
                    self.session.categories_crawled = i
                    self.session.save()
                    
                    # Crawl products for this category
                    products_found = self.crawl_category_products(category)
                    
                    # Update category last crawled time
                    category.last_crawled = timezone.now()
                    category.save()
                    
                    logger.info(f"Found {products_found} products in {category.name}")
                    
                    # Add delay between categories
                    delay = self.session.crawl_settings.get('delay_between_requests', 2.0)
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"Error crawling category {category.name}: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"Error crawling products: {str(e)}")
            raise
    
    def crawl_category_products(self, category):
        """
        Crawl products for a specific category using the correct ASDA URL format.
        """
        try:
            # Map category codes to URL slugs for proper URL construction
            category_url_map = {
                '1215686352935': 'fruit-veg-flowers',
                '1215135760597': 'meat-poultry-fish', 
                '1215660378320': 'chilled-food',
                '1215338621416': 'frozen-food',
                '1215337189632': 'food-cupboard',
                '1215686354843': 'bakery',
                '1215135760614': 'drinks',
                '1215135760648': 'toiletries-beauty',
                '1215135760665': 'laundry-household',
                '1215686353929': 'health-wellness',
                '1215686356579': 'sweets-treats-snacks',
                '1215135760631': 'baby-toddler-kids',
                '1215662103573': 'pet-food-accessories',
                '1215686351451': 'world-food',
                '1215686355606': 'dietary-lifestyle',
            }
            
            # Get the URL slug for this category
            url_slug = category_url_map.get(category.url_code)
            if not url_slug:
                logger.warning(f"⚠️ No URL slug found for category {category.name} ({category.url_code})")
                return 0
            
            # Construct proper ASDA category URL
            category_url = f"https://groceries.asda.com/cat/{url_slug}/{category.url_code}"
            
            logger.info(f"🛒 Crawling category: {category.name}")
            logger.info(f"🔗 URL: {category_url}")
            
            # Navigate to category page
            self.driver.get(category_url)
            time.sleep(3)
            
            # Handle popups
            self._handle_popups()
            
            # Rest of your existing crawling logic...
            # (continue with the existing product extraction code)
            
            return self._extract_products_from_current_page(category)
            
        except Exception as e:
            logger.error(f"❌ Error crawling category {category.name}: {str(e)}")
            return 0

















    def _find_product_containers(self, soup):
        """Find product containers using multiple selectors."""
        selectors = [
            'div.co-product',
            'div[class*="co-product"]',
            'div[class*="product-tile"]',
            'div[class*="product-item"]',
            'article[class*="product"]',
            '[data-testid*="product"]'
        ]
        
        for selector in selectors:
            containers = soup.select(selector)
            if containers:
                logger.info(f"Found {len(containers)} products using selector: {selector}")
                return containers
        
        logger.warning("No product containers found with any selector")
        return []
    
    def extract_product_data(self, container, category):
        """Extract product data from container."""
        try:
            # Extract product name and URL
            title_link = container.select_one('a.co-product__anchor, a[href*="/product/"]')
            if not title_link:
                return None
            
            name = title_link.get_text(strip=True)
            product_url = urljoin(self.base_url, title_link.get('href', ''))
            
            # Extract price
            price_element = container.select_one('strong.co-product__price, .price strong')
            if not price_element:
                return None
            
            price_text = price_element.get_text(strip=True)
            price_match = re.search(r'£(\d+\.?\d*)', price_text)
            if not price_match:
                return None
            
            price = float(price_match.group(1))
            
            # Extract ASDA ID
            asda_id_match = re.search(r'/(\d+)$', product_url)
            asda_id = asda_id_match.group(1) if asda_id_match else f"{category.url_code}_{hash(name) % 100000}"
            
            # Extract other data
            was_price = None
            was_price_element = container.select_one('span.co-product__was-price')
            if was_price_element:
                was_price_match = re.search(r'£(\d+\.?\d*)', was_price_element.get_text())
                if was_price_match:
                    was_price = float(was_price_match.group(1))
            
            unit_element = container.select_one('span.co-product__volume')
            unit = unit_element.get_text(strip=True) if unit_element else 'each'
            
            img_element = container.select_one('img.asda-img')
            image_url = img_element.get('src', '') if img_element else ''
            
            return {
                'name': name,
                'price': price,
                'was_price': was_price,
                'unit': unit,
                'description': name,
                'image_url': image_url,
                'product_url': product_url,
                'asda_id': asda_id,
                'in_stock': True,
                'special_offer': '',
                'rating': None,
                'review_count': '',
                'price_per_unit': '',
            }
            
        except Exception as e:
            logger.error(f"Error extracting product data: {str(e)}")
            return None
    
    def save_product_data(self, product_data, scraped_from_category):
        """Save product data with improved category assignment."""
        try:
            # Determine the best category for this product
            correct_category = self._determine_product_category(product_data, scraped_from_category)
            
            # Rest of your existing save logic, but use correct_category instead of category
            product, created = AsdaProduct.objects.get_or_create(
                asda_id=product_data['asda_id'],
                defaults={
                    'name': product_data['name'],
                    'price': product_data['price'],
                    'was_price': product_data.get('was_price'),
                    'unit': product_data.get('unit', 'each'),
                    'description': product_data.get('description', ''),
                    'image_url': product_data.get('image_url', ''),
                    'product_url': product_data['product_url'],
                    'asda_id': product_data['asda_id'],
                    'category': correct_category,  # Use the determined category
                    'in_stock': product_data.get('in_stock', True),
                    'special_offer': product_data.get('special_offer', ''),
                    'rating': product_data.get('rating'),
                    'review_count': product_data.get('review_count', ''),
                    'price_per_unit': product_data.get('price_per_unit', ''),
                }
            )
            
            if created:
                self.session.products_found += 1
                logger.info(f"✅ Created: {product.name} in {correct_category.name}")
            else:
                # Update existing product, including potential category reassignment
                for field, value in product_data.items():
                    if field not in ['asda_id'] and value is not None:
                        setattr(product, field, value)
                product.category = correct_category
                product.save()
                self.session.products_updated += 1
                logger.info(f"📝 Updated: {product.name} in {correct_category.name}")
            
            self.session.save()
            
            # Update category product count
            correct_category.product_count = correct_category.products.count()
            correct_category.save()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving product {product_data.get('name', 'Unknown')}: {str(e)}")
            return False    









    def _handle_popups(self):
        """Handle cookie banners and other popups with enhanced detection."""
        try:
            logger.info("🍪 Checking for popups and cookie banners")
            
            # Wait a moment for popups to appear
            time.sleep(2)
            
            # Enhanced popup selectors
            popup_selectors = [
                # Cookie banners
                "button[id*='accept']",
                "button[class*='accept']", 
                "button[data-testid*='accept']",
                "#accept-cookies",
                ".cookie-accept",
                "button:contains('Accept')",
                "button:contains('Accept All')",
                "button:contains('Allow All')",
                
                # Generic close buttons
                "button[aria-label*='close']",
                "button[aria-label*='Close']",
                ".modal-close",
                ".popup-close",
                "[data-testid*='close']",
                
                # ASDA specific
                ".notification-banner button",
                ".banner-close",
                ".consent-banner button"
            ]
            
            popups_handled = 0
            
            for selector in popup_selectors:
                try:
                    if ':contains(' in selector:
                        # Convert to XPath for text content
                        text = selector.split("'")[1]
                        xpath = f"//button[contains(text(), '{text}')]"
                        elements = self.driver.find_elements(By.XPATH, xpath)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            try:
                                # Try regular click first
                                element.click()
                                logger.info(f"✅ Clicked popup with selector: {selector}")
                                popups_handled += 1
                                time.sleep(1)
                                break
                            except:
                                try:
                                    # Try JavaScript click as fallback
                                    self.driver.execute_script("arguments[0].click();", element)
                                    logger.info(f"✅ JS clicked popup with selector: {selector}")
                                    popups_handled += 1
                                    time.sleep(1)
                                    break
                                except:
                                    continue
                    
                    if popups_handled >= 3:  # Don't handle too many popups
                        break
                        
                except Exception as e:
                    logger.debug(f"Popup selector {selector} failed: {str(e)}")
                    continue
            
            if popups_handled > 0:
                logger.info(f"🎯 Successfully handled {popups_handled} popups")
            else:
                logger.info("ℹ️ No popups found to handle")
                
        except Exception as e:
            logger.warning(f"⚠️ Error handling popups: {str(e)}")


    def _filter_valid_categories(self, discovered_categories):
            """
            Filter out promotional banners and navigation elements that aren't real product categories.
            
            Args:
                discovered_categories: List of category dictionaries
                
            Returns:
                List of filtered category dictionaries
            """
            # Known promotional/navigation elements to exclude
            invalid_categories = {
                'rollback', 'summer', 'offers', 'deals', 'sale', 'clearance',
                'new', 'trending', 'popular', 'featured', 'seasonal', 'winter',
                'spring', 'autumn', 'fall', 'christmas', 'easter', 'halloween',
                'back-to-school', 'mothers-day', 'fathers-day', 'valentines'
            }
            
            # Known valid ASDA product categories
            valid_categories = {
                'fresh-food-dairy', 'meat-poultry', 'fruit-vegetables', 
                'food-cupboard', 'frozen', 'bakery', 'drinks', 'alcohol',
                'health-beauty', 'household', 'baby-toddler', 'pet-care',
                'clothing', 'home-garden', 'electronics', 'toys-games',
                'sports-leisure', 'books-music-games'
            }
            
            filtered_categories = []
            
            for category in discovered_categories:
                url_code = category['url_code'].lower()
                name = category['name'].lower()
                
                # Skip if clearly promotional
                if any(invalid in url_code for invalid in invalid_categories):
                    logger.info(f"🚫 Skipping promotional category: {category['name']}")
                    continue
                    
                # Skip if clearly promotional by name
                if any(invalid in name for invalid in invalid_categories):
                    logger.info(f"🚫 Skipping promotional category: {category['name']}")
                    continue
                    
                # Prefer known valid categories
                if any(valid in url_code for valid in valid_categories):
                    logger.info(f"✅ Valid product category: {category['name']}")
                    filtered_categories.append(category)
                    continue
                    
                # For unknown categories, do a quick validation
                if len(url_code) > 3 and '-' in url_code:  # Looks like a proper category code
                    logger.info(f"🤔 Unknown category, will validate: {category['name']}")
                    filtered_categories.append(category)
                else:
                    logger.info(f"🚫 Skipping suspicious category: {category['name']}")
            
            logger.info(f"📊 Filtered {len(discovered_categories)} → {len(filtered_categories)} valid categories")
            return filtered_categories
    

    def _determine_product_category(self, product_data, scraped_from_category):
            """
            Determine the correct category for a product based on its name and characteristics.
            Automatically discovers and creates new categories when needed.
            
            Args:
                product_data: Dictionary of product information
                scraped_from_category: The category page it was scraped from
                
            Returns:
                AsdaCategory object - the most appropriate category
            """
            product_name = product_data['name'].lower()
            
            # Map keywords to the actual numeric category codes in your database
            category_keywords = {
                # Core Food Categories (Priority 1)
                '1215686352935': [  # Fruit, Veg & Flowers
                    'banana', 'apple', 'orange', 'grape', 'tomato', 'cucumber', 
                    'lettuce', 'carrot', 'onion', 'potato', 'avocado', 'melon',
                    'berry', 'cherry', 'plum', 'spinach', 'broccoli', 'pepper',
                    'fruit', 'vegetable', 'veg', 'salad', 'herbs', 'flowers'
                ],
                '1215135760597': [  # Meat, Poultry & Fish
                    'chicken', 'beef', 'pork', 'lamb', 'turkey', 'bacon', 'ham',
                    'sausage', 'mince', 'steak', 'chop', 'breast', 'thigh', 'wing',
                    'fish', 'salmon', 'cod', 'tuna', 'meat', 'poultry'
                ],
                '1215660378320': [  # Chilled Food
                    'milk', 'cheese', 'yogurt', 'butter', 'cream', 'egg', 'dairy',
                    'fresh', 'organic', 'free range', 'chilled', 'refrigerated'
                ],
                '1215338621416': [  # Frozen Food
                    'frozen', 'ice cream', 'ice', 'freezer', 'sorbet', 'gelato',
                    'frozen meal', 'frozen pizza', 'frozen vegetables'
                ],
                '1215337189632': [  # Food Cupboard
                    'pasta', 'rice', 'flour', 'sugar', 'oil', 'vinegar', 'sauce',
                    'tin', 'can', 'jar', 'packet', 'cereal', 'biscuit', 'crisp',
                    'canned', 'dried', 'instant', 'cooking', 'seasoning', 'spice'
                ],
                '1215686354843': [  # Bakery
                    'bread', 'roll', 'bun', 'cake', 'pastry', 'croissant', 'bagel',
                    'bakery', 'baked', 'loaf', 'sandwich', 'toast', 'muffin', 'scone'
                ],
                '1215135760614': [  # Drinks
                    'water', 'juice', 'soft drink', 'tea', 'coffee', 'squash',
                    'drink', 'beverage', 'cola', 'lemonade', 'smoothie', 'energy drink'
                ],
                
                # Household & Personal Care (Priority 2)
                '1215135760665': [  # Laundry & Household
                    'cleaning', 'cleaner', 'toilet', 'kitchen', 'bathroom', 'washing up',
                    'detergent', 'bleach', 'disinfectant', 'sponge', 'cloth', 'foil',
                    'cling film', 'bag', 'bin', 'tissue', 'paper', 'household', 'laundry'
                ],
                '1215135760648': [  # Toiletries & Beauty
                    'toothpaste', 'shampoo', 'soap', 'deodorant', 'moisturiser',
                    'makeup', 'skincare', 'hair', 'dental', 'beauty', 'cosmetic',
                    'toiletries', 'personal care', 'hygiene'
                ],
                '1215686353929': [  # Health & Wellness
                    'vitamin', 'supplement', 'medicine', 'health', 'wellness',
                    'pharmacy', 'medical', 'first aid', 'pain relief'
                ],
                
                # Specialty Categories (Priority 3) - Now we'll create these if needed
                '1215686356579': [  # Sweets, Treats & Snacks
                    'chocolate', 'sweet', 'candy', 'snack', 'crisp', 'nuts',
                    'treat', 'biscuit', 'cookie', 'confectionery'
                ],
                '1215135760631': [  # Baby, Toddler & Kids
                    'baby', 'toddler', 'child', 'kids', 'infant', 'nappy',
                    'formula', 'baby food', 'children'
                ],
                '1215662103573': [  # Pet Food & Accessories
                    'pet', 'dog', 'cat', 'animal', 'pet food', 'dog food', 'cat food'
                ],
                '1215686351451': [  # World Food
                    'world', 'international', 'ethnic', 'asian', 'indian',
                    'chinese', 'mexican', 'italian', 'foreign'
                ],
                '1215686355606': [  # Dietary & Lifestyle
                    'organic', 'gluten free', 'vegan', 'vegetarian', 'healthy',
                    'diet', 'low fat', 'sugar free', 'free from'
                ]
            }
            
            # Map category codes to their names for creating missing categories
            category_names = {
                '1215686352935': 'Fruit, Veg & Flowers',
                '1215135760597': 'Meat, Poultry & Fish',
                '1215660378320': 'Chilled Food',
                '1215338621416': 'Frozen Food',
                '1215337189632': 'Food Cupboard',
                '1215686354843': 'Bakery',
                '1215135760614': 'Drinks',
                '1215135760665': 'Laundry & Household',
                '1215135760648': 'Toiletries & Beauty',
                '1215686353929': 'Health & Wellness',
                '1215686356579': 'Sweets, Treats & Snacks',
                '1215135760631': 'Baby, Toddler & Kids',
                '1215662103573': 'Pet Food & Accessories',
                '1215686351451': 'World Food',
                '1215686355606': 'Dietary & Lifestyle'
            }
            
            # Get or refresh active categories cache
            self._refresh_category_cache()
            
            # Check each category for keyword matches
            best_category_code = None
            best_score = 0
            
            for category_code, keywords in category_keywords.items():
                score = sum(1 for keyword in keywords if keyword in product_name)
                if score > best_score:
                    best_score = score
                    best_category_code = category_code
            
            # If we found a keyword match, get or create that category
            if best_category_code and best_score > 0:
                category = self._get_or_create_category(best_category_code, category_names)
                if category:
                    logger.info(f"📝 Reassigned '{product_data['name'][:30]}...' to '{category.name}' (score: {best_score})")
                    return category
            
            # Fallback to the category it was scraped from
            logger.debug(f"📍 Keeping '{product_data['name'][:30]}...' in '{scraped_from_category.name}' (no match)")
            return scraped_from_category

    def _get_or_create_category(self, category_code, category_names):
        """
        Get an existing category or create a new one if it doesn't exist.
        
        Args:
            category_code: The numeric category code
            category_names: Dictionary mapping codes to names
            
        Returns:
            AsdaCategory object or None if creation fails
        """
        try:
            # First check if it exists in our cache
            if hasattr(self, '_active_categories_cache') and category_code in self._active_categories_cache:
                return self._active_categories_cache[category_code]
            
            # Try to get from database
            try:
                category = AsdaCategory.objects.get(url_code=category_code, is_active=True)
                # Add to cache
                if not hasattr(self, '_active_categories_cache'):
                    self._active_categories_cache = {}
                self._active_categories_cache[category_code] = category
                return category
            except AsdaCategory.DoesNotExist:
                pass
            
            # Category doesn't exist, so create it
            if category_code in category_names:
                category_name = category_names[category_code]
                
                # Check if we should create this category (validate it first)
                if self._should_create_category(category_code, category_name):
                    category = self._create_new_category(category_code, category_name)
                    if category:
                        # Add to cache
                        if not hasattr(self, '_active_categories_cache'):
                            self._active_categories_cache = {}
                        self._active_categories_cache[category_code] = category
                        logger.info(f"🆕 Created new category: {category.name} ({category_code})")
                        return category
                else:
                    logger.debug(f"🚫 Skipped creating category: {category_name} (validation failed)")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting/creating category {category_code}: {str(e)}")
            return None

    def _should_create_category(self, category_code, category_name):
        """
        Determine if we should create a new category by testing if it's valid on ASDA.
        
        Args:
            category_code: The numeric category code
            category_name: The category name
            
        Returns:
            bool: True if category should be created
        """
        try:
            # Get the URL slug mapping for testing
            category_url_map = {
                '1215686352935': 'fruit-veg-flowers',
                '1215135760597': 'meat-poultry-fish',
                '1215660378320': 'chilled-food',
                '1215338621416': 'frozen-food',
                '1215337189632': 'food-cupboard',
                '1215686354843': 'bakery',
                '1215135760614': 'drinks',
                '1215135760665': 'laundry-household',
                '1215135760648': 'toiletries-beauty',
                '1215686353929': 'health-wellness',
                '1215686356579': 'sweets-treats-snacks',
                '1215135760631': 'baby-toddler-kids',
                '1215662103573': 'pet-food-accessories',
                '1215686351451': 'world-food',
                '1215686355606': 'dietary-lifestyle',
            }
            
            url_slug = category_url_map.get(category_code)
            if not url_slug:
                logger.debug(f"🤔 No URL slug found for category {category_code}, skipping validation")
                return False
            
            # Test the category URL to make sure it's valid
            test_url = f"https://groceries.asda.com/cat/{url_slug}/{category_code}"
            logger.debug(f"🧪 Validating new category: {category_name} → {test_url}")
            
            current_url = self.driver.current_url
            self.driver.get(test_url)
            time.sleep(2)
            
            # Check if page loaded successfully
            page_title = self.driver.title.lower()
            loaded_url = self.driver.current_url
            
            # Navigate back to the original page
            self.driver.get(current_url)
            time.sleep(1)
            
            is_valid = ('404' not in page_title and 
                    'error' not in page_title and 
                    'not found' not in page_title and
                    url_slug in loaded_url)
            
            if is_valid:
                logger.info(f"✅ Category validation successful: {category_name}")
            else:
                logger.warning(f"❌ Category validation failed: {category_name}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"❌ Error validating category {category_name}: {str(e)}")
            return False

    def _create_new_category(self, category_code, category_name):
        """
        Create a new category in the database.
        
        Args:
            category_code: The numeric category code
            category_name: The category name
            
        Returns:
            AsdaCategory object or None if creation fails
        """
        try:
            category, created = AsdaCategory.objects.get_or_create(
                url_code=category_code,
                defaults={
                    'name': category_name,
                    'is_active': True
                }
            )
            
            if created:
                logger.info(f"🎉 Successfully created new category: {category.name}")
                
                # Update session statistics
                if hasattr(self.session, 'categories_discovered'):
                    self.session.categories_discovered += 1
                else:
                    self.session.categories_discovered = 1
                self.session.save()
                
            return category
            
        except Exception as e:
            logger.error(f"❌ Error creating category {category_name}: {str(e)}")
            return None

    def _refresh_category_cache(self):
        """Refresh the category cache from the database."""
        try:
            self._active_categories_cache = {
                cat.url_code: cat for cat in AsdaCategory.objects.filter(is_active=True)
            }
            logger.debug(f"🔄 Refreshed category cache: {len(self._active_categories_cache)} categories")
        except Exception as e:
            logger.error(f"❌ Error refreshing category cache: {str(e)}")
            if not hasattr(self, '_active_categories_cache'):
                self._active_categories_cache = {}

    def _clear_category_cache(self):
        """Clear the category cache when categories change."""
        if hasattr(self, '_active_categories_cache'):
            delattr(self, '_active_categories_cache')
            logger.debug("🗑️ Cleared category cache")

    def _extract_products_from_current_page(self, category):
        """
        Extract products from the current page using Selenium and BeautifulSoup.
        
        This method handles the actual product extraction from ASDA category pages,
        including pagination and different product layouts.
        
        Args:
            category: AsdaCategory object representing the category being scraped
            
        Returns:
            int: Number of products found and saved
        """
        try:
            products_found = 0
            max_products = self.session.crawl_settings.get('max_products_per_category', 100)
            
            logger.info(f"🔍 Extracting products from {category.name} page")
            
            # Wait for products to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, 
                        'div.co-product, div[class*="co-product"], div[class*="product-tile"]'
                    ))
                )
            except TimeoutException:
                logger.warning(f"⏰ Timeout waiting for products to load on {category.name}")
                return 0
            
            # Extract products from all pages (with pagination)
            page_num = 1
            max_pages = 5  # Limit to prevent infinite loops
            
            while page_num <= max_pages and products_found < max_products:
                logger.info(f"📄 Processing page {page_num} of {category.name}")
                
                # Get page source and parse with BeautifulSoup
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Find product containers
                product_containers = self._find_product_containers(soup)
                
                if not product_containers:
                    logger.warning(f"❌ No product containers found on page {page_num} of {category.name}")
                    break
                
                logger.info(f"🛍️ Found {len(product_containers)} product containers on page {page_num}")
                
                # Extract data from each product
                page_products = 0
                for container in product_containers:
                    if products_found >= max_products:
                        logger.info(f"🔢 Reached maximum products limit ({max_products}) for {category.name}")
                        break
                    
                    try:
                        product_data = self.extract_product_data(container, category)
                        
                        if product_data:
                            # Save product to database
                            saved = self.save_product_data(product_data, category)
                            if saved:
                                products_found += 1
                                page_products += 1
                                
                                # Update session statistics
                                self.session.products_found = products_found
                                self.session.save()
                                
                                logger.debug(f"✅ Saved product: {product_data['name'][:50]}...")
                        
                    except Exception as e:
                        logger.error(f"❌ Error extracting product data: {str(e)}")
                        continue
                
                logger.info(f"📊 Page {page_num}: {page_products} products extracted")
                
                # Try to navigate to next page
                if page_products > 0 and products_found < max_products:
                    if not self._navigate_to_next_page():
                        logger.info(f"🔚 No more pages available for {category.name}")
                        break
                    page_num += 1
                    time.sleep(2)  # Add delay between pages
                else:
                    break
            
            logger.info(f"🎯 Total products extracted from {category.name}: {products_found}")
            return products_found
            
        except Exception as e:
            logger.error(f"❌ Error extracting products from {category.name}: {str(e)}")
            return 0

    def _navigate_to_next_page(self):
        """
        Navigate to the next page of products if pagination exists.
        
        Returns:
            bool: True if successfully navigated to next page, False otherwise
        """
        try:
            # Look for "Next" or pagination buttons
            next_selectors = [
                'a[aria-label="Next"]',
                'a.pagination-next',
                'a[class*="next"]',
                'button[aria-label="Next"]',
                'button.pagination-next',
                'button[class*="next"]'
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    # Check if button is enabled
                    if next_button.is_enabled() and next_button.is_displayed():
                        # Scroll to button and click
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(1)
                        next_button.click()
                        
                        # Wait for page to load
                        time.sleep(3)
                        logger.debug(f"✅ Navigated to next page using selector: {selector}")
                        return True
                        
                except (NoSuchElementException, Exception):
                    continue
            
            # Alternative: Look for page numbers and click the next one
            try:
                page_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[class*="pagination"], a[class*="page"]')
                
                for link in page_links:
                    link_text = link.text.strip()
                    if link_text.isdigit() and link.is_enabled():
                        # Found a numeric page link, try to click it
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                        time.sleep(1)
                        link.click()
                        time.sleep(3)
                        logger.debug(f"✅ Navigated to page: {link_text}")
                        return True
                        
            except Exception as e:
                logger.debug(f"Could not find numeric pagination: {str(e)}")
            
            logger.debug("🔚 No next page button found or enabled")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error navigating to next page: {str(e)}")
            return False

    def _scroll_to_load_products(self):
        """
        Scroll down the page to trigger lazy loading of products.
        
        Many modern websites load products dynamically as you scroll.
        """
        try:
            # Get initial height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            scroll_attempts = 0
            max_scrolls = 5
            
            while scroll_attempts < max_scrolls:
                # Scroll down to bottom
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # Wait for new content to load
                time.sleep(2)
                
                # Calculate new scroll height and compare to last height
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                
                if new_height == last_height:
                    break  # No more content loaded
                    
                last_height = new_height
                scroll_attempts += 1
                
            logger.debug(f"📜 Completed {scroll_attempts} scroll attempts to load products")
            
        except Exception as e:
            logger.error(f"❌ Error during scroll loading: {str(e)}")

    def _wait_for_page_load(self, timeout=10):
        """
        Wait for page to fully load including JavaScript.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        try:
            # Wait for document ready state
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Additional wait for AJAX requests (if any)
            time.sleep(2)
            
            logger.debug("✅ Page fully loaded")
            
        except TimeoutException:
            logger.warning(f"⏰ Page load timeout after {timeout} seconds")
        except Exception as e:
            logger.error(f"❌ Error waiting for page load: {str(e)}")







    """
Optional updates for your Selenium scraper to better integrate with the enhanced link mapping system.

Add these methods to your existing SeleniumAsdaScraper class if you want better integration.
These are OPTIONAL - your current scraper works fine as-is.
"""

    # ADD THESE METHODS TO YOUR EXISTING SeleniumAsdaScraper CLASS:

    def extract_page_links(self, current_url):
        """
        Extract all links from the current page for link mapping integration.
        
        This method can be called to contribute discovered links to the
        enhanced link mapping system.
        
        Returns:
            List of discovered links with metadata
        """
        try:
            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            links = []
            for i, anchor in enumerate(soup.find_all('a', href=True)):
                try:
                    # Resolve relative URLs
                    absolute_url = urljoin(current_url, anchor['href'])
                    
                    # Skip invalid URLs
                    if not self._is_valid_asda_url(absolute_url):
                        continue
                    
                    # Extract link information
                    link_info = {
                        'url': absolute_url,
                        'anchor_text': anchor.get_text(strip=True)[:500],
                        'position': i + 1,
                        'css_classes': ' '.join(anchor.get('class', [])),
                        'id': anchor.get('id', ''),
                        'title': anchor.get('title', ''),
                        'link_type': self._classify_link_type(anchor, absolute_url),
                    }
                    
                    links.append(link_info)
                    
                except Exception as e:
                    logger.warning(f"Error processing link: {e}")
                    continue
            
            logger.debug(f"Extracted {len(links)} links from {current_url}")
            return links
            
        except Exception as e:
            logger.error(f"Error extracting links from page: {e}")
            return []

    def _is_valid_asda_url(self, url):
        """Check if URL is a valid ASDA URL for crawling."""
        if not url or not isinstance(url, str):
            return False
        
        # Must be ASDA domain
        if not url.startswith('https://groceries.asda.com'):
            return False
        
        # Skip certain file types and paths
        skip_patterns = [
            '/api/', '/ajax/', '.js', '.css', '.png', '.jpg', '.jpeg', 
            '.gif', '.pdf', '.zip', '/checkout', '/account', '/login'
        ]
        
        return not any(pattern in url.lower() for pattern in skip_patterns)

    def _classify_link_type(self, anchor, url):
        """Classify the type of link based on context and URL."""
        # Check CSS classes and IDs for hints
        classes = ' '.join(anchor.get('class', [])).lower()
        anchor_id = anchor.get('id', '').lower()
        text = anchor.get_text(strip=True).lower()
        
        # Navigation links
        if any(keyword in classes for keyword in ['nav', 'menu', 'breadcrumb']):
            if 'breadcrumb' in classes:
                return 'breadcrumb'
            return 'navigation'
        
        # Pagination
        if any(keyword in classes or keyword in text for keyword in ['page', 'next', 'prev', 'more']):
            return 'pagination'
        
        # Product links
        if '/product/' in url or 'product' in classes:
            return 'product'
        
        # Category links
        if '/dept/' in url or '/cat/' in url or 'category' in classes:
            return 'category'
        
        return 'other'

    def update_url_map_if_exists(self, url, page_metadata):
        """
        Update URL map with Selenium-extracted data if the URL exists in the mapping system.
        
        This allows Selenium to contribute additional data to URLs discovered
        by the enhanced crawler.
        """
        try:
            from .models import UrlMap
            
            # Try to find this URL in the mapping system
            url_hash = UrlMap.generate_url_hash(url)
            
            try:
                url_map = UrlMap.objects.get(
                    url_hash=url_hash,
                    crawl_session=self.session
                )
                
                # Update with Selenium-specific data
                url_map.page_title = page_metadata.get('title', '')[:500]
                url_map.meta_description = page_metadata.get('description', '')[:1000]
                
                # Add any additional metadata from Selenium
                if 'products_found' in page_metadata:
                    url_map.products_found = page_metadata['products_found']
                
                if 'categories_found' in page_metadata:
                    url_map.categories_found = page_metadata['categories_found']
                
                url_map.save(update_fields=[
                    'page_title', 'meta_description', 'products_found', 'categories_found'
                ])
                
                logger.debug(f"Updated URL map for {url}")
                
            except UrlMap.DoesNotExist:
                # URL not in mapping system, that's fine
                logger.debug(f"URL not in mapping system: {url}")
                
        except ImportError:
            # Enhanced mapping models not available
            pass
        except Exception as e:
            logger.warning(f"Error updating URL map: {e}")

    def extract_page_metadata(self):
        """Extract metadata from the current page."""
        try:
            metadata = {
                'title': self.driver.title,
                'current_url': self.driver.current_url,
                'page_source_length': len(self.driver.page_source),
            }
            
            # Try to extract meta description
            try:
                meta_desc = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    'meta[name="description"]'
                )
                metadata['description'] = meta_desc.get_attribute('content')
            except:
                metadata['description'] = ''
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Error extracting page metadata: {e}")
            return {}

    # MODIFY YOUR EXISTING crawl_category_products METHOD TO INCLUDE LINK EXTRACTION:

    def crawl_category_products_enhanced(self, category):
        """
        Enhanced version of crawl_category_products that also extracts links.
        
        Replace your existing method with this if you want link extraction.
        """
        try:
            # Your existing category crawling logic here...
            # (keep all your existing URL construction and navigation code)
            
            # After navigating to the category page, extract metadata and links
            current_url = self.driver.current_url
            page_metadata = self.extract_page_metadata()
            
            # Extract links for the enhanced mapping system
            discovered_links = self.extract_page_links(current_url)
            
            # Update URL map if it exists
            self.update_url_map_if_exists(current_url, page_metadata)
            
            # Your existing product extraction logic...
            # (keep all your existing product scraping code)
            
            # Log discovered links
            if discovered_links:
                logger.info(f"Discovered {len(discovered_links)} links on {category.name} page")
            
            # Continue with your existing logic...
            return self._extract_products_from_current_page(category)
            
        except Exception as e:
            logger.error(f"Error in enhanced category crawling: {e}")
            return 0

    # ADD THIS UTILITY METHOD FOR INTEGRATION:

    def can_integrate_with_enhanced_crawler(self):
        """Check if enhanced crawler models are available for integration."""
        try:
            from .models import UrlMap, LinkRelationship
            return True
        except ImportError:
            return False

    def log_integration_status(self):
        """Log whether integration with enhanced crawler is available."""
        if self.can_integrate_with_enhanced_crawler():
            logger.info("✅ Enhanced crawler integration available")
        else:
            logger.info("ℹ️ Enhanced crawler integration not available - running standalone")

    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver cleanup complete")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")    


    """
    USAGE INSTRUCTIONS:

    1. These updates are OPTIONAL - your current Selenium scraper works fine as-is.

    2. If you want better integration with the enhanced link mapping system:
    - Add the above methods to your SeleniumAsdaScraper class
    - Optionally replace crawl_category_products with crawl_category_products_enhanced

    3. The integration provides:
    - Link discovery that feeds into the mapping system
    - Metadata extraction from JavaScript-rendered pages
    - Cross-system data sharing

    4. Benefits of integration:
    - Selenium can handle JavaScript-heavy pages that requests/BeautifulSoup can't
    - Enhanced crawler gets more comprehensive link discovery
    - Better overall website mapping

    5. To use:
    - Run enhanced crawler first to map basic structure
    - Use Selenium scraper for complex pages and product extraction
    - Both contribute to the same crawl session and URL mapping

    6. If you prefer to keep it simple:
    - Your current Selenium scraper works perfectly fine as-is
    - No updates are required for functionality
    """
