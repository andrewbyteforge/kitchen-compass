"""
Django management command to delete ASDA products from the database.

File: asda_scraper/management/commands/delete_asda_products.py
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from asda_scraper.models import AsdaProduct, AsdaCategory, CrawlSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Delete ASDA products from the database with various options."""
    
    help = 'Delete ASDA products from the database'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        # Delete options
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete ALL products (requires --confirm)'
        )
        
        parser.add_argument(
            '--category',
            type=str,
            help='Delete products from specific category (by name or ID)'
        )
        
        parser.add_argument(
            '--older-than',
            type=int,
            help='Delete products older than X days'
        )
        
        parser.add_argument(
            '--price-range',
            type=str,
            help='Delete products in price range (e.g., "10-50")'
        )
        
        parser.add_argument(
            '--out-of-stock',
            action='store_true',
            help='Delete only out-of-stock products'
        )
        
        parser.add_argument(
            '--duplicates',
            action='store_true',
            help='Delete duplicate products (keeps newest)'
        )
        
        # Safety options
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion (required for destructive operations)'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        
        # Additional options
        parser.add_argument(
            '--reset-categories',
            action='store_true',
            help='Also reset category product counts'
        )
        
        parser.add_argument(
            '--clear-sessions',
            action='store_true',
            help='Also clear crawl session history'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        try:
            # Validate options
            if not any([options['all'], options['category'], options['older_than'], 
                       options['price_range'], options['out_of_stock'], options['duplicates']]):
                raise CommandError('Please specify what to delete (--all, --category, etc.)')
            
            # Build queryset
            queryset = self._build_queryset(options)
            count = queryset.count()
            
            if count == 0:
                self.stdout.write(self.style.WARNING('No products match the criteria'))
                return
            
            # Show what will be deleted
            self._show_deletion_summary(queryset, options)
            
            # Dry run mode
            if options['dry_run']:
                self.stdout.write(self.style.WARNING(f'\nDRY RUN: Would delete {count} products'))
                return
            
            # Require confirmation for destructive operations
            if not options['confirm']:
                self.stdout.write(self.style.ERROR(
                    '\nDeletion requires --confirm flag to proceed'
                ))
                return
            
            # Final confirmation for large deletions
            if count > 1000:
                response = input(f'\nAre you sure you want to delete {count} products? (yes/no): ')
                if response.lower() != 'yes':
                    self.stdout.write(self.style.WARNING('Deletion cancelled'))
                    return
            
            # Perform deletion
            with transaction.atomic():
                deleted_count = queryset.delete()[0]
                self.stdout.write(self.style.SUCCESS(
                    f'\n✓ Successfully deleted {deleted_count} products'
                ))
                
                # Reset category counts if requested
                if options['reset_categories']:
                    self._reset_category_counts()
                
                # Clear sessions if requested
                if options['clear_sessions']:
                    self._clear_crawl_sessions()
                
        except Exception as e:
            raise CommandError(f'Error deleting products: {str(e)}')
    
    def _build_queryset(self, options):
        """Build queryset based on options."""
        queryset = AsdaProduct.objects.all()
        
        # Filter by category
        if options['category']:
            try:
                # Try as ID first
                category = AsdaCategory.objects.get(pk=int(options['category']))
            except (ValueError, AsdaCategory.DoesNotExist):
                # Try as name
                try:
                    category = AsdaCategory.objects.get(name__iexact=options['category'])
                except AsdaCategory.DoesNotExist:
                    raise CommandError(f"Category not found: {options['category']}")
            
            queryset = queryset.filter(category=category)
            self.stdout.write(f"Filtering by category: {category.name}")
        
        # Filter by age
        if options['older_than']:
            cutoff_date = timezone.now() - timezone.timedelta(days=options['older_than'])
            queryset = queryset.filter(created_at__lt=cutoff_date)
            self.stdout.write(f"Filtering products older than {options['older_than']} days")
        
        # Filter by price range
        if options['price_range']:
            try:
                min_price, max_price = map(float, options['price_range'].split('-'))
                queryset = queryset.filter(price__gte=min_price, price__lte=max_price)
                self.stdout.write(f"Filtering by price range: £{min_price} - £{max_price}")
            except ValueError:
                raise CommandError('Invalid price range format. Use: "min-max"')
        
        # Filter out of stock
        if options['out_of_stock']:
            queryset = queryset.filter(in_stock=False)
            self.stdout.write("Filtering out-of-stock products only")
        
        # Filter duplicates
        if options['duplicates']:
            # Find duplicate asda_ids
            from django.db.models import Count
            duplicates = (AsdaProduct.objects
                         .values('asda_id')
                         .annotate(count=Count('id'))
                         .filter(count__gt=1))
            
            duplicate_ids = [item['asda_id'] for item in duplicates]
            
            # Keep only older duplicates (delete all but the newest)
            ids_to_delete = []
            for asda_id in duplicate_ids:
                products = AsdaProduct.objects.filter(asda_id=asda_id).order_by('-created_at')
                # Add all but the first (newest) to deletion list
                ids_to_delete.extend(products[1:].values_list('id', flat=True))
            
            queryset = AsdaProduct.objects.filter(id__in=ids_to_delete)
            self.stdout.write(f"Found {len(duplicate_ids)} products with duplicates")
        
        return queryset
    
    def _show_deletion_summary(self, queryset, options):
        """Show summary of what will be deleted."""
        count = queryset.count()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('DELETION SUMMARY')
        self.stdout.write('='*60)
        self.stdout.write(f'Total products to delete: {count}')
        
        # Show breakdown by category
        category_counts = {}
        for product in queryset.select_related('category'):
            cat_name = product.category.name if product.category else 'Uncategorized'
            category_counts[cat_name] = category_counts.get(cat_name, 0) + 1
        
        if category_counts:
            self.stdout.write('\nBy category:')
            for cat_name, count in sorted(category_counts.items()):
                self.stdout.write(f'  {cat_name}: {count}')
        
        # Show sample products
        self.stdout.write('\nSample products to be deleted:')
        for product in queryset[:5]:
            self.stdout.write(f'  - {product.name} (£{product.price})')
        
        if count > 5:
            self.stdout.write(f'  ... and {count - 5} more')
        
        self.stdout.write('='*60)
    
    def _reset_category_counts(self):
        """Reset product counts for all categories."""
        self.stdout.write('\nResetting category product counts...')
        
        for category in AsdaCategory.objects.all():
            old_count = category.product_count
            new_count = category.products.count()
            category.product_count = new_count
            category.save()
            
            if old_count != new_count:
                self.stdout.write(f'  {category.name}: {old_count} → {new_count}')
        
        self.stdout.write(self.style.SUCCESS('✓ Category counts updated'))
    
    def _clear_crawl_sessions(self):
        """Clear crawl session history."""
        self.stdout.write('\nClearing crawl sessions...')
        
        session_count = CrawlSession.objects.count()
        if session_count > 0:
            CrawlSession.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'✓ Deleted {session_count} crawl sessions'))
        else:
            self.stdout.write('No crawl sessions to delete')