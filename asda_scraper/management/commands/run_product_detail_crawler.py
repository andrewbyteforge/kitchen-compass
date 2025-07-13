"""
Django management command to run the product detail crawler.

Usage:
    python manage.py run_product_detail_crawler [--limit N]
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from asda_scraper.models import CrawlSession, CrawlQueue, Product
from asda_scraper.scrapers import ProductDetailCrawler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to run the ASDA product detail crawler."""

    help = 'Run the ASDA product detail crawler to extract nutrition information'

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of products to process',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force run even if another crawler is active',
        )
        parser.add_argument(
            '--no-nutrition',
            action='store_true',
            help='Only process products without nutrition data',
        )

    def handle(self, *args, **options):
        """
        Handle the command execution.

        Args:
            *args: Positional arguments
            **options: Command options
        """
        try:
            self.stdout.write("Starting ASDA Product Detail Crawler...")
            logger.info("Product detail crawler command initiated")

            # Check if crawler is already running
            if not options['force']:
                active_session = CrawlSession.objects.filter(
                    crawler_type='PRODUCT_DETAIL',
                    status='RUNNING'
                ).exists()

                if active_session:
                    raise CommandError(
                        "Product detail crawler is already running. "
                        "Use --force to override."
                    )

            # Check queue status
            pending_count = CrawlQueue.objects.filter(
                queue_type='PRODUCT_DETAIL',
                status='PENDING'
            ).count()

            if pending_count == 0:
                self.stdout.write(
                    self.style.WARNING(
                        "No pending URLs in product detail queue. "
                        "Run product list crawler first."
                    )
                )
                return

            self.stdout.write(
                f"Found {pending_count} pending URLs in queue"
            )

            # Show products without nutrition
            if options.get('no_nutrition'):
                no_nutrition_count = Product.objects.filter(
                    nutrition_scraped=False,
                    is_available=True
                ).count()
                self.stdout.write(
                    f"Products without nutrition data: {no_nutrition_count}"
                )

            # Create new crawl session
            # For continuous processing, total_items is the full queue size
            total_queue_items = CrawlQueue.objects.filter(
                queue_type='PRODUCT_DETAIL',
                status='PENDING'
            ).count()
            
            limit = options.get('limit')
            if limit is None:
                total_items = total_queue_items
            else:
                total_items = min(total_queue_items, limit)
                
            session = CrawlSession.objects.create(
                crawler_type='PRODUCT_DETAIL',
                status='RUNNING',
                started_at=timezone.now(),
                total_items=total_items
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created crawl session ID: {session.id}"
                )
            )

            # Initialize and run crawler
            crawler = ProductDetailCrawler(session=session)
            
            # Apply limit if specified
            if limit is not None:
                crawler.limit = limit
                
            crawler.run()

            # Report results
            session.refresh_from_db()
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nProduct detail crawling completed!\n"
                    f"Status: {session.status}\n"
                    f"Duration: {session.duration}\n"
                    f"Processed: {session.processed_items}\n"
                    f"Failed: {session.failed_items}\n"
                    f"Success Rate: {session.success_rate:.1f}%\n"
                    f"Nutrition Extracted: {getattr(crawler, 'nutrition_extracted', 0)}"
                )
            )

            # Show statistics
            total_products = Product.objects.count()
            products_with_nutrition = Product.objects.filter(
                nutrition_scraped=True
            ).count()

            if total_products > 0:
                self.stdout.write(
                    f"\nOverall Statistics:\n"
                    f"Total Products: {total_products}\n"
                    f"With Nutrition: {products_with_nutrition} "
                    f"({products_with_nutrition / total_products * 100:.1f}%)"
                )

            # Show queue status
            remaining = CrawlQueue.objects.filter(
                queue_type='PRODUCT_DETAIL',
                status='PENDING'
            ).count()

            if remaining > 0:
                self.stdout.write(
                    f"\nRemaining in queue: {remaining} URLs"
                )

        except CommandError:
            raise
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\nCrawler interrupted by user")
            )
            if 'session' in locals():
                session.status = 'STOPPED'
                session.completed_at = timezone.now()
                session.save()
        except Exception as e:
            error_msg = f"Error running product detail crawler: {str(e)}"
            logger.error(error_msg, exc_info=True)

            if 'session' in locals():
                session.status = 'FAILED'
                session.completed_at = timezone.now()
                session.error_log = str(e)
                session.save()

            raise CommandError(error_msg)