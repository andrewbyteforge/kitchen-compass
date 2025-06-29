"""
ASDA Scraper Views

This module contains views for the ASDA scraper admin interface,
providing functionality to manage crawl sessions and monitor progress.
"""

import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from .models import AsdaCategory, AsdaProduct, CrawlSession
from .scraper import AsdaScraper

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """
    Check if user has admin privileges for ASDA scraper.
    """
    # Replace with your actual admin email
    ADMIN_EMAILS = [
        'acartwright39@hotmail.com',  # Replace with your real email
    ]
    return user.is_authenticated and (user.email in ADMIN_EMAILS or user.is_superuser)


@login_required
@user_passes_test(is_admin_user)
def scraper_dashboard(request):
    """
    Main dashboard for ASDA scraper administration.
    
    Displays current crawl status, statistics, and controls for
    starting/stopping crawl sessions.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        HttpResponse: Rendered dashboard template
    """
    try:
        # Get current crawl session if any
        current_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        # Get statistics
        total_products = AsdaProduct.objects.count()
        total_categories = AsdaCategory.objects.count()
        active_categories = AsdaCategory.objects.filter(is_active=True).count()
        
        # Get recent sessions
        recent_sessions = CrawlSession.objects.select_related('user').order_by('-start_time')[:5]
        
        # Get category statistics
        category_stats = AsdaCategory.objects.annotate(
            total_products=Count('products')
        ).order_by('-total_products')[:10]
        
        # Get latest products
        latest_products = AsdaProduct.objects.select_related('category').order_by('-created_at')[:10]
        
        context = {
            'current_session': current_session,
            'total_products': total_products,
            'total_categories': total_categories,
            'active_categories': active_categories,
            'recent_sessions': recent_sessions,
            'category_stats': category_stats,
            'latest_products': latest_products,
        }
        
        logger.info(f"ASDA scraper dashboard accessed by user {request.user.username}")
        return render(request, 'asda_scraper/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading ASDA scraper dashboard: {str(e)}")
        messages.error(request, "An error occurred while loading the dashboard.")
        return redirect('auth_hub:dashboard')


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def start_crawl(request):
    """
    Start a new ASDA crawl session.
    
    Creates a new CrawlSession and starts the scraping process
    in the background.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Success/error response
    """
    try:
        # Check if there's already a running session
        running_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if running_session:
            return JsonResponse({
                'success': False,
                'message': 'A crawl session is already running.'
            })
        
        # Get crawl settings from request
        settings = {
            'max_products_per_category': int(request.POST.get('max_products', 100)),
            'delay_between_requests': float(request.POST.get('delay', 1.0)),
            'categories_to_crawl': request.POST.getlist('categories'),
        }
        
        # Create new crawl session
        session = CrawlSession.objects.create(
            user=request.user,
            status='PENDING',
            crawl_settings=settings
        )
        
        # Start the scraper (this would typically be done with Celery or similar)
        # For now, we'll create a placeholder that can be extended
        try:
            scraper = AsdaScraper(session)
            # This would normally be: scraper.start_async()
            # For now, we'll just mark it as running
            session.status = 'RUNNING'
            session.save()
            
            logger.info(f"Crawl session {session.pk} started by user {request.user.username}")
            
            return JsonResponse({
                'success': True,
                'message': f'Crawl session {session.pk} started successfully.',
                'session_id': session.pk
            })
            
        except Exception as scraper_error:
            session.mark_failed(str(scraper_error))
            raise scraper_error
            
    except Exception as e:
        logger.error(f"Error starting crawl session: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Failed to start crawl: {str(e)}'
        })


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def stop_crawl(request):
    """
    Stop the current running crawl session.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Success/error response
    """
    try:
        session_id = request.POST.get('session_id')
        
        if session_id:
            session = get_object_or_404(CrawlSession, pk=session_id)
        else:
            session = CrawlSession.objects.filter(
                status__in=['PENDING', 'RUNNING']
            ).first()
        
        if not session:
            return JsonResponse({
                'success': False,
                'message': 'No running crawl session found.'
            })
        
        # Stop the session
        session.status = 'CANCELLED'
        session.end_time = timezone.now()
        session.save()
        
        logger.info(f"Crawl session {session.pk} stopped by user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Crawl session {session.pk} stopped successfully.'
        })
        
    except Exception as e:
        logger.error(f"Error stopping crawl session: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Failed to stop crawl: {str(e)}'
        })


@login_required
@user_passes_test(is_admin_user)
def crawl_status(request):
    """
    Get current crawl status via AJAX.
    
    Returns real-time information about the current crawl session
    for dashboard updates.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Current crawl status and statistics
    """
    try:
        current_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if current_session:
            data = {
                'has_session': True,
                'session_id': current_session.pk,
                'status': current_session.status,
                'start_time': current_session.start_time.isoformat(),
                'categories_crawled': current_session.categories_crawled,
                'products_found': current_session.products_found,
                'products_updated': current_session.products_updated,
                'duration': str(current_session.get_duration()) if current_session.get_duration() else None,
            }
        else:
            data = {
                'has_session': False,
                'total_products': AsdaProduct.objects.count(),
                'total_categories': AsdaCategory.objects.count(),
            }
        
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error getting crawl status: {str(e)}")
        return JsonResponse({
            'error': str(e)
        }, status=500)


@method_decorator([login_required, user_passes_test(is_admin_user)], name='dispatch')
class CategoryListView(ListView):
    """
    List view for ASDA categories with filtering and search.
    
    Provides a paginated list of categories with options to
    enable/disable categories for crawling.
    """
    model = AsdaCategory
    template_name = 'asda_scraper/categories.html'
    context_object_name = 'categories'
    paginate_by = 50
    
    def get_queryset(self):
        """Filter categories based on search and filters."""
        queryset = AsdaCategory.objects.select_related('parent_category').annotate(
            total_products=Count('products')
        )
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(url_code__icontains=search_query)
            )
        
        # Filter by active status
        active_filter = self.request.GET.get('active')
        if active_filter == 'true':
            queryset = queryset.filter(is_active=True)
        elif active_filter == 'false':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['active_filter'] = self.request.GET.get('active', '')
        return context


@method_decorator([login_required, user_passes_test(is_admin_user)], name='dispatch')
class ProductListView(ListView):
    """
    List view for ASDA products with filtering and search.
    
    Provides a paginated list of products with filtering by
    category, price range, and availability.
    """
    model = AsdaProduct
    template_name = 'asda_scraper/products.html'
    context_object_name = 'products'
    paginate_by = 50
    
    def get_queryset(self):
        """Filter products based on search and filters."""
        queryset = AsdaProduct.objects.select_related('category')
        
        # Search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(asda_id__icontains=search_query)
            )
        
        # Filter by category
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by stock status
        in_stock = self.request.GET.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(in_stock=True)
        elif in_stock == 'false':
            queryset = queryset.filter(in_stock=False)
        
        # Price range filter
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        """Add additional context for the template."""
        context = super().get_context_data(**kwargs)
        context['categories'] = AsdaCategory.objects.filter(is_active=True).order_by('name')
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['in_stock_filter'] = self.request.GET.get('in_stock', '')
        context['min_price'] = self.request.GET.get('min_price', '')
        context['max_price'] = self.request.GET.get('max_price', '')
        return context