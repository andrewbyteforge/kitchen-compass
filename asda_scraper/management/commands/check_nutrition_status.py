"""
Management command to check nutrition status of products in the database.

File: asda_scraper/management/commands/check_nutrition_status.py
"""

import json
from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from django.utils import timezone

from asda_scraper.models import AsdaProduct, AsdaCategory


class Command(BaseCommand):
    """Check the nutrition status of products in the database."""
    
    help = 'Check nutrition status of products and show what needs crawling'
    
    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('NUTRITION STATUS CHECK'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        # Total products
        total_products = AsdaProduct.objects.count()
        self.stdout.write(f"\nTotal products in database: {total_products}")
        
        # Products with URLs
        with_urls = AsdaProduct.objects.filter(
            product_url__isnull=False,
            product_url__gt=''
        ).exclude(product_url='').count()
        self.stdout.write(f"Products with URLs: {with_urls}")
        
        # Products with nutrition info
        with_nutrition = AsdaProduct.objects.filter(
            nutritional_info__isnull=False
        ).exclude(
            Q(nutritional_info__exact={}) | Q(nutritional_info={})
        ).count()
        self.stdout.write(f"Products with nutrition info: {with_nutrition}")
        
        # Check actual nutrition content
        products_with_real_nutrition = 0
        products_with_empty_nutrition = 0
        products_with_partial_nutrition = 0
        
        for product in AsdaProduct.objects.filter(nutritional_info__isnull=False):
            if isinstance(product.nutritional_info, dict):
                nutrition_data = product.nutritional_info.get('nutrition', {})
                if nutrition_data:
                    nutrient_count = len(nutrition_data)
                    if nutrient_count >= 5:
                        products_with_real_nutrition += 1
                    elif nutrient_count > 0:
                        products_with_partial_nutrition += 1
                else:
                    products_with_empty_nutrition += 1
        
        self.stdout.write(f"\nNutrition data quality:")
        self.stdout.write(f"  - Full nutrition (5+ nutrients): {products_with_real_nutrition}")
        self.stdout.write(f"  - Partial nutrition (1-4 nutrients): {products_with_partial_nutrition}")
        self.stdout.write(f"  - Empty nutrition data: {products_with_empty_nutrition}")
        
        # Products that need nutrition crawling
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        
        needs_nutrition = AsdaProduct.objects.filter(
            product_url__isnull=False,
            product_url__gt=''
        ).exclude(
            product_url=''
        ).filter(
            Q(nutritional_info__isnull=True) | 
            Q(nutritional_info__exact={}) |
            Q(nutritional_info={}) |
            Q(updated_at__lt=three_days_ago)
        )
        
        # Exclude products with good nutrition data
        products_needing_nutrition = []
        for product in needs_nutrition:
            if isinstance(product.nutritional_info, dict):
                nutrition_data = product.nutritional_info.get('nutrition', {})
                if nutrition_data and len(nutrition_data) >= 5:
                    continue  # Skip products with good nutrition
            products_needing_nutrition.append(product)
        
        self.stdout.write(f"\nProducts needing nutrition crawl: {len(products_needing_nutrition)}")
        
        # Show breakdown by category
        category_counts = {}
        for product in products_needing_nutrition[:1000]:  # Limit to first 1000
            cat_name = product.category.name
            if cat_name not in category_counts:
                category_counts[cat_name] = 0
            category_counts[cat_name] += 1
        
        self.stdout.write("\nTop categories needing nutrition:")
        for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            self.stdout.write(f"  - {category}: {count} products")
        
        # Show some example products
        self.stdout.write("\nExample products needing nutrition:")
        for product in products_needing_nutrition[:5]:
            self.stdout.write(f"  - {product.name[:60]}...")
            self.stdout.write(f"    Category: {product.category.name}")
            self.stdout.write(f"    URL: {product.product_url}")
            self.stdout.write(f"    Current nutrition: {product.nutritional_info}")
            self.stdout.write("")
        
        # Recommendations
        self.stdout.write(self.style.SUCCESS("\nRECOMMENDATIONS:"))
        
        if len(products_needing_nutrition) > 0:
            self.stdout.write("1. Run nutrition crawler from dashboard or command line:")
            self.stdout.write("   python manage.py crawl_nutrition --max-products 50")
            
            # Find best category to crawl
            if category_counts:
                best_category = max(category_counts.items(), key=lambda x: x[1])[0]
                self.stdout.write(f"\n2. Focus on '{best_category}' category for best results:")
                self.stdout.write(f"   python manage.py crawl_nutrition --category \"{best_category}\" --max-products 20")
        else:
            self.stdout.write("All products with URLs already have nutrition data!")
            self.stdout.write("Consider:")
            self.stdout.write("1. Running a product crawl first to get more products")
            self.stdout.write("2. Force recrawling with: python manage.py crawl_nutrition --force-recrawl")