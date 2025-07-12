"""
ASDA Scraper Views Package

This package contains all views for the ASDA scraper application,
organized into logical modules for better maintainability.

File: asda_scraper/views/__init__.py
"""

# Import all views to maintain backward compatibility
from .dashboard import scraper_dashboard, get_proxy_status_summary
from .crawl_operations import (
    start_crawl,
    stop_crawl,
    crawl_status,
    run_selenium_scraper_with_error_handling
)
from .product_views import ProductListView, delete_products_view
from .category_views import CategoryListView
from .session_views import session_detail

# Make all views available at package level
__all__ = [
    'scraper_dashboard',
    'get_proxy_status_summary',
    'start_crawl',
    'stop_crawl',
    'crawl_status',
    'run_selenium_scraper_with_error_handling',
    'ProductListView',
    'delete_products_view',
    'CategoryListView',
    'session_detail',
]