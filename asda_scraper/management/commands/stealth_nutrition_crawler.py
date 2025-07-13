"""
Production stealth nutrition crawler command.

File: asda_scraper/management/commands/stealth_nutrition_crawler.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from asda_scraper.models import AsdaProduct
from asda_scraper.scrapers.stealth_webdriver_manager import StealthWebDriverManager
from asda_scraper.scrapers.nutrition_extractor import NutritionExtractor
from asda_scraper.scrapers.enhanced_popup_handler import EnhancedPopupHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Production nutrition crawler using stealth measures to avoid bot detection.
    """
    
    help = 'Crawl nutrition data using stealth measures to avoid bot detection'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--max-products',
            type=int,
            default=50,
            help='Maximum number of products to process (default: 50)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=8.0,
            help='Delay between requests in seconds (default: 8.0)'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category name (e.g. "Bakery")'
        )
        parser.add_argument(
            '--prioritize-processed',
            action='store_true',
            default=True,
            help='Prioritize processed foods over fresh produce (default: True)'
        )
        parser.add_argument(
            '--continue-on-error',
            action='store_true',
            default=True,
            help='Continue processing if individual products fail (default: True)'
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Run in headless mode (not recommended - may be detected)'
        )
    
    def handle(self, *args, **options):
        """Execute the stealth nutrition crawler."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("🥷 STEALTH NUTRITION CRAWLER"))
            self.stdout.write("="*60)
            
            max_products = options['max_products']
            delay = options['delay']
            category_filter = options['category']
            prioritize_processed = options['prioritize_processed']
            continue_on_error = options['continue_on_error']
            headless = options['headless']
            
            # Display settings
            self.stdout.write(f"📦 Max products: {max_products}")
            self.stdout.write(f"⏱️  Delay between requests: {delay}s")
            self.stdout.write(f"🔍 Category filter: {category_filter or 'None'}")
            self.stdout.write(f"🥫 Prioritize processed foods: {prioritize_processed}")
            self.stdout.write(f"🤖 Headless mode: {headless}")
            self.stdout.write("")
            
            if headless:
                self.stdout.write(self.style.WARNING("⚠️  Headless mode may be detected by ASDA"))
            
            # Get products to process
            products = self._get_products_to_crawl(
                max_products, category_filter, prioritize_processed
            )
            
            if not products:
                self.stdout.write(self.style.ERROR("❌ No products found to process"))
                return
            
            self.stdout.write(f"🔬 Found {len(products)} products to process")
            
            # Setup stealth crawler
            self.stdout.write("🥷 Setting up stealth browser...")
            stealth_manager = StealthWebDriverManager(headless=headless)
            driver = stealth_manager.setup_stealth_driver()
            
            try:
                # Initialize components
                extractor = NutritionExtractor(driver)
                popup_handler = EnhancedPopupHandler(driver)
                
                # Initial navigation to handle cookies
                self.stdout.write("🌐 Initial navigation for cookie handling...")
                if stealth_manager.navigate_like_human(driver, "https://groceries.asda.com/"):
                    popup_results = popup_handler.handle_all_popups(max_attempts=3, timeout=15.0)
                    if popup_results['popups_handled'] > 0:
                        self.stdout.write(f"✅ Handled {popup_results['popups_handled']} initial popups")
                
                # Process products
                stats = self._process_products(
                    products, driver, stealth_manager, extractor, popup_handler, 
                    delay, continue_on_error
                )
                
                # Display final results
                self._display_final_results(stats)
                
            finally:
                self.stdout.write("🧹 Closing browser...")
                driver.quit()
                
        except Exception as e:
            logger.error(f"Stealth nutrition crawler failed: {e}")
            raise CommandError(f"Crawler failed: {e}")
    
    def _get_products_to_crawl(self, max_products, category_filter, prioritize_processed):
        """Get products that need nutrition data."""
        # Base query: products with URLs that need nutrition data
        products = AsdaProduct.objects.filter(
            product_url__isnull=False
        ).filter(
            Q(nutritional_info__isnull=True) | Q(nutritional_info={})
        ).exclude(product_url='')
        
        # Apply category filter
        if category_filter:
            products = products.filter(category__name__icontains=category_filter)
        
        # Prioritize processed foods if requested
        if prioritize_processed:
            # Categories likely to have nutrition data
            priority_terms = [
                'bakery', 'bread', 'cereal', 'biscuit', 'cake', 'pasta', 'rice',
                'meat', 'fish', 'chicken', 'beef', 'dairy', 'milk', 'cheese',
                'snack', 'crisp', 'chocolate', 'sauce', 'soup', 'frozen', 'tin'
            ]
            
            # Try to get priority products first
            priority_products = products.filter(
                category__name__iregex='|'.join(priority_terms)
            )[:max_products]
            
            if priority_products.exists():
                return list(priority_products)
            
            # If no priority products, exclude fresh produce
            exclude_terms = ['fruit', 'veg', 'flower', 'fresh', 'produce']
            for term in exclude_terms:
                products = products.exclude(category__name__icontains=term)
        
        return list(products[:max_products])
    
    def _process_products(self, products, driver, stealth_manager, extractor, 
                         popup_handler, delay, continue_on_error):
        """Process products for nutrition extraction."""
        stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'no_nutrition': 0,
            'errors': [],
            'start_time': time.time()
        }
        
        total_products = len(products)
        
        for i, product in enumerate(products, 1):
            try:
                self.stdout.write(f"\n🔬 [{i}/{total_products}] Processing: {product.name[:50]}")
                self.stdout.write(f"   🔗 URL: {product.product_url}")
                
                # Navigate with stealth
                if stealth_manager.navigate_like_human(driver, product.product_url):
                    # Check for access issues
                    if not stealth_manager.handle_access_denied(driver):
                        self.stdout.write("   ❌ Access denied - bot detected")
                        stats['failed'] += 1
                        continue
                    
                    # Handle popups
                    popup_handler.handle_all_popups(max_attempts=1, timeout=5.0)
                    
                    # Extract nutrition
                    start_time = time.time()
                    nutrition_data = extractor.extract_from_url(product.product_url)
                    extraction_time = time.time() - start_time
                    
                    if nutrition_data:
                        # Save nutrition data
                        self._save_nutrition_data(product, nutrition_data)
                        stats['successful'] += 1
                        self.stdout.write(f"   ✅ Found {len(nutrition_data)} nutrients ({extraction_time:.2f}s)")
                    else:
                        stats['no_nutrition'] += 1
                        self.stdout.write(f"   ⚠️  No nutrition data found ({extraction_time:.2f}s)")
                        
                else:
                    self.stdout.write("   ❌ Navigation failed")
                    stats['failed'] += 1
                
                stats['processed'] += 1
                
                # Delay between products (human-like)
                if i < total_products:
                    self.stdout.write(f"   ⏳ Waiting {delay}s...")
                    time.sleep(delay)
                
            except Exception as e:
                error_msg = f"Error processing {product.name}: {e}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)
                stats['failed'] += 1
                
                if continue_on_error:
                    self.stdout.write(f"   ❌ Error: {e} (continuing...)")
                    continue
                else:
                    raise
        
        return stats
    
    def _save_nutrition_data(self, product, nutrition_data):
        """Save nutrition data to product."""
        try:
            enhanced_data = {
                'nutrition': nutrition_data,
                'extracted_at': timezone.now().isoformat(),
                'extraction_method': 'stealth_nutrition_crawler',
                'data_count': len(nutrition_data)
            }
            
            product.nutritional_info = enhanced_data
            product.save(update_fields=['nutritional_info', 'updated_at'])
            
        except Exception as e:
            logger.error(f"Error saving nutrition data for {product.name}: {e}")
            raise
    
    def _display_final_results(self, stats):
        """Display final crawling results."""
        end_time = time.time()
        total_time = end_time - stats['start_time']
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🏁 STEALTH NUTRITION CRAWL COMPLETE"))
        self.stdout.write("="*60)
        
        # Basic stats
        self.stdout.write(f"📊 Products processed: {stats['processed']}")
        self.stdout.write(f"✅ Successful extractions: {stats['successful']}")
        self.stdout.write(f"⚠️  No nutrition found: {stats['no_nutrition']}")
        self.stdout.write(f"❌ Failed/errors: {stats['failed']}")
        self.stdout.write(f"⏱️  Total time: {total_time:.1f} seconds")
        
        # Success rate
        if stats['processed'] > 0:
            success_rate = (stats['successful'] / stats['processed']) * 100
            self.stdout.write(f"📈 Success rate: {success_rate:.1f}%")
            
            avg_time_per_product = total_time / stats['processed']
            self.stdout.write(f"⚡ Average time per product: {avg_time_per_product:.1f}s")
        
        # Recommendations
        self.stdout.write(f"\n💡 RECOMMENDATIONS:")
        
        if stats['successful'] > 0:
            self.stdout.write("   ✅ Stealth approach is working!")
        
        if stats['failed'] > stats['successful']:
            self.stdout.write("   ⚠️  High failure rate - consider:")
            self.stdout.write("     • Increasing delays between requests")
            self.stdout.write("     • Using UK VPN if outside UK")
            self.stdout.write("     • Running during off-peak hours")
        
        if stats['no_nutrition'] > stats['successful']:
            self.stdout.write("   ℹ️  Many products lack nutrition data - this is normal for:")
            self.stdout.write("     • Fresh produce (fruits, vegetables)")
            self.stdout.write("     • Basic ingredients")
            self.stdout.write("     • Consider focusing on processed foods")
        
        # Error summary
        if stats['errors']:
            self.stdout.write(f"\n❌ ERRORS ({len(stats['errors'])}):")
            for error in stats['errors'][:5]:  # Show first 5 errors
                self.stdout.write(f"   • {error}")
            if len(stats['errors']) > 5:
                self.stdout.write(f"   ... and {len(stats['errors']) - 5} more")
        
        self.stdout.write("\n✅ Crawl completed successfully!")