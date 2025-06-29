"""
Django Management Command for ASDA Scraper

This command provides a CLI interface for running the refactored ASDA scraper
with various configuration options and comprehensive error handling.

File: asda_scraper/management/commands/run_asda_crawl.py
"""

import logging
import time
from typing import Optional
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone

from asda_scraper.models import CrawlSession, AsdaCategory, AsdaProduct
from asda_scraper.selenium_scraper import (
    create_selenium_scraper, 
    ScrapingResult, 
    ScraperException, 
    DriverSetupException
)


class Command(BaseCommand):
    """
    Django management command to run the ASDA scraper.
    
    This command provides comprehensive options for configuring and running
    the scraper from the command line with detailed progress reporting.
    """
    
    help = 'Run the ASDA product scraper with configurable settings'
    
    def __init__(self, *args, **kwargs):
        """Initialize the command with logging setup."""
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)
    
    def add_arguments(self, parser):
        """
        Add command line arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        # Basic scraper settings
        parser.add_argument(
            '--headless',
            action='store_true',
            default=False,
            help='Run browser in headless mode (no visible window)'
        )
        
        parser.add_argument(
            '--max-categories',
            type=int,
            default=10,
            help='Maximum number of categories to scrape'
        )
        
        parser.add_argument(
            '--category-priority',
            type=int,
            default=2,
            choices=[1, 2, 3, 4, 5],
            help='Category priority level (1=core food, 2=+household, 3=+specialty)'
        )
        
        parser.add_argument(
            '--max-products',
            type=int,
            default=100,
            help='Maximum products per category'
        )
        
        parser.add_argument(
            '--delay',
            type=float,
            default=2.0,
            help='Delay between requests in seconds'
        )
        
        # User and session options
        parser.add_argument(
            '--user',
            type=str,
            default='admin',
            help='Username to associate with the crawl session'
        )
        
        parser.add_argument(
            '--session-name',
            type=str,
            help='Optional name for the crawl session'
        )
        
        # Output and logging options
        parser.add_argument(
            '--verbose',
            action='store_true',
            default=False,
            help='Enable verbose logging output'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Perform a dry run without actually saving data'
        )
        
        parser.add_argument(
            '--categories-only',
            action='store_true',
            default=False,
            help='Only discover categories, do not scrape products'
        )
        
        # System options
        parser.add_argument(
            '--cleanup-stuck',
            action='store_true',
            default=False,
            help='Clean up stuck sessions before starting'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            default=False,
            help='Force start even if another session is running'
        )
    
    def handle(self, *args, **options):
        """
        Main command handler.
        
        Args:
            *args: Positional arguments
            **options: Keyword arguments from command line
        """
        try:
            # Setup logging
            self._setup_logging(options['verbose'])
            
            # Display startup banner
            self._display_banner()
            
            # Validate options
            self._validate_options(options)
            
            # Clean up stuck sessions if requested
            if options['cleanup_stuck']:
                self._cleanup_stuck_sessions()
            
            # Check for existing sessions
            if not options['force']:
                self._check_existing_sessions()
            
            # Get or create user
            user = self._get_user(options['user'])
            
            # Create crawl session
            session = self._create_crawl_session(user, options)
            
            # Run the scraper
            result = self._run_scraper(session, options)
            
            # Display results
            self._display_results(session, result)
            
        except CommandError:
            raise
        except Exception as e:
            error_msg = f"Command failed with unexpected error: {str(e)}"
            self.logger.error(error_msg)
            raise CommandError(error_msg)
    
    def _setup_logging(self, verbose: bool):
        """
        Setup logging configuration.
        
        Args:
            verbose: Whether to enable verbose logging
        """
        level = logging.DEBUG if verbose else logging.INFO
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Suppress some noisy loggers
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    def _display_banner(self):
        """Display startup banner."""
        banner = """
