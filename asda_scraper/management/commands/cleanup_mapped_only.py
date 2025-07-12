"""
Django management command to aggressively cleanup categories to essential mapped ones only.

File: asda_scraper/management/commands/cleanup_mapped_only.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from asda_scraper.models import AsdaCategory
from asda_scraper.scrapers.config import ASDA_CATEGORY_MAPPINGS, validate_category_mapping

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to keep only categories that have proper URL mappings.
    
    This command deactivates all categories that don't have corresponding
    entries in ASDA_CATEGORY_MAPPINGS to eliminate "No URL slug found" warnings.
    """
    
    help = 'Keep only categories with proper URL mappings'
    
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
            '--keep-priority',
            type=int,
            default=2,
            help='Only keep mapped categories with priority <= this value (default: 2)',
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
            self.stdout.write(self.style.SUCCESS('AGGRESSIVE CATEGORY CLEANUP - MAPPED ONLY'))
            self.stdout.write(self.style.SUCCESS('='*70))
            
            dry_run = options['dry_run']
            keep_priority = options['keep_priority']
            
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
            
            # Show current status
            self._show_current_status()
            
            # Analyze categories
            categories_to_keep, categories_to_deactivate = self._analyze_categories(keep_priority)
            
            # Show cleanup plan
            self._show_cleanup_plan(categories_to_keep, categories_to_deactivate)
            
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
            
            # Count how many active categories have mappings
            mapped_active = 0
            for category in AsdaCategory.objects.filter(is_active=True):
                if validate_category_mapping(category.url_code):
                    mapped_active += 1
            
            self.stdout.write(f"\nCURRENT STATUS:")
            self.stdout.write(f"  Total categories in database: {total_categories}")
            self.stdout.write(f"  Active categories: {active_categories}")
            self.stdout.write(f"  Categories in mappings config: {mapped_categories}")
            self.stdout.write(f"  Active categories with mappings: {mapped_active}")
            self.stdout.write(f"  Active categories WITHOUT mappings: {active_categories - mapped_active}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing current status: {e}"))
    
    def _analyze_categories(self, keep_priority: int):
        """
        Analyze categories to determine what to keep and what to deactivate.
        
        Args:
            keep_priority: Maximum priority level to keep
            
        Returns:
            tuple: (categories_to_keep, categories_to_deactivate)
        """
        try:
            categories_to_keep = []
            categories_to_deactivate = []
            
            all_active_categories = AsdaCategory.objects.filter(is_active=True)
            
            for category in all_active_categories:
                # Check if category has proper mapping
                if validate_category_mapping(category.url_code):
                    cat_info = ASDA_CATEGORY_MAPPINGS[category.url_code]
                    priority = cat_info.get('priority', 5)
                    
                    # Check if we should skip this category
                    skip_validation = cat_info.get('skip_validation', False)
                    
                    if priority <= keep_priority and not skip_validation:
                        categories_to_keep.append((category, f'Has mapping (P{priority})', priority))
                    else:
                        reason = f'Priority {priority} > {keep_priority}' if priority > keep_priority else 'Marked for skipping'
                        categories_to_deactivate.append((category, reason))
                else:
                    # No mapping found - deactivate
                    categories_to_deactivate.append((category, 'No URL mapping found'))
            
            return categories_to_keep, categories_to_deactivate
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error analyzing categories: {e}"))
            return [], []
    
    def _show_cleanup_plan(self, categories_to_keep, categories_to_deactivate):
        """
        Show the cleanup plan.
        
        Args:
            categories_to_keep: List of categories to keep
            categories_to_deactivate: List of categories to deactivate
        """
        try:
            self.stdout.write(f"\nCLEANUP PLAN:")
            self.stdout.write(f"="*50)
            
            self.stdout.write(f"\nCATEGORIES TO KEEP ({len(categories_to_keep)}):")
            self.stdout.write("-" * 40)
            if categories_to_keep:
                for category, reason, priority in categories_to_keep:
                    self.stdout.write(f"  ✓ {category.name} - {reason}")
            else:
                self.stdout.write("  (none)")
            
            self.stdout.write(f"\nCATEGORIES TO DEACTIVATE ({len(categories_to_deactivate)}):")
            self.stdout.write("-" * 40)
            if categories_to_deactivate:
                for category, reason in categories_to_deactivate:
                    self.stdout.write(f"  ✗ {category.name} - {reason}")
            else:
                self.stdout.write("  (none)")
                
            # Show summary
            self.stdout.write(f"\nSUMMARY:")
            self.stdout.write(f"  Will keep: {len(categories_to_keep)} categories")
            self.stdout.write(f"  Will deactivate: {len(categories_to_deactivate)} categories")
            
            if len(categories_to_keep) == 0:
                self.stdout.write(self.style.ERROR("  ⚠️  WARNING: No categories will remain active!"))
            elif len(categories_to_keep) < 5:
                self.stdout.write(self.style.WARNING(f"  ⚠️  Only {len(categories_to_keep)} categories will remain active"))
            else:
                self.stdout.write(self.style.SUCCESS(f"  ✓ {len(categories_to_keep)} categories will remain active"))
                
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
                
                # Count mapped active categories
                mapped_active = 0
                for category in AsdaCategory.objects.filter(is_active=True):
                    if validate_category_mapping(category.url_code):
                        mapped_active += 1
                
                self.stdout.write(f"\nFINAL STATUS:")
                self.stdout.write(f"  Total categories: {total_categories}")
                self.stdout.write(f"  Active categories: {active_categories}")
                self.stdout.write(f"  Active with mappings: {mapped_active}")
                self.stdout.write(f"  Active without mappings: {active_categories - mapped_active}")
                
                if active_categories > 0 and mapped_active == active_categories:
                    self.stdout.write(self.style.SUCCESS("✓ ALL active categories now have proper URL mappings!"))
                    self.stdout.write(self.style.SUCCESS("✓ Ready for reliable crawling!"))
                elif mapped_active > 0:
                    self.stdout.write(self.style.WARNING(f"⚠ {active_categories - mapped_active} active categories still need mappings"))
                else:
                    self.stdout.write(self.style.ERROR("✗ No active categories have proper URL mappings"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing final status: {e}"))