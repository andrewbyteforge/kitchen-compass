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
        
        Args:
            product_data: Dictionary of product information
            scraped_from_category: The category page it was scraped from
            
        Returns:
            AsdaCategory object - the most appropriate category
        """
        product_name = product_data['name'].lower()
        
        # Category mapping based on product names/keywords
        category_keywords = {
            'fruit-vegetables': [
                'banana', 'apple', 'orange', 'grape', 'tomato', 'cucumber', 
                'lettuce', 'carrot', 'onion', 'potato', 'avocado', 'melon',
                'berry', 'cherry', 'plum', 'spinach', 'broccoli', 'pepper'
            ],
            'meat-poultry': [
                'chicken', 'beef', 'pork', 'lamb', 'turkey', 'bacon', 'ham',
                'sausage', 'mince', 'steak', 'chop', 'breast', 'thigh', 'wing'
            ],
            'fresh-food-dairy': [
                'milk', 'cheese', 'yogurt', 'butter', 'cream', 'egg', 'dairy',
                'fresh', 'organic', 'free range'
            ],
            'frozen': [
                'frozen', 'ice cream', 'ice', 'freezer', 'sorbet'
            ],
            'food-cupboard': [
                'pasta', 'rice', 'flour', 'sugar', 'oil', 'vinegar', 'sauce',
                'tin', 'can', 'jar', 'packet', 'cereal', 'biscuit', 'crisp'
            ],
            'household': [
                'cleaning', 'cleaner', 'toilet', 'kitchen', 'bathroom', 'washing up',
                'detergent', 'bleach', 'disinfectant', 'sponge', 'cloth', 'foil',
                'cling film', 'bag', 'bin', 'tissue', 'paper'
            ],
            'health-beauty': [
                'toothpaste', 'shampoo', 'soap', 'deodorant', 'moisturiser',
                'makeup', 'skincare', 'hair', 'dental', 'beauty', 'cosmetic'
            ],
            'bakery': [
                'bread', 'roll', 'bun', 'cake', 'pastry', 'croissant', 'bagel'
            ],
            'drinks': [
                'water', 'juice', 'soft drink', 'tea', 'coffee', 'squash'
            ]
        }
        
        # Check each category for keyword matches
        best_category = None
        best_score = 0
        
        for category_code, keywords in category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in product_name)
            if score > best_score:
                best_score = score
                best_category = category_code
        
        # If we found a keyword match, try to get that category
        if best_category and best_score > 0:
            try:
                category = AsdaCategory.objects.get(url_code=best_category, is_active=True)
                logger.info(f"📝 Reassigned '{product_data['name']}' to '{category.name}' (keyword match)")
                return category
            except AsdaCategory.DoesNotExist:
                logger.warning(f"⚠️ Keyword category '{best_category}' not found in database")
        
        # Fallback to the category it was scraped from
        logger.info(f"📍 Keeping '{product_data['name']}' in '{scraped_from_category.name}' (no keyword match)")
        return scraped_from_category











    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver cleanup complete")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")