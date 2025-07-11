"""
Category-related views for ASDA scraper.

File: asda_scraper/views/category_views.py
"""

import logging
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.db.models import Q, Count

from asda_scraper.models import AsdaCategory
from .base import is_admin_user

logger = logging.getLogger(__name__)


@method_decorator([login_required, user_passes_test(is_admin_user)], name='dispatch')
class CategoryListView(ListView):
    """
    Enhanced list view for ASDA categories with filtering and search.
    """
    model = AsdaCategory
    template_name = 'asda_scraper/categories.html'
    context_object_name = 'categories'
    paginate_by = 50
    
    def get_queryset(self):
        """Filter categories based on search and filters."""
        queryset = AsdaCategory.objects.all().order_by('name')
        
        # Search filter
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(url_code__icontains=search_query)
            )
        
        # Status filter
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['status_filter'] = self.request.GET.get('status', '')
        context['total_categories'] = AsdaCategory.objects.count()
        context['active_categories'] = AsdaCategory.objects.filter(is_active=True).count()
        return context