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
from datetime import timedelta
from django.db import models
from django.db.models import Count, Min, OuterRef
from datetime import timedelta
import random
from django.db import models
from django.db.models import Q, Count, Min, OuterRef
from asda_scraper.models import AsdaProduct, AsdaCategory, CrawlSession

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
        
        parser.add_argument(
            '--force-recrawl',
            action='store_true',
            help='Force recrawl of products even if updated within 3 days'
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
    
    from django.db.models import Count, Min
    import random

    # Replace the _get_products_to_process method with this improved version
    def _get_products_to_process(self, options) -> 'QuerySet':
        """
        Get products to process based on command options.
        
        Implements a 3-day check to avoid re-crawling recently updated products
        and ensures fair distribution across categories.
        
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
            # Use Q objects to search by category name only
            category_filter = Q(category__name__icontains=options['category'])
            products = products.filter(category_filter)
            self.stdout.write(
                f"📂 Filtering to category: {options['category']}"
            )
        
        # Apply the 3-day freshness check (unless force_recrawl is specified)
        if not options.get('force_recrawl', False):
            # Calculate the cutoff date (3 days ago)
            three_days_ago = timezone.now() - timedelta(days=3)
            
            # Filter to products that either:
            # 1. Have never been updated (updated_at is null)
            # 2. Were updated more than 3 days ago
            # 3. Have no nutritional info
            products = products.filter(
                Q(updated_at__isnull=True) |  # Never updated
                Q(updated_at__lt=three_days_ago) |  # Updated more than 3 days ago
                Q(nutritional_info__isnull=True) |  # No nutritional info
                Q(nutritional_info__exact={})  # Empty nutritional info
            )
            
            self.stdout.write(
                self.style.WARNING(
                    f"⏰ Only processing products not updated in the last 3 days "
                    f"(since {three_days_ago.strftime('%Y-%m-%d %H:%M')})"
                )
            )
        
        # Filter to products missing nutritional info (if specified)
        if options['missing_only']:
            # Check both null and empty dict cases
            products = products.filter(
                Q(nutritional_info__isnull=True) | 
                Q(nutritional_info__exact={})
            )
            self.stdout.write("🔍 Only processing products without nutritional info")
        
        # Filter to products with valid URLs
        products = products.exclude(product_url='').exclude(product_url__isnull=True)
        
        # Get distribution strategy from options (new option)
        distribution_strategy = options.get('distribution', 'round_robin')
        
        if distribution_strategy == 'round_robin' and not options.get('category'):
            # ROUND ROBIN: Take products from each category in turn
            products_list = []
            limit = options.get('limit', 50)
            
            # Get all categories with products needing crawl
            categories_with_products = AsdaCategory.objects.annotate(
                products_needing_crawl=Count(
                    'products',
                    filter=products.filter(category=models.OuterRef('pk')).values('pk')[:1]
                )
            ).filter(products_needing_crawl__gt=0).order_by('?')  # Random order
            
            self.stdout.write(
                f"\n🔄 Using round-robin distribution across {categories_with_products.count()} categories"
            )
            
            # Take products from each category in turn
            products_per_category = max(1, limit // max(1, categories_with_products.count()))
            remaining = limit
            
            for category in categories_with_products:
                if remaining <= 0:
                    break
                    
                category_products = products.filter(
                    category=category
                ).order_by('?')[:min(products_per_category, remaining)]  # Random order within category
                
                products_list.extend(list(category_products))
                remaining -= len(category_products)
                
                if category_products:
                    self.stdout.write(
                        f"  • {category.name}: {len(category_products)} products"
                    )
            
            # Convert back to QuerySet-like behavior
            if products_list:
                product_ids = [p.id for p in products_list]
                products = AsdaProduct.objects.filter(id__in=product_ids)
            else:
                products = AsdaProduct.objects.none()
                
        elif distribution_strategy == 'least_processed':
            # LEAST PROCESSED: Prioritize categories with lowest nutrition coverage
            products = products.select_related('category').annotate(
                category_coverage=Count(
                    'category__products',
                    filter=~Q(category__products__nutritional_info__exact={})
                )
            ).order_by('category_coverage', 'category__name', '?')  # Random within same coverage
            
        else:
            # DEFAULT: Order by category and name (current behavior)
            products = products.select_related('category').order_by('category__name', 'name')
        
        # Apply limit if specified
        limit = options.get('limit', 50)
        total_before_limit = products.count()
        
        # Report findings
        self.stdout.write(
            f"\n📊 Found {total_before_limit} products matching criteria"
        )
        if total_before_limit > limit:
            self.stdout.write(
                f"📋 Processing first {limit} products (use --limit to change)"
            )
        
        # Return limited queryset
        return products[:limit]


    # Update the add_arguments method to include the new distribution option
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
            help='Crawl nutritional info for products in specific category (by name)'
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
        
        parser.add_argument(
            '--force-recrawl',
            action='store_true',
            help='Force recrawl of products even if updated within 3 days'
        )
        
        parser.add_argument(
            '--distribution',
            type=str,
            choices=['round_robin', 'least_processed', 'default'],
            default='round_robin',
            help='How to distribute crawling across categories (default: round_robin)'
        )

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
        Process products to extract nutritional information with enhanced database handling.
        
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
                # Calculate days since last update
                days_since_update = "Never"
                if product.updated_at:
                    time_diff = timezone.now() - product.updated_at
                    days_since_update = f"{time_diff.days} days ago"
                
                self.stdout.write(
                    f"\n{'='*80}\n"
                    f"🛍️ Processing {idx}/{len(products)}: {product.name[:50]}...\n"
                    f"📂 Category: {product.category.name}\n"
                    f"🔗 URL: {product.product_url[:60]}...\n"
                    f"🆔 ASDA ID: {product.asda_id}\n"
                    f"📅 Last updated: {days_since_update}\n"
                    f"🧪 Has nutrition: {'Yes' if product.has_nutritional_info() else 'No'}\n"
                    f"{'='*80}"
                )
                
                # Additional freshness check (in case force_recrawl is used)
                if not options.get('force_recrawl', False):
                    three_days_ago = timezone.now() - timedelta(days=3)
                    if product.updated_at and product.updated_at > three_days_ago and product.has_nutritional_info():
                        self.stdout.write(
                            self.style.WARNING(
                                f"⏭️ Product was updated {days_since_update} and has nutritional data, skipping"
                            )
                        )
                        skipped_count += 1
                        continue
                
                # Validate product has a URL
                if not product.product_url:
                    self.stdout.write(
                        self.style.WARNING("⚠️ Product has no URL, skipping")
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
                    
                    # Save to database with enhanced error handling
                    if not dry_run:
                        save_success = self._save_nutritional_data_to_product(
                            product, nutritional_data, scraper
                        )
                        
                        if save_success:
                            self.stdout.write(
                                self.style.SUCCESS("💾 Successfully saved to database")
                            )
                            success_count += 1
                        else:
                            self.stdout.write(
                                self.style.ERROR("❌ Failed to save to database")
                            )
                            error_count += 1
                    else:
                        self.stdout.write("🔍 DRY RUN - not saved to database")
                        success_count += 1
                    
                else:
                    self.stdout.write(
                        self.style.WARNING("⚠️ No nutritional information found")
                    )
                    error_count += 1
                
                # Delay between requests to be respectful
                if delay > 0 and idx < len(products):
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
                
                # Log the full error for debugging
                import traceback
                logger.error(f"Error processing product {product.asda_id}: {traceback.format_exc()}")
                
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
            f"📈 Success rate: {(success_count/(success_count+error_count)*100 if (success_count+error_count) > 0 else 0):.1f}%\n"
            f"{'='*80}"
        )




    def _save_nutritional_data_to_product(self, product, nutritional_data, scraper):
        """
        Save nutritional data to a specific product with enhanced error handling.
        
        Args:
            product: AsdaProduct instance
            nutritional_data: Dictionary of nutritional information
            scraper: SeleniumAsdaScraper instance
            
        Returns:
            bool: True if save was successful
        """
        try:
            from django.db import transaction
            
            # Use database transaction to ensure data integrity
            with transaction.atomic():
                # Add metadata to nutritional data
                enhanced_nutritional_data = {
                    'nutrition': nutritional_data,
                    'extracted_at': timezone.now().isoformat(),
                    'source_url': product.product_url,
                    'extraction_method': 'selenium_scraper_v2',
                    'data_count': len(nutritional_data)
                }
                
                # Update the product
                product.nutritional_info = enhanced_nutritional_data
                product.updated_at = timezone.now()
                product.save(update_fields=['nutritional_info', 'updated_at'])
                
                # Update scraper session
                scraper.session.products_updated += 1
                scraper.session.save()
                
                # Log the successful save
                logger.info(
                    f"✅ Saved nutritional data for product {product.asda_id} "
                    f"({product.name[:50]}) - {len(nutritional_data)} values"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Database error saving nutritional data for {product.asda_id}: {str(e)}")
            return False