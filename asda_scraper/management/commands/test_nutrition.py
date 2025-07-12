"""
Improved test command for debugging nutrition extraction with timeout handling.

Save as: asda_scraper/management/commands/test_nutrition.py (replace existing)
"""

import logging
import signal
import time
from django.core.management.base import BaseCommand, CommandError
from asda_scraper.models import AsdaProduct
from asda_scraper.scrapers.webdriver_manager import WebDriverManager
from asda_scraper.scrapers.nutrition_extractor import NutritionExtractor

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")


class Command(BaseCommand):
    """
    Test nutrition extraction on a single product with timeout handling.
    """
    
    help = 'Test nutrition extraction on a single product for debugging'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--product-id',
            type=str,
            help='ASDA product ID to test'
        )
        parser.add_argument(
            '--url',
            type=str,
            help='Direct product URL to test'
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            default=False,
            help='Run browser in headless mode'
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout in seconds (default: 30)'
        )
        parser.add_argument(
            '--find-processed-food',
            action='store_true',
            help='Find a processed food product likely to have nutrition info'
        )
    
    def handle(self, *args, **options):
        """Execute the test command."""
        try:
            self.stdout.write(self.style.SUCCESS('='*70))
            self.stdout.write(self.style.SUCCESS('NUTRITION EXTRACTION TEST'))
            self.stdout.write(self.style.SUCCESS('='*70))
            
            # Get product URL
            product_url = None
            product = None
            
            if options['find_processed_food']:
                # Find a processed food product more likely to have nutrition info
                product = self._find_processed_food_product()
                if product:
                    product_url = product.product_url
                    self.stdout.write(f"Found processed food product: {product.name}")
                    self.stdout.write(f"Category: {product.category.name}")
                    self.stdout.write(f"URL: {product_url}")
                else:
                    raise CommandError("No processed food products found")
                    
            elif options['url']:
                product_url = options['url']
                self.stdout.write(f"Testing direct URL: {product_url}")
                
            elif options['product_id']:
                try:
                    product = AsdaProduct.objects.get(asda_id=options['product_id'])
                    product_url = product.product_url
                    self.stdout.write(f"Testing product: {product.name}")
                    self.stdout.write(f"Category: {product.category.name}")
                    self.stdout.write(f"URL: {product_url}")
                except AsdaProduct.DoesNotExist:
                    raise CommandError(f"Product with ID {options['product_id']} not found")
                    
            else:
                # Get a random product with a URL
                product = AsdaProduct.objects.filter(
                    product_url__isnull=False,
                    product_url__gt=''
                ).first()
                
                if not product:
                    raise CommandError("No products with URLs found in database")
                
                product_url = product.product_url
                self.stdout.write(f"Testing random product: {product.name}")
                self.stdout.write(f"Category: {product.category.name}")
                self.stdout.write(f"URL: {product_url}")
            
            if not product_url:
                raise CommandError("No product URL available")
            
            # Setup WebDriver
            self.stdout.write("\n🔧 Setting up WebDriver...")
            driver_manager = WebDriverManager(headless=options['headless'])
            driver = driver_manager.setup_driver()
            
            try:
                # Setup nutrition extractor
                self.stdout.write("🔍 Initializing nutrition extractor...")
                nutrition_extractor = NutritionExtractor(driver)
                
                # Extract nutrition data with timeout
                self.stdout.write(f"\n🚀 Starting extraction (timeout: {options['timeout']}s)...")
                
                start_time = time.time()
                nutrition_data = None
                
                try:
                    # Set up timeout using signal (Unix-like systems)
                    if hasattr(signal, 'SIGALRM'):
                        signal.signal(signal.SIGALRM, timeout_handler)
                        signal.alarm(options['timeout'])
                    
                    nutrition_data = nutrition_extractor.extract_from_url(product_url)
                    
                    if hasattr(signal, 'SIGALRM'):
                        signal.alarm(0)  # Cancel the alarm
                        
                except TimeoutError:
                    self.stdout.write(self.style.WARNING(f"⏰ Extraction timed out after {options['timeout']} seconds"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ Extraction failed: {e}"))
                
                extract_time = time.time() - start_time
                
                # Display results
                self.stdout.write(f"\n{'='*70}")
                self.stdout.write(f"⏱️  Extraction took: {extract_time:.1f} seconds")
                
                if nutrition_data:
                    self.stdout.write(self.style.SUCCESS(f"✅ SUCCESS! Found {len(nutrition_data)} nutrition values:"))
                    self.stdout.write(f"{'='*70}")
                    
                    for key, value in nutrition_data.items():
                        self.stdout.write(f"  • {key}: {value}")
                        
                    self.stdout.write(f"\n{'='*70}")
                    self.stdout.write(self.style.SUCCESS("🎉 Nutrition extraction successful!"))
                    
                    # Save to database if we have a product
                    if product:
                        try:
                            enhanced_data = {
                                'nutrition': nutrition_data,
                                'extracted_at': time.time(),
                                'extraction_method': 'test_nutrition_command',
                                'data_count': len(nutrition_data)
                            }
                            product.nutritional_info = enhanced_data
                            product.save(update_fields=['nutritional_info'])
                            self.stdout.write(self.style.SUCCESS("💾 Saved nutrition data to database!"))
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"⚠️ Could not save to database: {e}"))
                    
                else:
                    self.stdout.write(self.style.WARNING("❌ No nutrition data found"))
                    self.stdout.write(f"{'='*70}")
                    self.stdout.write("\n🔍 Troubleshooting suggestions:")
                    
                    if product and any(keyword in product.category.name.lower() 
                                     for keyword in ['fruit', 'vegetable', 'fresh', 'produce']):
                        self.stdout.write("  • This appears to be fresh produce - may not have nutrition labels")
                        self.stdout.write("  • Try testing with: --find-processed-food")
                    else:
                        self.stdout.write("  1. Check if the product page actually has nutrition information")
                        self.stdout.write("  2. Try running without --headless to see the page visually")
                        self.stdout.write("  3. Check the logs for detailed debugging information")
                        self.stdout.write("  4. ASDA may have changed their website structure")
                
            finally:
                driver.quit()
                self.stdout.write("\n🔧 WebDriver closed")
                
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise CommandError(f"Nutrition extraction test failed: {e}")
    
    def _find_processed_food_product(self):
        """
        Find a processed food product likely to have nutrition information.
        
        Returns:
            AsdaProduct: Product likely to have nutrition info
        """
        # Look for processed foods that definitely have nutrition labels
        processed_food_keywords = [
            'bread', 'pasta', 'rice', 'cereal', 'biscuit', 'chocolate',
            'crisp', 'cake', 'yogurt', 'milk', 'cheese', 'butter',
            'sauce', 'soup', 'ready meal', 'pizza', 'sandwich'
        ]
        
        # Exclude fresh produce categories
        exclude_keywords = [
            'fruit', 'vegetable', 'fresh', 'produce', 'flower',
            'plant', 'organic', 'salad', 'herb'
        ]
        
        for keyword in processed_food_keywords:
            # Look for products with the keyword in the name
            products = AsdaProduct.objects.filter(
                name__icontains=keyword,
                product_url__isnull=False,
                product_url__gt=''
            )
            
            # Filter out fresh produce categories
            for exclude in exclude_keywords:
                products = products.exclude(category__name__icontains=exclude)
            
            if products.exists():
                product = products.first()
                self.stdout.write(f"🔍 Found {keyword} product: {product.name}")
                return product
        
        # Fallback: look for any non-fresh product
        products = AsdaProduct.objects.filter(
            product_url__isnull=False,
            product_url__gt=''
        )
        
        for exclude in exclude_keywords:
            products = products.exclude(category__name__icontains=exclude)
        
        if products.exists():
            return products.first()
        
        return None