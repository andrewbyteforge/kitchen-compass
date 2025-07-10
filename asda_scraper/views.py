"""
Updated ASDA Scraper Views

This module contains updated views that integrate with the refactored Selenium scraper,
providing improved error handling, logging, and user feedback.

File: asda_scraper/views.py (REPLACE EXISTING)
"""

import logging
import json
import threading
import time
from typing import Dict, Any
from decimal import Decimal  # ADD THIS IMPORT
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum  # ADD Sum HERE
from django.utils import timezone
from django.db import transaction, connection  # ADD connection HERE
import os

from .models import AsdaCategory, AsdaProduct, CrawlSession
# Import from the selenium_scraper.py file directly
from .selenium_scraper import create_selenium_scraper, ScrapingResult, ScraperException, DriverSetupException

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """
    Check if user has admin privileges for ASDA scraper.
    
    Args:
        user: Django user object
        
    Returns:
        bool: True if user has admin access
    """
    ADMIN_EMAILS = [
        'acartwright39@hotmail.com',  # Your actual email
    ]
    return user.is_authenticated and (user.email in ADMIN_EMAILS or user.is_superuser)


@login_required
@user_passes_test(is_admin_user)
def scraper_dashboard(request):
    """
    Enhanced dashboard view with proxy information.
    
    Update your existing scraper_dashboard function with this code.
    """
    # Get comprehensive statistics using the helper function
    stats = _get_dashboard_statistics()
    
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
    """Get a summary of proxy system status."""
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


def _get_dashboard_statistics() -> Dict[str, Any]:
    """
    Get comprehensive dashboard statistics.

    Returns:
        Dict[str, Any]: Dictionary containing various statistics
    """
    try:
        return {
            'total_products': AsdaProduct.objects.count(),
            'total_categories': AsdaCategory.objects.count(),
            'active_categories': AsdaCategory.objects.filter(is_active=True).count(),
            'products_with_images': AsdaProduct.objects.exclude(image_url='').count(),
            'products_on_sale': AsdaProduct.objects.filter(was_price__isnull=False).count(),
            'recent_products': AsdaProduct.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'total_sessions': CrawlSession.objects.count(),
            'successful_sessions': CrawlSession.objects.filter(status='COMPLETED').count(),
            'failed_sessions': CrawlSession.objects.filter(status='FAILED').count(),
        }
    except Exception as e:
        logger.error(f"Error getting dashboard statistics: {e}")
        return {}


def _parse_error_message(error_log: str) -> Dict[str, Any]:
    """
    Parse error log to extract useful information.
    
    Args:
        error_log: Raw error log string
        
    Returns:
        Dict[str, Any]: Parsed error information
    """
    try:
        # Try to extract structured error information
        if 'Error Code:' in error_log:
            lines = error_log.split('\n')
            error_info = {}
            
            for line in lines:
                if 'Error Code:' in line:
                    error_info['code'] = line.split('Error Code:')[1].strip()
                elif 'Context:' in line:
                    error_info['context'] = line.split('Context:')[1].strip()
            
            return error_info
        else:
            return {'message': error_log[:200]}  # Truncate long messages
    except Exception:
        return {'message': 'Error parsing error log'}


def _check_system_health() -> Dict[str, Any]:
    """
    Check system health for scraper components.
    
    Returns:
        Dict[str, Any]: System health status
    """
    health = {
        'overall': 'healthy',
        'issues': [],
        'warnings': []
    }
    
    try:
        # Check if Chrome/ChromeDriver is available
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            
            driver = webdriver.Chrome(options=options)
            driver.quit()
            
        except Exception as e:
            health['issues'].append('Chrome WebDriver not available')
            health['overall'] = 'degraded'
        
        # Check for stuck sessions
        stuck_sessions = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING'],
            start_time__lt=timezone.now() - timezone.timedelta(hours=2)
        ).count()
        
        if stuck_sessions > 0:
            health['warnings'].append(f'{stuck_sessions} sessions appear to be stuck')
            if health['overall'] == 'healthy':
                health['overall'] = 'warning'
        
        # Check database connectivity
        try:
            AsdaCategory.objects.count()
        except Exception:
            health['issues'].append('Database connectivity issues')
            health['overall'] = 'critical'
        
    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        health['issues'].append('Health check failed')
        health['overall'] = 'unknown'
    
    return health


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def start_crawl(request):
    """
    Start a new crawl session with improved error handling.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Result of the crawl start attempt
    """
    try:
        # Check if a crawl is already running
        existing_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if existing_session:
            return JsonResponse({
                'success': False,
                'message': f'Crawl session {existing_session.pk} is already running'
            })
        
        # Parse crawl settings
        crawl_settings = _parse_crawl_settings(request)
        
        # Validate settings
        validation_errors = _validate_crawl_settings(crawl_settings)
        if validation_errors:
            return JsonResponse({
                'success': False,
                'message': 'Invalid crawl settings',
                'errors': validation_errors
            })
        
        # Create new crawl session
        session = CrawlSession.objects.create(
            user=request.user,
            status='PENDING',
            crawl_settings=crawl_settings
        )
        
        # Start scraper in background thread
        thread = threading.Thread(
            target=run_selenium_scraper_with_error_handling,
            args=(session,)
        )
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started crawl session {session.pk} by user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Crawl session {session.pk} started successfully',
            'session_id': session.pk
        })
        
    except Exception as e:
        logger.error(f"Error starting crawl session: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Failed to start crawl: {str(e)}'
        })


