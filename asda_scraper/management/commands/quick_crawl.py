"""
Quick crawl management commands for easy automation.

Save as: asda_scraper/management/commands/quick_crawl.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Quick crawl command that runs products first, then nutrition.
    """
    
    help = 'Run quick crawl: products first (fast), then nutrition separately'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--products-only',
            action='store_true',
            help='Only crawl products (fast mode)'
        )
        parser.add_argument(
            '--nutrition-only',
            action='store_true',
            help='Only crawl nutrition data'
        )
        parser.add_argument(
            '--max-products',
            type=int,
            default=200,
            help='Maximum products for nutrition crawl (default: 200)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay between nutrition requests (default: 1.0s)'
        )
    
    def handle(self, *args, **options):
        """Execute the quick crawl."""
        try:
            self.stdout.write(self.style.SUCCESS('='*70))
            self.stdout.write(self.style.SUCCESS('QUICK CRAWL - PRODUCTS + NUTRITION'))
            self.stdout.write(self.style.SUCCESS('='*70))
            
            if options['nutrition_only']:
                # Only run nutrition crawler
                self._run_nutrition_crawler(options)
                
            elif options['products_only']:
                # Only run product crawler
                self._run_product_crawler()
                
            else:
                # Run both in sequence
                self.stdout.write("🚀 STEP 1: Fast product crawling...")
                self._run_product_crawler()
                
                self.stdout.write("\n🔬 STEP 2: Nutrition data extraction...")
                self._run_nutrition_crawler(options)
            
            self.stdout.write(self.style.SUCCESS("\n✅ Quick crawl completed!"))
            
        except Exception as e:
            logger.error(f"Quick crawl failed: {e}")
            raise CommandError(f"Quick crawl failed: {e}")
    
    def _run_product_crawler(self):
        """Run the fast product crawler via dashboard."""
        self.stdout.write("⚡ Starting fast product crawler...")
        self.stdout.write("   Use the dashboard to start product crawling")
        self.stdout.write("   Or run: python manage.py run_asda_crawl --crawl-type PRODUCT")
        
    def _run_nutrition_crawler(self, options):
        """Run the nutrition crawler."""
        try:
            self.stdout.write("🔬 Starting nutrition extraction...")
            
            # Build nutrition command arguments
            nutrition_args = [
                f'--max-products={options["max_products"]}',
                f'--delay={options["delay"]}',
                '--headless',
                '--exclude-fresh',
                '--priority-categories'
            ]
            
            self.stdout.write(f"   Command: crawl_nutrition {' '.join(nutrition_args)}")
            
            # Call the nutrition crawler
            call_command('crawl_nutrition', *nutrition_args)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Nutrition crawler failed: {e}"))
            raise