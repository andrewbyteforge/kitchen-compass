"""
Django management command to cleanup excessive ASDA subcategories.

File: asda_scraper/management/commands/cleanup_categories.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from asda_scraper.models import AsdaCategory
from asda_scraper.scrapers.config import ASDA_CATEGORY_MAPPINGS, validate_category_mapping

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to cleanup excessive ASDA subcategories.
    
    This command helps remove overly specific subcategories that
    were automatically discovered but don't have proper URL mappings.
    """
    
    help = 'Cleanup excessive ASDA subcategories and focus on main categories'
    
    def add_arguments(self, parser):
        """
        Add command arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without making changes',
        )
        parser.add_argument(
            '--keep-essential',
            action='store_true',
            default=True,
            help='Keep essential categories (default: True)',
        )
        parser.add_argument(
            '--priority-limit',
            type=int,
            default=2,
            help='Only keep categories with priority <= this value (default: 2)',
        )
    
    def handle(self, *args, **options):
        """
        Execute the command.
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        try:
            self.stdout.write(self.style.SUCCESS('='*70))
            self.stdout.write(self.style.SUCCESS('ASDA Category Cleanup Tool'))
            self.stdout.write(self.style.SUCCESS('='*70))
            
            dry_run = options['dry_run']
            priority_limit = options['priority_limit']
            
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
            
            # Get current status
            self._show_current_status()
            
            # Find categories to clean up
            categories_to_deactivate, categories_to_keep = self._analyze_categories(priority_limit)
            
            # Show cleanup plan
            self._show_cleanup_plan(categories_to_deactivate, categories_to_keep)
            
            # Execute cleanup if not dry run
            if not dry_run:
                self._execute_cleanup(categories_to_deactivate)
            
            # Show final status
            self._show_final_status(dry_run)
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise CommandError(f"Cleanup failed: {e}")
    
    def _show_current_status(self):
        """
        Show current category status.
        """
        try:
            total_categories = AsdaCategory.objects.count()
            active_categories = AsdaCategory.objects.filter(is_active=True).count()
            mapped_categories = len(ASDA_CATEGORY_MAPPINGS)
            
            self.stdout.write(f"\nCURRENT STATUS:")
            self.stdout.write(f"  Total categories in database: {total_categories}")
            self.stdout.write(f"  Active categories: {active_categories}")
            self.stdout.write(f"  Categories with URL mappings: {mapped_categories}")
            self.stdout.write(f"  Categories without mappings: {active_categories - mapped_categories}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing current status: {e}"))
    
    def _analyze_categories(self, priority_limit: int):
        """
        Analyze categories to determine what to keep and what to clean.
        
        Args:
            priority_limit: Maximum priority level to keep
            
        Returns:
            tuple: (categories_to_deactivate, categories_to_keep)
        """
        try:
            categories_to_deactivate = []
            categories_to_keep = []
            
            all_categories = AsdaCategory.objects.filter(is_active=True)
            
            for category in all_categories:
                # Check if category has proper mapping
                if validate_category_mapping(category.url_code):
                    cat_info = ASDA_CATEGORY_MAPPINGS[category.url_code]
                    priority = cat_info.get('priority', 5)
                    
                    if priority <= priority_limit:
                        categories_to_keep.append((category, 'Has mapping', priority))
                    else:
                        categories_to_deactivate.append((category, f'Priority {priority} > {priority_limit}'))
                else:
                    # Determine if this is an essential category based on name
                    if self._is_essential_category(category):
                        categories_to_keep.append((category, 'Essential but no mapping', None))
                    else:
                        categories_to_deactivate.append((category, 'No mapping & not essential'))
            
            return categories_to_deactivate, categories_to_keep
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error analyzing categories: {e}"))
            return [], []
    
    def _is_essential_category(self, category: AsdaCategory) -> bool:
        """
        Determine if a category is essential based on its name.
        
        Args:
            category: AsdaCategory instance
            
        Returns:
            bool: True if category is considered essential
        """
        essential_keywords = [
            # Main food categories
            'fruit', 'meat', 'fish', 'dairy', 'frozen', 'chilled',
            # Basic bread types
            'bread', 'rolls', 'bagels', 'wraps',
            # Main cake types
            'cakes', 'desserts',
            # Essential subcategories
            'gluten free', 'organic', 'vegetarian', 'vegan'
        ]
        
        category_name_lower = category.name.lower()
        
        # Check for essential keywords
        for keyword in essential_keywords:
            if keyword in category_name_lower:
                return True
        
        # Avoid overly specific categories
        specific_indicators = [
            'view all', 'mini', 'exceptional', 'mr kipling', 'cadbury',
            'party', 'birthday', 'christmas', 'easter', 'toasters',
            'candles', 'badges'
        ]
        
        for indicator in specific_indicators:
            if indicator in category_name_lower:
                return False
        
        return False
    
    def _show_cleanup_plan(self, categories_to_deactivate, categories_to_keep):
        """
        Show the cleanup plan.
        
        Args:
            categories_to_deactivate: List of categories to deactivate
            categories_to_keep: List of categories to keep
        """
        try:
            self.stdout.write(f"\nCLEANUP PLAN:")
            self.stdout.write(f"="*50)
            
            self.stdout.write(f"\nCATEGORIES TO KEEP ({len(categories_to_keep)}):")
            self.stdout.write("-" * 40)
            for category, reason, priority in categories_to_keep:
                priority_str = f"(P{priority})" if priority else ""
                self.stdout.write(f"  ✓ {category.name} {priority_str} - {reason}")
            
            self.stdout.write(f"\nCATEGORIES TO DEACTIVATE ({len(categories_to_deactivate)}):")
            self.stdout.write("-" * 40)
            for category, reason in categories_to_deactivate:
                self.stdout.write(f"  ✗ {category.name} - {reason}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing cleanup plan: {e}"))
    
    def _execute_cleanup(self, categories_to_deactivate):
        """
        Execute the cleanup by deactivating categories.
        
        Args:
            categories_to_deactivate: List of categories to deactivate
        """
        try:
            if not categories_to_deactivate:
                self.stdout.write("No categories need to be deactivated.")
                return
            
            self.stdout.write(f"\nEXECUTING CLEANUP...")
            
            deactivated_count = 0
            
            with transaction.atomic():
                for category, reason in categories_to_deactivate:
                    try:
                        category.is_active = False
                        category.save(update_fields=['is_active'])
                        deactivated_count += 1
                        self.stdout.write(f"  ✗ Deactivated: {category.name}")
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Error deactivating {category.name}: {e}"))
            
            self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully deactivated {deactivated_count} categories"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error executing cleanup: {e}"))
    
    def _show_final_status(self, dry_run: bool):
        """
        Show final status after cleanup.
        
        Args:
            dry_run: Whether this was a dry run
        """
        try:
            if dry_run:
                self.stdout.write(f"\nDRY RUN COMPLETE - No changes were made")
                self.stdout.write("Run without --dry-run to execute the cleanup")
            else:
                total_categories = AsdaCategory.objects.count()
                active_categories = AsdaCategory.objects.filter(is_active=True).count()
                mapped_active = sum(1 for cat in AsdaCategory.objects.filter(is_active=True) 
                                   if validate_category_mapping(cat.url_code))
                
                self.stdout.write(f"\nFINAL STATUS:")
                self.stdout.write(f"  Total categories: {total_categories}")
                self.stdout.write(f"  Active categories: {active_categories}")
                self.stdout.write(f"  Active with mappings: {mapped_active}")
                
                if active_categories > 0 and mapped_active == active_categories:
                    self.stdout.write(self.style.SUCCESS("✓ All active categories now have proper URL mappings!"))
                elif mapped_active > 0:
                    self.stdout.write(self.style.WARNING(f"⚠ {active_categories - mapped_active} active categories still need mappings"))
                else:
                    self.stdout.write(self.style.ERROR("✗ No active categories have proper URL mappings"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing final status: {e}"))