"""
Django Management Command for checking nutrition crawl status.

This command checks which AsdaProduct items require nutritional data
crawling based on the freshness threshold and reports summary statistics
and optional detailed listings.
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from django.db.models import Q, Count, F
from django.utils import timezone
from asda_scraper.models import AsdaProduct, AsdaCategory

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to check nutritional data crawl status.

    Reports products needing crawling based on the specified threshold in
    days, provides a category breakdown, and optionally lists sample products.
    """
    help = 'Check which products need nutritional data crawling.'

    def add_arguments(self, parser):
        """
        Add command-line arguments for filtering and output details.

        Args:
            parser (ArgumentParser): The parser to which arguments are added.
        """
        parser.add_argument(
            '--category',
            type=str,
            help='Check specific category name (case-insensitive partial match).'
        )
        parser.add_argument(
            '--show-details',
            action='store_true',
            help='Show detailed information for sample products needing crawl.'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Number of days to consider data "fresh" (default: 3).'
        )

    def handle(self, *args, **options):
        """
        Execute the nutrition crawl status check.

        Returns:
            int: Exit code, 0 on success, non-zero on error.
        """
        days = options.get('days')
        if days is None or days < 0:
            raise CommandError(f"Invalid --days value: {days!r}")

        cutoff_date = timezone.now() - timedelta(days=days)
        self.stdout.write(self.style.SUCCESS(
            "📊 NUTRITIONAL DATA CRAWL STATUS CHECK"
        ))
        self.stdout.write(
            f"\n⏰ Checking for products not updated since: "
            f"{cutoff_date.strftime('%Y-%m-%d %H:%M')}"
        )

        try:
            products = AsdaProduct.objects.all()
            if options.get('category'):
                cat = options['category']
                products = products.filter(category__name__icontains=cat)
                self.stdout.write(f"📂 Filtering to category: {cat}")

            total = products.count()
            with_nut = products.exclude(
                Q(nutritional_info__isnull=True) |
                Q(nutritional_info__exact={})
            ).count()

            needs = products.filter(
                Q(updated_at__isnull=True) |
                Q(updated_at__lt=cutoff_date) |
                Q(nutritional_info__isnull=True) |
                Q(nutritional_info__exact={})
            ).exclude(
                Q(product_url='') | Q(product_url__isnull=True)
            )
            needs_count = needs.count()

            recent = products.filter(
                updated_at__gte=cutoff_date
            ).exclude(
                Q(nutritional_info__isnull=True) |
                Q(nutritional_info__exact={})
            ).count()

            coverage = (with_nut / total * 100) if total > 0 else 0.0

            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(f"📦 Total products: {total}")
            self.stdout.write(f"✅ With nutritional data: {with_nut}")
            self.stdout.write(f"🕐 Recently updated (last {days} days): {recent}")
            self.stdout.write(f"🔄 Need crawling: {needs_count}")
            self.stdout.write(f"📈 Coverage: {coverage:.1f}%")
            self.stdout.write("=" * 60 + "\n")

            # Breakdown and details
            self._show_category_breakdown(cutoff_date)
            if options.get('show_details') and needs_count > 0:
                self._show_product_details(needs[:20])

        except DatabaseError as db_err:
            logger.exception("Database error during nutrition status check")
            self.stderr.write(self.style.ERROR(
                f"Database error: {db_err}"
            ))
            return 1
        except Exception as exc:
            logger.exception("Unexpected error in nutrition status check")
            self.stderr.write(self.style.ERROR(
                f"Error: {exc}"
            ))
            return 1

        return 0

    def _show_category_breakdown(self, cutoff_date):
        """
        Show breakdown of nutritional crawl status by category.

        Args:
            cutoff_date (datetime): Cutoff date for stale data calculation.
        """
        self.stdout.write("📂 BREAKDOWN BY CATEGORY:")
        self.stdout.write("-" * 60)
        try:
            cats = AsdaCategory.objects.annotate(
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
            ).filter(total_products__gt=0).order_by('-products_needing_crawl')

            for cat in cats[:10]:
                cov = (cat.products_with_nutrition / cat.total_products * 100)
                self.stdout.write(
                    f"\n{cat.name}: Total={cat.total_products} | "
                    f"WithNut={cat.products_with_nutrition} | "
                    f"NeedCrawl={cat.products_needing_crawl} | "
                    f"Coverage={cov:.1f}%"
                )
        except DatabaseError as db_err:
            logger.error("DB error in _show_category_breakdown", exc_info=db_err)
            self.stderr.write(self.style.ERROR(
                "Could not retrieve category breakdown."
            ))

    def _show_product_details(self, products):
        """
        Display sample products that require nutritional data crawl.

        Args:
            products (QuerySet): Up to 20 AsdaProduct instances to display.
        """
        self.stdout.write("\n\n📋 SAMPLE PRODUCTS NEEDING CRAWL:")
        self.stdout.write("-" * 60)
        try:
            for prod in products:
                if prod.updated_at:
                    diff = timezone.now() - prod.updated_at
                    last = f"{diff.days} days ago"
                else:
                    last = "Never"

                self.stdout.write(
                    f"\n• {prod.name[:50]}...\n"
                    f"  Category: {prod.category.name}\n"
                    f"  ASDA ID: {prod.asda_id}\n"
                    f"  Last updated: {last}\n"
                    f"  Has nutrition: "
                    f"{'Yes' if prod.has_nutritional_info() else 'No'}"
                )
        except Exception as exc:
            logger.error("Error in _show_product_details", exc_info=exc)
            self.stderr.write(self.style.ERROR(
                "Could not display product details."
            ))
