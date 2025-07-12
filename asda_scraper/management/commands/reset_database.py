"""
Django management command to reset ASDA scraper database data.

File: asda_scraper/management/commands/reset_database.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from asda_scraper.models import (
    AsdaProduct, 
    AsdaCategory, 
    CrawlSession
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to reset ASDA scraper database data.
    
    This command provides various options for clearing data to allow
    fresh crawling and testing of the scraper functionality.
    """
    
    help = 'Reset ASDA scraper database data to start fresh'
    
    def add_arguments(self, parser):
        """
        Add command arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--products',
            action='store_true',
            help='Delete all product data (products, prices, nutrition)',
        )
        parser.add_argument(
            '--categories',
            action='store_true',
            help='Delete all category data',
        )
        parser.add_argument(
            '--sessions',
            action='store_true',
            help='Delete all crawl session data',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete ALL data (products, categories, sessions)',
        )
        parser.add_argument(
            '--nutrition-only',
            action='store_true',
            help='Clear only nutritional information from products (keep products/prices)',
        )
        parser.add_argument(
            '--prices-only',
            action='store_true',
            help='This option is not available - prices are stored within product records',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt (use with caution)',
        )
        parser.add_argument(
            '--keep-categories',
            action='store_true',
            help='Keep categories when using --all option',
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
            self.stdout.write(self.style.SUCCESS('ASDA SCRAPER DATABASE RESET'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
            # Show current database status
            self._show_current_status()
            
            # Determine what to reset
            reset_plan = self._determine_reset_plan(options)
            
            if not reset_plan:
                self.stdout.write(self.style.WARNING("No reset options specified. Use --help for options."))
                return
            
            # Show reset plan
            self._show_reset_plan(reset_plan)
            
            # Confirm action if not auto-confirmed
            if not options['confirm']:
                if not self._confirm_reset():
                    self.stdout.write(self.style.WARNING("Reset cancelled by user."))
                    return
            
            # Execute reset
            self._execute_reset(reset_plan)
            
            # Show final status
            self._show_final_status()
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise CommandError(f"Database reset failed: {e}")
    
    def _show_current_status(self):
        """
        Show current database status before reset.
        """
        try:
            products_count = AsdaProduct.objects.count()
            categories_count = AsdaCategory.objects.count()
            sessions_count = CrawlSession.objects.count()
            
            self.stdout.write(f"\nCURRENT DATABASE STATUS:")
            self.stdout.write(f"  Products: {products_count}")
            self.stdout.write(f"  Categories: {categories_count}")
            self.stdout.write(f"  Crawl Sessions: {sessions_count}")
            
            # Show active sessions
            active_sessions = CrawlSession.objects.filter(status__in=['PENDING', 'RUNNING'])
            if active_sessions.exists():
                self.stdout.write(self.style.WARNING(f"\n⚠️  WARNING: {active_sessions.count()} active crawl sessions detected!"))
                for session in active_sessions:
                    self.stdout.write(
                        self.style.WARNING(f"    Session #{session.pk} - {session.status} - {session.get_crawl_type_display()}")
                    )
                self.stdout.write(self.style.WARNING(f"    Consider stopping these sessions before resetting data."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing current status: {e}"))
    
    def _determine_reset_plan(self, options):
        """
        Determine what data to reset based on options.
        
        Args:
            options: Command options
            
        Returns:
            dict: Reset plan configuration
        """
        plan = {
            'products': False,
            'categories': False,
            'sessions': False,
            'nutritional_info_only': False  # This will clear only the nutritional_info JSON field
        }
        
        if options['all']:
            plan['products'] = True
            plan['categories'] = not options['keep_categories']
            plan['sessions'] = True
        else:
            plan['products'] = options['products']
            plan['categories'] = options['categories']
            plan['sessions'] = options['sessions']
            plan['nutritional_info_only'] = options['nutrition_only']
        
        return plan
    
    def _show_reset_plan(self, reset_plan):
        """
        Show what will be reset.
        
        Args:
            reset_plan: Reset plan configuration
        """
        try:
            self.stdout.write(f"\nRESET PLAN:")
            
            actions = []
            
            if reset_plan['products']:
                actions.append("✓ Delete ALL products and related data")
            if reset_plan['categories']:
                actions.append("✓ Delete ALL categories")
            if reset_plan['sessions']:
                actions.append("✓ Delete ALL crawl sessions")
            if reset_plan['nutritional_info_only']:
                actions.append("✓ Clear ONLY nutritional information from products")
            
            if actions:
                for action in actions:
                    self.stdout.write(f"  {action}")
            else:
                self.stdout.write(f"  No actions planned")
            
            # Show impact estimates
            self._show_impact_estimates(reset_plan)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing reset plan: {e}"))
    
    def _show_impact_estimates(self, reset_plan):
        """
        Show estimated impact of the reset.
        
        Args:
            reset_plan: Reset plan configuration
        """
        try:
            self.stdout.write(f"\nESTIMATED IMPACT:")
            
            if reset_plan['products']:
                count = AsdaProduct.objects.count()
                self.stdout.write(f"  • {count} products will be deleted")
                
                products_with_nutrition = AsdaProduct.objects.exclude(nutritional_info={}).count()
                self.stdout.write(f"  • {products_with_nutrition} products have nutritional information")
            
            if reset_plan['nutritional_info_only']:
                count = AsdaProduct.objects.exclude(nutritional_info={}).count()
                self.stdout.write(f"  • Nutritional info will be cleared from {count} products")
            
            if reset_plan['categories']:
                count = AsdaCategory.objects.count()
                self.stdout.write(f"  • {count} categories will be deleted")
            
            if reset_plan['sessions']:
                count = CrawlSession.objects.count()
                self.stdout.write(f"  • {count} crawl sessions will be deleted")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing impact estimates: {e}"))
    
    def _confirm_reset(self):
        """
        Ask user to confirm the reset operation.
        
        Returns:
            bool: True if user confirms
        """
        try:
            self.stdout.write(self.style.WARNING(f"\n⚠️  This action cannot be undone!"))
            response = input("Type 'yes' to confirm the reset: ")
            return response.lower() == 'yes'
            
        except (EOFError, KeyboardInterrupt):
            return False
    
    def _execute_reset(self, reset_plan):
        """
        Execute the database reset according to the plan.
        
        Args:
            reset_plan: Reset plan configuration
        """
        try:
            self.stdout.write(f"\nEXECUTING RESET...")
            
            deleted_counts = {}
            
            with transaction.atomic():
                
                # Clear nutritional info only (don't delete products)
                if reset_plan['nutritional_info_only']:
                    updated_count = AsdaProduct.objects.exclude(nutritional_info={}).update(nutritional_info={})
                    deleted_counts['nutrition_cleared'] = updated_count
                    self.stdout.write(f"  ✓ Cleared nutritional info from {updated_count} products")
                
                # Delete products completely
                if reset_plan['products']:
                    # Count before deletion
                    product_count = AsdaProduct.objects.count()
                    
                    # Delete products (this will also clear nutritional_info)
                    AsdaProduct.objects.all().delete()
                    
                    deleted_counts['products'] = product_count
                    self.stdout.write(f"  ✓ Deleted {product_count} products")
                
                # Delete categories
                if reset_plan['categories']:
                    count = AsdaCategory.objects.count()
                    AsdaCategory.objects.all().delete()
                    deleted_counts['categories'] = count
                    self.stdout.write(f"  ✓ Deleted {count} categories")
                
                # Delete sessions
                if reset_plan['sessions']:
                    count = CrawlSession.objects.count()
                    CrawlSession.objects.all().delete()
                    deleted_counts['sessions'] = count
                    self.stdout.write(f"  ✓ Deleted {count} crawl sessions")
            
            # Log the reset
            logger.info(f"Database reset completed: {deleted_counts}")
            
            self.stdout.write(self.style.SUCCESS(f"\n✓ Database reset completed successfully!"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error executing reset: {e}"))
            raise
    
    def _show_final_status(self):
        """
        Show database status after reset.
        """
        try:
            products_count = AsdaProduct.objects.count()
            categories_count = AsdaCategory.objects.count()
            sessions_count = CrawlSession.objects.count()
            products_with_nutrition = AsdaProduct.objects.exclude(nutritional_info={}).count()
            
            self.stdout.write(f"\nFINAL DATABASE STATUS:")
            self.stdout.write(f"  Products: {products_count}")
            self.stdout.write(f"  Categories: {categories_count}")
            self.stdout.write(f"  Crawl Sessions: {sessions_count}")
            self.stdout.write(f"  Products with nutrition: {products_with_nutrition}")
            
            # Show recommendations
            self.stdout.write(f"\nRECOMMENDATIONS:")
            if categories_count == 0:
                self.stdout.write(f"  1. Run: python manage.py validate_categories --discover")
            if products_count == 0:
                self.stdout.write(f"  2. Run: python manage.py run_asda_crawl --crawl-type PRODUCT")
            
            self.stdout.write(f"\n✓ Ready for fresh crawling!")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing final status: {e}"))

# delete DB
#  python manage.py reset_database --products --confirm