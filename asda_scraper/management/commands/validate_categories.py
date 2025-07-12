"""
Django management command to validate and fix ASDA categories.

File: asda_scraper/management/commands/validate_categories.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from asda_scraper.models import AsdaCategory, CrawlSession
from asda_scraper.scrapers.webdriver_manager import WebDriverManager
from asda_scraper.scrapers.category_manager import CategoryManager
from asda_scraper.scrapers.config import ASDA_CATEGORY_MAPPINGS, validate_category_mapping
from asda_scraper.scrapers.exceptions import DriverSetupException

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to validate and fix ASDA categories.
    
    This command helps diagnose and fix category-related issues
    before running the main crawler.
    """
    
    help = 'Validate and fix ASDA categories before crawling'
    
    def add_arguments(self, parser):
        """
        Add command arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--discover',
            action='store_true',
            help='Discover and create missing categories',
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate existing categories against ASDA website',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Fix invalid categories (deactivate broken ones)',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all categories and their status',
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean up promotional and invalid categories',
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            default=True,
            help='Run browser in headless mode (default: True)',
        )
        parser.add_argument(
            '--max-categories',
            type=int,
            default=10,
            help='Maximum number of categories to process (default: 10)',
        )
        parser.add_argument(
            '--priority',
            type=int,
            default=2,
            help='Maximum priority level to include (default: 2)',
        )
    
    def handle(self, *args, **options):
        """
        Execute the command.
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        try:
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS('ASDA Category Validation Tool'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
            # Initialize components
            driver_manager = None
            driver = None
            category_manager = None
            
            # Create temporary crawl session for validation
            session = self._create_validation_session(options)
            
            try:
                # Set up WebDriver if needed for validation
                if options['validate'] or options['discover']:
                    self.stdout.write("Setting up WebDriver...")
                    driver_manager = WebDriverManager(headless=options['headless'])
                    driver = driver_manager.setup_driver()
                    category_manager = CategoryManager(driver, session)
                    self.stdout.write(self.style.SUCCESS("✓ WebDriver setup successful"))
                
                # Execute requested operations
                if options['list']:
                    self._list_categories()
                
                if options['clean']:
                    self._clean_categories()
                
                if options['discover']:
                    if not category_manager:
                        raise CommandError("WebDriver required for category discovery")
                    self._discover_categories(category_manager)
                
                if options['validate']:
                    if not category_manager:
                        raise CommandError("WebDriver required for category validation")
                    self._validate_categories(category_manager)
                
                if options['fix']:
                    self._fix_categories()
                
                # Summary
                self._print_summary()
                
            finally:
                # Cleanup
                if driver:
                    try:
                        driver.quit()
                    except Exception as e:
                        logger.warning(f"Error closing driver: {e}")
                
                # Mark session as completed
                session.mark_completed()
            
        except DriverSetupException as e:
            raise CommandError(f"WebDriver setup failed: {e}")
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise CommandError(f"Command failed: {e}")
    
    def _create_validation_session(self, options: dict) -> CrawlSession:
        """
        Create a temporary crawl session for validation.
        
        Args:
            options: Command options
            
        Returns:
            CrawlSession: Temporary session for validation
        """
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get first superuser or create a dummy user for validation
            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.filter(is_staff=True).first()
            if not admin_user:
                # Create a temporary validation user if no admin exists
                admin_user = User.objects.create_user(
                    username='validation_temp',
                    email='validation@temp.com',
                    is_staff=True
                )
            
            session = CrawlSession.objects.create(
                user=admin_user,
                status='RUNNING',
                crawl_type='PRODUCT',  # Use existing crawl_type field
                crawl_settings={
                    'max_categories': options['max_categories'],
                    'category_priority': options['priority'],
                    'validation_mode': True
                },
                notes=f"Category validation session - max_categories: {options['max_categories']}, priority: {options['priority']}"
            )
            
            self.stdout.write(f"Created validation session: {session.pk}")
            return session
            
        except Exception as e:
            raise CommandError(f"Failed to create validation session: {e}")
    
    def _list_categories(self):
        """
        List all categories and their status.
        """
        try:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.WARNING("CATEGORY LISTING"))
            self.stdout.write("="*60)
            
            # Get all categories
            categories = AsdaCategory.objects.all().order_by('name')
            
            if not categories.exists():
                self.stdout.write(self.style.WARNING("No categories found in database"))
                return
            
            # Print header
            self.stdout.write(f"{'Name':<30} {'Code':<15} {'Active':<8} {'Last Crawled'}")
            self.stdout.write("-" * 70)
            
            # List categories
            active_count = 0
            for category in categories:
                status = "✓" if category.is_active else "✗"
                last_crawled = category.last_crawled.strftime("%m/%d %H:%M") if category.last_crawled else "Never"
                
                self.stdout.write(f"{category.name:<30} {category.url_code:<15} {status:<8} {last_crawled}")
                
                if category.is_active:
                    active_count += 1
            
            # Summary
            self.stdout.write("-" * 70)
            self.stdout.write(f"Total: {categories.count()}, Active: {active_count}")
            
            # Check for missing mappings
            missing_mappings = []
            for category in categories:
                if not validate_category_mapping(category.url_code):
                    missing_mappings.append(category)
            
            if missing_mappings:
                self.stdout.write(self.style.ERROR("\nCategories missing from ASDA_CATEGORY_MAPPINGS:"))
                for cat in missing_mappings:
                    self.stdout.write(f"  - {cat.name} ({cat.url_code})")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error listing categories: {e}"))
    
    def _clean_categories(self):
        """
        Clean up promotional and invalid categories.
        """
        try:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.WARNING("CLEANING CATEGORIES"))
            self.stdout.write("="*60)
            
            promotional_codes = ['rollback', 'summer', 'events-inspiration', 'christmas', 'easter']
            cleaned_count = 0
            
            with transaction.atomic():
                for promo in promotional_codes:
                    categories = AsdaCategory.objects.filter(
                        url_code__icontains=promo,
                        is_active=True
                    )
                    
                    count = categories.count()
                    if count > 0:
                        categories.update(is_active=False)
                        cleaned_count += count
                        self.stdout.write(f"Deactivated {count} categories containing '{promo}'")
            
            if cleaned_count > 0:
                self.stdout.write(self.style.SUCCESS(f"✓ Cleaned {cleaned_count} promotional categories"))
            else:
                self.stdout.write("No promotional categories found to clean")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error cleaning categories: {e}"))
    
    def _discover_categories(self, category_manager: CategoryManager):
        """
        Discover and create missing categories.
        
        Args:
            category_manager: CategoryManager instance
        """
        try:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.WARNING("DISCOVERING CATEGORIES"))
            self.stdout.write("="*60)
            
            self.stdout.write("Starting category discovery...")
            start_time = time.time()
            
            success = category_manager.discover_categories()
            
            duration = time.time() - start_time
            
            if success:
                active_count = AsdaCategory.objects.filter(is_active=True).count()
                self.stdout.write(self.style.SUCCESS(f"✓ Category discovery completed in {duration:.2f}s"))
                self.stdout.write(f"Active categories: {active_count}")
            else:
                self.stdout.write(self.style.ERROR("✗ Category discovery failed"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during category discovery: {e}"))
    
    def _validate_categories(self, category_manager: CategoryManager):
        """
        Validate existing categories against ASDA website.
        
        Args:
            category_manager: CategoryManager instance
        """
        try:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.WARNING("VALIDATING CATEGORIES"))
            self.stdout.write("="*60)
            
            self.stdout.write("Starting category validation...")
            start_time = time.time()
            
            valid_count, invalid_count = category_manager.validate_all_categories()
            
            duration = time.time() - start_time
            
            self.stdout.write(f"Validation completed in {duration:.2f}s")
            self.stdout.write(f"Valid categories: {valid_count}")
            self.stdout.write(f"Invalid categories: {invalid_count}")
            
            if invalid_count > 0:
                self.stdout.write(self.style.WARNING(f"⚠ {invalid_count} categories were deactivated"))
            else:
                self.stdout.write(self.style.SUCCESS("✓ All categories are valid"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during category validation: {e}"))
    
    def _fix_categories(self):
        """
        Fix invalid categories by deactivating them.
        """
        try:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.WARNING("FIXING CATEGORIES"))
            self.stdout.write("="*60)
            
            # Find categories without proper mappings
            invalid_categories = []
            
            for category in AsdaCategory.objects.filter(is_active=True):
                if not validate_category_mapping(category.url_code):
                    invalid_categories.append(category)
            
            if invalid_categories:
                with transaction.atomic():
                    for category in invalid_categories:
                        category.is_active = False
                        category.save(update_fields=['is_active'])
                        self.stdout.write(f"Deactivated: {category.name} ({category.url_code})")
                
                self.stdout.write(self.style.SUCCESS(f"✓ Fixed {len(invalid_categories)} invalid categories"))
            else:
                self.stdout.write("No categories need fixing")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error fixing categories: {e}"))
    
    def _print_summary(self):
        """
        Print final summary.
        """
        try:
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.SUCCESS("SUMMARY"))
            self.stdout.write("="*60)
            
            total_categories = AsdaCategory.objects.count()
            active_categories = AsdaCategory.objects.filter(is_active=True).count()
            
            self.stdout.write(f"Total categories in database: {total_categories}")
            self.stdout.write(f"Active categories: {active_categories}")
            self.stdout.write(f"Categories in mappings: {len(ASDA_CATEGORY_MAPPINGS)}")
            
            if active_categories == 0:
                self.stdout.write(self.style.ERROR("⚠ WARNING: No active categories found!"))
                self.stdout.write("Run with --discover to create categories")
            else:
                self.stdout.write(self.style.SUCCESS("✓ Ready for crawling"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error printing summary: {e}"))