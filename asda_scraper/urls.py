"""
URL configuration for ASDA scraper app.

Defines routes for admin dashboard and crawler controls.
"""

from django.urls import path
from . import views

app_name = 'asda_scraper'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    # Category Crawler Controls
    path('start-category-crawler/', views.start_category_crawler, name='start_category_crawler'),
    path('stop-category-crawler/', views.stop_category_crawler, name='stop_category_crawler'),
    
    # Product List Crawler Controls
    path('start-product-list-crawler/', views.start_product_list_crawler, name='start_product_list_crawler'),
    path('stop-product-list-crawler/', views.stop_product_list_crawler, name='stop_product_list_crawler'),
    
    # Product Detail Crawler Controls
    path('start-product-detail-crawler/', views.start_product_detail_crawler, name='start_product_detail_crawler'),
    path('stop-product-detail-crawler/', views.stop_product_detail_crawler, name='stop_product_detail_crawler'),
    
    # Legacy URLs for backward compatibility
    path('start-product-crawler/', views.start_product_crawler, name='start_product_crawler'),
    path('stop-product-crawler/', views.stop_product_crawler, name='stop_product_crawler'),
    path('start-nutrition-crawler/', views.start_nutrition_crawler, name='start_nutrition_crawler'),
    path('stop-nutrition-crawler/', views.stop_nutrition_crawler, name='stop_nutrition_crawler'),
    
    # AJAX endpoints for status updates
    path('crawler-status/', views.crawler_status, name='crawler_status'),
]