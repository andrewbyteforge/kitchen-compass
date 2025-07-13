"""
Django management command to run the product list crawler.

Usage:
    python manage.py run_product_list_crawler [--limit N]
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from asda_scraper.models import CrawlSession, CrawlQueue, Category
from asda_scraper.scrapers import ProductListCrawler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to run the ASDA product list crawler."""

    help = 'Run the ASDA product list crawler to extract products from category pages'

    def add_arguments(self, parser):
        """
        Add command line arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of categories to process',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force run even if another crawler is active',
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Process only specific category by name',
        )

    def handle(self, *args, **options):
        """
        Handle the command execution.

        Args:
            *args: Positional arguments
            **options: Command options
        """
        try:
            self.stdout.write("Starting ASDA Product List Crawler...")
            logger.info("Product list crawler command initiated")

            # Check if crawler is already running
            if not options['force']:
                active_session = CrawlSession.objects.filter(
                    crawler_type='PRODUCT_LIST',
                    status='RUNNING'
                ).exists()

                if active_session:
                    raise CommandError(
                        "Product list crawler is already running. "
                        "Use --force to override."
                    )

            # Check queue status
            pending_count = CrawlQueue.objects.filter(
                queue_type='PRODUCT_LIST',
                status='PENDING'
            ).count()

            if pending_count == 0:
                self.stdout.write(
                    self.style.WARNING(
                        "No pending URLs in product list queue. "
                        "Run category mapper first."
                    )
                )
                return

            self.stdout.write(
                f"Found {pending_count} pending categories in queue"
            )

            # Show category statistics
            total_categories = Category.objects.filter(is_active=True).count()
            self.stdout.write(
                f"Total active categories: {total_categories}"
            )

            # Apply filters if specified
            raw_limit = options.get('limit')
            if raw_limit is None:
                limit = pending_count
            else:
                limit = raw_limit
            if options.get('category'):
                # Filter by category name
                category_name = options['category']
                filtered_count = CrawlQueue.objects.filter(
                    queue_type='PRODUCT_LIST',
                    status='PENDING',
                    category__name__icontains=category_name
                ).count()
                
                if filtered_count == 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"No pending categories matching '{category_name}'"
                        )
                    )
                    return
                
                limit = min(limit, filtered_count)
                self.stdout.write(
                    f"Processing {limit} categories matching '{category_name}'"
                )

            # Create new crawl session
            session = CrawlSession.objects.create(
                crawler_type='PRODUCT_LIST',
                status='RUNNING',
                started_at=timezone.now(),
                total_items=min(pending_count, limit)
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created crawl session ID: {session.id}"
                )
            )

            # Initialize and run crawler
            crawler = ProductListCrawler(session=session)
            
            # Apply limit if specified
            if options.get('limit'):
                crawler.limit = options['limit']
            
            # Apply category filter if specified
            if options.get('category'):
                crawler.category_filter = options['category']
            
            # Run the crawler
            crawler.run()

            # Report results
            session.refresh_from_db()
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nProduct list crawling completed!\n"
                    f"Status: {session.status}\n"
                    f"Duration: {session.duration}\n"
                    f"Processed: {session.processed_items}\n"
                    f"Failed: {session.failed_items}\n"
                    f"Success Rate: {session.success_rate:.1f}%\n"
                    f"Products Found: {getattr(crawler, 'products_found', 0)}"
                )
            )

            # Show product statistics
            from asda_scraper.models import Product
            total_products = Product.objects.count()
            new_products = Product.objects.filter(
                created_at__gte=session.started_at
            ).count()

            self.stdout.write(
                f"\nProduct Statistics:\n"
                f"Total Products: {total_products}\n"
                f"New Products: {new_products}"
            )

            # Check if detail queue needs populating
            detail_queue_count = CrawlQueue.objects.filter(
                queue_type='PRODUCT_DETAIL',
                status='PENDING'
            ).count()

            if detail_queue_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n{detail_queue_count} products added to detail queue"
                    )
                )

        except CommandError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in product list crawler: {str(e)}")
            self.stderr.write(
                self.style.ERROR(
                    f"Unexpected error: {str(e)}"
                )
            )
            raise CommandError(str(e))