╔══════════════════════════════════════════════════╗
║              ASDA Product Scraper                ║
║                                                  ║
║  A production-ready scraper for ASDA grocery    ║
║  data with comprehensive error handling and      ║
║  progress tracking.                              ║
╚══════════════════════════════════════════════════╝
        """
        self.stdout.write(self.style.SUCCESS(banner))
    
    def _validate_options(self, options: dict):
        """
        Validate command line options.
        
        Args:
            options: Dictionary of command options
            
        Raises:
            CommandError: If options are invalid
        """
        if options['max_categories'] <= 0:
            raise CommandError("max-categories must be greater than 0")
        
        if options['max_products'] <= 0:
            raise CommandError("max-products must be greater than 0")
        
        if options['delay'] < 0:
            raise CommandError("delay cannot be negative")
        
        if options['category_priority'] not in [1, 2, 3, 4, 5]:
            raise CommandError("category-priority must be between 1 and 5")
    
    def _cleanup_stuck_sessions(self):
        """Clean up sessions that appear to be stuck."""
        try:
            stuck_sessions = CrawlSession.objects.filter(
                status__in=['PENDING', 'RUNNING'],
                start_time__lt=timezone.now() - timezone.timedelta(hours=2)
            )
            
            count = stuck_sessions.count()
            if count > 0:
                stuck_sessions.update(
                    status='FAILED',
                    error_message='Session cleaned up by management command',
                    end_time=timezone.now()
                )
                self.stdout.write(
                    self.style.WARNING(f"Cleaned up {count} stuck sessions")
                )
            else:
                self.stdout.write("No stuck sessions found")
                
        except Exception as e:
            self.logger.warning(f"Error cleaning up stuck sessions: {e}")
    
    def _check_existing_sessions(self):
        """
        Check for existing running sessions.
        
        Raises:
            CommandError: If a session is already running
        """
        existing_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if existing_session:
            raise CommandError(
                f"Crawl session {existing_session.pk} is already running. "
                f"Use --force to override or stop the existing session first."
            )
    
    def _get_user(self, username: str) -> User:
        """
        Get or create user for the crawl session.
        
        Args:
            username: Username to find or create
            
        Returns:
            User: Django user object
            
        Raises:
            CommandError: If user cannot be found or created
        """
        try:
            # Try to get existing user
            try:
                user = User.objects.get(username=username)
                self.stdout.write(f"Using existing user: {username}")
                return user
            except User.DoesNotExist:
                # Create new user
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@example.com"
                )
                self.stdout.write(
                    self.style.WARNING(f"Created new user: {username}")
                )
                return user
                
        except Exception as e:
            raise CommandError(f"Failed to get/create user {username}: {str(e)}")
    
    def _create_crawl_session(self, user: User, options: dict) -> CrawlSession:
        """
        Create a new crawl session.
        
        Args:
            user: User to associate with the session
            options: Command options
            
        Returns:
            CrawlSession: Created session object
        """
        try:
            # Build crawl settings
            crawl_settings = {
                'max_categories': options['max_categories'],
                'category_priority': options['category_priority'],
                'max_products_per_category': options['max_products'],
                'delay_between_requests': options['delay'],
                'use_selenium': True,
                'headless': options['headless'],
                'dry_run': options['dry_run'],
                'categories_only': options['categories_only'],
            }
            
            # Create session
            session = CrawlSession.objects.create(
                user=user,
                status='PENDING',
                crawl_settings=crawl_settings
            )
            
            # Add session name if provided
            if options['session_name']:
                session.notes = f"Session Name: {options['session_name']}"
                session.save()
            
            self.stdout.write(
                self.style.SUCCESS(f"Created crawl session {session.pk}")
            )
            
            return session
            
        except Exception as e:
            raise CommandError(f"Failed to create crawl session: {str(e)}")
    
    def _run_scraper(self, session: CrawlSession, options: dict) -> ScrapingResult:
        """
        Run the scraper with the given session.
        
        Args:
            session: CrawlSession object
            options: Command options
            
        Returns:
            ScrapingResult: Results of the scraping operation
            
        Raises:
            CommandError: If scraping fails
        """
        try:
            self.stdout.write("Starting scraper...")
            start_time = time.time()
            
            # Create and configure scraper
            scraper = create_selenium_scraper(
                crawl_session=session,
                headless=options['headless']
            )
            
            # Display configuration
            self._display_configuration(session, options)
            
            # Run scraper
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING("DRY RUN MODE - No data will be saved")
                )
            
            result = scraper.start_crawl()
            
            # Calculate total time
            total_time = time.time() - start_time
            result.duration = total_time
            
            return result
            
        except DriverSetupException as e:
            error_msg = f"WebDriver setup failed: {str(e)}"
            self.logger.error(error_msg)
            session.mark_failed(error_msg)
            raise CommandError(error_msg)
            
        except ScraperException as e:
            error_msg = f"Scraper error: {str(e)}"
            self.logger.error(error_msg)
            session.mark_failed(error_msg)
            raise CommandError(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error during scraping: {str(e)}"
            self.logger.error(error_msg)
            session.mark_failed(error_msg)
            raise CommandError(error_msg)
    
    def _display_configuration(self, session: CrawlSession, options: dict):
        """
        Display scraper configuration.
        
        Args:
            session: CrawlSession object
            options: Command options
        """
        config_lines = [
            "Scraper Configuration:",
            f"  Session ID: {session.pk}",
            f"  User: {session.user.username}",
            f"  Headless: {options['headless']}",
            f"  Max Categories: {options['max_categories']}",
            f"  Category Priority: {options['category_priority']}",
            f"  Max Products per Category: {options['max_products']}",
            f"  Delay: {options['delay']}s",
            f"  Dry Run: {options['dry_run']}",
            f"  Categories Only: {options['categories_only']}",
        ]
        
        self.stdout.write("\n".join(config_lines))
        self.stdout.write("")
    
    def _display_results(self, session: CrawlSession, result: ScrapingResult):
        """
        Display scraping results.
        
        Args:
            session: CrawlSession object
            result: ScrapingResult object
        """
        # Refresh session from database
        session.refresh_from_db()
        
        # Create results summary
        results_lines = [
            "",
            "╔══════════════════════════════════════════════════╗",
            "║                 Scraping Results                ║",
            "╚══════════════════════════════════════════════════╝",
            "",
            f"Session ID: {session.pk}",
            f"Status: {session.status}",
            f"Duration: {result.duration:.2f} seconds" if result.duration else "Duration: N/A",
            "",
            "Product Statistics:",
            f"  Products Found: {result.products_found}",
            f"  Products Saved: {result.products_saved}",
            f"  Products Updated: {session.products_updated}",
            "",
            "Category Statistics:",
            f"  Categories Processed: {result.categories_processed}",
            f"  Categories Crawled: {session.categories_crawled}",
            "",
        ]
        
        # Add performance metrics
        if result.duration and result.duration > 0:
            products_per_minute = (result.products_found / result.duration) * 60
            categories_per_minute = (result.categories_processed / result.duration) * 60
            
            results_lines.extend([
                "Performance Metrics:",
                f"  Products per minute: {products_per_minute:.1f}",
                f"  Categories per minute: {categories_per_minute:.1f}",
                "",
            ])
        
        # Add error information
        if result.errors:
            results_lines.extend([
                f"Errors Encountered: {len(result.errors)}",
                "  (Check logs for detailed error information)",
                "",
            ])
        else:
            results_lines.extend([
                "✅ No errors encountered",
                "",
            ])
        
        # Add database statistics
        total_products = AsdaProduct.objects.count()
        total_categories = AsdaCategory.objects.filter(is_active=True).count()
        
        results_lines.extend([
            "Database Statistics:",
            f"  Total Products: {total_products}",
            f"  Active Categories: {total_categories}",
            "",
        ])
        
        # Display results
        for line in results_lines:
            if line.startswith("✅"):
                self.stdout.write(self.style.SUCCESS(line))
            elif "Errors Encountered:" in line and result.errors:
                self.stdout.write(self.style.ERROR(line))
            elif line.startswith("╔") or line.startswith("╚") or line.startswith("║"):
                self.stdout.write(self.style.SUCCESS(line))
            else:
                self.stdout.write(line)
        
        # Final status message
        if session.status == 'COMPLETED':
            self.stdout.write(
                self.style.SUCCESS("🎉 Scraping completed successfully!")
            )
        elif session.status == 'FAILED':
            self.stdout.write(
                self.style.ERROR("❌ Scraping failed - check logs for details")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠️ Scraping ended with status: {session.status}")
            )


# Example usage patterns for the management command:
"""
Basic usage:
python manage.py run_asda_crawl

With custom settings:
python manage.py run_asda_crawl --headless --max-categories 5 --verbose

Categories only (no products):
python manage.py run_asda_crawl --categories-only

Dry run (test without saving):
python manage.py run_asda_crawl --dry-run --verbose

Force run (override existing session):
python manage.py run_asda_crawl --force --cleanup-stuck

Production run with optimal settings:
python manage.py run_asda_crawl --headless --max-categories 15 --category-priority 3 --delay 1.5

Development/testing run:
python manage.py run_asda_crawl --verbose --max-categories 2 --max-products 10 --user testuser
"""