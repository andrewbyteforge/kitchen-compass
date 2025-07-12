"""
Django Management Command for ASDA Scraper - FIXED VERSION

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
# CORRECT IMPORTS - Use the scrapers package properly
from asda_scraper.scrapers import SeleniumAsdaScraper, create_selenium_scraper, ScrapingResult, ScraperException, DriverSetupException

logger = logging.getLogger(__name__)


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
        # Core settings
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
            help='Maximum priority level to include (1=highest, 3=lowest, default: 2)'
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
        
        # Browser settings
        parser.add_argument(
            '--headless',
            action='store_true',
            default=False,
            help='Run browser in headless mode'
        )
        
        parser.add_argument(
            '--no-headless',
            action='store_true',
            help='Force browser to run with GUI (opposite of --headless)'
        )
        
        # Operation modes
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
        
        # Session management
        parser.add_argument(
            '--session-name',
            type=str,
            help='Optional name for the crawl session'
        )
        
        parser.add_argument(
            '--user',
            type=str,
            help='Username to associate with the session (default: first superuser)'
        )
        
        # Debug options
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
        
        parser.add_argument(
            '--status-only',
            action='store_true',
            help='Only show current system status, don\'t start crawl'
        )
    
    def handle(self, *args, **options):
        """
        Execute the command.
        
        Args:
            *args: Positional arguments
            **options: Keyword arguments from command line
        """
        try:
            # Configure logging level
            if options['verbose']:
                logging.getLogger('asda_scraper').setLevel(logging.DEBUG)
            
            # Handle --no-headless option
            if options['no_headless']:
                options['headless'] = False
            
            # Show status only if requested
            if options['status_only']:
                self._show_system_status()
                return
            
            # Show startup banner
            self._show_startup_banner(options)
            
            # Get or create user
            user = self._get_user(options)
            
            # Create crawl session
            session = self._create_session(user, options)
            
            # Run scraper
            result = self._run_scraper(session, options)
            
            # Display results
            self._display_results(session, result)
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nCrawl interrupted by user.')
            )
        except CommandError:
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in command: {str(e)}")
            raise CommandError(f"Command failed: {str(e)}")
    
    def _show_startup_banner(self, options: dict):
        """
        Show startup banner with key information.
        
        Args:
            options: Command options
        """
        banner_lines = [
            "=" * 60,
            "ASDA Product Scraper",
            "=" * 60,
            f"Mode: {'DRY RUN' if options['dry_run'] else 'LIVE'}",
            f"Categories: {options['categories_only'] and 'Discovery Only' or 'Full Crawl'}",
            f"Browser: {'Headless' if options['headless'] else 'Visible'}",
            f"Max Categories: {options['max_categories']}",
            f"Priority Level: {options['category_priority']}",
            "=" * 60
        ]
        
        for line in banner_lines:
            self.stdout.write(self.style.SUCCESS(line))
    
    def _show_system_status(self):
        """Show current system status."""
        try:
            # Get current statistics
            total_categories = AsdaCategory.objects.count()
            active_categories = AsdaCategory.objects.filter(is_active=True).count()
            total_products = AsdaProduct.objects.count()
            recent_sessions = CrawlSession.objects.filter(
                start_time__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()
            
            # Check for active sessions
            active_session = CrawlSession.objects.filter(
                status__in=['PENDING', 'RUNNING']
            ).first()
            
            status_lines = [
                "=" * 50,
                "SYSTEM STATUS",
                "=" * 50,
                f"Categories: {active_categories}/{total_categories} active",
                f"Products: {total_products:,} total",
                f"Recent Sessions: {recent_sessions} (last 7 days)",
                f"Active Session: {active_session.pk if active_session else 'None'}",
                "=" * 50
            ]
            
            for line in status_lines:
                self.stdout.write(line)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error getting system status: {str(e)}")
            )
    
    def _get_user(self, options: dict) -> User:
        """
        Get user for the session.
        
        Args:
            options: Command options
            
        Returns:
            User: Django user instance
            
        Raises:
            CommandError: If user cannot be found or created
        """
        try:
            if options['user']:
                user = User.objects.get(username=options['user'])
                self.stdout.write(f"Using user: {user.username}")
            else:
                # Get first superuser
                user = User.objects.filter(is_superuser=True).first()
                if not user:
                    # Create a default admin user
                    user = User.objects.create_superuser(
                        username='asda_scraper_admin',
                        email='admin@asdascaper.local',
                        password='admin123'
                    )
                    self.stdout.write(
                        self.style.WARNING(f"Created default admin user: {user.username}")
                    )
                else:
                    self.stdout.write(f"Using superuser: {user.username}")
            
            return user
            
        except User.DoesNotExist:
            raise CommandError(f"User '{options['user']}' not found")
        except Exception as e:
            raise CommandError(f"Error getting user: {str(e)}")
    
    def _create_session(self, user: User, options: dict) -> CrawlSession:
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
        # Refresh session from database to get final counts
        session.refresh_from_db()
        
        # Calculate rates
        duration_minutes = result.duration / 60 if result.duration > 0 else 0.1
        products_per_minute = session.products_found / duration_minutes if duration_minutes > 0 else 0
        categories_per_minute = session.categories_crawled / duration_minutes if duration_minutes > 0 else 0
        
        # Display results
        result_lines = [
            "",
            "=" * 60,
            "SCRAPING RESULTS",
            "=" * 60,
            f"Session ID: {session.pk}",
            f"Status: {session.status}",
            f"Duration: {result.duration:.1f} seconds ({duration_minutes:.1f} minutes)",
            "",
            "CATEGORIES:",
            f"  Processed: {session.categories_crawled}",
            f"  Rate: {categories_per_minute:.1f} categories/minute",
            "",
            "PRODUCTS:",
            f"  Found: {session.products_found}",
            f"  Updated: {session.products_updated}",
            f"  Rate: {products_per_minute:.1f} products/minute",
            "",
            "ERRORS:",
            f"  Count: {len(result.errors) if hasattr(result, 'errors') else 0}",
        ]
        
        # Add error details if present
        if hasattr(result, 'errors') and result.errors:
            result_lines.extend([
                "",
                "ERROR DETAILS:",
            ])
            for i, error in enumerate(result.errors[:5], 1):
                result_lines.append(f"  {i}. {error}")
            if len(result.errors) > 5:
                result_lines.append(f"  ... and {len(result.errors) - 5} more errors")
        
        result_lines.append("=" * 60)
        
        # Color code based on success
        style = self.style.SUCCESS if session.status == 'COMPLETED' else self.style.ERROR
        
        for line in result_lines:
            self.stdout.write(style(line))
        
        # Final status message
        if session.status == 'COMPLETED':
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Scraping completed successfully!")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"\n✗ Scraping failed. Check logs for details.")
            )