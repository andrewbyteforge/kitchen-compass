"""
Stealth nutrition test to avoid bot detection.

File: asda_scraper/management/commands/stealth_nutrition_test.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from asda_scraper.models import AsdaProduct
from asda_scraper.scrapers.stealth_webdriver_manager import StealthWebDriverManager
from asda_scraper.scrapers.nutrition_extractor import NutritionExtractor
from asda_scraper.scrapers.enhanced_popup_handler import EnhancedPopupHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Stealth nutrition test to avoid ASDA bot detection.
    """
    
    help = 'Test nutrition extraction with anti-bot detection measures'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--test-url',
            type=str,
            help='Test specific product URL'
        )
        parser.add_argument(
            '--max-products',
            type=int,
            default=3,
            help='Maximum number of products to test (default: 3)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=5.0,
            help='Delay between requests in seconds (default: 5.0)'
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Run in headless mode (may be detected)'
        )
    
    def handle(self, *args, **options):
        """Execute the stealth nutrition test."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("🥷 STEALTH NUTRITION TEST"))
            self.stdout.write("="*60)
            
            # Setup stealth driver
            self.stdout.write("🔧 Setting up stealth browser...")
            stealth_manager = StealthWebDriverManager(headless=options['headless'])
            driver = stealth_manager.setup_stealth_driver()
            
            try:
                if options['test_url']:
                    self._test_single_url(driver, stealth_manager, options)
                else:
                    self._test_multiple_products(driver, stealth_manager, options)
                    
            finally:
                self.stdout.write("🧹 Closing browser...")
                driver.quit()
                
        except Exception as e:
            logger.error(f"Stealth test failed: {e}")
            raise CommandError(f"Test failed: {e}")
    
    def _test_single_url(self, driver, stealth_manager, options):
        """Test a single URL with stealth measures."""
        test_url = options['test_url']
        
        self.stdout.write(f"🎯 Testing URL: {test_url}")
        
        # Navigate with stealth
        if stealth_manager.navigate_like_human(driver, test_url):
            self.stdout.write("✅ Navigation successful")
            
            # Check for access denied
            if not stealth_manager.handle_access_denied(driver):
                self.stdout.write(self.style.ERROR("❌ Access denied - bot detected"))
                return
            
            # Handle popups
            self._handle_popups_with_delay(driver)
            
            # Test nutrition extraction
            self._extract_nutrition_with_debugging(driver, test_url)
            
        else:
            self.stdout.write(self.style.ERROR("❌ Navigation failed"))
    
    def _test_multiple_products(self, driver, stealth_manager, options):
        """Test multiple products with stealth measures."""
        max_products = options['max_products']
        delay = options['delay']
        
        # Get suitable products (avoid fresh produce)
        products = self._get_suitable_products(max_products)
        
        if not products:
            self.stdout.write(self.style.ERROR("❌ No suitable products found"))
            return
        
        self.stdout.write(f"🔬 Testing {len(products)} products with {delay}s delays")
        
        for i, product in enumerate(products, 1):
            self.stdout.write(f"\n🔬 [{i}/{len(products)}] Testing: {product.name[:50]}")
            
            # Navigate with stealth
            if stealth_manager.navigate_like_human(driver, product.product_url):
                # Check for blocking
                if not stealth_manager.handle_access_denied(driver):
                    self.stdout.write("   ❌ Access denied - skipping")
                    continue
                
                # Handle popups
                self._handle_popups_with_delay(driver)
                
                # Extract nutrition
                self._extract_nutrition_with_debugging(driver, product.product_url)
                
            else:
                self.stdout.write("   ❌ Navigation failed")
            
            # Human-like delay between products
            if i < len(products):
                self.stdout.write(f"   ⏳ Waiting {delay}s before next product...")
                time.sleep(delay)
    
    def _get_suitable_products(self, max_products):
        """Get products suitable for nutrition testing."""
        # Prefer processed foods over fresh produce
        prefer_categories = [
            'bakery', 'bread', 'cereal', 'pasta', 'rice', 'meat', 'fish',
            'dairy', 'snack', 'crisp', 'chocolate', 'sauce', 'soup', 'frozen'
        ]
        
        exclude_categories = [
            'fruit', 'veg', 'flower', 'fresh', 'produce'
        ]
        
        # Try to get products from preferred categories first
        products = AsdaProduct.objects.filter(
            product_url__isnull=False
        ).exclude(product_url='')
        
        # Filter by preferred categories
        preferred_products = products.filter(
            category__name__iregex='|'.join(prefer_categories)
        )[:max_products]
        
        if preferred_products.exists():
            return list(preferred_products)
        
        # If no preferred products, exclude fresh produce
        for exclude_term in exclude_categories:
            products = products.exclude(category__name__icontains=exclude_term)
        
        return list(products[:max_products])
    
    def _handle_popups_with_delay(self, driver):
        """Handle popups with realistic delays."""
        self.stdout.write("   🚫 Handling popups...")
        
        popup_handler = EnhancedPopupHandler(driver)
        
        # Give page time to load popups
        time.sleep(2)
        
        results = popup_handler.handle_all_popups(max_attempts=3, timeout=10.0)
        
        if results['popups_handled'] > 0:
            self.stdout.write(f"   ✅ Handled {results['popups_handled']} popups")
        else:
            self.stdout.write("   ℹ️  No popups found")
        
        # Brief pause after popup handling
        time.sleep(1)
    
    def _extract_nutrition_with_debugging(self, driver, url):
        """Extract nutrition with detailed debugging."""
        self.stdout.write("   🔬 Extracting nutrition data...")
        
        try:
            # Check page state first
            page_title = driver.title
            current_url = driver.current_url
            
            self.stdout.write(f"   📄 Page title: {page_title[:50]}")
            self.stdout.write(f"   🔗 Current URL: {current_url}")
            
            # Check if we're on the right page
            if "asda" not in current_url.lower():
                self.stdout.write("   ❌ Not on ASDA domain")
                return
            
            # Check for product page indicators
            try:
                body_text = driver.find_element("tag name", "body").text
                
                if len(body_text) < 100:
                    self.stdout.write("   ⚠️  Page appears blank or minimal content")
                    self.stdout.write("   💡 This may indicate bot detection")
                    return
                
                # Look for product indicators
                product_indicators = ["nutrition", "ingredients", "product", "£"]
                found_indicators = [ind for ind in product_indicators if ind.lower() in body_text.lower()]
                
                if found_indicators:
                    self.stdout.write(f"   ✅ Product page indicators: {', '.join(found_indicators)}")
                else:
                    self.stdout.write("   ⚠️  No product page indicators found")
                
            except Exception as e:
                self.stdout.write(f"   ❌ Error checking page content: {e}")
                return
            
            # Extract nutrition
            extractor = NutritionExtractor(driver)
            
            start_time = time.time()
            nutrition_data = extractor.extract_from_url(url)
            extraction_time = time.time() - start_time
            
            self.stdout.write(f"   ⏱️  Extraction time: {extraction_time:.2f}s")
            
            if nutrition_data:
                self.stdout.write(self.style.SUCCESS(f"   ✅ Found {len(nutrition_data)} nutrition items"))
                
                # Show sample data
                for key, value in list(nutrition_data.items())[:3]:
                    self.stdout.write(f"      • {key}: {value}")
                
                if len(nutrition_data) > 3:
                    self.stdout.write(f"      ... and {len(nutrition_data) - 3} more")
                    
            else:
                self.stdout.write("   ⚠️  No nutrition data found")
                self._debug_nutrition_failure(driver)
            
        except Exception as e:
            self.stdout.write(f"   ❌ Nutrition extraction failed: {e}")
    
    def _debug_nutrition_failure(self, driver):
        """Debug why nutrition extraction failed."""
        try:
            self.stdout.write("   🐛 Debugging extraction failure...")
            
            # Check for nutrition-related elements
            nutrition_selectors = [
                "[class*='nutrition']",
                "[data-testid*='nutrition']",
                "table",
                "[aria-label*='nutrition']"
            ]
            
            found_elements = []
            for selector in nutrition_selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    if elements:
                        found_elements.append(f"{selector}({len(elements)})")
                except:
                    continue
            
            if found_elements:
                self.stdout.write(f"      🔍 Found elements: {', '.join(found_elements)}")
            else:
                self.stdout.write("      ❌ No nutrition elements found")
            
            # Check if page has dynamic content that needs time
            self.stdout.write("      ⏳ Waiting for dynamic content...")
            time.sleep(3)
            
            # Try extraction again
            extractor = NutritionExtractor(driver)
            retry_data = extractor.extract_from_url(driver.current_url)
            
            if retry_data:
                self.stdout.write(f"      ✅ Retry successful: {len(retry_data)} items found")
            else:
                self.stdout.write("      ❌ Retry failed - no nutrition data available")
                
        except Exception as e:
            self.stdout.write(f"      ❌ Debug failed: {e}")