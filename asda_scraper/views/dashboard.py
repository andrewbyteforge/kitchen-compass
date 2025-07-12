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
from django.conf import settings

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
    # 1) Core scraper stats
    stats = get_dashboard_statistics()

    recent_sessions = (
        CrawlSession.objects
        .select_related('user')
        .order_by('-start_time')[:5]
    )

    current_session = (
        CrawlSession.objects
        .filter(status__in=['PENDING', 'RUNNING'])
        .first()
    )

    category_stats = (
        AsdaCategory.objects
        .annotate(total_products=Count('products'))
        .filter(total_products__gt=0)
        .order_by('-total_products')[:5]
    )

    latest_products = (
        AsdaProduct.objects
        .select_related('category')
        .order_by('-created_at')[:6]
    )

    # 2) Proxy stats initialization
    proxy_config = None
    active_proxies = 0
    total_proxies = 0
    today_proxy_cost = Decimal('0.00')

    try:
        from asda_scraper.models import ProxyConfiguration, EnhancedProxyModel

        # Load the active proxy configuration
        proxy_config = ProxyConfiguration.objects.filter(is_active=True).first()

        # Only gather proxy data if the table exists
        if EnhancedProxyModel._meta.db_table in connection.introspection.table_names():
            total_proxies = EnhancedProxyModel.objects.count()
            active_proxies = EnhancedProxyModel.objects.filter(status='active').count()

            # Calculate today's cost for premium & standard proxies
            today = timezone.now().date()
            desired_tiers = {'premium', 'standard'}

            # Which provider names map to those tiers?
            providers_for_tiers = [
                provider_name
                for provider_name, cfg in settings.PROXY_PROVIDERS.items()
                if cfg.get('tier') in desired_tiers
            ]

            today_cost = (
                EnhancedProxyModel.objects
                .filter(
                    provider__in=providers_for_tiers,
                    last_used__date=today
                )
                .aggregate(total=Sum('total_cost'))['total']
                or Decimal('0.00')
            )
            today_proxy_cost = today_cost

    except Exception as e:
        # Log at debug level if proxies aren’t set up yet
        logger.debug(f"Proxy models not available: {e}")

    # 3) Build context and render
    context = {
        # Core stats
        'total_products':        stats.get('total_products', 0),
        'total_categories':      stats.get('total_categories', 0),
        'active_categories':     stats.get('active_categories', 0),
        'products_on_sale':      stats.get('products_on_sale', 0),
        'recent_products':       stats.get('recent_products', 0),
        'products_with_images':  stats.get('products_with_images', 0),

        # Sessions
        'recent_sessions':       recent_sessions,
        'current_session':       current_session,
        'total_sessions':        stats.get('total_sessions', 0),
        'successful_sessions':   stats.get('successful_sessions', 0),
        'failed_sessions':       stats.get('failed_sessions', 0),

        # Misc
        'category_stats':        category_stats,
        'latest_products':       latest_products,

        # Proxy
        'proxy_config':          proxy_config,
        'active_proxies':        active_proxies,
        'total_proxies':         total_proxies,
        'today_proxy_cost':      today_proxy_cost,
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
        if not config or not getattr(config, 'enable_proxy_service', False):
            return {
                'enabled': False,
                'message': 'Proxy service is disabled',
            }

        active_count = EnhancedProxyModel.objects.filter(status='active').count()

        return {
            'enabled': True,
            'active_proxies': active_count,
            'config': config,
            'message': f'{active_count} active proxies available',
        }
    except Exception:
        return {
            'enabled': False,
            'message': 'Proxy system not configured',
        }
