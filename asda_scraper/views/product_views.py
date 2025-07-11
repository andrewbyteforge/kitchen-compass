"""
Product-related views for ASDA scraper.

File: asda_scraper/views/product_views.py
"""

import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.db.models import Q, Count
from django.db import transaction
from django.utils import timezone

from asda_scraper.models import AsdaProduct, AsdaCategory
from .base import is_admin_user

logger = logging.getLogger(__name__)


@method_decorator([login_required, user_passes_test(is_admin_user)], name='dispatch')
class ProductListView(ListView):
    """
    Enhanced list view for ASDA products with filtering and search.
    """
    model = AsdaProduct
    template_name = 'asda_scraper/products.html'
    context_object_name = 'products'
    paginate_by = 50
    
    def get_queryset(self):
        """Filter products based on search and filters."""
        queryset = AsdaProduct.objects.select_related('category').order_by('-created_at')
        
        # Search filter
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(asda_id__icontains=search_query) |
                Q(category__name__icontains=search_query)
            )
        
        # Category filter
        category_filter = self.request.GET.get('category')
        if category_filter:
            queryset = queryset.filter(category_id=category_filter)
        
        # Price range filter
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                pass
        
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                pass
        
        # Stock filter
        stock_filter = self.request.GET.get('stock')
        if stock_filter == 'in_stock':
            queryset = queryset.filter(in_stock=True)
        elif stock_filter == 'out_of_stock':
            queryset = queryset.filter(in_stock=False)
        
        # Sale filter
        sale_filter = self.request.GET.get('sale')
        if sale_filter == 'on_sale':
            queryset = queryset.filter(was_price__isnull=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['category_filter'] = self.request.GET.get('category', '')
        context['min_price'] = self.request.GET.get('min_price', '')
        context['max_price'] = self.request.GET.get('max_price', '')
        context['stock_filter'] = self.request.GET.get('stock', '')
        context['sale_filter'] = self.request.GET.get('sale', '')
        context['categories'] = AsdaCategory.objects.filter(is_active=True).order_by('name')
        context['total_products'] = AsdaProduct.objects.count()
        return context


@login_required
@user_passes_test(is_admin_user)
def delete_products_view(request):
    """
    Web interface for deleting products.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        HttpResponse: Rendered template or JsonResponse
    """
    if request.method == 'POST':
        try:
            # Get deletion parameters
            delete_type = request.POST.get('delete_type')
            confirm = request.POST.get('confirm') == 'true'
            
            if not confirm:
                return JsonResponse({
                    'success': False,
                    'message': 'Please confirm the deletion'
                })
            
            deleted_count = 0
            
            with transaction.atomic():
                if delete_type == 'all':
                    # Delete all products
                    deleted_count = AsdaProduct.objects.all().delete()[0]
                    # Reset all category counts
                    AsdaCategory.objects.update(product_count=0)
                    
                elif delete_type == 'category':
                    # Delete by category
                    category_id = request.POST.get('category_id')
                    if category_id:
                        queryset = AsdaProduct.objects.filter(category_id=category_id)
                        deleted_count = queryset.delete()[0]
                        # Update category count
                        category = AsdaCategory.objects.get(pk=category_id)
                        category.product_count = 0
                        category.save()
                
                elif delete_type == 'old':
                    # Delete old products
                    days = int(request.POST.get('days', 30))
                    cutoff_date = timezone.now() - timezone.timedelta(days=days)
                    queryset = AsdaProduct.objects.filter(updated_at__lt=cutoff_date)
                    deleted_count = queryset.delete()[0]
                    
                elif delete_type == 'duplicates':
                    # Delete duplicates
                    deleted_count = _delete_duplicate_products()
                
                elif delete_type == 'out_of_stock':
                    # Delete out of stock products
                    queryset = AsdaProduct.objects.filter(in_stock=False)
                    deleted_count = queryset.delete()[0]
                
                # Update category counts
                for category in AsdaCategory.objects.all():
                    category.product_count = category.products.count()
                    category.save()
                
                # Log the deletion
                logger.info(f"User {request.user} deleted {deleted_count} products (type: {delete_type})")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully deleted {deleted_count} products',
                    'deleted_count': deleted_count
                })
                
        except Exception as e:
            logger.error(f"Error deleting products: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    # GET request - show deletion options
    context = {
        'total_products': AsdaProduct.objects.count(),
        'categories': AsdaCategory.objects.filter(product_count__gt=0).order_by('name'),
        'out_of_stock_count': AsdaProduct.objects.filter(in_stock=False).count(),
        'duplicate_count': _get_duplicate_count(),
    }
    
    return render(request, 'asda_scraper/delete_products.html', context)


def _get_duplicate_count():
    """
    Get count of duplicate products.
    
    Returns:
        int: Number of duplicate products
    """
    duplicates = (AsdaProduct.objects
                 .values('asda_id')
                 .annotate(count=Count('id'))
                 .filter(count__gt=1))
    
    total_duplicates = 0
    for item in duplicates:
        # Count all but one (the one we'd keep)
        total_duplicates += item['count'] - 1
    
    return total_duplicates


def _delete_duplicate_products():
    """
    Delete duplicate products, keeping the newest.
    
    Returns:
        int: Number of products deleted
    """
    duplicates = (AsdaProduct.objects
                 .values('asda_id')
                 .annotate(count=Count('id'))
                 .filter(count__gt=1))
    
    ids_to_delete = []
    for item in duplicates:
        products = AsdaProduct.objects.filter(
            asda_id=item['asda_id']
        ).order_by('-created_at')
        # Keep newest, delete rest
        ids_to_delete.extend(products[1:].values_list('id', flat=True))
    
    return AsdaProduct.objects.filter(id__in=ids_to_delete).delete()[0]