"""
Management command for dual browser crawling.

File: asda_scraper/management/commands/dual_crawl.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from asda_scraper.scrapers.dual_browser_manager import run_dual_browser_crawl

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for running dual browser crawling.
    Shows both product and nutrition crawlers working simultaneously.
    """
    
    help = 'Run dual browser crawling with visible windows for monitoring'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--max-products',
            type=int,
            default=50,
            help='Maximum number of products to crawl (default: 50)'
        )
        parser.add_argument(
            '--max-nutrition',
            type=int,
            default=30,
            help='Maximum number of nutrition items to process (default: 30)'
        )
        parser.add_argument(
            '--product-delay',
            type=float,
            default=1.0,
            help='Delay between product requests in seconds (default: 1.0)'
        )
        parser.add_argument(
            '--nutrition-delay',
            type=float,
            default=2.0,
            help='Delay between nutrition requests in seconds (default: 2.0)'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category name (e.g., "Bakery")'
        )
        parser.add_argument(
            '--demo-mode',
            action='store_true',
            help='Run in demo mode with reduced numbers for testing'
        )
    
    def handle(self, *args, **options):
        """Execute the dual browser crawling command."""
        try:
            # Adjust parameters for demo mode
            if options['demo_mode']:
                options['max_products'] = 10
                options['max_nutrition'] = 10
                options['product_delay'] = 2.0
                options['nutrition_delay'] = 3.0
                self.stdout.write(
                    self.style.WARNING("🧪 Running in DEMO mode with reduced parameters")
                )
            
            # Display start information
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("🚀 DUAL BROWSER CRAWL STARTING"))
            self.stdout.write("="*60)
            self.stdout.write(f"📅 Start time: {timezone.now()}")
            self.stdout.write(f"🛒 Max products: {options['max_products']}")
            self.stdout.write(f"🔬 Max nutrition: {options['max_nutrition']}")
            self.stdout.write(f"⏱️  Product delay: {options['product_delay']}s")
            self.stdout.write(f"⏱️  Nutrition delay: {options['nutrition_delay']}s")
            
            if options['category']:
                self.stdout.write(f"📂 Category filter: {options['category']}")
            
            self.stdout.write("")
            self.stdout.write("🖥️  Two browser windows will open:")
            self.stdout.write("   🛒 Left window: Product crawler")
            self.stdout.write("   🔬 Right window: Nutrition crawler")
            self.stdout.write("")
            self.stdout.write("💡 Watch both windows to see crawling progress")
            self.stdout.write("   Press Ctrl+C to stop gracefully")
            self.stdout.write("")
            
            # Start dual crawling
            try:
                stats = run_dual_browser_crawl(
                    max_products=options['max_products'],
                    max_nutrition=options['max_nutrition'],
                    product_delay=options['product_delay'],
                    nutrition_delay=options['nutrition_delay'],
                    category_filter=options['category']
                )
                
                # Display results
                self._display_results(stats)
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\n🛑 Crawl stopped by user"))
                return
            
        except Exception as e:
            logger.error(f"Dual crawl command failed: {e}")
            raise CommandError(f"Dual crawl failed: {e}")
    
    def _display_results(self, stats):
        """
        Display crawling results in a formatted way.
        
        Args:
            stats: Dictionary containing crawl statistics
        """
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("🏁 DUAL CRAWL COMPLETED"))
        self.stdout.write("="*60)
        
        # Product crawler results
        product_stats = stats.get('products', {})
        self.stdout.write(self.style.HTTP_INFO("🛒 PRODUCT CRAWLER RESULTS:"))
        self.stdout.write(f"   Categories processed: {product_stats.get('processed', 0)}")
        self.stdout.write(f"   Products found: {product_stats.get('found', 0)}")
        self.stdout.write(f"   Errors encountered: {product_stats.get('errors', 0)}")
        
        # Calculate product success rate
        if product_stats.get('processed', 0) > 0:
            success_rate = (product_stats.get('found', 0) / product_stats.get('processed', 1)) * 100
            self.stdout.write(f"   Success rate: {success_rate:.1f}%")
        
        self.stdout.write("")
        
        # Nutrition crawler results
        nutrition_stats = stats.get('nutrition', {})
        self.stdout.write(self.style.HTTP_INFO("🔬 NUTRITION CRAWLER RESULTS:"))
        self.stdout.write(f"   Products processed: {nutrition_stats.get('processed', 0)}")
        self.stdout.write(f"   Nutrition data found: {nutrition_stats.get('found', 0)}")
        self.stdout.write(f"   Errors encountered: {nutrition_stats.get('errors', 0)}")
        
        # Calculate nutrition success rate
        if nutrition_stats.get('processed', 0) > 0:
            success_rate = (nutrition_stats.get('found', 0) / nutrition_stats.get('processed', 1)) * 100
            self.stdout.write(f"   Success rate: {success_rate:.1f}%")
        
        self.stdout.write("")
        
        # Overall statistics
        total_products = product_stats.get('found', 0)
        total_nutrition = nutrition_stats.get('found', 0)
        total_errors = product_stats.get('errors', 0) + nutrition_stats.get('errors', 0)
        
        self.stdout.write(self.style.SUCCESS("📊 OVERALL SUMMARY:"))
        self.stdout.write(f"   Total products found: {total_products}")
        self.stdout.write(f"   Total nutrition data: {total_nutrition}")
        self.stdout.write(f"   Total errors: {total_errors}")
        
        if total_products > 0:
            nutrition_coverage = (total_nutrition / total_products) * 100
            self.stdout.write(f"   Nutrition coverage: {nutrition_coverage:.1f}%")
        
        self.stdout.write("")
        self.stdout.write("✅ Dual crawl completed successfully!")
        
        # Usage tips
        self.stdout.write("")
        self.stdout.write("💡 NEXT STEPS:")
        self.stdout.write("   • Run 'python manage.py view_products' to see results")
        self.stdout.write("   • Use '--demo-mode' for quick testing")
        self.stdout.write("   • Adjust delays if you encounter rate limiting")