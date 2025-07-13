"""
Views for ASDA scraper admin dashboard.

Provides dashboard and crawler control functionality.
"""

import logging
import json
import subprocess
import threading
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.decorators import user_passes_test
from django.core.management import call_command
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from .models import Product, Category, CrawlSession, NutritionInfo, CrawlQueue

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """
    Check if user has admin privileges for ASDA scraper.

    Args:
        user: Django user object

    Returns:
        bool: True if user is admin or superuser
    """
    return user.is_authenticated and (user.is_staff or user.is_superuser)


class DashboardView(UserPassesTestMixin, TemplateView):
    """
    Main dashboard view for ASDA scraper.

    Displays crawler statistics and controls.
    """

    template_name = 'asda_scraper/dashboard.html'

    def test_func(self):
        """Check if user has permission to access dashboard."""
        return is_admin_user(self.request.user)

    def get_context_data(self, **kwargs):
        """
        Add dashboard statistics to context.

        Returns:
            dict: Context data for template
        """
        context = super().get_context_data(**kwargs)

        try:
            # Product statistics
            context['total_products'] = Product.objects.count()
            context['products_with_nutrition'] = Product.objects.filter(
                nutrition_scraped=True
            ).count()
            context['products_on_offer'] = Product.objects.filter(
                on_offer=True
            ).count()
            context['products_available'] = Product.objects.filter(
                is_available=True
            ).count()

            # Category statistics
            context['total_categories'] = Category.objects.count()
            context['active_categories'] = Category.objects.filter(
                is_active=True
            ).count()

            # Recent crawl sessions
            context['recent_sessions'] = CrawlSession.objects.all()[:10]

            # Current crawler status
            context['category_crawler_running'] = CrawlSession.objects.filter(
                crawler_type='CATEGORY',
                status='RUNNING'
            ).exists()
            context['product_list_crawler_running'] = CrawlSession.objects.filter(
                crawler_type='PRODUCT_LIST',
                status='RUNNING'
            ).exists()
            context['product_detail_crawler_running'] = CrawlSession.objects.filter(
                crawler_type='PRODUCT_DETAIL',
                status='RUNNING'
            ).exists()

            # Last crawl times
            last_category_crawl = CrawlSession.objects.filter(
                crawler_type='CATEGORY'
            ).first()
            last_product_list_crawl = CrawlSession.objects.filter(
                crawler_type='PRODUCT_LIST'
            ).first()
            last_product_detail_crawl = CrawlSession.objects.filter(
                crawler_type='PRODUCT_DETAIL'
            ).first()

            context['last_category_crawl'] = (
                last_category_crawl.started_at if last_category_crawl else None
            )
            context['last_product_list_crawl'] = (
                last_product_list_crawl.started_at if last_product_list_crawl else None
            )
            context['last_product_detail_crawl'] = (
                last_product_detail_crawl.started_at if last_product_detail_crawl else None
            )

            # Queue statistics
            context['category_queue_pending'] = CrawlQueue.objects.filter(
                queue_type='CATEGORY',
                status='PENDING'
            ).count()
            context['product_list_queue_pending'] = CrawlQueue.objects.filter(
                queue_type='PRODUCT_LIST',
                status='PENDING'
            ).count()
            context['product_detail_queue_pending'] = CrawlQueue.objects.filter(
                queue_type='PRODUCT_DETAIL',
                status='PENDING'
            ).count()

            logger.info(f"Dashboard accessed by {self.request.user.username}")

        except Exception as e:
            logger.error(f"Error loading dashboard data: {str(e)}")
            messages.error(
                self.request,
                "Error loading dashboard data. Please try again."
            )

        return context


@user_passes_test(is_admin_user)
def start_category_crawler(request):
    """
    Start the category mapper crawler.

    Args:
        request: HTTP request object

    Returns:
        HttpResponse: Redirect to dashboard
    """
    try:
        # Check if crawler is already running
        if CrawlSession.objects.filter(
            crawler_type='CATEGORY',
            status='RUNNING'
        ).exists():
            messages.warning(
                request,
                "Category crawler is already running."
            )
            logger.warning(
                f"Attempted to start category crawler "
                f"by {request.user.username} but it's already running"
            )
        else:
            # Run the management command in a separate thread
            def run_crawler():
                try:
                    call_command('run_category_mapper')
                except Exception as e:
                    logger.error(f"Error in category crawler thread: {str(e)}")

            thread = threading.Thread(target=run_crawler)
            thread.daemon = True
            thread.start()

            messages.success(
                request,
                "Category crawler started successfully."
            )
            logger.info(
                f"Category crawler started by {request.user.username}"
            )

    except Exception as e:
        logger.error(f"Error starting category crawler: {str(e)}")
        messages.error(
            request,
            "Failed to start category crawler. Please check logs."
        )

    return redirect('asda_scraper:dashboard')


