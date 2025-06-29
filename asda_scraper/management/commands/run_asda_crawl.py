"""
Django management command for running ASDA crawl sessions.

This command allows running ASDA scraping from the command line,
useful for scheduled tasks and testing.
"""

import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from asda_scraper.models import CrawlSession
from asda_scraper.scraper import AsdaScraper

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to run ASDA product crawling.
    
    Usage:
        python manage.py run_asda_crawl --user admin@example.com
        python manage.py run_asda_crawl --user admin@example.com --max-products 50
    """
    
    help = 'Run ASDA product crawling session'
    
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
    
    def handle(self, *args, **options):
        """Execute the crawl command."""
        try:
            # Get user
            user_email = options['user']
            try:
                user = User.objects.get(email=user_email)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User with email {user_email} does not exist')
                )
                return
            
            # Check for existing running session
            existing_session = CrawlSession.objects.filter(
                status__in=['PENDING', 'RUNNING']
            ).first()
            
            if existing_session:
                self.stdout.write(
                    self.style.ERROR(f'Crawl session {existing_session.pk} is already running')
                )
                return
            
            # Create crawl settings
            crawl_settings = {
                'max_products_per_category': options['max_products'],
                'delay_between_requests': options['delay'],
                'categories_to_crawl': options.get('categories', []),
            }
            
            # Create new crawl session
            session = CrawlSession.objects.create(
                user=user,
                status='PENDING',
                crawl_settings=crawl_settings
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Created crawl session {session.pk}')
            )
            
            # Start the scraper
            scraper = AsdaScraper(session)
            scraper.start_crawl()
            
            self.stdout.write(
                self.style.SUCCESS(f'Crawl session {session.pk} completed successfully')
            )
            
        except Exception as e:
            logger.error(f"Error in run_asda_crawl command: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Error running crawl: {str(e)}')
            )