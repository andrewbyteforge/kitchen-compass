"""
Complete Django Management Command for ASDA Scraper.

File: asda_scraper/management/commands/run_asda_crawl.py
"""

import logging
import time
from typing import Optional
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone

from asda_scraper.models import CrawlSession, AsdaCategory, AsdaProduct

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management command to run the ASDA scraper.
    """
    
    help = 'Run the ASDA product scraper with configurable settings'
    
    def __init__(self, *args, **kwargs):
        """Initialize the command with logging setup."""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--max-categories',
            type=int,
            default=10,
            help='Maximum number of categories to crawl (default: 10)'
        )
        parser.add_argument(
            '--category-priority',
            type=int,
            default=2,
            help='Maximum priority level to include (default: 2)'
        )
        parser.add_argument(
            '--max-products',
            type=int,
            default=100,
            help='Maximum products per category (default: 100)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='Delay between requests in seconds (default: 2.0)'
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            default=False,
            help='Run browser in headless mode'
        )
        parser.add_argument(
            '--crawl-type',
            choices=['PRODUCT', 'NUTRITION', 'BOTH'],
            default='PRODUCT',
            help='Type of data to crawl (default: PRODUCT)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without saving data (for testing)'
        )
        parser.add_argument(
            '--categories-only',
            action='store_true',
            help='Only discover/validate categories, skip products'
        )
        parser.add_argument(
            '--session-name',
            type=str,
            help='Optional name for the crawl session'
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Username to associate with the session'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        try:
            # Show startup banner
            self._show_startup_banner(options)
            
            # Check for existing active sessions
            self._check_active_sessions()
            
            # Get user
            user = self._get_user(options)
            if not user:
                raise CommandError("No valid user found. Create a superuser first.")
            
            # Show system status
            self._show_system_status()
            
            # Create session
            session = self._create_session(user, options)
            
            # Run scraper
            self._run_scraper(session, options)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nCrawl interrupted by user.'))
        except Exception as e:
            self.logger.error(f"Command failed: {str(e)}")
            raise CommandError(f"Command failed: {str(e)}")
    
    def _show_startup_banner(self, options: dict):
        """Show startup banner."""
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(self.style.SUCCESS('ASDA PRODUCT SCRAPER'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f"Crawl Type: {options['crawl_type']}")
        self.stdout.write(f"Mode: {'DRY RUN' if options['dry_run'] else 'LIVE'}")
        self.stdout.write(f"Browser: {'Headless' if options['headless'] else 'Visible'}")
        self.stdout.write(f"Max Categories: {options['max_categories']}")
        self.stdout.write('')
    
    def _check_active_sessions(self):
        """Check for active sessions."""
        active = CrawlSession.objects.filter(status__in=['PENDING', 'RUNNING'])
        
        if active.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  {active.count()} active sessions found. "
                    f"Use 'python manage.py crawler_status --kill-stuck' to clean up first."
                )
            )
            # Don't exit - just warn
    
    def _get_user(self, options: dict) -> Optional[User]:
        """Get user for the crawl session."""
        if options['user']:
            try:
                return User.objects.get(username=options['user'])
            except User.DoesNotExist:
                return None
        else:
            return User.objects.filter(is_superuser=True).first()
    
    def _show_system_status(self):
        """Show current system status."""
        total_categories = AsdaCategory.objects.count()
        active_categories = AsdaCategory.objects.filter(is_active=True).count()
        total_products = AsdaProduct.objects.count()
        
        self.stdout.write(f"DATABASE STATUS:")
        self.stdout.write(f"  Categories: {active_categories}/{total_categories} active")
        self.stdout.write(f"  Products: {total_products}")
        
        if active_categories == 0:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  No active categories found! "
                    "Run 'python manage.py validate_categories --discover' first."
                )
            )
        self.stdout.write('')
    
    def _create_session(self, user: User, options: dict) -> CrawlSession:
        """Create a new crawl session."""
        crawl_settings = {
            'max_categories': options['max_categories'],
            'category_priority': options['category_priority'],
            'max_products_per_category': options['max_products'],
            'delay_between_requests': options['delay'],
            'use_selenium': True,
            'headless': options['headless'],
            'dry_run': options['dry_run'],
            'categories_only': options['categories_only'],
            'crawl_type': options['crawl_type'],
        }
        
        session = CrawlSession.objects.create(
            user=user,
            status='PENDING',
            crawl_type=options['crawl_type'],
            crawl_settings=crawl_settings
        )
        
        if options['session_name']:
            session.notes = f"Session Name: {options['session_name']}"
            session.save()
        
        self.stdout.write(
            self.style.SUCCESS(f"✓ Created {options['crawl_type']} crawl session #{session.pk}")
        )
        self.stdout.write(f"User: {user.username}")
        self.stdout.write('')
        
        return session
    
    def _run_scraper(self, session: CrawlSession, options: dict):
        """Run the scraper."""
        try:
            self.stdout.write("Starting scraper...")
            start_time = time.time()
            
            # Import and create scraper
            from asda_scraper.scrapers import SeleniumAsdaScraper
            
            if options['dry_run']:
                self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be saved"))
                # In dry run, just create session and mark complete
                session.status = 'COMPLETED'
                session.end_time = timezone.now()
                session.save()
                self.stdout.write(self.style.SUCCESS("✓ Dry run completed"))
                return
            
            # Create scraper
            scraper = SeleniumAsdaScraper(
                crawl_session=session,
                headless=options['headless']
            )
            
            # Start crawling
            self.stdout.write("🚀 Starting crawl...")
            result = scraper.start_crawl()
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Display results
            self._display_results(session, duration)
            
        except Exception as e:
            # Mark session as failed
            session.status = 'FAILED'
            session.end_time = timezone.now()
            session.error_log = str(e)
            session.save()
            
            self.stdout.write(self.style.ERROR(f"✗ Scraper failed: {e}"))
            raise CommandError(f"Scraper failed: {e}")
    
    def _display_results(self, session: CrawlSession, duration: float):
        """Display scraping results."""
        # Refresh session from database
        session.refresh_from_db()
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('CRAWL COMPLETED'))
        self.stdout.write(self.style.SUCCESS('='*60))
        
        self.stdout.write(f"Session ID: {session.pk}")
        self.stdout.write(f"Status: {session.status}")
        self.stdout.write(f"Duration: {duration:.1f} seconds")
        self.stdout.write(f"Categories Crawled: {session.categories_crawled}")
        self.stdout.write(f"Products Found: {session.products_found}")
        self.stdout.write(f"Products Updated: {session.products_updated}")
        
        if session.crawl_type in ['NUTRITION', 'BOTH']:
            self.stdout.write(f"Products with Nutrition: {session.products_with_nutrition}")
        
        if session.errors_count > 0:
            self.stdout.write(self.style.WARNING(f"Errors: {session.errors_count}"))
        
        self.stdout.write(f"\n✓ View results at: http://127.0.0.1:8000/scraper/")
        self.stdout.write(f"✓ Monitor with: python manage.py crawler_status")