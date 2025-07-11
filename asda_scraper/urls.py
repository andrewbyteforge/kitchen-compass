"""
ASDA Scraper URL Configuration

URL patterns for the ASDA scraper admin interface.
Organized to work with the new modular view structure.

File: asda_scraper/urls.py
"""

from django.urls import path

# Import views from the new modular structure
from .views import (
    # Dashboard views
    scraper_dashboard,
    get_proxy_status_summary,
    
    # Crawl operation views
    start_crawl,
    stop_crawl,
    crawl_status,
    
    # Data list views
    CategoryListView,
    ProductListView,
    
    # Product management views
    delete_products_view,
    
    # Session views
    session_detail,
)

app_name = 'asda_scraper'

urlpatterns = [
    # Dashboard
    path('', scraper_dashboard, name='dashboard'),
    
    # Crawl management
    path('start/', start_crawl, name='start_crawl'),
    path('stop/', stop_crawl, name='stop_crawl'),
    path('status/', crawl_status, name='crawl_status'),
    
    # Data views
    path('categories/', CategoryListView.as_view(), name='categories'),
    path('products/', ProductListView.as_view(), name='products'),
    
    # Session management
    path('session/<int:session_id>/', session_detail, name='session_detail'),
    
    # Product management
    path('delete-products/', delete_products_view, name='delete_products'),
    
    # API endpoints (if needed in future)
    # path('api/proxy-status/', get_proxy_status_summary, name='proxy_status'),
]