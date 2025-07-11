# Step 1: Management command to clean up and focus on target categories
# Save as: asda_scraper/management/commands/setup_target_categories.py

"""
Django Management Command to set up target categories for KitchenCompass.

This command:
1. Removes baby/toddler products
2. Sets up only the categories needed for meal planning
3. Ensures proper category configuration
"""

import logging
from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from django.db import transaction
from asda_scraper.models import AsdaCategory, AsdaProduct

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Set up target categories and clean database for KitchenCompass'
    
    # Target categories based on the URLs provided
    TARGET_CATEGORIES = {
        '1215686352935': {
            'name': 'Fruit, Veg & Flowers',
            'slug': 'fruit-veg-flowers',
            'url': 'https://groceries.asda.com/cat/fruit-veg-flowers/1215686352935'
        },
        '1215135760597': {
            'name': 'Meat, Poultry & Fish',
            'slug': 'meat-poultry-fish',
            'url': 'https://groceries.asda.com/cat/meat-poultry-fish/1215135760597'
        },
        '1215686354843': {
            'name': 'Bakery',
            'slug': 'bakery',
            'url': 'https://groceries.asda.com/cat/bakery/1215686354843'
        },
        '1215660378320': {
            'name': 'Chilled Food',
            'slug': 'chilled-food',
            'url': 'https://groceries.asda.com/cat/chilled-food/1215660378320'
        },
        '1215338621416': {
            'name': 'Frozen Food',
            'slug': 'frozen-food',
            'url': 'https://groceries.asda.com/cat/frozen-food/1215338621416'
        },
        '1215337189632': {
            'name': 'Food Cupboard',
            'slug': 'food-cupboard',
            'url': 'https://groceries.asda.com/cat/food-cupboard/1215337189632'
        },
        '1215686356579': {
            'name': 'Sweets, Treats & Snacks',
            'slug': 'sweets-treats-snacks',
            'url': 'https://groceries.asda.com/cat/sweets-treats-snacks/1215686356579'
        },
        '1215686355606': {
            'name': 'Dietary & Lifestyle',
            'slug': 'dietary-lifestyle',
            'url': 'https://groceries.asda.com/cat/dietary-lifestyle/1215686355606'
        },
        '1215135760614': {
            'name': 'Drinks',
            'slug': 'drinks',
            'url': 'https://groceries.asda.com/cat/drinks/1215135760614'
        },
        '1215685911554': {
            'name': 'Beer, Wine & Spirits',
            'slug': 'beer-wine-spirits',
            'url': 'https://groceries.asda.com/cat/beer-wine-spirits/1215685911554'
        },
        '1215686351451': {
            'name': 'World Food',
            'slug': 'world-food',
            'url': 'https://groceries.asda.com/cat/world-food/1215686351451'
        }
    }
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-unwanted',
            action='store_true',
            help='Delete all baby/toddler/non-food products'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up target categories for KitchenCompass'))
        
        dry_run = options['dry_run']
        delete_unwanted = options['delete_unwanted']
        
        # Step 1: Delete unwanted products
        if delete_unwanted:
            self._delete_unwanted_products(dry_run)
        
        # Step 2: Deactivate non-target categories
        self._deactivate_non_target_categories(dry_run)
        
        # Step 3: Create/update target categories
        self._setup_target_categories(dry_run)
        
        # Step 4: Show summary
        self._show_summary()
    
    def _delete_unwanted_products(self, dry_run):
        """Delete baby/toddler/non-food products."""
        self.stdout.write('\n🗑️  Removing unwanted products...')
        
        # Define unwanted product filters
        unwanted_filters = Q()
        unwanted_keywords = [
            'baby', 'toddler', 'kids', 'infant', 'nappy', 'diaper',
            'month', 'maternity', 'pregnancy', 'nursery', 'pram',
            'pushchair', 'bottle', 'dummy', 'sippy', 'teething'
        ]
        
        for keyword in unwanted_keywords:
            unwanted_filters |= Q(name__icontains=keyword)
            unwanted_filters |= Q(category__name__icontains=keyword)
        
        # Also exclude non-food categories
        non_food_categories = [
            'household', 'cleaning', 'laundry', 'pet', 'toiletries',
            'beauty', 'health', 'wellness', 'pharmacy', 'home', 'garden'
        ]
        
        for category in non_food_categories:
            unwanted_filters |= Q(category__name__icontains=category)
        
        unwanted_products = AsdaProduct.objects.filter(unwanted_filters)
        count = unwanted_products.count()
        
        if dry_run:
            self.stdout.write(f'Would delete {count} unwanted products')
        else:
            deleted = unwanted_products.delete()
            self.stdout.write(self.style.SUCCESS(f'✅ Deleted {deleted[0]} unwanted products'))
    
    def _deactivate_non_target_categories(self, dry_run):
        """Deactivate categories not in our target list."""
        self.stdout.write('\n🔧 Configuring categories...')
        
        target_codes = set(self.TARGET_CATEGORIES.keys())
        non_target_categories = AsdaCategory.objects.exclude(url_code__in=target_codes)
        
        count = non_target_categories.count()
        if dry_run:
            self.stdout.write(f'Would deactivate {count} non-target categories')
        else:
            updated = non_target_categories.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'✅ Deactivated {updated} non-target categories'))
    
    def _setup_target_categories(self, dry_run):
        """Create or update target categories."""
        self.stdout.write('\n📁 Setting up target categories...')
        
        for url_code, info in self.TARGET_CATEGORIES.items():
            if dry_run:
                self.stdout.write(f'Would create/update: {info["name"]}')
            else:
                category, created = AsdaCategory.objects.update_or_create(
                    url_code=url_code,
                    defaults={
                        'name': info['name'],
                        'is_active': True,
                    }
                )
                action = 'Created' if created else 'Updated'
                self.stdout.write(f'✅ {action}: {category.name}')
    
    def _show_summary(self):
        """Show database summary."""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 DATABASE SUMMARY')
        self.stdout.write('='*60)
        
        # Category stats
        total_categories = AsdaCategory.objects.count()
        active_categories = AsdaCategory.objects.filter(is_active=True).count()
        
        self.stdout.write(f'Total categories: {total_categories}')
        self.stdout.write(f'Active categories: {active_categories}')
        
        # Product stats
        total_products = AsdaProduct.objects.count()
        products_with_nutrition = AsdaProduct.objects.exclude(nutritional_info={}).count()
        
        self.stdout.write(f'\nTotal products: {total_products}')
        self.stdout.write(f'Products with nutrition: {products_with_nutrition}')
        self.stdout.write(f'Products needing nutrition: {total_products - products_with_nutrition}')
        
        # Show active categories
        self.stdout.write('\n🎯 Active Categories:')
        for cat in AsdaCategory.objects.filter(is_active=True).annotate(
            product_count=Count('products')
        ).order_by('name'):
            self.stdout.write(f'  • {cat.name}: {cat.product_count} products')


