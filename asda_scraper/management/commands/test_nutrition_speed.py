"""
Test nutrition crawler speed with visible browser.

File: asda_scraper/management/commands/test_nutrition_speed.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from asda_scraper.models import AsdaProduct
from asda_scraper.scrapers.webdriver_manager import WebDriverManager
from asda_scraper.scrapers.nutrition_extractor import NutritionExtractor
from asda_scraper.scrapers.enhanced_popup_handler import EnhancedPopupHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Test nutrition crawler speed with visible browser window.
    """
    
    help = 'Test nutrition crawler speed with visible browser'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--max-products',
            type=int,
            default=10,
            help='Maximum number of products to test (default: 10)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='Delay between requests in seconds (default: 2.0)'
        )
        parser.add_argument(
            '--show-details',
            action='store_true',
            help='Show detailed extraction information'
        )
        parser.add_argument(
            '--test-url',
            type=str,
            help='Test specific nutrition URL'
        )
    
    def handle(self, *args, **options):
        """Execute the nutrition speed test."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("🔬 NUTRITION CRAWLER SPEED TEST"))
            self.stdout.write("="*60)
            
            if options['test_url']:
                self._test_single_url(options)
            else:
                self._test_multiple_products(options)
                
        except Exception as e:
            logger.error(f"Nutrition speed test failed: {e}")
            raise CommandError(f"Test failed: {e}")
    
    def _test_single_url(self, options):
        """Test a single nutrition URL."""
        url = options['test_url']
        
        self.stdout.write(f"🎯 Testing single URL: {url}")
        self.stdout.write("🔬 Opening browser...")
        
        # Setup browser
        driver_manager = WebDriverManager(headless=False)
        driver = driver_manager.setup_driver()
        
        try:
            # Position browser
            driver.set_window_position(100, 100)
            driver.set_window_size(1200, 800)
            driver.execute_script("document.title = '🔬 Nutrition Speed Test - KitchenCompass';")
            
            # Initialize extractor and enhanced popup handler
            extractor = NutritionExtractor(driver)
            popup_handler = EnhancedPopupHandler(driver)
            
            # Handle initial popups
            self.stdout.write("🚫 Handling privacy popups...")
            popup_results = popup_handler.handle_all_popups(max_attempts=3, timeout=15.0)
            if popup_results['popups_handled'] > 0:
                self.stdout.write(f"✅ Handled {popup_results['popups_handled']} popups in {popup_results['time_taken']:.2f}s")
            
            # Test extraction
            start_time = time.time()
            self.stdout.write(f"⏱️  Starting extraction...")
            
            nutrition_data = extractor.extract_from_url(url)
            
            end_time = time.time()
            extraction_time = end_time - start_time
            
            # Display results
            self.stdout.write(f"⏱️  Extraction time: {extraction_time:.2f} seconds")
            
            if nutrition_data:
                self.stdout.write(self.style.SUCCESS("✅ Nutrition data found:"))
                for key, value in nutrition_data.items():
                    self.stdout.write(f"   • {key}: {value}")
            else:
                self.stdout.write(self.style.ERROR("❌ No nutrition data found"))
            
        finally:
            driver.quit()
    
    def _test_multiple_products(self, options):
        """Test multiple products for speed analysis."""
        max_products = options['max_products']
        delay = options['delay']
        show_details = options['show_details']
        
        # Get products with product URLs that need nutrition data
        products = AsdaProduct.objects.filter(
            product_url__isnull=False
        ).exclude(product_url='')[:max_products]
        
        total_products = len(products)
        
        if total_products == 0:
            self.stdout.write(self.style.ERROR("❌ No products with product URLs found"))
            return
        
        self.stdout.write(f"🔬 Testing {total_products} products")
        self.stdout.write("🔬 Opening browser...")
        
        # Setup browser
        driver_manager = WebDriverManager(headless=False)
        driver = driver_manager.setup_driver()
        
        try:
            # Position browser
            driver.set_window_position(100, 100)
            driver.set_window_size(1200, 800)
            driver.execute_script("document.title = '🔬 Nutrition Speed Test - KitchenCompass';")
            
            # Initialize components
            extractor = NutritionExtractor(driver)
            popup_handler = EnhancedPopupHandler(driver)
            
            # Handle initial popups on first page
            self.stdout.write("🚫 Handling privacy popups...")
            popup_results = popup_handler.handle_all_popups(max_attempts=3, timeout=15.0)
            if popup_results['popups_handled'] > 0:
                self.stdout.write(f"✅ Handled {popup_results['popups_handled']} popups in {popup_results['time_taken']:.2f}s")
            
            # Track statistics
            stats = {
                'total_time': 0,
                'successful': 0,
                'failed': 0,
                'times': []
            }
            
            start_test = time.time()
            
            for i, product in enumerate(products, 1):
                try:
                    self.stdout.write(f"🔬 [{i}/{total_products}] Testing: {product.name[:40]}")
                    
                    # Handle popups before each extraction
                    popup_handler.handle_all_popups(max_attempts=1, timeout=3.0)
                    
                    start_time = time.time()
                    nutrition_data = extractor.extract_from_url(product.product_url)
                    end_time = time.time()
                    
                    extraction_time = end_time - start_time
                    stats['times'].append(extraction_time)
                    
                    if nutrition_data:
                        stats['successful'] += 1
                        status = self.style.SUCCESS("✅")
                        
                        if show_details:
                            self.stdout.write(f"   Nutrition found: {len(nutrition_data)} items")
                            for key, value in list(nutrition_data.items())[:3]:
                                self.stdout.write(f"     • {key}: {value}")
                    else:
                        stats['failed'] += 1
                        status = self.style.ERROR("❌")
                    
                    self.stdout.write(f"   {status} Time: {extraction_time:.2f}s")
                    
                    # Delay between requests
                    if i < total_products:
                        time.sleep(delay)
                
                except Exception as e:
                    stats['failed'] += 1
                    self.stdout.write(f"   {self.style.ERROR('❌')} Error: {e}")
                    continue
            
            end_test = time.time()
            total_test_time = end_test - start_test
            
            # Calculate statistics
            self._display_speed_stats(stats, total_test_time, total_products)
            
        finally:
            driver.quit()
    
    def _display_speed_stats(self, stats, total_time, total_products):
        """Display speed test statistics."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 SPEED TEST RESULTS"))
        self.stdout.write("="*60)
        
        # Basic stats
        self.stdout.write(f"Total products tested: {total_products}")
        self.stdout.write(f"Successful extractions: {stats['successful']}")
        self.stdout.write(f"Failed extractions: {stats['failed']}")
        self.stdout.write(f"Total test time: {total_time:.2f} seconds")
        
        # Success rate
        if total_products > 0:
            success_rate = (stats['successful'] / total_products) * 100
            self.stdout.write(f"Success rate: {success_rate:.1f}%")
        
        # Time statistics
        if stats['times']:
            avg_time = sum(stats['times']) / len(stats['times'])
            min_time = min(stats['times'])
            max_time = max(stats['times'])
            
            self.stdout.write(f"\n⏱️  TIMING ANALYSIS:")
            self.stdout.write(f"Average extraction time: {avg_time:.2f}s")
            self.stdout.write(f"Fastest extraction: {min_time:.2f}s")
            self.stdout.write(f"Slowest extraction: {max_time:.2f}s")
            
            # Performance categories
            fast_count = len([t for t in stats['times'] if t < 3.0])
            medium_count = len([t for t in stats['times'] if 3.0 <= t < 8.0])
            slow_count = len([t for t in stats['times'] if t >= 8.0])
            
            self.stdout.write(f"\n📈 PERFORMANCE BREAKDOWN:")
            self.stdout.write(f"Fast (< 3s): {fast_count} ({fast_count/len(stats['times'])*100:.1f}%)")
            self.stdout.write(f"Medium (3-8s): {medium_count} ({medium_count/len(stats['times'])*100:.1f}%)")
            self.stdout.write(f"Slow (> 8s): {slow_count} ({slow_count/len(stats['times'])*100:.1f}%)")
        
        # Recommendations
        self.stdout.write(f"\n💡 RECOMMENDATIONS:")
        
        if stats['times']:
            avg_time = sum(stats['times']) / len(stats['times'])
            
            if avg_time > 8.0:
                self.stdout.write("   • Nutrition extraction is slow - consider optimizations")
                self.stdout.write("   • Check for network issues or site changes")
                self.stdout.write("   • Consider increasing delays to avoid rate limiting")
            elif avg_time > 5.0:
                self.stdout.write("   • Moderate speed - could be optimized further")
                self.stdout.write("   • Consider caching successful results")
            else:
                self.stdout.write("   • Good extraction speed!")
                self.stdout.write("   • Current approach is working well")
        
        if stats['failed'] > stats['successful']:
            self.stdout.write("   • High failure rate - check selectors and site structure")
            self.stdout.write("   • Review error logs for common issues")
        
        self.stdout.write("\n✅ Speed test completed!")