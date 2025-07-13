"""
Check what product categories are in the database.

File: asda_scraper/management/commands/check_product_categories.py
"""

import logging
from django.core.management.base import BaseCommand
from django.db.models import Count

from asda_scraper.models import AsdaProduct, AsdaCategory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Check what product categories are in the database.
    """
    
    help = 'Show product categories and suggest which are likely to have nutrition data'
    
    def handle(self, *args, **options):
        """Execute the command."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("📂 PRODUCT CATEGORIES ANALYSIS"))
            self.stdout.write("="*60)
            
            # Get categories with product counts
            categories = AsdaCategory.objects.annotate(
                product_count=Count('products')
            ).filter(product_count__gt=0).order_by('-product_count')
            
            total_categories = categories.count()
            self.stdout.write(f"📊 Total categories with products: {total_categories}")
            
            # Categories likely to have nutrition data
            nutrition_likely_categories = [
                'bakery', 'bread', 'cereal', 'biscuit', 'cake', 'pasta', 'rice',
                'meat', 'fish', 'chicken', 'beef', 'pork', 'dairy', 'milk', 'cheese',
                'yogurt', 'butter', 'snack', 'crisp', 'chocolate', 'sweet', 'candy',
                'sauce', 'soup', 'tin', 'can', 'jar', 'frozen', 'ready meal',
                'pizza', 'pie', 'sandwich', 'drink', 'juice', 'water', 'wine', 'beer'
            ]
            
            # Categories unlikely to have nutrition data
            nutrition_unlikely_categories = [
                'fruit', 'veg', 'vegetable', 'flower', 'plant', 'fresh', 'organic',
                'banana', 'apple', 'orange', 'potato', 'onion', 'carrot', 'lettuce'
            ]
            
            self.stdout.write(f"\n📋 CATEGORIES (showing all {total_categories}):")
            self.stdout.write("="*60)
            
            likely_count = 0
            unlikely_count = 0
            
            for i, category in enumerate(categories, 1):
                category_name_lower = category.name.lower()
                
                # Determine likelihood of nutrition data
                is_likely = any(term in category_name_lower for term in nutrition_likely_categories)
                is_unlikely = any(term in category_name_lower for term in nutrition_unlikely_categories)
                
                if is_likely:
                    likely_icon = "🧪✅"
                    likely_count += category.product_count
                elif is_unlikely:
                    likely_icon = "🧪❌"
                    unlikely_count += category.product_count
                else:
                    likely_icon = "🧪❓"
                
                self.stdout.write(f"{i:2d}. {category.name} ({category.product_count} products) {likely_icon}")
            
            # Summary
            self.stdout.write("\n" + "="*60)
            self.stdout.write("📊 NUTRITION DATA LIKELIHOOD SUMMARY")
            self.stdout.write("="*60)
            
            total_products = sum(cat.product_count for cat in categories)
            
            self.stdout.write(f"🧪✅ Likely to have nutrition: {likely_count} products")
            self.stdout.write(f"🧪❌ Unlikely to have nutrition: {unlikely_count} products")
            self.stdout.write(f"🧪❓ Unknown likelihood: {total_products - likely_count - unlikely_count} products")
            
            if likely_count > 0:
                self.stdout.write(f"\n💡 RECOMMENDATION:")
                self.stdout.write("   Focus nutrition extraction on categories marked with 🧪✅")
                self.stdout.write("   These processed foods are more likely to have nutrition labels")
                
                # Show command to crawl more categories
                self.stdout.write(f"\n📝 To get more products with nutrition data, crawl these categories:")
                good_categories = [cat for cat in categories if any(term in cat.name.lower() for term in nutrition_likely_categories)]
                
                if good_categories:
                    example_category = good_categories[0].name
                    self.stdout.write(f"   python manage.py run_asda_crawl --crawl-type PRODUCT --category \"{example_category}\"")
                
            else:
                self.stdout.write(f"\n⚠️  WARNING:")
                self.stdout.write("   You mostly have fresh produce which rarely has nutrition data")
                self.stdout.write("   Consider crawling processed food categories:")
                self.stdout.write("   • Bakery & Cakes")
                self.stdout.write("   • Meat, Fish & Poultry") 
                self.stdout.write("   • Dairy, Eggs & Chilled")
                self.stdout.write("   • Tins, Cans & Packets")
                
        except Exception as e:
            logger.error(f"Category check failed: {e}")
            self.stdout.write(self.style.ERROR(f"Command failed: {e}"))