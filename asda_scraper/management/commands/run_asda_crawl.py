"""
Enhanced Django management command for running ASDA crawling with link mapping.

This command allows running ASDA scraping from the command line with enhanced
link mapping capabilities, useful for scheduled tasks and testing.

Usage:
    python manage.py run_asda_crawl --user admin@example.com
    python manage.py run_asda_crawl --user admin@example.com --max-products 50
    python manage.py run_asda_crawl --user admin@example.com --enhanced --max-pages 100
"""

import logging
import json
import sys
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from asda_scraper.models import CrawlSession, UrlMap, CrawlQueue

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Enhanced management command to run ASDA product crawling.
    
    Supports both traditional product scraping and enhanced link mapping.
    """
    
    help = 'Run ASDA product crawling session with optional enhanced link mapping'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--user',
            type=str,
            required=True,
            help='Email of user to run crawl as'
        )
        parser.add_argument(
            '--max-products',
            type=int,
            default=100,
            help='Maximum products to crawl per category (default: 100)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay between requests in seconds (default: 1.0)'
        )
        parser.add_argument(
            '--categories',
            nargs='*',
            help='Specific category URL codes to crawl (crawls all active if not specified)'
        )
        
        # Enhanced crawling options
        parser.add_argument(
            '--enhanced',
            action='store_true',
            help='Use enhanced crawler with link mapping (experimental)'
        )
        parser.add_argument(
            '--max-pages',
            type=int,
            default=100,
            help='Maximum pages to crawl in enhanced mode (default: 100)'
        )
        parser.add_argument(
            '--max-depth',
            type=int,
            default=3,
            help='Maximum crawling depth in enhanced mode (default: 3)'
        )
        parser.add_argument(
            '--start-urls',
            nargs='+',
            default=['https://groceries.asda.com/'],
            help='Starting URLs for enhanced crawling'
        )
        parser.add_argument(
            '--session-id',
            type=str,
            help='Resume existing crawl session by ID'
        )
        parser.add_argument(
            '--stats-only',
            action='store_true',
            help='Show crawl session statistics and exit'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be crawled without actually crawling'
        )
    
    def handle(self, *args, **options):
        """Execute the crawl command."""
        try:
            # Configure logging
            if options['verbose']:
                logging.getLogger('asda_scraper').setLevel(logging.DEBUG)
            
            # Handle stats-only option
            if options['stats_only']:
                self._show_statistics()
                return
            
            # Get user
            try:
                user = User.objects.get(email=options['user'])
            except User.DoesNotExist:
                raise CommandError(f"User with email {options['user']} not found")
            
            # Handle enhanced vs traditional crawling
            if options['enhanced']:
                self._run_enhanced_crawl(user, options)
            else:
                self._run_traditional_crawl(user, options)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nCrawl interrupted by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            logger.error(f"Command error: {str(e)}")
            raise CommandError(str(e))
    
    def _run_traditional_crawl(self, user, options):
        """Run traditional product-focused crawl."""
        self.stdout.write(self.style.SUCCESS("Starting traditional ASDA crawl..."))
        
        # Create crawl session
        session = CrawlSession.objects.create(
            user=user,
            status='PENDING',
            crawl_settings={
                'max_products_per_category': options['max_products'],
                'delay_between_requests': options['delay'],
                'categories_to_crawl': options['categories'] or [],
                'crawl_type': 'traditional'
            }
        )
        
        logger.info(f"Created traditional crawl session {session.session_id} for user {user.email}")
        
        try:
            # Try to import and use existing scraper
            try:
                from asda_scraper.scraper import AsdaScraper
                scraper = AsdaScraper(session)
                scraper.start_crawl()
                
            except ImportError:
                # Fallback to Selenium scraper
                try:
                    from asda_scraper.selenium_scraper import SeleniumAsdaScraper
                    scraper = SeleniumAsdaScraper(session)
                    scraper.start_crawl()
                    
                except ImportError:
                    raise CommandError("No scraper available. Please ensure scraper modules are properly installed.")
            
            self.stdout.write(
                self.style.SUCCESS(f"Traditional crawl completed successfully: {session.session_id}")
            )
            
        except Exception as e:
            session.mark_failed(str(e))
            raise CommandError(f"Traditional crawl failed: {str(e)}")
    
    def _run_enhanced_crawl(self, user, options):
        """Run enhanced crawl with link mapping."""
        self.stdout.write(self.style.SUCCESS("Starting enhanced ASDA crawl with link mapping..."))
        
        # Handle session resumption
        if options['session_id']:
            try:
                session = CrawlSession.objects.get(session_id=options['session_id'])
                if session.status not in ['PAUSED', 'FAILED']:
                    raise CommandError(f"Session {options['session_id']} is not resumable (status: {session.status})")
                self.stdout.write(f"Resuming session: {session.session_id}")
            except CrawlSession.DoesNotExist:
                raise CommandError(f"Session {options['session_id']} not found")
        else:
            # Create new enhanced session
            session = CrawlSession.objects.create(
                user=user,
                start_url=options['start_urls'][0],
                max_depth=options['max_depth'],
                delay_seconds=options['delay'],
                notes=f"Enhanced crawl via management command. Max pages: {options['max_pages']}",
                crawl_settings={
                    'crawl_type': 'enhanced',
                    'max_pages': options['max_pages'],
                    'start_urls': options['start_urls'],
                }
            )
        
        # Display session info
        self._display_session_info(session, options)
        
        # Handle dry run
        if options['dry_run']:
            self._perform_dry_run(session, options)
            return
        
        # Try to run enhanced crawler
        try:
            # Check if enhanced crawler is available
            try:
                from asda_scraper.enhanced_crawler import EnhancedAsdaCrawler
                
                # Initialize enhanced crawler
                crawler = EnhancedAsdaCrawler(
                    crawl_session=session,
                    max_depth=options['max_depth'],
                    delay=options['delay'],
                    max_pages=options['max_pages']
                )
                
                # Start crawling
                start_time = timezone.now()
                crawler.start_crawl(start_urls=options['start_urls'])
                
                # Show results
                self._show_final_results(session, start_time)
                
            except ImportError:
                self.stdout.write(
                    self.style.WARNING("Enhanced crawler not available. Creating basic URL mapping...")
                )
                self._create_basic_url_mapping(session, options)
                
        except Exception as e:
            session.mark_failed(str(e))
            raise CommandError(f"Enhanced crawl failed: {str(e)}")
    
    def _create_basic_url_mapping(self, session, options):
        """Create basic URL mapping when enhanced crawler is not available."""
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        
        self.stdout.write("Creating basic URL mapping...")
        
        session.status = 'RUNNING'
        session.save()
        
        # Add start URLs to mapping
        for url in options['start_urls']:
            url_map, created = UrlMap.objects.get_or_create(
                crawl_session=session,
                url_hash=UrlMap.generate_url_hash(url),
                defaults={
                    'url': url,
                    'normalized_url': UrlMap.normalize_url(url),
                    'url_type': UrlMap.classify_url_type(url),
                    'depth': 0,
                    'status': 'discovered'
                }
            )
            
            if created:
                session.urls_discovered += 1
                self.stdout.write(f"Added URL: {url}")
        
        session.save()
        session.mark_completed()
        
        self.stdout.write(
            self.style.SUCCESS(f"Basic URL mapping completed: {session.urls_discovered} URLs discovered")
        )
    
    def _display_session_info(self, session, options):
        """Display information about the crawl session."""
        self.stdout.write("\n" + "="*60)
        self.stdout.write(f"Session ID: {session.session_id}")
        self.stdout.write(f"Status: {session.get_status_display()}")
        self.stdout.write(f"User: {session.user.email}")
        self.stdout.write(f"Start URL: {session.start_url}")
        self.stdout.write(f"Max Depth: {options['max_depth']}")
        self.stdout.write(f"Max Pages: {options['max_pages']}")
        self.stdout.write(f"Delay: {options['delay']} seconds")
        
        # Show existing progress if resuming
        if session.urls_discovered > 0:
            self.stdout.write(f"\nExisting Progress:")
            self.stdout.write(f"  URLs Discovered: {session.urls_discovered}")
            self.stdout.write(f"  URLs Crawled: {session.urls_crawled}")
            self.stdout.write(f"  Products Found: {session.products_found}")
            self.stdout.write(f"  Errors: {session.errors_count}")
        
        self.stdout.write("="*60 + "\n")
    
    def _perform_dry_run(self, session, options):
        """Perform a dry run to show what would be crawled."""
        self.stdout.write(self.style.WARNING("DRY RUN MODE - No actual crawling will be performed\n"))
        
        self.stdout.write("Configuration:")
        self.stdout.write(f"  Max Pages: {options['max_pages']}")
        self.stdout.write(f"  Max Depth: {options['max_depth']}")
        self.stdout.write(f"  Delay: {options['delay']} seconds")
        self.stdout.write(f"  Start URLs: {', '.join(options['start_urls'])}")
        
        if session.urls_discovered > 0:
            discovered_urls = UrlMap.objects.filter(
                crawl_session=session
            ).order_by('depth', '-priority')[:10]
            
            self.stdout.write(f"\nExisting URLs (showing first 10):")
            for url_map in discovered_urls:
                self.stdout.write(
                    f"  [{url_map.depth}] {url_map.get_status_display()} "
                    f"{url_map.get_url_type_display()}: {url_map.url[:60]}..."
                )
    
    def _show_final_results(self, session, start_time):
        """Show final crawling results."""
        duration = timezone.now() - start_time
        session.refresh_from_db()
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("CRAWL COMPLETED"))
        self.stdout.write("="*60)
        self.stdout.write(f"Session ID: {session.session_id}")
        self.stdout.write(f"Duration: {duration}")
        self.stdout.write(f"Status: {session.get_status_display()}")
        self.stdout.write("")
        self.stdout.write("Results:")
        self.stdout.write(f"  URLs Discovered: {session.urls_discovered}")
        self.stdout.write(f"  URLs Crawled: {session.urls_crawled}")
        self.stdout.write(f"  Products Found: {session.products_found}")
        self.stdout.write(f"  Errors: {session.errors_count}")
        
        if session.urls_crawled > 0:
            avg_time = duration.total_seconds() / session.urls_crawled
            rate = session.urls_crawled / duration.total_seconds() * 60
            self.stdout.write(f"\nPerformance:")
            self.stdout.write(f"  Average time per URL: {avg_time:.2f} seconds")
            self.stdout.write(f"  URLs per minute: {rate:.1f}")
        
        self.stdout.write("="*60)
    
    def _show_statistics(self):
        """Show statistics for all crawl sessions."""
        sessions = CrawlSession.objects.all().order_by('-start_time')[:10]
        
        if not sessions:
            self.stdout.write("No crawl sessions found")
            return
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write("ASDA CRAWL SESSION STATISTICS")
        self.stdout.write("="*80)
        
        # Header
        self.stdout.write(
            f"{'Session ID':<25} {'Type':<12} {'Status':<12} {'URLs':<8} {'Products':<10} {'Started':<20}"
        )
        self.stdout.write("-" * 80)
        
        # Session data
        for session in sessions:
            crawl_type = session.crawl_settings.get('crawl_type', 'traditional') if session.crawl_settings else 'traditional'
            
            status_color = {
                'COMPLETED': self.style.SUCCESS,
                'RUNNING': self.style.WARNING,
                'FAILED': self.style.ERROR,
                'PAUSED': self.style.HTTP_INFO,
            }.get(session.status, self.style.HTTP_NOT_MODIFIED)
            
            self.stdout.write(
                f"{session.session_id:<25} "
                f"{crawl_type:<12} "
                f"{status_color(session.status):<20} "  # Account for color codes
                f"{session.urls_crawled:<8} "
                f"{session.products_found:<10} "
                f"{session.start_time.strftime('%Y-%m-%d %H:%M') if session.start_time else 'N/A':<20}"
            )
        
        # Summary
        total_sessions = sessions.count()
        completed = sessions.filter(status='COMPLETED').count()
        enhanced_sessions = [s for s in sessions if s.crawl_settings and s.crawl_settings.get('crawl_type') == 'enhanced']
        
        self.stdout.write("-" * 80)
        self.stdout.write(f"Total Sessions: {total_sessions}")
        self.stdout.write(f"Completed: {completed}")
        self.stdout.write(f"Enhanced Sessions: {len(enhanced_sessions)}")
        self.stdout.write("="*80)