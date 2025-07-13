"""
Django management command to run the category mapper crawler.

Usage:
    python manage.py run_category_mapper
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from asda_scraper.models import CrawlSession
from asda_scraper.scrapers import CategoryMapperCrawler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to run the ASDA category mapper crawler."""

    help = 'Run the ASDA category mapper to discover all product categories'

    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force run even if another crawler is active',
        )

    def handle(self, *args, **options):
        """
        Handle the command execution.

        Args:
            *args: Positional arguments
            **options: Command options
        """
        try:
            self.stdout.write("Starting ASDA Category Mapper...")
            logger.info("Category mapper command initiated")

            # Check if crawler is already running
            if not options['force']:
                active_session = CrawlSession.objects.filter(
                    crawler_type='CATEGORY',
                    status='RUNNING'
                ).exists()

                if active_session:
                    raise CommandError(
                        "Category mapper is already running. "
                        "Use --force to override."
                    )

            # Create new crawl session
            session = CrawlSession.objects.create(
                crawler_type='CATEGORY',
                status='RUNNING',
                started_at=timezone.now()
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created crawl session ID: {session.id}"
                )
            )

            # Initialize and run crawler
            crawler = CategoryMapperCrawler(session=session)
            crawler.run()

            # Report results
            session.refresh_from_db()
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nCategory mapping completed successfully!\n"
                    f"Status: {session.status}\n"
                    f"Duration: {session.duration}\n"
                    f"Processed: {session.processed_items}\n"
                    f"Failed: {session.failed_items}\n"
                    f"Success Rate: {session.success_rate:.1f}%"
                )
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
            error_msg = f"Error running category mapper: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if 'session' in locals():
                session.status = 'FAILED'
                session.completed_at = timezone.now()
                session.error_log = str(e)
                session.save()
            
            raise CommandError(error_msg)