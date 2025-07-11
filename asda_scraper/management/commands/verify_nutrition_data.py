import logging
from django.core.management.base import BaseCommand
from django.db.models import Q
from asda_scraper.models import AsdaProduct

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Management command to verify nutritional data integrity.
    """
    
    help = 'Verify nutritional data integrity and display statistics'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--product-id',
            type=str,
            help='Check specific product by ASDA ID'
        )
        
        parser.add_argument(
            '--category',
            type=str,
            help='Check products in specific category'
        )
        
        parser.add_argument(
            '--show-examples',
            action='store_true',
            help='Show example nutritional data'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write(
            self.style.SUCCESS("🔍 NUTRITIONAL DATA VERIFICATION")
        )
        
        if options['product_id']:
            self._verify_single_product(options['product_id'])
        elif options['category']:
            self._verify_category_products(options['category'])
        else:
            self._verify_all_products(options['show_examples'])
    
    def _verify_single_product(self, asda_id):
        """Verify a single product's nutritional data."""
        try:
            product = AsdaProduct.objects.get(asda_id=asda_id)
            
            self.stdout.write(f"\n📦 Product: {product.name}")
            self.stdout.write(f"🆔 ASDA ID: {product.asda_id}")
            self.stdout.write(f"📂 Category: {product.category.name}")
            self.stdout.write(f"🔗 URL: {product.product_url}")
            
            summary = product.get_nutritional_data_summary()
            
            if summary['has_data']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Has nutritional data: {summary['nutrient_count']} nutrients"
                    )
                )
                self.stdout.write(f"📅 Extracted: {summary['extracted_at']}")
                self.stdout.write(f"🛠️ Method: {summary['extraction_method']}")
                
                self.stdout.write("\n🧪 Nutritional Values:")
                nutrition_data = product.get_nutritional_info()
                for nutrient, value in nutrition_data.items():
                    self.stdout.write(f"  • {nutrient}: {value}")
            else:
                self.stdout.write(
                    self.style.WARNING("⚠️ No nutritional data found")
                )
                
        except AsdaProduct.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ Product with ID {asda_id} not found")
            )
    
    def _verify_category_products(self, category_name):
        """Verify nutritional data for products in a category."""
        # Fixed query - removed the slug lookup since AsdaCategory doesn't have slug field
        products = AsdaProduct.objects.filter(
            category__name__icontains=category_name
        )
        
        if not products.exists():
            self.stdout.write(
                self.style.WARNING(f"⚠️ No products found in category: {category_name}")
            )
            return
        
        total = products.count()
        with_nutrition = sum(1 for p in products if p.has_nutritional_info())
        
        self.stdout.write(f"\n📂 Category: {category_name}")
        self.stdout.write(f"📦 Total products: {total}")
        self.stdout.write(f"🧪 With nutrition data: {with_nutrition}")
        if total > 0:
            self.stdout.write(f"📈 Coverage: {(with_nutrition/total*100):.1f}%")
        
        # Show some examples
        products_with_nutrition = [p for p in products[:5] if p.has_nutritional_info()]
        if products_with_nutrition:
            self.stdout.write("\n✅ Examples with nutritional data:")
            for product in products_with_nutrition:
                nutrition_count = len(product.get_nutritional_info())
                self.stdout.write(f"  • {product.name[:50]} ({nutrition_count} nutrients)")
        
        # Show some products without nutrition data
        products_without_nutrition = [p for p in products[:5] if not p.has_nutritional_info()]
        if products_without_nutrition:
            self.stdout.write(f"\n❌ Examples WITHOUT nutritional data:")
            for product in products_without_nutrition:
                self.stdout.write(f"  • {product.name[:50]} (ID: {product.asda_id})")
                self.stdout.write(f"    🔗 URL: {product.product_url[:60]}...")





    def _verify_all_products(self, show_examples):
        """Verify nutritional data for all products."""
        total_products = AsdaProduct.objects.count()
        
        # Count products with actual nutritional data
        with_nutrition_count = 0
        products_with_data = []
        
        for product in AsdaProduct.objects.all()[:100]:  # Sample first 100 for speed
            if product.has_nutritional_info():
                with_nutrition_count += 1
                products_with_data.append(product)
        
        # Estimate total based on sample
        if total_products > 100:
            estimated_with_nutrition = int((with_nutrition_count / 100) * total_products)
        else:
            estimated_with_nutrition = with_nutrition_count
        
        self.stdout.write(f"\n📊 OVERALL STATISTICS:")
        self.stdout.write(f"📦 Total products: {total_products}")
        self.stdout.write(f"🧪 With nutrition data: {estimated_with_nutrition}")
        if total_products > 0:
            self.stdout.write(f"📈 Coverage: {(estimated_with_nutrition/total_products*100):.1f}%")
        
        if show_examples and products_with_data:
            self.stdout.write(f"\n✅ Example products with nutritional data:")
            
            for product in products_with_data[:5]:
                nutrition_data = product.get_nutritional_info()
                self.stdout.write(f"\n📦 {product.name[:50]}")
                self.stdout.write(f"  🆔 ID: {product.asda_id}")
                self.stdout.write(f"  🧪 Nutrients: {len(nutrition_data)}")
                for nutrient, value in list(nutrition_data.items())[:3]:  # Show first 3
                    self.stdout.write(f"    • {nutrient}: {value}")
                if len(nutrition_data) > 3:
                    self.stdout.write(f"    ... and {len(nutrition_data) - 3} more")
        
        # Show some products that need nutrition data
        products_without_nutrition = AsdaProduct.objects.filter(
            product_url__isnull=False
        ).exclude(product_url='')[:5]
        
        if products_without_nutrition:
            self.stdout.write(f"\n❌ Example products that need nutritional data:")
            for product in products_without_nutrition:
                if not product.has_nutritional_info():
                    self.stdout.write(f"  • {product.name[:50]} (ID: {product.asda_id})")
                    self.stdout.write(f"    📂 Category: {product.category.name}")
                    self.stdout.write(f"    🔗 Has URL: {'Yes' if product.product_url else 'No'}")
                    break