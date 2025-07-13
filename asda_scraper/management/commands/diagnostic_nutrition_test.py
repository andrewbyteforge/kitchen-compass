"""
Diagnostic nutrition test with detailed browser debugging.

File: asda_scraper/management/commands/diagnostic_nutrition_test.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from asda_scraper.models import AsdaProduct
from asda_scraper.scrapers.webdriver_manager import WebDriverManager
from asda_scraper.scrapers.nutrition_extractor import NutritionExtractor
from asda_scraper.scrapers.enhanced_popup_handler import EnhancedPopupHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Diagnostic test for nutrition extraction with detailed browser debugging.
    """
    
    help = 'Diagnostic test for nutrition extraction with detailed browser info'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--max-products',
            type=int,
            default=3,
            help='Maximum number of products to test (default: 3)'
        )
        parser.add_argument(
            '--test-url',
            type=str,
            help='Test specific product URL instead of database products'
        )
        parser.add_argument(
            '--debug-steps',
            action='store_true',
            help='Show detailed debugging steps'
        )
    
    def handle(self, *args, **options):
        """Execute the diagnostic test."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("🔍 DIAGNOSTIC NUTRITION TEST"))
            self.stdout.write("="*60)
            
            # Setup browser with debugging
            self.stdout.write("🔧 Setting up browser with debugging...")
            driver = self._setup_debug_browser()
            
            try:
                if options['test_url']:
                    self._test_specific_url(driver, options['test_url'], options['debug_steps'])
                else:
                    self._test_database_products(driver, options['max_products'], options['debug_steps'])
                    
            finally:
                self.stdout.write("🧹 Closing browser...")
                driver.quit()
                
        except Exception as e:
            logger.error(f"Diagnostic test failed: {e}")
            raise CommandError(f"Test failed: {e}")
    
    def _setup_debug_browser(self):
        """Set up browser with enhanced debugging."""
        try:
            # Use WebDriverManager but with more debugging
            driver_manager = WebDriverManager(headless=False)
            driver = driver_manager.setup_driver()
            
            # Position and size browser
            driver.set_window_position(100, 100)
            driver.set_window_size(1400, 900)
            
            # Set title for identification
            driver.execute_script("document.title = '🔍 Diagnostic Test - KitchenCompass';")
            
            # Test basic browser functionality
            self.stdout.write("🧪 Testing browser functionality...")
            
            # Test navigation to simple page first
            self.stdout.write("📡 Testing basic navigation...")
            driver.get("https://www.google.com")
            time.sleep(2)
            
            current_url = driver.current_url
            page_title = driver.title
            
            self.stdout.write(f"   ✅ Navigated to: {current_url}")
            self.stdout.write(f"   ✅ Page title: {page_title}")
            
            if "google" not in current_url.lower():
                self.stdout.write(self.style.WARNING("⚠️  Unexpected URL - may indicate network/proxy issues"))
            
            return driver
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Browser setup failed: {e}"))
            raise
    
    def _test_specific_url(self, driver, test_url, debug_steps):
        """Test a specific product URL."""
        self.stdout.write(f"\n🎯 Testing specific URL: {test_url}")
        
        # Navigate and debug
        self._navigate_with_debugging(driver, test_url, debug_steps)
        
        # Test nutrition extraction
        self._test_nutrition_extraction(driver, test_url, debug_steps)
    
    def _test_database_products(self, driver, max_products, debug_steps):
        """Test products from database."""
        self.stdout.write(f"\n📊 Testing {max_products} products from database...")
        
        # Get products
        products = AsdaProduct.objects.filter(
            product_url__isnull=False
        ).exclude(product_url='')[:max_products]
        
        total_products = len(products)
        
        if total_products == 0:
            self.stdout.write(self.style.ERROR("❌ No products with URLs found in database"))
            return
        
        self.stdout.write(f"📦 Found {total_products} products to test")
        
        # Test each product
        for i, product in enumerate(products, 1):
            self.stdout.write(f"\n🔬 [{i}/{total_products}] Testing: {product.name[:50]}")
            self.stdout.write(f"   🔗 URL: {product.product_url}")
            
            # Navigate and test
            self._navigate_with_debugging(driver, product.product_url, debug_steps)
            self._test_nutrition_extraction(driver, product.product_url, debug_steps)
            
            # Brief pause between products
            if i < total_products:
                time.sleep(2)
    
    def _navigate_with_debugging(self, driver, url, debug_steps):
        """Navigate to URL with detailed debugging."""
        try:
            self.stdout.write(f"🌐 Navigating to: {url}")
            
            # Set timeouts
            driver.set_page_load_timeout(30)
            
            start_time = time.time()
            driver.get(url)
            load_time = time.time() - start_time
            
            self.stdout.write(f"   ⏱️  Page loaded in {load_time:.2f}s")
            
            # Check what we actually got
            current_url = driver.current_url
            page_title = driver.title
            
            self.stdout.write(f"   📍 Current URL: {current_url}")
            self.stdout.write(f"   📄 Page title: {page_title}")
            
            # Check if we're on the right domain
            if "asda" not in current_url.lower():
                self.stdout.write(self.style.WARNING("⚠️  Not on ASDA domain - possible redirect or blocking"))
            
            # Check for error indicators
            error_indicators = ['404', 'error', 'not found', 'access denied', 'blocked']
            if any(indicator in page_title.lower() for indicator in error_indicators):
                self.stdout.write(self.style.ERROR("❌ Error page detected"))
            
            # Check if page is blank
            try:
                body_text = driver.find_element("tag name", "body").text.strip()
                if not body_text or len(body_text) < 50:
                    self.stdout.write(self.style.WARNING("⚠️  Page appears to be blank or minimal content"))
                    
                    # Check for loading indicators
                    loading_selectors = [
                        "[class*='loading']",
                        "[class*='spinner']",
                        "[id*='loading']",
                        ".loader"
                    ]
                    
                    for selector in loading_selectors:
                        try:
                            elements = driver.find_elements("css selector", selector)
                            if elements:
                                self.stdout.write(f"   🔄 Found loading indicator: {selector}")
                                break
                        except:
                            continue
                else:
                    self.stdout.write(f"   📝 Page content length: {len(body_text)} characters")
            except Exception as e:
                self.stdout.write(f"   ❌ Error checking page content: {e}")
            
            # Handle popups
            self.stdout.write("   🚫 Checking for popups...")
            popup_handler = EnhancedPopupHandler(driver)
            popup_results = popup_handler.handle_all_popups(max_attempts=2, timeout=10.0)
            
            if popup_results['popups_handled'] > 0:
                self.stdout.write(f"   ✅ Handled {popup_results['popups_handled']} popups")
            else:
                self.stdout.write("   ℹ️  No popups found")
            
            # Wait a moment for any dynamic content
            time.sleep(3)
            
            if debug_steps:
                self._show_detailed_page_info(driver)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Navigation failed: {e}"))
    
    def _test_nutrition_extraction(self, driver, url, debug_steps):
        """Test nutrition extraction with debugging."""
        try:
            self.stdout.write("   🔬 Testing nutrition extraction...")
            
            extractor = NutritionExtractor(driver)
            
            start_time = time.time()
            nutrition_data = extractor.extract_from_url(url)
            extraction_time = time.time() - start_time
            
            self.stdout.write(f"   ⏱️  Extraction time: {extraction_time:.2f}s")
            
            if nutrition_data:
                self.stdout.write(self.style.SUCCESS(f"   ✅ Found {len(nutrition_data)} nutrition items"))
                
                if debug_steps:
                    self.stdout.write("   📊 Nutrition data found:")
                    for key, value in list(nutrition_data.items())[:5]:
                        self.stdout.write(f"      • {key}: {value}")
                    if len(nutrition_data) > 5:
                        self.stdout.write(f"      ... and {len(nutrition_data) - 5} more")
            else:
                self.stdout.write(self.style.WARNING("   ⚠️  No nutrition data found"))
                
                if debug_steps:
                    self._debug_nutrition_failure(driver)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Nutrition extraction failed: {e}"))
    
    def _show_detailed_page_info(self, driver):
        """Show detailed page information for debugging."""
        try:
            self.stdout.write("   🔍 Detailed page info:")
            
            # Check for common ASDA elements
            asda_indicators = [
                ".asda-logo",
                "[class*='asda']",
                "nav",
                ".product-details",
                ".product-info",
                "[data-testid*='product']"
            ]
            
            found_indicators = []
            for indicator in asda_indicators:
                try:
                    elements = driver.find_elements("css selector", indicator)
                    if elements:
                        found_indicators.append(f"{indicator} ({len(elements)})")
                except:
                    continue
            
            if found_indicators:
                self.stdout.write(f"      🎯 ASDA elements found: {', '.join(found_indicators)}")
            else:
                self.stdout.write("      ⚠️  No ASDA-specific elements found")
            
            # Check for nutrition-related elements
            nutrition_selectors = [
                "[class*='nutrition']",
                "[data-testid*='nutrition']",
                "table",
                ".product-nutrition",
                "[aria-label*='nutrition']"
            ]
            
            nutrition_elements = []
            for selector in nutrition_selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    if elements:
                        nutrition_elements.append(f"{selector} ({len(elements)})")
                except:
                    continue
            
            if nutrition_elements:
                self.stdout.write(f"      🧪 Nutrition elements: {', '.join(nutrition_elements)}")
            else:
                self.stdout.write("      ⚠️  No nutrition elements found")
                
        except Exception as e:
            self.stdout.write(f"      ❌ Error getting page info: {e}")
    
    def _debug_nutrition_failure(self, driver):
        """Debug why nutrition extraction failed."""
        try:
            self.stdout.write("   🐛 Debugging nutrition extraction failure:")
            
            # Check if we're on a product page
            product_indicators = [
                ".product-details",
                ".product-info",
                "[data-testid*='product']",
                ".pdp",  # Product Detail Page
                ".product-title",
                "h1"
            ]
            
            on_product_page = False
            for indicator in product_indicators:
                try:
                    elements = driver.find_elements("css selector", indicator)
                    if elements and any(el.is_displayed() for el in elements):
                        on_product_page = True
                        break
                except:
                    continue
            
            if not on_product_page:
                self.stdout.write("      ❌ Not on a product page")
            else:
                self.stdout.write("      ✅ Appears to be on a product page")
            
            # Check page source for nutrition keywords
            try:
                page_source = driver.page_source.lower()
                nutrition_keywords = ['nutrition', 'energy', 'kcal', 'protein', 'fat', 'carb']
                found_keywords = [kw for kw in nutrition_keywords if kw in page_source]
                
                if found_keywords:
                    self.stdout.write(f"      🔍 Found nutrition keywords: {', '.join(found_keywords)}")
                else:
                    self.stdout.write("      ❌ No nutrition keywords found in page source")
            except:
                self.stdout.write("      ❌ Could not check page source")
                
        except Exception as e:
            self.stdout.write(f"      ❌ Debug failed: {e}")