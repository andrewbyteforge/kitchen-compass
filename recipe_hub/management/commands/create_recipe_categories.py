"""
Management command to create initial recipe categories.

This command populates the database with default recipe categories
that users can select when creating recipes.
"""

import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from recipe_hub.models import RecipeCategory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Create default recipe categories."""
    
    help = 'Creates initial recipe categories for the application'
    
    # Default categories with icons
    CATEGORIES = [
        {
            'name': 'Breakfast',
            'description': 'Start your day with these delicious breakfast recipes',
            'icon': 'bi-egg-fried'
        },
        {
            'name': 'Lunch',
            'description': 'Satisfying midday meals',
            'icon': 'bi-basket2'
        },
        {
            'name': 'Dinner',
            'description': 'Hearty dinner recipes for the whole family',
            'icon': 'bi-moon-stars'
        },
        {
            'name': 'Appetizers',
            'description': 'Perfect starters and party snacks',
            'icon': 'bi-diagram-3'
        },
        {
            'name': 'Desserts',
            'description': 'Sweet treats and indulgent desserts',
            'icon': 'bi-cake2'
        },
        {
            'name': 'Beverages',
            'description': 'Refreshing drinks and cocktails',
            'icon': 'bi-cup-straw'
        },
        {
            'name': 'Salads',
            'description': 'Fresh and healthy salad recipes',
            'icon': 'bi-flower1'
        },
        {
            'name': 'Soups',
            'description': 'Warming soups and stews',
            'icon': 'bi-droplet-half'
        },
        {
            'name': 'Vegetarian',
            'description': 'Meat-free recipes',
            'icon': 'bi-leaf'
        },
        {
            'name': 'Vegan',
            'description': 'Plant-based recipes without animal products',
            'icon': 'bi-tree'
        },
        {
            'name': 'Gluten-Free',
            'description': 'Recipes without gluten',
            'icon': 'bi-slash-circle'
        },
        {
            'name': 'Quick & Easy',
            'description': 'Recipes ready in 30 minutes or less',
            'icon': 'bi-lightning'
        },
        {
            'name': 'Italian',
            'description': 'Classic Italian cuisine',
            'icon': 'bi-geo-alt'
        },
        {
            'name': 'Mexican',
            'description': 'Spicy and flavorful Mexican dishes',
            'icon': 'bi-fire'
        },
        {
            'name': 'Asian',
            'description': 'Recipes from across Asia',
            'icon': 'bi-globe2'
        },
        {
            'name': 'Mediterranean',
            'description': 'Healthy Mediterranean diet recipes',
            'icon': 'bi-sun'
        },
        {
            'name': 'BBQ & Grilling',
            'description': 'Outdoor cooking and barbecue recipes',
            'icon': 'bi-grid-3x3'
        },
        {
            'name': 'Baking',
            'description': 'Breads, pastries, and baked goods',
            'icon': 'bi-bread-slice'
        },
        {
            'name': 'Seafood',
            'description': 'Fresh fish and seafood recipes',
            'icon': 'bi-water'
        },
        {
            'name': 'Holiday',
            'description': 'Special occasion and holiday recipes',
            'icon': 'bi-gift'
        }
    ]
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing categories before creating new ones',
        )
    
    @transaction.atomic
    def handle(self, *args, **options):
        """Execute the command."""
        try:
            if options['clear']:
                self.stdout.write('Clearing existing categories...')
                deleted_count = RecipeCategory.objects.all().delete()[0]
                self.stdout.write(
                    self.style.WARNING(f'Deleted {deleted_count} existing categories')
                )
                logger.info(f"Cleared {deleted_count} existing recipe categories")
            
            created_count = 0
            updated_count = 0
            
            for category_data in self.CATEGORIES:
                category, created = RecipeCategory.objects.update_or_create(
                    name=category_data['name'],
                    defaults={
                        'description': category_data['description'],
                        'icon': category_data['icon'],
                        'is_active': True
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created category: {category.name}')
                    )
                else:
                    updated_count += 1
                    self.stdout.write(f'Updated category: {category.name}')
            
            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully processed {len(self.CATEGORIES)} categories:'
                )
            )
            self.stdout.write(f'  - Created: {created_count}')
            self.stdout.write(f'  - Updated: {updated_count}')
            
            logger.info(
                f"Recipe categories processed - Created: {created_count}, "
                f"Updated: {updated_count}"
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating categories: {str(e)}')
            )
            logger.error(f"Error in create_recipe_categories command: {str(e)}")
            raise