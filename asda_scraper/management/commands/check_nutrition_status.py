"""
Django Management Command for checking nutrition crawl status.

Save this as: asda_scraper/management/commands/check_nutrition_status.py
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q, Count, F
from django.utils import timezone
from asda_scraper.models import AsdaProduct, AsdaCategory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to check the status of nutritional data collection.
    
    Shows which products need nutritional data crawling based on the 3-day rule.
    """
    
    help = 'Check which products need nutritional data crawling'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--category',
            type=str,
            help='Check specific category'
        )
        
        parser.add_argument(
            '--show-details',
            action='store_true',
            help='Show detailed product information'
        )
        
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Number of days to consider as "fresh" (default: 3)'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write(
            self.style.SUCCESS("📊 NUTRITIONAL DATA CRAWL STATUS CHECK")
        )
        
        # Calculate cutoff date
        days = options['days']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            f"\n⏰ Checking for products not updated since: "
            f"{cutoff_date.strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Get all products
        all_products = AsdaProduct.objects.all()
        
        # Apply category filter if specified
        if options['category']:
            all_products = all_products.filter(
                category__name__icontains=options['category']
            )
            self.stdout.write(f"📂 Filtering to category: {options['category']}")
        
        # Count total products
        total_products = all_products.count()
        
        # Products with nutritional data
        with_nutrition = all_products.exclude(
            Q(nutritional_info__isnull=True) | Q(nutritional_info__exact={})
        ).count()
        
        # Products needing crawl (based on 3-day rule)
        needs_crawl = all_products.filter(
            Q(updated_at__isnull=True) |  # Never updated
            Q(updated_at__lt=cutoff_date) |  # Updated more than X days ago
            Q(nutritional_info__isnull=True) |  # No nutritional info
            Q(nutritional_info__exact={})  # Empty nutritional info
        ).exclude(
            product_url=''
        ).exclude(
            product_url__isnull=True
        )
        
        needs_crawl_count = needs_crawl.count()
        
        # Recently updated products
        recently_updated = all_products.filter(
            updated_at__gte=cutoff_date,
        ).exclude(
            Q(nutritional_info__isnull=True) | Q(nutritional_info__exact={})
        ).count()
        
        # Display summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"📦 Total products: {total_products}")
        self.stdout.write(f"✅ With nutritional data: {with_nutrition}")
        self.stdout.write(f"🕐 Recently updated (last {days} days): {recently_updated}")
        self.stdout.write(f"🔄 Need crawling: {needs_crawl_count}")
        self.stdout.write(f"📈 Nutrition coverage: {(with_nutrition/total_products*100 if total_products > 0 else 0):.1f}%")
        self.stdout.write(f"{'='*60}\n")
        
        # Show category breakdown
        self._show_category_breakdown(cutoff_date)
        
        # Show details if requested
        if options['show_details'] and needs_crawl_count > 0:
            self._show_product_details(needs_crawl[:20])  # Show first 20
    
    def _show_category_breakdown(self, cutoff_date):
        """Show breakdown by category."""
        self.stdout.write("📂 BREAKDOWN BY CATEGORY:")
        self.stdout.write("-" * 60)
        
        categories = AsdaCategory.objects.annotate(
            total_products=Count('products'),
            products_with_nutrition=Count(
                'products',
                filter=~Q(products__nutritional_info__exact={})
            ),
            products_needing_crawl=Count(
                'products',
                filter=(
                    Q(products__updated_at__isnull=True) |
                    Q(products__updated_at__lt=cutoff_date) |
                    Q(products__nutritional_info__isnull=True) |
                    Q(products__nutritional_info__exact={})
                ) & ~Q(products__product_url='')
            )
        ).filter(
            total_products__gt=0
        ).order_by('-products_needing_crawl')
        
        for cat in categories[:10]:  # Show top 10
            if cat.total_products > 0:
                coverage = (cat.products_with_nutrition / cat.total_products * 100)
                self.stdout.write(
                    f"\n{cat.name}:"
                    f"\n  Total: {cat.total_products}"
                    f" | With nutrition: {cat.products_with_nutrition}"
                    f" | Need crawl: {cat.products_needing_crawl}"
                    f" | Coverage: {coverage:.1f}%"
                )
    
    def _show_product_details(self, products):
        """Show detailed information about products needing crawl."""
        self.stdout.write(f"\n\n📋 SAMPLE PRODUCTS NEEDING CRAWL:")
        self.stdout.write("-" * 60)
        
        for product in products:
            days_since_update = "Never"
            if product.updated_at:
                time_diff = timezone.now() - product.updated_at
                days_since_update = f"{time_diff.days} days ago"
            
            self.stdout.write(
                f"\n• {product.name[:50]}..."
                f"\n  Category: {product.category.name}"
                f"\n  ASDA ID: {product.asda_id}"
                f"\n  Last updated: {days_since_update}"
                f"\n  Has nutrition: {'Yes' if product.has_nutritional_info() else 'No'}"
            )