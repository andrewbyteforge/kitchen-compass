"""
Updated nutrition crawling command using the standalone crawler.

File: asda_scraper/management/commands/crawl_nutrition.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from asda_scraper.models import CrawlSession
from asda_scraper.scrapers.standalone_nutrition_crawler import run_nutrition_crawler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for crawling nutritional information.
    Uses the standalone nutrition crawler for independence.
    """
    
    help = 'Crawl nutritional information for existing ASDA products'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--max-products',
            type=int,
            default=100,
            help='Maximum number of products to process (default: 100)'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category name (e.g., "Bakery")'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='Delay between product requests in seconds (default: 2.0)'
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            default=True,
            help='Run browser in headless mode (default: True)'
        )
        parser.add_argument(
            '--show-browser',
            action='store_true',
            help='Show browser window (disables headless mode)'
        )
        parser.add_argument(
            '--force-recrawl',
            action='store_true',
            help='Force recrawl of products that already have nutrition data'
        )
        parser.add_argument(
            '--exclude-fresh',
            action='store_true',
            default=True,
            help='Exclude fresh produce (fruits, vegetables) - default: True'
        )
        parser.add_argument(
            '--priority-categories',
            action='store_true',
            default=True,
            help='Prioritize categories likely to have nutrition info (default: True)'
        )
    
    def handle(self, *args, **options):
        """Execute the nutrition crawling command."""
        try:
            self.stdout.write(self.style.SUCCESS('='*70))
            self.stdout.write(self.style.SUCCESS('ASDA NUTRITIONAL INFORMATION CRAWLER'))
            self.stdout.write(self.style.SUCCESS('='*70))
            
            # Handle headless mode
            headless = options['headless'] and not options['show_browser']
            
            # Log settings
            self.stdout.write(f"\nSettings:")
            self.stdout.write(f"  Max products: {options['max_products']}")
            self.stdout.write(f"  Category filter: {options.get('category', 'None')}")
            self.stdout.write(f"  Delay: {options['delay']}s")
            self.stdout.write(f"  Headless: {headless}")
            self.stdout.write(f"  Exclude fresh: {options['exclude_fresh']}")
            self.stdout.write(f"  Priority categories: {options['priority_categories']}")
            self.stdout.write(f"  Force recrawl: {options['force_recrawl']}")
            self.stdout.write("")
            
            # Create a crawl session for tracking
            session = self._create_session(options)
            
            try:
                # Run the standalone nutrition crawler
                self.stdout.write("Starting nutrition crawler...")
                
                stats = run_nutrition_crawler(
                    max_products=options['max_products'],
                    category_filter=options.get('category'),
                    exclude_fresh=options['exclude_fresh'],
                    priority_categories=options['priority_categories'],
                    delay=options['delay'],
                    force_recrawl=options['force_recrawl'],
                    headless=headless
                )
                
                # Update session with results
                session.products_found = stats['products_processed']
                session.products_with_nutrition = stats['nutrition_found']
                session.nutrition_errors = stats['errors']
                session.status = 'COMPLETED'
                session.save()
                
                # Show summary
                self.stdout.write("")
                self.stdout.write(self.style.SUCCESS('='*70))
                self.stdout.write(self.style.SUCCESS('CRAWL COMPLETE'))
                self.stdout.write(self.style.SUCCESS('='*70))
                self.stdout.write(f"Products processed: {stats['products_processed']}")
                self.stdout.write(f"Nutrition found: {stats['nutrition_found']}")
                self.stdout.write(f"Errors: {stats['errors']}")
                self.stdout.write(f"Skipped: {stats['skipped']}")
                
                success_rate = 0
                if stats['products_processed'] > 0:
                    success_rate = (stats['nutrition_found'] / stats['products_processed']) * 100
                self.stdout.write(f"Success rate: {success_rate:.1f}%")
                
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("\nInterrupted by user"))
                session.status = 'CANCELLED'
                session.save()
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\nError: {e}"))
                session.status = 'FAILED'
                session.error_log = str(e)
                session.save()
                raise
                
        except Exception as e:
            logger.error(f"Nutrition crawling failed: {e}")
            raise CommandError(f"Nutrition crawling failed: {e}")
    
    def _create_session(self, options: dict) -> CrawlSession:
        """Create a crawl session for tracking."""
        try:
            # Get or create a user for the session
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.create_user(
                    username='nutrition_crawler',
                    email='nutrition@crawler.com',
                    is_staff=True
                )
            
            session = CrawlSession.objects.create(
                user=user,
                status='RUNNING',
                crawl_type='NUTRITION',
                crawl_settings={
                    'max_products': options['max_products'],
                    'category_filter': options.get('category'),
                    'delay': options['delay'],
                    'force_recrawl': options['force_recrawl'],
                    'exclude_fresh': options['exclude_fresh'],
                    'priority_categories': options['priority_categories'],
                    'nutrition_only': True
                },
                notes=f"Standalone nutrition crawling - {options['max_products']} products"
            )
            
            return session
            
        except Exception as e:
            raise CommandError(f"Failed to create session: {e}")