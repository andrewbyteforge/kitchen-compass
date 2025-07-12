"""
Separate Management Command for ASDA Nutritional Information Crawling.

File: asda_scraper/management/commands/crawl_nutrition.py
"""

import logging
import time
from typing import Dict, Optional
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from asda_scraper.models import AsdaProduct, AsdaCategory, CrawlSession
from asda_scraper.scrapers.webdriver_manager import WebDriverManager
from asda_scraper.scrapers.nutrition_extractor import NutritionExtractor
from asda_scraper.scrapers.popup_handler import PopupHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Separate management command for crawling nutritional information.
    
    This runs independently from the main product crawler for maximum reliability.
    """
    
    help = 'Crawl nutritional information for existing ASDA products'
    
    def add_arguments(self, parser):
        """
        Add command arguments with enhanced options.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--max-products',
            type=int,
            default=100,  # Increased default
            help='Maximum number of products to process (default: 100)',
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Only process products from specific category',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,  # Reduced default delay
            help='Delay between products in seconds (default: 1.0)',
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            default=True,
            help='Run browser in headless mode (default: True)',
        )
        parser.add_argument(
            '--force-recrawl',
            action='store_true',
            help='Recrawl nutrition even if already exists',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Test mode - do not save nutrition data',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=15,
            help='Page load timeout in seconds (default: 15)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Process products in batches (default: 50)',
        )
        parser.add_argument(
            '--priority-categories',
            action='store_true',
            help='Only process products from priority categories (priority 1-2)',
        )
        parser.add_argument(
            '--exclude-fresh',
            action='store_true',
            default=True,
            help='Exclude fresh produce (unlikely to have nutrition labels)',
        )

    # Also update the _get_products_to_process method for better filtering
    def _get_products_to_process(self, options: dict):
        """
        Get products that need nutritional information with enhanced filtering.
        
        Args:
            options: Command options
            
        Returns:
            QuerySet: Products to process
        """
        try:
            # Base query - products with URLs but no nutrition data
            query = AsdaProduct.objects.filter(
                product_url__isnull=False,
                product_url__gt=''
            ).exclude(
                product_url=''
            )
            
            # Exclude fresh produce if requested (they rarely have nutrition labels)
            if options.get('exclude_fresh', True):
                fresh_keywords = ['fruit', 'vegetable', 'fresh', 'produce', 'flower', 'plant']
                for keyword in fresh_keywords:
                    query = query.exclude(category__name__icontains=keyword)
                self.stdout.write("🥬 Excluding fresh produce categories")
            
            # Filter by priority categories if requested
            if options.get('priority_categories'):
                priority_categories = AsdaCategory.objects.filter(
                    url_code__in=[
                        '1215686354843',  # Bakery
                        '1215337189632',  # Food Cupboard  
                        '1215660378320',  # Chilled Food
                        '1215338621416',  # Frozen Food
                        '1215686356579',  # Sweets, Treats & Snacks
                    ]
                )
                query = query.filter(category__in=priority_categories)
                self.stdout.write("🎯 Filtering to priority categories only")
            
            # Filter by category if specified
            if options['category']:
                query = query.filter(category__name__icontains=options['category'])
                self.stdout.write(f"📂 Filtering to category: {options['category']}")
            
            # Skip products with recent nutrition data unless force recrawl
            if not options['force_recrawl']:
                # Only get products without nutrition or with old nutrition
                seven_days_ago = timezone.now() - timezone.timedelta(days=7)
                query = query.filter(
                    Q(nutritional_info__isnull=True) | 
                    Q(nutritional_info__exact={}) |
                    Q(updated_at__lt=seven_days_ago)
                )
                self.stdout.write("🔄 Skipping products with recent nutrition data")
            
            # Prioritize products likely to have nutrition info
            # Order by: processed foods first, then by newest products
            query = query.order_by(
                'category__name',  # Group by category  
                '-created_at'      # Newer products first
            )
            
            # Limit results
            max_products = options['max_products']
            products = list(query[:max_products])
            
            self.stdout.write(f"📦 Selected {len(products)} products for nutrition crawling:")
            
            # Show category breakdown
            from collections import Counter
            category_counts = Counter(p.category.name for p in products)
            for category, count in category_counts.most_common():
                self.stdout.write(f"  • {category}: {count} products")
            
            # Show some examples
            if products:
                self.stdout.write(f"\n📋 Sample products:")
                for p in products[:5]:
                    self.stdout.write(f"  • {p.name[:50]}... ({p.category.name})")
            
            return products
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error getting products: {e}"))
            return []




    def handle(self, *args, **options):
        """
        Execute the nutrition crawling command.
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        try:
            self.stdout.write(self.style.SUCCESS('='*70))
            self.stdout.write(self.style.SUCCESS('ASDA NUTRITIONAL INFORMATION CRAWLER'))
            self.stdout.write(self.style.SUCCESS('='*70))
            
            # Setup
            driver_manager = None
            driver = None
            
            try:
                # Get products to process
                products = self._get_products_to_process(options)
                if not products:
                    self.stdout.write(self.style.WARNING("No products found to process"))
                    return
                
                self.stdout.write(f"Found {len(products)} products to process")
                
                # Setup WebDriver
                self.stdout.write("Setting up WebDriver...")
                driver_manager = WebDriverManager(headless=options['headless'])
                driver = driver_manager.setup_driver()
                
                # Setup timeouts
                driver.set_page_load_timeout(options['timeout'])
                
                # Create session
                session = self._create_nutrition_session(options)
                
                # Setup extractors
                nutrition_extractor = NutritionExtractor(driver)
                popup_handler = PopupHandler(driver)
                
                # Process products
                self._process_products(
                    products, driver, nutrition_extractor, 
                    popup_handler, session, options
                )
                
                # Complete session
                session.mark_completed()
                
            finally:
                if driver:
                    driver.quit()
                    
        except Exception as e:
            logger.error(f"Nutrition crawling failed: {e}")
            raise CommandError(f"Nutrition crawling failed: {e}")
    
    def _get_products_to_process(self, options: dict):
        """
        Get products that need nutritional information.
        
        Args:
            options: Command options
            
        Returns:
            QuerySet: Products to process
        """
        try:
            # Base query - products with URLs but no nutrition data
            query = AsdaProduct.objects.filter(
                product_url__isnull=False,
                product_url__gt=''
            ).exclude(
                product_url=''
            )
            
            # Filter by category if specified
            if options['category']:
                query = query.filter(category__name__icontains=options['category'])
            
            # Skip products with recent nutrition data unless force recrawl
            if not options['force_recrawl']:
                # Only get products without nutrition or with old nutrition
                three_days_ago = timezone.now() - timezone.timedelta(days=3)
                query = query.filter(
                    Q(nutritional_info__isnull=True) | 
                    Q(nutritional_info__exact={}) |
                    Q(updated_at__lt=three_days_ago)
                )
            
            # Order by priority: newer products first, then by category
            query = query.order_by('-created_at', 'category__name')
            
            # Limit results
            max_products = options['max_products']
            products = list(query[:max_products])
            
            self.stdout.write(f"Selected {len(products)} products for nutrition crawling:")
            
            # Show category breakdown
            from collections import Counter
            category_counts = Counter(p.category.name for p in products)
            for category, count in category_counts.most_common():
                self.stdout.write(f"  • {category}: {count} products")
            
            return products
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error getting products: {e}"))
            return []
    
    def _create_nutrition_session(self, options: dict) -> CrawlSession:
        """
        Create a session for nutrition crawling.
        
        Args:
            options: Command options
            
        Returns:
            CrawlSession: Created session
        """
        try:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.create_user(
                    username='nutrition_crawler',
                    email='nutrition@crawler.com',
                    is_staff=True
                )
            
            session = CrawlSession.objects.create(
                user=user,
                status='RUNNING',
                crawl_type='NUTRITION',
                crawl_settings={
                    'max_products': options['max_products'],
                    'category_filter': options.get('category'),
                    'delay': options['delay'],
                    'timeout': options['timeout'],
                    'force_recrawl': options['force_recrawl'],
                    'dry_run': options['dry_run'],
                    'nutrition_only': True
                },
                notes=f"Nutrition crawling session - {options['max_products']} products"
            )
            
            self.stdout.write(f"Created nutrition session: {session.pk}")
            return session
            
        except Exception as e:
            raise CommandError(f"Failed to create session: {e}")
    
    def _process_products(self, products, driver, nutrition_extractor, popup_handler, session, options):
        """
        Process products for nutritional information.
        
        Args:
            products: List of products to process
            driver: WebDriver instance
            nutrition_extractor: NutritionExtractor instance
            popup_handler: PopupHandler instance
            session: CrawlSession instance
            options: Command options
        """
        try:
            delay = options['delay']
            dry_run = options['dry_run']
            timeout = options['timeout']
            
            success_count = 0
            error_count = 0
            skipped_count = 0
            
            for i, product in enumerate(products, 1):
                try:
                    self.stdout.write(f"\n{'-'*60}")
                    self.stdout.write(f"[{i}/{len(products)}] Processing: {product.name[:50]}...")
                    self.stdout.write(f"Category: {product.category.name}")
                    self.stdout.write(f"URL: {product.product_url}")
                    
                    # Check if already has nutrition (unless force recrawl)
                    if not options['force_recrawl'] and self._has_recent_nutrition(product):
                        self.stdout.write(self.style.WARNING("⏭️ Already has recent nutrition data, skipping"))
                        skipped_count += 1
                        continue
                    
                    # Extract nutrition
                    self.stdout.write("🔍 Extracting nutritional information...")
                    
                    start_time = time.time()
                    nutrition_data = self._extract_nutrition_with_timeout(
                        nutrition_extractor, product.product_url, timeout
                    )
                    extract_time = time.time() - start_time
                    
                    if nutrition_data:
                        self.stdout.write(self.style.SUCCESS(
                            f"✅ Found {len(nutrition_data)} nutrition values "
                            f"(took {extract_time:.1f}s)"
                        ))
                        
                        # Show extracted data
                        for key, value in list(nutrition_data.items())[:5]:
                            self.stdout.write(f"   • {key}: {value}")
                        if len(nutrition_data) > 5:
                            self.stdout.write(f"   ... and {len(nutrition_data) - 5} more")
                        
                        # Save to database (unless dry run)
                        if not dry_run:
                            self._save_nutrition_data(product, nutrition_data, session)
                        
                        success_count += 1
                        
                    else:
                        self.stdout.write(self.style.WARNING(
                            f"⚠️ No nutrition data found (took {extract_time:.1f}s)"
                        ))
                        error_count += 1
                    
                    # Update session progress
                    session.products_found = success_count
                    session.nutrition_errors = error_count
                    session.save()
                    
                    # Delay between products
                    if delay > 0 and i < len(products):
                        self.stdout.write(f"⏳ Waiting {delay}s before next product...")
                        time.sleep(delay)
                        
                except KeyboardInterrupt:
                    self.stdout.write(self.style.WARNING("\n⚠️ Interrupted by user"))
                    break
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ Error processing product: {e}"))
                    error_count += 1
                    logger.error(f"Error processing product {product.asda_id}: {e}")
                    continue
            
            # Final summary
            self._show_final_summary(success_count, error_count, skipped_count)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error in product processing: {e}"))
    
    def _extract_nutrition_with_timeout(self, nutrition_extractor, product_url, timeout):
        """
        Extract nutrition with timeout handling.
        
        Args:
            nutrition_extractor: NutritionExtractor instance
            product_url: Product URL
            timeout: Timeout in seconds
            
        Returns:
            dict: Nutrition data or None
        """
        try:
            # Set a reasonable timeout for nutrition extraction
            original_timeout = nutrition_extractor.driver.get_timeouts().get('pageLoad', 30)
            nutrition_extractor.driver.set_page_load_timeout(timeout)
            
            try:
                nutrition_data = nutrition_extractor.extract_from_url(product_url)
                return nutrition_data
            finally:
                # Restore original timeout
                nutrition_extractor.driver.set_page_load_timeout(original_timeout)
                
        except Exception as e:
            logger.warning(f"Timeout or error extracting nutrition: {e}")
            return None
    
    def _has_recent_nutrition(self, product) -> bool:
        """
        Check if product has recent nutritional information.
        
        Args:
            product: AsdaProduct instance
            
        Returns:
            bool: True if has recent nutrition data
        """
        if not product.nutritional_info:
            return False
        
        if not isinstance(product.nutritional_info, dict):
            return False
        
        if not product.nutritional_info:
            return False
        
        # Check if updated recently
        three_days_ago = timezone.now() - timezone.timedelta(days=3)
        return product.updated_at and product.updated_at > three_days_ago
    
    def _save_nutrition_data(self, product, nutrition_data, session):
        """
        Save nutrition data to product.
        
        Args:
            product: AsdaProduct instance
            nutrition_data: Dictionary of nutrition data
            session: CrawlSession instance
        """
        try:
            # Create enhanced nutrition data with metadata
            enhanced_data = {
                'nutrition': nutrition_data,
                'extracted_at': timezone.now().isoformat(),
                'extraction_method': 'separate_nutrition_crawler',
                'data_count': len(nutrition_data)
            }
            
            product.nutritional_info = enhanced_data
            product.save(update_fields=['nutritional_info'])
            
            # Update session
            session.products_with_nutrition += 1
            session.save()
            
            self.stdout.write("💾 Nutrition data saved to database")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error saving nutrition data: {e}"))
    
    def _show_final_summary(self, success_count, error_count, skipped_count):
        """
        Show final summary of nutrition crawling.
        
        Args:
            success_count: Number of successful extractions
            error_count: Number of failed extractions
            skipped_count: Number of skipped products
        """
        total_processed = success_count + error_count
        success_rate = (success_count / total_processed * 100) if total_processed > 0 else 0
        
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(self.style.SUCCESS("NUTRITION CRAWLING SUMMARY"))
        self.stdout.write(f"{'='*70}")
        self.stdout.write(f"✅ Successful extractions: {success_count}")
        self.stdout.write(f"❌ Failed extractions: {error_count}")
        self.stdout.write(f"⏭️ Skipped products: {skipped_count}")
        self.stdout.write(f"📈 Success rate: {success_rate:.1f}%")
        self.stdout.write(f"{'='*70}")
        
        if success_count > 0:
            self.stdout.write(self.style.SUCCESS(
                f"🎉 Successfully added nutrition data to {success_count} products!"
            ))
        
        if error_count > 0:
            self.stdout.write(self.style.WARNING(
                f"⚠️ {error_count} products had no nutrition data available"
            ))