import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)


"""
ASDA Scraper Module

This module contains the main scraping logic for ASDA products.
It handles category discovery, product extraction, and data storage.
"""

import logging
import time
from django.utils import timezone
from .models import AsdaCategory, AsdaProduct, CrawlSession

logger = logging.getLogger(__name__)


class AsdaScraper:
    """
    Main scraper class for ASDA product data.
    
    This class handles the scraping of ASDA product information,
    including category discovery and product data extraction.
    
    Attributes:
        session: Associated CrawlSession object
        base_url: ASDA base URL
        headers: HTTP headers for requests
    """
    
    def __init__(self, crawl_session):
        """
        Initialize the scraper with a crawl session.
        
        Args:
            crawl_session: CrawlSession object to track progress
        """
        self.session = crawl_session
        self.base_url = "https://groceries.asda.com"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        logger.info(f"ASDA Scraper initialized for session {self.session.pk}")
    
    def start_crawl(self):
        """
        Start the crawling process.
        
        This method orchestrates the entire scraping process,
        from category discovery to product extraction.
        """
        try:
            logger.info(f"Starting ASDA crawl session {self.session.pk}")
            
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
            logger.error(f"Error in crawl session {self.session.pk}: {str(e)}")
            self.session.mark_failed(str(e))


    def debug_category_page(self, category):
        """
        Debug method to test category page access and HTML structure.
        
        Args:
            category: AsdaCategory object to test
        """
        try:
            # Construct ASDA category URL
            category_url = f"https://groceries.asda.com/cat/{category.url_code}"
            
            logger.info(f"DEBUG: Testing URL: {category_url}")
            
            # Make request with headers
            response = requests.get(category_url, headers=self.headers, timeout=30)
            
            logger.info(f"DEBUG: Response status: {response.status_code}")
            logger.info(f"DEBUG: Response URL: {response.url}")
            logger.info(f"DEBUG: Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"DEBUG: Non-200 status code: {response.status_code}")
                return
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Log page title
            title = soup.find('title')
            logger.info(f"DEBUG: Page title: {title.get_text() if title else 'No title found'}")
            
            # Look for different possible product containers
            selectors_to_try = [
                'div.co-product',
                'div[class*="product"]',
                'article[class*="product"]',
                'div[data-testid*="product"]',
                '.product-tile',
                '.product-item',
                '.product-card'
            ]
            
            for selector in selectors_to_try:
                elements = soup.select(selector)
                logger.info(f"DEBUG: Selector '{selector}' found {len(elements)} elements")
                
                if elements:
                    # Log the first element structure
                    first_element = elements[0]
                    logger.info(f"DEBUG: First element classes: {first_element.get('class')}")
                    logger.info(f"DEBUG: First element structure (first 500 chars):")
                    logger.info(str(first_element)[:500])
                    break
            
            # Look for pagination or load more indicators
            pagination_selectors = [
                'nav[aria-label*="pagination"]',
                'button[aria-label*="Next"]',
                'a[aria-label*="Next"]',
                'button:contains("Load more")',
                'button:contains("Show more")'
            ]
            
            for selector in pagination_selectors:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"DEBUG: Pagination found with selector '{selector}': {len(elements)} elements")
            
            # Save HTML to file for inspection (first 10000 chars)
            debug_file = f"debug_category_{category.url_code}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(str(soup)[:10000])
            logger.info(f"DEBUG: Saved HTML sample to {debug_file}")
            
            return soup
            
        except Exception as e:
            logger.error(f"DEBUG: Error testing category page: {str(e)}")
            return None
    
    def discover_categories(self):
        """
        Discover ASDA product categories from the main page.
        
        This method scrapes the ASDA groceries homepage to find
        all available product categories and their URL codes.
        """
        try:
            logger.info("Discovering ASDA categories")
            
            # For now, we'll create some basic categories manually
            # In a full implementation, this would scrape the ASDA site
            default_categories = [
                {
                    'name': 'Fruit, Veg & Flowers',
                    'url_code': '1215686352935',
                    'parent': None
                },
                {
                    'name': 'Meat & Poultry',
                    'url_code': '1215686352936',
                    'parent': None
                },
                {
                    'name': 'Fresh Food & Dairy',
                    'url_code': '1215686352937',
                    'parent': None
                },
                {
                    'name': 'Food Cupboard',
                    'url_code': '1215686352938',
                    'parent': None
                },
                {
                    'name': 'Frozen',
                    'url_code': '1215686352939',
                    'parent': None
                },
            ]
            
            for cat_data in default_categories:
                category, created = AsdaCategory.objects.get_or_create(
                    url_code=cat_data['url_code'],
                    defaults={
                        'name': cat_data['name'],
                        'parent_category': cat_data['parent'],
                        'is_active': True
                    }
                )
                if created:
                    logger.info(f"Created category: {category.name}")
            
        except Exception as e:
            logger.error(f"Error discovering categories: {str(e)}")
            raise
    
    def crawl_products(self):
        """
        Crawl products for all active categories.
        
        This method iterates through active categories and
        scrapes product data for each one.
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
                    delay = self.session.crawl_settings.get('delay_between_requests', 1.0)
                    time.sleep(delay)
                    
                except Exception as e:
                    logger.error(f"Error crawling category {category.name}: {str(e)}")
                    continue
            
        except Exception as e:
            logger.error(f"Error crawling products: {str(e)}")
            raise
    
    import requests
    from bs4 import BeautifulSoup
    import re
    from urllib.parse import urljoin, urlparse
    import time

    def crawl_category_products(self, category):
        """
        Crawl products for a specific category with enhanced debugging.
        
        Args:
            category: AsdaCategory object to crawl
            
        Returns:
            int: Number of products found
        """
        try:
            logger.info(f"Starting crawl for category: {category.name} (URL code: {category.url_code})")
            
            # First, run debug to understand the page structure
            soup = self.debug_category_page(category)
            if not soup:
                logger.error(f"Failed to load category page for {category.name}")
                return 0
            
            # Try different product container selectors
            product_containers = []
            selectors = [
                'div.co-product',
                'div[class*="co-product"]',
                'div[class*="product"]',
                'article[class*="product"]',
                '[data-testid*="product"]'
            ]
            
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    logger.info(f"Found {len(containers)} products using selector: {selector}")
                    product_containers = containers
                    break
            
            if not product_containers:
                logger.warning(f"No product containers found for {category.name}")
                logger.info("Available CSS classes on page:")
                
                # Log some class names to help identify the right selector
                all_divs = soup.find_all('div', class_=True)[:20]  # First 20 divs
                for div in all_divs:
                    classes = div.get('class', [])
                    if classes:
                        logger.info(f"  Found div with classes: {' '.join(classes)}")
                
                return 0
            
            logger.info(f"Processing {len(product_containers)} products")
            
            products_found = 0
            for i, container in enumerate(product_containers):
                try:
                    logger.info(f"Processing product {i+1}/{len(product_containers)}")
                    
                    # Log container structure for first few products
                    if i < 3:
                        logger.info(f"Product {i+1} container classes: {container.get('class')}")
                    
                    product_data = self.extract_asda_product_data(container, category)
                    
                    if product_data:
                        logger.info(f"Extracted product: {product_data['name']} - £{product_data['price']}")
                        success = self.save_product_data(product_data, category)
                        if success:
                            products_found += 1
                    else:
                        logger.warning(f"Failed to extract data from product container {i+1}")
                        # Log the container HTML for debugging (first 300 chars)
                        logger.info(f"Container HTML: {str(container)[:300]}")
                    
                except Exception as e:
                    logger.error(f"Error processing product {i+1}: {str(e)}")
                    continue
            
            logger.info(f"Successfully processed {products_found} products for {category.name}")
            return products_found
            
        except Exception as e:
            logger.error(f"Error in crawl_category_products for {category.name}: {str(e)}")
            return 0







    def extract_asda_product_data(self, container, category):
        """
        Extract product data from ASDA HTML container with enhanced debugging.
        
        Args:
            container: BeautifulSoup element containing product data
            category: AsdaCategory object
            
        Returns:
            dict: Product data or None if extraction fails
        """
        try:
            # Extract product name and URL - try multiple selectors
            title_selectors = [
                'a.co-product__anchor',
                'a[class*="product"]',
                'h3 a',
                'h2 a',
                '.product-title a',
                'a[href*="/product/"]'
            ]
            
            title_link = None
            for selector in title_selectors:
                title_link = container.select_one(selector)
                if title_link:
                    logger.debug(f"Found product link using selector: {selector}")
                    break
            
            if not title_link:
                logger.warning("No product title link found")
                logger.info(f"Container HTML (first 500 chars): {str(container)[:500]}")
                return None
            
            name = title_link.get_text(strip=True)
            product_url = urljoin(self.base_url, title_link.get('href', ''))
            
            logger.debug(f"Product name: {name}")
            logger.debug(f"Product URL: {product_url}")
            
            if not name:
                logger.warning("Product name is empty")
                return None
            
            # Extract ASDA ID from URL
            asda_id = ''
            if product_url:
                id_match = re.search(r'/(\d+)$', product_url)
                if id_match:
                    asda_id = id_match.group(1)
            
            if not asda_id:
                asda_id = f"{category.url_code}_{hash(name) % 100000}"
            
            logger.debug(f"ASDA ID: {asda_id}")
            
            # Extract current price - try multiple selectors
            price_selectors = [
                'strong.co-product__price',
                '.price strong',
                '.current-price',
                '[class*="price"]:not([class*="was"])'
            ]
            
            price_element = None
            for selector in price_selectors:
                price_element = container.select_one(selector)
                if price_element:
                    logger.debug(f"Found price using selector: {selector}")
                    break
            
            if not price_element:
                logger.warning("No price element found")
                return None
            
            price_text = price_element.get_text(strip=True)
            logger.debug(f"Price text: {price_text}")
            
            # Extract numeric price
            price_match = re.search(r'£(\d+\.?\d*)', price_text)
            if not price_match:
                logger.warning(f"Could not extract price from: {price_text}")
                return None
            
            price = float(price_match.group(1))
            logger.debug(f"Extracted price: £{price}")
            
            # Extract other fields with fallbacks
            was_price = None
            was_price_element = container.select_one('span.co-product__was-price')
            if was_price_element:
                was_price_text = was_price_element.get_text(strip=True)
                was_price_match = re.search(r'£(\d+\.?\d*)', was_price_text)
                if was_price_match:
                    was_price = float(was_price_match.group(1))
                    logger.debug(f"Found was price: £{was_price}")
            
            # Extract volume/unit
            unit = 'each'  # default
            volume_element = container.select_one('span.co-product__volume')
            if volume_element:
                unit = volume_element.get_text(strip=True)
                logger.debug(f"Found unit: {unit}")
            
            # Extract image URL
            image_url = ''
            img_element = container.select_one('img.asda-img')
            if img_element and img_element.get('src'):
                image_url = img_element['src']
                logger.debug(f"Found image: {image_url}")
            
            # Return the extracted data
            product_data = {
                'name': name,
                'price': price,
                'was_price': was_price,
                'unit': unit,
                'description': name,  # Use name as description for now
                'image_url': image_url,
                'product_url': product_url,
                'asda_id': asda_id,
                'in_stock': True,  # Default to in stock
                'special_offer': '',
                'rating': None,
                'review_count': '',
                'price_per_unit': '',
            }
            
            logger.info(f"Successfully extracted product data for: {name}")
            return product_data
            
        except Exception as e:
            logger.error(f"Error extracting product data: {str(e)}")
            logger.info(f"Container HTML: {str(container)[:500]}")
            return None










    def check_for_next_page(self, soup):
        """
        Check if there are more pages to crawl.
        
        Args:
            soup: BeautifulSoup object of current page
            
        Returns:
            bool: True if more pages exist
        """
        try:
            # Look for pagination controls
            next_button = soup.find('a', {'aria-label': 'Next page'})
            if next_button and not next_button.get('disabled'):
                return True
            
            # Look for "Load more" or "Show more" buttons
            load_more = soup.find('button', string=re.compile(r'load more|show more', re.I))
            if load_more and not load_more.get('disabled'):
                return True
            
            # Check for numbered pagination
            pagination = soup.find('nav', {'aria-label': 'pagination'})
            if pagination:
                current_page = pagination.find('button', {'aria-current': 'page'})
                if current_page:
                    next_sibling = current_page.find_next_sibling('button')
                    if next_sibling and not next_sibling.get('disabled'):
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking for next page: {str(e)}")
            return False