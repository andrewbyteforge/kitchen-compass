"""
Simple test crawler command to verify basic functionality.

File: asda_scraper/management/commands/test_crawler.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone

from asda_scraper.models import CrawlSession, AsdaCategory, AsdaProduct

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Simple test command to verify crawler setup.
    """
    
    help = 'Test crawler setup and basic functionality'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test mode - do not save data',
        )
    
    def handle(self, *args, **options):
        """Execute the test command."""
        try:
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS('ASDA SCRAPER TEST'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
            # Test database connectivity
            self._test_database()
            
            # Test imports
            self._test_imports()
            
            # Test user setup
            self._test_user_setup()
            
            # Test session creation
            if not options['dry_run']:
                self._test_session_creation()
            
            self.stdout.write(self.style.SUCCESS('\n✓ All tests passed!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ Test failed: {e}'))
            raise CommandError(f"Test failed: {e}")
    
    def _test_database(self):
        """Test database connectivity."""
        self.stdout.write('\n1. Testing database connectivity...')
        
        categories_count = AsdaCategory.objects.count()
        products_count = AsdaProduct.objects.count()
        sessions_count = CrawlSession.objects.count()
        
        self.stdout.write(f'   Categories: {categories_count}')
        self.stdout.write(f'   Products: {products_count}')
        self.stdout.write(f'   Sessions: {sessions_count}')
        self.stdout.write('   ✓ Database connectivity OK')
    
    def _test_imports(self):
        """Test scraper imports."""
        self.stdout.write('\n2. Testing scraper imports...')
        
        try:
            from asda_scraper.scrapers import SeleniumAsdaScraper
            self.stdout.write('   ✓ SeleniumAsdaScraper import OK')
        except ImportError as e:
            self.stdout.write(f'   ✗ SeleniumAsdaScraper import failed: {e}')
            raise
        
        try:
            from asda_scraper.scrapers.popup_handler import PopupHandler
            self.stdout.write('   ✓ PopupHandler import OK')
        except ImportError as e:
            self.stdout.write(f'   ✗ PopupHandler import failed: {e}')
            raise
        
        try:
            from asda_scraper.scrapers.webdriver_manager import WebDriverManager
            self.stdout.write('   ✓ WebDriverManager import OK')
        except ImportError as e:
            self.stdout.write(f'   ✗ WebDriverManager import failed: {e}')
            raise
    
    def _test_user_setup(self):
        """Test user setup."""
        self.stdout.write('\n3. Testing user setup...')
        
        superuser = User.objects.filter(is_superuser=True).first()
        if superuser:
            self.stdout.write(f'   ✓ Superuser found: {superuser.username}')
        else:
            self.stdout.write('   ⚠ No superuser found - you may need to create one')
        
        total_users = User.objects.count()
        self.stdout.write(f'   Total users: {total_users}')
    
    def _test_session_creation(self):
        """Test session creation."""
        self.stdout.write('\n4. Testing session creation...')
        
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()
        
        if not user:
            raise CommandError("No users found in database")
        
        # Create test session
        session = CrawlSession.objects.create(
            user=user,
            status='PENDING',
            crawl_type='PRODUCT',
            crawl_settings={
                'test': True,
                'max_categories': 1
            },
            notes='Test session created by test_crawler command'
        )
        
        self.stdout.write(f'   ✓ Test session created: #{session.pk}')
        
        # Clean up - mark as cancelled
        session.status = 'CANCELLED'
        session.end_time = timezone.now()
        session.save()
        
        self.stdout.write(f'   ✓ Test session cleaned up')
    
    def _test_webdriver_setup(self):
        """Test WebDriver setup (optional)."""
        self.stdout.write('\n5. Testing WebDriver setup...')
        
        try:
            from asda_scraper.scrapers.webdriver_manager import WebDriverManager
            
            # Try to create WebDriver manager
            driver_manager = WebDriverManager(headless=True)
            self.stdout.write('   ✓ WebDriverManager created')
            
            # Don't actually start the driver in test mode
            self.stdout.write('   ✓ WebDriver setup appears OK (not started)')
            
        except Exception as e:
            self.stdout.write(f'   ⚠ WebDriver setup issue: {e}')
            self.stdout.write('   This may not be critical for basic testing')