@user_passes_test(is_admin_user)
def stop_category_crawler(request):
    """
    Stop the category crawler.

    Args:
        request: HTTP request object

    Returns:
        HttpResponse: Redirect to dashboard
    """
    try:
        # Find running crawler session
        session = CrawlSession.objects.filter(
            crawler_type='CATEGORY',
            status='RUNNING'
        ).first()

        if session:
            session.status = 'STOPPED'
            session.completed_at = timezone.now()
            session.save()

            messages.success(
                request,
                "Category crawler stopped successfully."
            )
            logger.info(
                f"Category crawler stopped by {request.user.username} "
                f"- Session ID: {session.id}"
            )
        else:
            messages.warning(
                request,
                "No running category crawler found."
            )

    except Exception as e:
        logger.error(f"Error stopping category crawler: {str(e)}")
        messages.error(
            request,
            "Failed to stop category crawler. Please check logs."
        )

    return redirect('asda_scraper:dashboard')


@user_passes_test(is_admin_user)
def start_product_list_crawler(request):
    """
    Start the product list crawler.

    Args:
        request: HTTP request object

    Returns:
        HttpResponse: Redirect to dashboard
    """
    try:
        # Check if crawler is already running
        if CrawlSession.objects.filter(
            crawler_type='PRODUCT_LIST',
            status='RUNNING'
        ).exists():
            messages.warning(
                request,
                "Product list crawler is already running."
            )
            logger.warning(
                f"Attempted to start product list crawler "
                f"by {request.user.username} but it's already running"
            )
        else:
            # Check if there are URLs to process
            pending_urls = CrawlQueue.objects.filter(
                queue_type='PRODUCT_LIST',
                status='PENDING'
            ).count()

            if pending_urls == 0:
                messages.warning(
                    request,
                    "No categories to process. Run category crawler first."
                )
                return redirect('asda_scraper:dashboard')

            # Run the management command in a separate thread
            def run_crawler():
                try:
                    call_command('run_product_list_crawler')
                except Exception as e:
                    logger.error(f"Error in product list crawler thread: {str(e)}")

            thread = threading.Thread(target=run_crawler)
            thread.daemon = True
            thread.start()

            messages.success(
                request,
                f"Product list crawler started. {pending_urls} categories to process."
            )
            logger.info(
                f"Product list crawler started by {request.user.username}"
            )

    except Exception as e:
        logger.error(f"Error starting product list crawler: {str(e)}")
        messages.error(
            request,
            "Failed to start product list crawler. Please check logs."
        )

    return redirect('asda_scraper:dashboard')


@user_passes_test(is_admin_user)
def stop_product_list_crawler(request):
    """
    Stop the product list crawler.

    Args:
        request: HTTP request object

    Returns:
        HttpResponse: Redirect to dashboard
    """
    try:
        # Find running crawler session
        session = CrawlSession.objects.filter(
            crawler_type='PRODUCT_LIST',
            status='RUNNING'
        ).first()

        if session:
            session.status = 'STOPPED'
            session.completed_at = timezone.now()
            session.save()

            messages.success(
                request,
                "Product list crawler stopped successfully."
            )
            logger.info(
                f"Product list crawler stopped by {request.user.username} "
                f"- Session ID: {session.id}"
            )
        else:
            messages.warning(
                request,
                "No running product list crawler found."
            )

    except Exception as e:
        logger.error(f"Error stopping product list crawler: {str(e)}")
        messages.error(
            request,
            "Failed to stop product list crawler. Please check logs."
        )

    return redirect('asda_scraper:dashboard')


@user_passes_test(is_admin_user)
def start_product_detail_crawler(request):
    """
    Start the product detail crawler.

    Args:
        request: HTTP request object

    Returns:
        HttpResponse: Redirect to dashboard
    """
    try:
        # Check if crawler is already running
        if CrawlSession.objects.filter(
            crawler_type='PRODUCT_DETAIL',
            status='RUNNING'
        ).exists():
            messages.warning(
                request,
                "Product detail crawler is already running."
            )
            logger.warning(
                f"Attempted to start product detail crawler "
                f"by {request.user.username} but it's already running"
            )
        else:
            # Check if there are products to process
            pending_products = CrawlQueue.objects.filter(
                queue_type='PRODUCT_DETAIL',
                status='PENDING'
            ).count()

            products_without_nutrition = Product.objects.filter(
                nutrition_scraped=False,
                is_available=True
            ).count()

            if pending_products == 0:
                messages.warning(
                    request,
                    "No products to process. Run product list crawler first."
                )
                return redirect('asda_scraper:dashboard')

            # Run the management command in a separate thread
            def run_crawler():
                try:
                    call_command('run_product_detail_crawler')
                except Exception as e:
                    logger.error(f"Error in product detail crawler thread: {str(e)}")

            thread = threading.Thread(target=run_crawler)
            thread.daemon = True
            thread.start()

            messages.success(
                request,
                f"Product detail crawler started. "
                f"{pending_products} products to process "
                f"({products_without_nutrition} without nutrition)."
            )
            logger.info(
                f"Product detail crawler started by {request.user.username}"
            )

    except Exception as e:
        logger.error(f"Error starting product detail crawler: {str(e)}")
        messages.error(
            request,
            "Failed to start product detail crawler. Please check logs."
        )

    return redirect('asda_scraper:dashboard')


