"""
ASDA Scraper URL Configuration

URL patterns for the ASDA scraper admin interface.
"""

from django.urls import path
from . import views

app_name = 'asda_scraper'

urlpatterns = [
    # Dashboard
    path('', views.scraper_dashboard, name='dashboard'),
    
    # Crawl management
    path('start/', views.start_crawl, name='start_crawl'),
    path('stop/', views.stop_crawl, name='stop_crawl'),
    path('status/', views.crawl_status, name='crawl_status'),
    
    # Data views
    path('categories/', views.CategoryListView.as_view(), name='categories'),
    path('products/', views.ProductListView.as_view(), name='products'),
]