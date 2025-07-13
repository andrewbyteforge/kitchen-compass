"""
Debug what product URLs are actually in the database.

File: asda_scraper/management/commands/debug_product_urls.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError

from asda_scraper.models import AsdaProduct

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Debug what product URLs are in the database.
    """
    
    help = 'Show actual product URLs in database to debug blank page issues'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of products to show (default: 10)'
        )
        parser.add_argument(
            '--show-nutrition',
            action='store_true',
            help='Show nutrition status for each product'
        )
    
    def handle(self, *args, **options):
        """Execute the debug command."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("🔍 DEBUG PRODUCT URLs"))
            self.stdout.write("="*60)
            
            limit = options['limit']
            show_nutrition = options['show_nutrition']
            
            # Check total products
            total_products = AsdaProduct.objects.count()
            self.stdout.write(f"📦 Total products in database: {total_products}")
            
            # Check products with URLs
            products_with_urls = AsdaProduct.objects.filter(
                product_url__isnull=False
            ).exclude(product_url='')
            
            url_count = products_with_urls.count()
            self.stdout.write(f"🔗 Products with URLs: {url_count}")
            
            if url_count == 0:
                self.stdout.write(self.style.ERROR("❌ No products with URLs found!"))
                self.stdout.write("   This explains why the nutrition test shows blank pages.")
                self.stdout.write("   You need to run the product crawler first to populate URLs.")
                return
            
            # Show sample URLs
            self.stdout.write(f"\n📋 Sample URLs (showing {min(limit, url_count)}):")
            self.stdout.write("="*60)
            
            for i, product in enumerate(products_with_urls[:limit], 1):
                self.stdout.write(f"\n{i}. {product.name[:50]}")
                self.stdout.write(f"   🆔 ASDA ID: {product.asda_id}")
                self.stdout.write(f"   🔗 URL: {product.product_url}")
                self.stdout.write(f"   📂 Category: {product.category.name}")
                self.stdout.write(f"   💰 Price: £{product.price}")
                
                # Check URL format
                url = product.product_url
                if "groceries.asda.com" in url:
                    self.stdout.write("   ✅ Valid ASDA domain")
                else:
                    self.stdout.write(f"   ⚠️  Unexpected domain: {url}")
                
                if "/product/" in url:
                    self.stdout.write("   ✅ Product URL format")
                else:
                    self.stdout.write("   ⚠️  Unexpected URL format")
                
                # Check nutrition status if requested
                if show_nutrition:
                    if hasattr(product, 'has_nutritional_info') and product.has_nutritional_info():
                        nutrition_data = product.get_nutritional_info()
                        self.stdout.write(f"   🧪 Nutrition: ✅ ({len(nutrition_data)} items)")
                    else:
                        self.stdout.write("   🧪 Nutrition: ❌ None")
            
            # Analyze URL patterns
            self.stdout.write(f"\n📊 URL ANALYSIS:")
            self.stdout.write("="*40)
            
            # Check domains
            domains = {}
            url_formats = {}
            
            for product in products_with_urls[:100]:  # Sample first 100
                url = product.product_url
                
                # Extract domain
                if "://" in url:
                    domain = url.split("://")[1].split("/")[0]
                    domains[domain] = domains.get(domain, 0) + 1
                
                # Check format
                if "/product/" in url:
                    url_formats["product_page"] = url_formats.get("product_page", 0) + 1
                elif "/search" in url:
                    url_formats["search_page"] = url_formats.get("search_page", 0) + 1
                elif "/category" in url or "/dept/" in url:
                    url_formats["category_page"] = url_formats.get("category_page", 0) + 1
                else:
                    url_formats["other"] = url_formats.get("other", 0) + 1
            
            # Show domain analysis
            self.stdout.write("🌐 Domains found:")
            for domain, count in domains.items():
                self.stdout.write(f"   • {domain}: {count} URLs")
            
            # Show format analysis
            self.stdout.write("\n📋 URL formats:")
            for format_type, count in url_formats.items():
                self.stdout.write(f"   • {format_type}: {count} URLs")
            
            # Check for issues
            self.stdout.write(f"\n⚠️  POTENTIAL ISSUES:")
            
            if "product_page" not in url_formats or url_formats["product_page"] == 0:
                self.stdout.write("   ❌ No product detail page URLs found")
                self.stdout.write("      URLs should contain '/product/' for nutrition extraction")
            
            if any(domain != "groceries.asda.com" for domain in domains.keys()):
                self.stdout.write("   ⚠️  Non-ASDA domains found")
                self.stdout.write("      All URLs should be from groceries.asda.com")
            
            if url_formats.get("other", 0) > 0:
                self.stdout.write(f"   ⚠️  {url_formats['other']} URLs with unexpected formats")
            
            # Recommendations
            self.stdout.write(f"\n💡 RECOMMENDATIONS:")
            
            if url_formats.get("product_page", 0) > 0:
                self.stdout.write("   ✅ You have product URLs - nutrition extraction should work")
                self.stdout.write("   📝 Try testing with a specific product URL:")
                
                # Get a good example URL
                good_product = None
                for product in products_with_urls[:10]:
                    if "/product/" in product.product_url and "groceries.asda.com" in product.product_url:
                        good_product = product
                        break
                
                if good_product:
                    self.stdout.write(f"      python manage.py test_nutrition_speed --test-url \"{good_product.product_url}\"")
            else:
                self.stdout.write("   ❌ No product detail URLs found")
                self.stdout.write("   📝 Run product crawler first:")
                self.stdout.write("      python manage.py run_asda_crawl --crawl-type PRODUCT")
            
        except Exception as e:
            logger.error(f"Debug command failed: {e}")
            raise CommandError(f"Debug failed: {e}")