@user_passes_test(is_admin_user)
def stop_product_detail_crawler(request):
    """
    Stop the product detail crawler.

    Args:
        request: HTTP request object

    Returns:
        HttpResponse: Redirect to dashboard
    """
    try:
        # Find running crawler session
        session = CrawlSession.objects.filter(
            crawler_type='PRODUCT_DETAIL',
            status='RUNNING'
        ).first()

        if session:
            session.status = 'STOPPED'
            session.completed_at = timezone.now()
            session.save()

            messages.success(
                request,
                "Product detail crawler stopped successfully."
            )
            logger.info(
                f"Product detail crawler stopped by {request.user.username} "
                f"- Session ID: {session.id}"
            )
        else:
            messages.warning(
                request,
                "No running product detail crawler found."
            )

    except Exception as e:
        logger.error(f"Error stopping product detail crawler: {str(e)}")
        messages.error(
            request,
            "Failed to stop product detail crawler. Please check logs."
        )

    return redirect('asda_scraper:dashboard')


# Keep the old function names for backward compatibility
start_product_crawler = start_product_list_crawler
stop_product_crawler = stop_product_list_crawler
start_nutrition_crawler = start_product_detail_crawler
stop_nutrition_crawler = stop_product_detail_crawler


@user_passes_test(is_admin_user)
def crawler_status(request):
    """
    Get current crawler status via AJAX.

    Args:
        request: HTTP request object

    Returns:
        JsonResponse: Current crawler status data
    """
    try:
        # Get current running sessions
        category_session = CrawlSession.objects.filter(
            crawler_type='CATEGORY',
            status='RUNNING'
        ).first()
        product_list_session = CrawlSession.objects.filter(
            crawler_type='PRODUCT_LIST',
            status='RUNNING'
        ).first()
        product_detail_session = CrawlSession.objects.filter(
            crawler_type='PRODUCT_DETAIL',
            status='RUNNING'
        ).first()

        status_data = {
            'category_crawler': {
                'running': category_session is not None,
                'processed': (
                    category_session.processed_items
                    if category_session else 0
                ),
                'total': (
                    category_session.total_items
                    if category_session else 0
                ),
                'failed': (
                    category_session.failed_items
                    if category_session else 0
                ),
            },
            'product_list_crawler': {
                'running': product_list_session is not None,
                'processed': (
                    product_list_session.processed_items
                    if product_list_session else 0
                ),
                'total': (
                    product_list_session.total_items
                    if product_list_session else 0
                ),
                'failed': (
                    product_list_session.failed_items
                    if product_list_session else 0
                ),
            },
            'product_detail_crawler': {
                'running': product_detail_session is not None,
                'processed': (
                    product_detail_session.processed_items
                    if product_detail_session else 0
                ),
                'total': (
                    product_detail_session.total_items
                    if product_detail_session else 0
                ),
                'failed': (
                    product_detail_session.failed_items
                    if product_detail_session else 0
                ),
            },
            'stats': {
                'total_products': Product.objects.count(),
                'products_with_nutrition': Product.objects.filter(
                    nutrition_scraped=True
                ).count(),
                'total_categories': Category.objects.count(),
            },
            'queue_stats': {
                'category_pending': CrawlQueue.objects.filter(
                    queue_type='CATEGORY',
                    status='PENDING'
                ).count(),
                'product_list_pending': CrawlQueue.objects.filter(
                    queue_type='PRODUCT_LIST',
                    status='PENDING'
                ).count(),
                'product_detail_pending': CrawlQueue.objects.filter(
                    queue_type='PRODUCT_DETAIL',
                    status='PENDING'
                ).count(),
            }
        }

        return JsonResponse(status_data)

    except Exception as e:
        logger.error(f"Error getting crawler status: {str(e)}")
        return JsonResponse({'error': 'Failed to get status'}, status=500)