def _parse_crawl_settings(request) -> Dict[str, Any]:
    """
    Parse crawl settings from request.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        Dict[str, Any]: Parsed crawl settings
    """
    # Default settings
    settings = {
        'max_categories': 10,
        'category_priority': 2,
        'max_products_per_category': 100,
        'delay_between_requests': 2.0,
        'use_selenium': True,
        'headless': False,
        'respect_robots_txt': True,
    }
    
    try:
        # Parse form data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        # Update settings with user input
        for key in ['max_categories', 'category_priority', 'max_products_per_category']:
            if key in data:
                try:
                    settings[key] = int(data[key])
                except (ValueError, TypeError):
                    pass
        
        for key in ['delay_between_requests']:
            if key in data:
                try:
                    settings[key] = float(data[key])
                except (ValueError, TypeError):
                    pass
        
        for key in ['headless', 'use_selenium']:
            if key in data:
                settings[key] = str(data.get(key, 'false')).lower() == 'true'
        
    except Exception as e:
        logger.warning(f"Error parsing crawl settings: {e}")
    
    return settings


def _validate_crawl_settings(settings: Dict[str, Any]) -> list:
    """
    Validate crawl settings.
    
    Args:
        settings: Dictionary of crawl settings
        
    Returns:
        list: List of validation errors
    """
    errors = []
    
    # Validate numeric ranges
    if settings.get('max_categories', 0) <= 0 or settings.get('max_categories', 0) > 50:
        errors.append('max_categories must be between 1 and 50')
    
    if settings.get('category_priority', 0) <= 0 or settings.get('category_priority', 0) > 5:
        errors.append('category_priority must be between 1 and 5')
    
    if settings.get('max_products_per_category', 0) <= 0:
        errors.append('max_products_per_category must be greater than 0')
    
    if settings.get('delay_between_requests', 0) < 0:
        errors.append('delay_between_requests cannot be negative')
    
    return errors


