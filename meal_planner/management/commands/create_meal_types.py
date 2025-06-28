"""
Management command to create default meal types.

This command populates the database with standard meal types
(breakfast, lunch, dinner, snack).
"""

import logging
from datetime import time
from django.core.management.base import BaseCommand
from django.db import transaction
from meal_planner.models import MealType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Create default meal types."""
    
    help = 'Creates default meal types for the application'
    
    # Default meal types with their properties
    MEAL_TYPES = [
        {
            'name': 'Breakfast',
            'display_order': 1,
            'default_time': time(7, 0),  # 7:00 AM
            'icon': 'bi-sunrise'
        },
        {
            'name': 'Lunch',
            'display_order': 2,
            'default_time': time(12, 0),  # 12:00 PM
            'icon': 'bi-sun'
        },
        {
            'name': 'Dinner',
            'display_order': 3,
            'default_time': time(18, 0),  # 6:00 PM
            'icon': 'bi-moon'
        },
        {
            'name': 'Snack',
            'display_order': 4,
            'default_time': time(15, 0),  # 3:00 PM
            'icon': 'bi-cup-straw'
        }
    ]
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing meal types with new values',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            help='Only check what meal types exist, do not create any',
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        """Execute the command."""
        force_update = options.get('force', False)
        check_only = options.get('check_only', False)
        
        # Display header
        self.stdout.write(
            self.style.HTTP_INFO(
                '=' * 60
            )
        )
        self.stdout.write(
            self.style.HTTP_INFO(
                'KitchenCompass - Meal Types Setup'
            )
        )
        self.stdout.write(
            self.style.HTTP_INFO(
                '=' * 60
            )
        )
        
        if check_only:
            self._check_meal_types()
            return
        
        try:
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            self.stdout.write(
                self.style.HTTP_INFO(
                    f'Processing {len(self.MEAL_TYPES)} meal types...\n'
                )
            )
            
            for meal_type_data in self.MEAL_TYPES:
                try:
                    if force_update:
                        # Update or create with force option
                        meal_type, created = MealType.objects.update_or_create(
                            name=meal_type_data['name'],
                            defaults={
                                'display_order': meal_type_data['display_order'],
                                'default_time': meal_type_data['default_time'],
                                'icon': meal_type_data['icon']
                            }
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Created meal type: {meal_type.name}'
                                )
                            )
                        else:
                            updated_count += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f'↻ Updated meal type: {meal_type.name}'
                                )
                            )
                    else:
                        # Only create if doesn't exist
                        meal_type, created = MealType.objects.get_or_create(
                            name=meal_type_data['name'],
                            defaults={
                                'display_order': meal_type_data['display_order'],
                                'default_time': meal_type_data['default_time'],
                                'icon': meal_type_data['icon']
                            }
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✓ Created meal type: {meal_type.name}'
                                )
                            )
                        else:
                            skipped_count += 1
                            self.stdout.write(
                                f'- Meal type already exists: {meal_type.name}'
                            )
                
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'✗ Error processing meal type {meal_type_data["name"]}: {str(e)}'
                        )
                    )
                    logger.error(
                        f"Error creating meal type {meal_type_data['name']}: {str(e)}"
                    )
            
            # Summary
            self.stdout.write('\n' + '-' * 60)
            self.stdout.write(
                self.style.SUCCESS(
                    'Meal Types Processing Summary:'
                )
            )
            self.stdout.write(f'  • Created: {created_count}')
            if force_update:
                self.stdout.write(f'  • Updated: {updated_count}')
            else:
                self.stdout.write(f'  • Skipped (already exist): {skipped_count}')
            self.stdout.write(f'  • Total processed: {len(self.MEAL_TYPES)}')
            
            # Show current meal types in database
            self._display_current_meal_types()
            
            # Log the results
            logger.info(
                f"Meal types command completed - Created: {created_count}, "
                f"Updated: {updated_count}, Skipped: {skipped_count}"
            )
            
            # Final success message
            total_in_db = MealType.objects.count()
            if created_count > 0 or updated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n🎉 Success! Your meal planner now has {total_in_db} meal types ready to use!'
                    )
                )
                self.stdout.write(
                    self.style.HTTP_INFO(
                        'You can now create meal plans that will automatically include '
                        'slots for each meal type on each day.'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ All {total_in_db} meal types are already configured correctly!'
                    )
                )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating meal types: {str(e)}')
            )
            logger.error(f"Error in create_meal_types command: {str(e)}")
            raise
    
    def _check_meal_types(self):
        """Check and display existing meal types without creating any."""
        self.stdout.write(
            self.style.HTTP_INFO(
                'Checking existing meal types (no changes will be made)...\n'
            )
        )
        
        existing_meal_types = MealType.objects.all().order_by('display_order')
        
        if existing_meal_types.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f'Found {existing_meal_types.count()} existing meal types:'
                )
            )
            self._display_current_meal_types()
        else:
            self.stdout.write(
                self.style.ERROR(
                    'No meal types found in database!'
                )
            )
            self.stdout.write(
                self.style.HTTP_INFO(
                    'Run "python manage.py create_meal_types" to create default meal types.'
                )
            )
        
        # Check if all expected meal types exist
        expected_names = {mt['name'] for mt in self.MEAL_TYPES}
        existing_names = {mt.name for mt in existing_meal_types}
        
        missing_names = expected_names - existing_names
        extra_names = existing_names - expected_names
        
        if missing_names:
            self.stdout.write(
                self.style.WARNING(
                    f'\nMissing meal types: {", ".join(missing_names)}'
                )
            )
        
        if extra_names:
            self.stdout.write(
                self.style.HTTP_INFO(
                    f'\nAdditional meal types: {", ".join(extra_names)}'
                )
            )
        
        if not missing_names and expected_names:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✅ All expected meal types are present!'
                )
            )
    
    def _display_current_meal_types(self):
        """Display current meal types in a formatted table."""
        self.stdout.write('\nCurrent meal types in database:')
        self.stdout.write('-' * 60)
        
        meal_types = MealType.objects.all().order_by('display_order')
        if meal_types.exists():
            # Table header
            self.stdout.write(
                f'{"ID":<4} {"Name":<12} {"Order":<6} {"Time":<10} {"Icon":<15}'
            )
            self.stdout.write('-' * 60)
            
            # Table rows
            for mt in meal_types:
                default_time_str = mt.default_time.strftime('%I:%M %p') if mt.default_time else 'Not set'
                self.stdout.write(
                    f'{mt.id:<4} {mt.name:<12} {mt.display_order:<6} '
                    f'{default_time_str:<10} {mt.icon:<15}'
                )
        else:
            self.stdout.write(
                self.style.ERROR('No meal types found in database!')
            )
        
        self.stdout.write('-' * 60)