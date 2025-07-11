"""
Dashboard views for ASDA scraper.

File: asda_scraper/views/dashboard.py
"""

import logging
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum
from django.utils import timezone
from django.db import connection

from asda_scraper.models import AsdaCategory, AsdaProduct, CrawlSession
from .base import is_admin_user, get_dashboard_statistics

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(is_admin_user)
def scraper_dashboard(request):
    """
    Enhanced dashboard view with proxy information.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        HttpResponse: Rendered dashboard template
    """
    # Get comprehensive statistics using the helper function
    stats = get_dashboard_statistics()
    
    # Get recent crawl sessions
    recent_sessions = CrawlSession.objects.select_related('user').order_by('-start_time')[:5]
    
    # Get current/active session
    current_session = CrawlSession.objects.filter(
        status__in=['PENDING', 'RUNNING']
    ).first()
    
    # Get category statistics
    category_stats = AsdaCategory.objects.annotate(
        total_products=Count('products')
    ).filter(total_products__gt=0).order_by('-total_products')[:5]
    
    # Get latest products
    latest_products = AsdaProduct.objects.select_related('category').order_by('-created_at')[:6]
    
    # NEW: Get proxy configuration and statistics
    proxy_config = None
    active_proxies = 0
    total_proxies = 0
    today_proxy_cost = Decimal('0.00')
    
    try:
        # Import proxy models - use conditional import in case models don't exist yet
        from asda_scraper.models import ProxyConfiguration, EnhancedProxyModel
        
        # Get active proxy configuration
        proxy_config = ProxyConfiguration.objects.filter(is_active=True).first()
        
        # Get proxy counts
        if EnhancedProxyModel._meta.db_table in connection.introspection.table_names():
            total_proxies = EnhancedProxyModel.objects.count()
            active_proxies = EnhancedProxyModel.objects.filter(status='active').count()
            
            # Calculate today's proxy cost
            today = timezone.now().date()
            today_cost = EnhancedProxyModel.objects.filter(
                tier__in=['premium', 'standard'],
                last_used__date=today
            ).aggregate(
                total=Sum('total_cost')
            )['total'] or Decimal('0.00')
            today_proxy_cost = today_cost
            
    except Exception as e:
        # If proxy models don't exist yet, continue without them
        logger.debug(f"Proxy models not available: {e}")
    
    context = {
        # Use values from the statistics function
        'total_products': stats.get('total_products', 0),
        'total_categories': stats.get('total_categories', 0),
        'active_categories': stats.get('active_categories', 0),
        'products_on_sale': stats.get('products_on_sale', 0),
        'recent_products': stats.get('recent_products', 0),
        'products_with_images': stats.get('products_with_images', 0),
        
        # Session data
        'recent_sessions': recent_sessions,
        'current_session': current_session,
        'total_sessions': stats.get('total_sessions', 0),
        'successful_sessions': stats.get('successful_sessions', 0),
        'failed_sessions': stats.get('failed_sessions', 0),
        
        # Other data
        'category_stats': category_stats,
        'latest_products': latest_products,
        
        # Proxy-related context
        'proxy_config': proxy_config,
        'active_proxies': active_proxies,
        'total_proxies': total_proxies,
        'today_proxy_cost': today_proxy_cost,
    }
    
    return render(request, 'asda_scraper/dashboard.html', context)


def get_proxy_status_summary():
    """
    Get a summary of proxy system status.
    
    Returns:
        dict: Proxy status information
    """
    try:
        from asda_scraper.models import ProxyConfiguration, EnhancedProxyModel
        
        config = ProxyConfiguration.objects.filter(is_active=True).first()
        if not config or not config.enable_proxy_service:
            return {
                'enabled': False,
                'message': 'Proxy service is disabled'
            }
        
        active_count = EnhancedProxyModel.objects.filter(status='active').count()
        
        return {
            'enabled': True,
            'active_proxies': active_count,
            'config': config,
            'message': f'{active_count} active proxies available'
        }
    except:
        return {
            'enabled': False,
            'message': 'Proxy system not configured'
        }