def run_selenium_scraper_with_error_handling(session: CrawlSession):
    """
    Run the Selenium scraper with comprehensive error handling.
    
    Args:
        session: CrawlSession object to process
    """
    scraper = None
    
    try:
        logger.info(f"Starting Selenium scraper for session {session.pk}")
        
        # Get headless setting
        headless = session.crawl_settings.get('headless', False)
        
        # Create and run scraper
        scraper = create_selenium_scraper(session, headless=headless)
        result = scraper.start_crawl()
        
        # Log results
        _log_scraping_results(session, result)
        
        # Handle any errors that occurred during scraping
        if result.errors:
            error_summary = _create_error_summary(result.errors)
            # Update error_log instead of error_message
            session.error_log = error_summary
            session.save()
            
            logger.warning(f"Session {session.pk} completed with {len(result.errors)} errors")
        else:
            logger.info(f"Session {session.pk} completed successfully")
        
    except DriverSetupException as e:
        error_msg = f"WebDriver setup failed: {str(e)}"
        logger.error(error_msg)
        session.mark_failed(error_msg)
        
    except ScraperException as e:
        error_msg = f"Scraper error: {str(e)}"
        logger.error(error_msg)
        session.mark_failed(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        session.mark_failed(error_msg)
    
    finally:
        # Ensure proper cleanup
        if scraper:
            try:
                scraper._cleanup()
            except Exception as cleanup_error:
                logger.error(f"Error during scraper cleanup: {cleanup_error}")
        
        # Log final session state
        session.refresh_from_db()
        logger.info(f"Session {session.pk} final status: {session.status}")


def _log_scraping_results(session: CrawlSession, result: ScrapingResult):
    """
    Log comprehensive scraping results.
    
    Args:
        session: CrawlSession object
        result: ScrapingResult object
    """
    logger.info(f"Scraping Results for Session {session.pk}:")
    logger.info(f"  Products Found: {result.products_found}")
    logger.info(f"  Products Saved: {result.products_saved}")
    logger.info(f"  Categories Processed: {result.categories_processed}")
    logger.info(f"  Duration: {result.duration:.2f} seconds")
    logger.info(f"  Error Count: {len(result.errors)}")
    
    if result.errors:
        logger.warning("Errors encountered:")
        for i, error in enumerate(result.errors[:5], 1):  # Log first 5 errors
            logger.warning(f"  {i}. {error}")
        if len(result.errors) > 5:
            logger.warning(f"  ... and {len(result.errors) - 5} more errors")


def _create_error_summary(errors: list) -> str:
    """
    Create a summary of errors for storage.
    
    Args:
        errors: List of error strings
        
    Returns:
        str: Formatted error summary
    """
    if not errors:
        return ""
    
    summary_lines = [f"Total Errors: {len(errors)}", ""]
    
    # Group similar errors
    error_counts = {}
    for error in errors:
        # Extract error type from error message
        error_type = error.split(':')[0] if ':' in error else 'Unknown'
        error_counts[error_type] = error_counts.get(error_type, 0) + 1
    
    # Add error type summary
    summary_lines.append("Error Types:")
    for error_type, count in sorted(error_counts.items()):
        summary_lines.append(f"  {error_type}: {count}")
    
    # Add first few actual errors
    summary_lines.extend(["", "Sample Errors:"])
    for i, error in enumerate(errors[:3], 1):
        summary_lines.append(f"  {i}. {error}")
    
    if len(errors) > 3:
        summary_lines.append(f"  ... and {len(errors) - 3} more")
    
    return "\n".join(summary_lines)


@login_required
@user_passes_test(is_admin_user)
@require_http_methods(["POST"])
def stop_crawl(request):
    """
    Stop the current crawl session with improved handling.
    
    Args:
        request: Django HttpRequest object
        
    Returns:
        JsonResponse: Result of the stop attempt
    """
    try:
        current_session = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING']
        ).first()
        
        if not current_session:
            return JsonResponse({
                'success': False,
                'message': 'No active crawl session found'
            })
        
        # Mark session as stopped
        current_session.status = 'CANCELLED'  # Use CANCELLED status
        current_session.end_time = timezone.now()
        # Use error_log instead of error_message
        if not current_session.error_log:
            current_session.error_log = 'Stopped by user'
        current_session.save()
        
        logger.info(f"Crawl session {current_session.pk} stopped by user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'Crawl session {current_session.pk} stopped successfully. '
                      'The browser may continue until the current operation completes.'
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
    Get current crawl status via AJAX with enhanced information.
    
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
            # Calculate progress percentage
            total_categories = AsdaCategory.objects.filter(is_active=True).count()
            progress_percent = 0
            if total_categories > 0:
                progress_percent = (current_session.categories_crawled / total_categories) * 100
            
            # Estimate remaining time
            duration = current_session.get_duration()
            estimated_remaining = None
            if duration and current_session.categories_crawled > 0:
                time_per_category = duration.total_seconds() / current_session.categories_crawled
                remaining_categories = total_categories - current_session.categories_crawled
                estimated_remaining = time_per_category * remaining_categories
            
            data = {
                'has_session': True,
                'session_id': current_session.pk,
                'status': current_session.status,
                'start_time': current_session.start_time.isoformat(),
                'categories_crawled': current_session.categories_crawled,
                'total_categories': total_categories,
                'progress_percent': round(progress_percent, 1),
                'products_found': current_session.products_found,
                'products_updated': current_session.products_updated,
                'duration': str(duration) if duration else None,
                'estimated_remaining': estimated_remaining,
                'using_selenium': current_session.crawl_settings.get('use_selenium', False),
                'error_log': current_session.error_log,  # Use error_log instead of error_message
            }
        else:
            data = {
                'has_session': False,
                'total_products': AsdaProduct.objects.count(),
                'total_categories': AsdaCategory.objects.count(),
                'system_health': _check_system_health(),
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
def session_detail(request, session_id):
    """
    Detailed view of a specific crawl session.
    
    Args:
        request: Django HttpRequest object
        session_id: ID of the crawl session
        
    Returns:
        HttpResponse: Rendered session detail template
    """
    try:
        session = get_object_or_404(CrawlSession, pk=session_id)
        
        # Parse error log if present
        error_summary = None
        if session.error_log:  # Use error_log instead of error_message
            error_summary = _parse_error_message(session.error_log)
        
        # Get session statistics
        session_stats = {
            'duration': session.get_duration(),
            'products_per_minute': 0,
            'categories_per_minute': 0,
        }
        
        if session_stats['duration']:
            minutes = session_stats['duration'].total_seconds() / 60
            if minutes > 0:
                session_stats['products_per_minute'] = round(session.products_found / minutes, 1)
                session_stats['categories_per_minute'] = round(session.categories_crawled / minutes, 1)
        
        context = {
            'session': session,
            'error_summary': error_summary,
            'session_stats': session_stats,
        }
        
        return render(request, 'asda_scraper/session_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error loading session detail: {e}")
        messages.error(request, "An error occurred while loading the session details.")
        return redirect('asda_scraper:dashboard')


# Additional utility functions as before...
# (keeping all the other functions from the previous version)



# Add these views to asda_scraper/views.py

@login_required
@user_passes_test(is_admin_user)
def delete_products_view(request):
    """
    Web interface for deleting products.
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
                    from django.db.models import Count
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
                    
                    deleted_count = AsdaProduct.objects.filter(
                        id__in=ids_to_delete
                    ).delete()[0]
                
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
    """Get count of duplicate products."""
    from django.db.models import Count
    duplicates = (AsdaProduct.objects
                 .values('asda_id')
                 .annotate(count=Count('id'))
                 .filter(count__gt=1))
    
    total_duplicates = 0
    for item in duplicates:
        # Count all but one (the one we'd keep)
        total_duplicates += item['count'] - 1
    
    return total_duplicates


# Add URL pattern to urls.py:
# path('delete-products/', delete_products_view, name='delete_products'),