# Step 2: Run the setup command
# python manage.py setup_target_categories --delete-unwanted

# Step 3: Update the selenium_scraper.py file
# Replace the ASDA_CATEGORY_MAPPINGS in selenium_scraper.py with this:

ASDA_CATEGORY_MAPPINGS = {
    # Food Categories for KitchenCompass
    '1215686352935': {
        'name': 'Fruit, Veg & Flowers',
        'slug': 'fruit-veg-flowers',
        'priority': 1,
    },
    '1215135760597': {
        'name': 'Meat, Poultry & Fish',
        'slug': 'meat-poultry-fish',
        'priority': 1,
    },
    '1215686354843': {
        'name': 'Bakery',
        'slug': 'bakery',
        'priority': 1,
    },
    '1215660378320': {
        'name': 'Chilled Food',
        'slug': 'chilled-food',
        'priority': 1,
    },
    '1215338621416': {
        'name': 'Frozen Food',
        'slug': 'frozen-food',
        'priority': 1,
    },
    '1215337189632': {
        'name': 'Food Cupboard',
        'slug': 'food-cupboard',
        'priority': 1,
    },
    '1215686356579': {
        'name': 'Sweets, Treats & Snacks',
        'slug': 'sweets-treats-snacks',
        'priority': 2,
    },
    '1215686355606': {
        'name': 'Dietary & Lifestyle',
        'slug': 'dietary-lifestyle',
        'priority': 1,
    },
    '1215135760614': {
        'name': 'Drinks',
        'slug': 'drinks',
        'priority': 2,
    },
    '1215685911554': {
        'name': 'Beer, Wine & Spirits',
        'slug': 'beer-wine-spirits',
        'priority': 3,
    },
    '1215686351451': {
        'name': 'World Food',
        'slug': 'world-food',
        'priority': 2,
    }
}

# Step 4: Create a focused crawler command
# Save as: asda_scraper/management/commands/crawl_food_categories.py

"""
Crawl only food categories with products and nutrition.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from asda_scraper.models import AsdaCategory, AsdaProduct, CrawlSession
from asda_scraper.selenium_scraper import create_selenium_scraper
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Crawl food categories with product and nutrition data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--products-only',
            action='store_true',
            help='Only crawl products, skip nutrition'
        )
        parser.add_argument(
            '--nutrition-only',
            action='store_true',
            help='Only crawl nutrition for existing products'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Crawl specific category by name or code'
        )
    
    def handle(self, *args, **options):
        # Get active categories
        categories = AsdaCategory.objects.filter(is_active=True)
        
        if options['category']:
            categories = categories.filter(
                Q(name__icontains=options['category']) |
                Q(url_code=options['category'])
            )
        
        self.stdout.write(f'Found {categories.count()} categories to crawl')
        
        # Create crawl session
        user, _ = User.objects.get_or_create(
            username='food_crawler',
            defaults={'email': 'crawler@kitchencompass.com'}
        )
        
        session = CrawlSession.objects.create(
            user=user,
            status='PENDING',
            notes='Food category crawl',
            crawl_settings={
                'categories': list(categories.values_list('url_code', flat=True)),
                'include_nutrition': not options['products_only'],
                'max_products_per_category': 200,
            }
        )
        
        # Run crawler
        scraper = create_selenium_scraper(session, headless=False)
        result = scraper.crawl()
        
        self.stdout.write(f'Crawl completed: {result.products_saved} products saved')