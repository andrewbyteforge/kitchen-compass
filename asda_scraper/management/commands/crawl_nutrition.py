"""
Django Management Command for crawling nutritional information.

Save this as: asda_scraper/management/commands/crawl_nutrition.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from asda_scraper.models import AsdaProduct, CrawlSession
from asda_scraper.selenium_scraper import SeleniumAsdaScraper

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Management command to crawl nutritional information for ASDA products.
    
    This command can be used to add nutritional information to existing products
    or crawl specific products by ID or category.
    """
    
    help = 'Crawl nutritional information for ASDA products'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            '--product-ids',
            nargs='+',
            help='Specific ASDA product IDs to crawl nutritional info for'
        )
        
        parser.add_argument(
            '--category',
            type=str,
            help='Crawl nutritional info for products in specific category (by name or slug)'
        )
        
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Maximum number of products to process (default: 50)'
        )
        
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Only process products without existing nutritional information'
        )
        
        parser.add_argument(
            '--delay',
            type=float,
            default=3.0,
            help='Delay between product crawls in seconds (default: 3.0)'
        )
        
        parser.add_argument(
            '--test-url',
            type=str,
            help='Test nutritional extraction on a specific product URL'
        )
        
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Run browser in headless mode'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test run without saving data to database'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        try:
            self.stdout.write(
                self.style.SUCCESS("🧪 Starting ASDA Nutritional Information Crawler")
            )
            
            # Handle test URL first if provided
            if options['test_url']:
                return self._test_single_url(options['test_url'], options['headless'])
            
            # Get products to process
            products = self._get_products_to_process(options)
            
            if not products.exists():
                self.stdout.write(
                    self.style.WARNING("⚠️ No products found matching criteria")
                )
                return
            
            total_products = products.count()
            limit = options['limit']
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"📊 Found {total_products} products to process "
                    f"(limiting to {limit})"
                )
            )
            
            # Initialize scraper with proper crawl session using correct fields
            # Get or create a default user for the crawl session
            user, created = User.objects.get_or_create(
                username='nutrition_crawler',
                defaults={'email': 'crawler@example.com'}
            )
            
            session = CrawlSession.objects.create(
                user=user,
                status='PENDING',
                notes=self._get_session_description(options),
                crawl_settings={
                    'nutrition_crawl': True,
                    'limit': options['limit'],
                    'missing_only': options['missing_only'],
                    'delay': options['delay']
                }
            )
            
            scraper = SeleniumAsdaScraper(crawl_session=session, headless=options['headless'])
            
            try:
                # Process products
                self._process_products(
                    scraper, 
                    products[:limit], 
                    options
                )
                
                # Finalize session
                session.status = 'COMPLETED'
                session.end_time = timezone.now()
                session.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Nutritional crawling completed. "
                        f"Processed: {session.products_updated} products"
                    )
                )
                
            except Exception as e:
                session.status = 'FAILED'
                session.end_time = timezone.now()
                session.error_log = str(e)
                session.save()
                raise
            finally:
                scraper.cleanup()
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n⚠️ Crawling interrupted by user")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error during nutritional crawling: {str(e)}")
            )
            raise CommandError(f"Crawling failed: {str(e)}")
    
    def _test_single_url(self, test_url: str, headless: bool = True):
        """
        Test nutritional extraction on a single URL.
        
        Args:
            test_url: URL to test
            headless: Whether to run browser in headless mode
        """
        self.stdout.write(
            self.style.SUCCESS(f"🧪 Testing nutritional extraction on: {test_url}")
        )
        
        # Create a temporary crawl session for testing using correct fields
        # Get or create a default user for the test session
        user, created = User.objects.get_or_create(
            username='nutrition_test_user',
            defaults={'email': 'test@example.com'}
        )
        
        session = CrawlSession.objects.create(
            user=user,
            status='PENDING',
            notes=f'Nutrition test for URL: {test_url[:100]}',
            crawl_settings={'test_mode': True, 'target_url': test_url}
        )
        
        scraper = SeleniumAsdaScraper(crawl_session=session, headless=headless)
        
        try:
            # Extract nutritional info
            nutritional_data = scraper._extract_nutritional_info_from_product_page(test_url)
            
            if nutritional_data:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Successfully extracted {len(nutritional_data)} nutritional values:"
                    )
                )
                
                for key, value in nutritional_data.items():
                    self.stdout.write(f"  • {key}: {value}")
            else:
                self.stdout.write(
                    self.style.WARNING("⚠️ No nutritional information found")
                )
            
            # Update session status
            session.status = 'COMPLETED'
            session.end_time = timezone.now()
            session.save()
                
        except Exception as e:
            session.status = 'FAILED'
            session.end_time = timezone.now()
            session.error_log = str(e)
            session.save()
            self.stdout.write(
                self.style.ERROR(f"❌ Error testing URL: {str(e)}")
            )
        finally:
            scraper.cleanup()
    
    def _get_products_to_process(self, options) -> 'QuerySet':
        """
        Get products to process based on command options.
        
        Args:
            options: Command options dictionary
            
        Returns:
            QuerySet: Products to process
        """
        # Start with all products
        products = AsdaProduct.objects.all()
        
        # Filter by specific product IDs
        if options['product_ids']:
            products = products.filter(asda_id__in=options['product_ids'])
            self.stdout.write(
                f"🎯 Filtering to specific product IDs: {options['product_ids']}"
            )
        
        # Filter by category
        if options['category']:
            category_filter = Q(category__name__icontains=options['category']) | \
                            Q(category__slug__icontains=options['category'])
            products = products.filter(category_filter)
            self.stdout.write(
                f"📂 Filtering to category: {options['category']}"
            )
        
        # Filter to products missing nutritional info
        if options['missing_only']:
            products = products.filter(
                Q(nutritional_info__isnull=True) | 
                Q(nutritional_info__exact={})
            )
            self.stdout.write("🔍 Only processing products without nutritional info")
        
        # Filter to products with valid URLs
        products = products.exclude(product_url='').exclude(product_url__isnull=True)
        
        # Order by category and name for systematic processing
        products = products.select_related('category').order_by('category__name', 'name')
        
        return products
    
    def _get_session_description(self, options) -> str:
        """Get description for crawl session."""
        if options['product_ids']:
            return f"Specific products: {', '.join(options['product_ids'][:5])}"
        elif options['category']:
            return f"Category: {options['category']}"
        elif options['missing_only']:
            return "Products missing nutritional info"
        else:
            return "All products"
    
    def _process_products(self, scraper, products, options):
        """
        Process products to extract nutritional information.
        
        Args:
            scraper: SeleniumAsdaScraper instance
            products: QuerySet of products to process
            options: Command options
        """
        delay = options['delay']
        dry_run = options['dry_run']
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        
        for idx, product in enumerate(products, 1):
            try:
                self.stdout.write(
                    f"\n{'='*80}\n"
                    f"🛍️ Processing {idx}/{len(products)}: {product.name[:50]}...\n"
                    f"📂 Category: {product.category.name}\n"
                    f"🔗 URL: {product.product_url[:60]}...\n"
                    f"{'='*80}"
                )
                
                # Check if product already has nutritional info
                if (product.nutritional_info and 
                    len(product.nutritional_info) > 0 and 
                    not options.get('missing_only')):
                    
                    self.stdout.write(
                        self.style.WARNING(
                            "⏭️ Product already has nutritional info, skipping"
                        )
                    )
                    skipped_count += 1
                    continue
                
                # Extract nutritional information
                nutritional_data = scraper._extract_nutritional_info_from_product_page(
                    product.product_url
                )
                
                if nutritional_data:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Extracted {len(nutritional_data)} nutritional values:"
                        )
                    )
                    
                    for key, value in nutritional_data.items():
                        self.stdout.write(f"  • {key}: {value}")
                    
                    # Save to database (unless dry run)
                    if not dry_run:
                        product.nutritional_info = nutritional_data
                        product.save()
                        scraper.session.products_updated += 1
                        scraper.session.save()
                        self.stdout.write("💾 Saved to database")
                    else:
                        self.stdout.write("🔍 DRY RUN - not saved to database")
                    
                    success_count += 1
                    
                else:
                    self.stdout.write(
                        self.style.WARNING("⚠️ No nutritional information found")
                    )
                    error_count += 1
                
                # Delay between requests to be respectful
                if delay > 0:
                    self.stdout.write(f"⏳ Waiting {delay} seconds...")
                    time.sleep(delay)
                
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING("\n⚠️ Interrupted by user")
                )
                break
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error processing product: {str(e)}")
                )
                error_count += 1
                
                # Continue with next product after error
                continue
        
        # Print summary
        self.stdout.write(
            f"\n{'='*80}\n"
            f"📊 NUTRITIONAL CRAWLING SUMMARY\n"
            f"{'='*80}\n"
            f"✅ Successful extractions: {success_count}\n"
            f"❌ Failed extractions: {error_count}\n"
            f"⏭️ Skipped products: {skipped_count}\n"
            f"📈 Success rate: {(success_count/(success_count+error_count)*100):.1f}%\n"
            f"{'='*80}"
        )