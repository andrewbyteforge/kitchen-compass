"""
Management command to set up initial ingredient categories.

This command creates default ingredient categories with keywords
for auto-categorization.
"""

import logging
from django.core.management.base import BaseCommand
from recipe_hub.models import IngredientCategory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Set up initial ingredient categories with keywords."""
    
    help = 'Creates initial ingredient categories for shopping list organization'
    
    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write("Setting up ingredient categories...")
        
        categories = [
            {
                'name': 'Produce',
                'display_order': 1,
                'keywords': 'lettuce,tomato,onion,pepper,carrot,celery,garlic,potato,broccoli,spinach,kale,cucumber,zucchini,mushroom,corn,peas,beans,apple,banana,orange,lemon,lime,strawberry,blueberry,grape,melon,avocado,herbs,basil,parsley,cilantro,mint,thyme,rosemary'
            },
            {
                'name': 'Meat & Seafood',
                'display_order': 2,
                'keywords': 'chicken,beef,pork,lamb,turkey,bacon,sausage,ham,ground meat,steak,roast,fish,salmon,tuna,shrimp,crab,lobster,scallops,mussels,oysters'
            },
            {
                'name': 'Dairy',
                'display_order': 3,
                'keywords': 'milk,cheese,yogurt,cream,butter,sour cream,cottage cheese,cream cheese,mozzarella,cheddar,parmesan,feta,ricotta,eggs,egg'
            },
            {
                'name': 'Bakery',
                'display_order': 4,
                'keywords': 'bread,roll,bun,bagel,muffin,croissant,pita,tortilla,naan,baguette,ciabatta,sourdough,whole wheat,multigrain'
            },
            {
                'name': 'Pantry',
                'display_order': 5,
                'keywords': 'flour,sugar,salt,pepper,oil,olive oil,vegetable oil,vinegar,rice,pasta,noodles,quinoa,oats,cereal,beans,lentils,chickpeas,canned,sauce,ketchup,mustard,mayo,spices,baking powder,baking soda,vanilla,chocolate'
            },
            {
                'name': 'Frozen',
                'display_order': 6,
                'keywords': 'frozen,ice cream,frozen vegetables,frozen fruit,frozen pizza,frozen meals,ice,sorbet'
            },
            {
                'name': 'Beverages',
                'display_order': 7,
                'keywords': 'water,juice,soda,coffee,tea,wine,beer,spirits,cocktail,smoothie,milk,almond milk,soy milk,coconut milk'
            },
            {
                'name': 'Snacks',
                'display_order': 8,
                'keywords': 'chips,crackers,cookies,candy,chocolate,nuts,popcorn,pretzels,granola,protein bar,fruit snacks'
            },
            {
                'name': 'Other',
                'display_order': 999,
                'keywords': ''
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for cat_data in categories:
            try:
                category, created = IngredientCategory.objects.update_or_create(
                    name=cat_data['name'],
                    defaults={
                        'display_order': cat_data['display_order'],
                        'keywords': cat_data['keywords'],
                        'is_active': True
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Created category: {category.name}")
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"Updated category: {category.name}")
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error creating category {cat_data['name']}: {str(e)}")
                )
                logger.error(f"Error creating category {cat_data['name']}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully created {created_count} and updated {updated_count} categories."
            )
        )
        
        # Auto-categorize existing ingredients
        self.stdout.write("\nAuto-categorizing existing ingredients...")
        
        from recipe_hub.models import Ingredient
        categorized_count = 0
        
        ingredients = Ingredient.objects.filter(category__isnull=True)
        total_ingredients = ingredients.count()
        
        for ingredient in ingredients:
            try:
                ingredient.auto_categorize()
                ingredient.save()
                categorized_count += 1
                
                if categorized_count % 100 == 0:
                    self.stdout.write(f"Processed {categorized_count}/{total_ingredients} ingredients...")
                    
            except Exception as e:
                logger.error(f"Error categorizing ingredient {ingredient.id}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\nAuto-categorized {categorized_count} out of {total_ingredients} ingredients."
            )
        )