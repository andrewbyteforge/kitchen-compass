"""
ASDA Scraper Admin Configuration

This module configures the Django admin interface for the ASDA scraper models.
Provides comprehensive admin views for managing categories, products, and crawl sessions.
"""

import logging
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import AsdaCategory, AsdaProduct, CrawlSession

logger = logging.getLogger(__name__)


@admin.register(AsdaCategory)
class AsdaCategoryAdmin(admin.ModelAdmin):
    """
    Admin interface for ASDA categories.
    
    Provides functionality to manage product categories with hierarchical structure,
    crawl status tracking, and bulk operations.
    """
    list_display = [
        'name', 
        'url_code', 
        'parent_category', 
        'product_count', 
        'is_active', 
        'last_crawled_display'
    ]
    list_filter = ['is_active', 'parent_category', 'last_crawled']
    search_fields = ['name', 'url_code']
    list_editable = ['is_active']
    readonly_fields = ['product_count', 'last_crawled', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'url_code', 'parent_category')
        }),
        ('Status', {
            'fields': ('is_active', 'product_count', 'last_crawled')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def last_crawled_display(self, obj):
        """Display last crawled time in a user-friendly format."""
        if obj.last_crawled:
            return obj.last_crawled.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    last_crawled_display.short_description = 'Last Crawled'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('parent_category')


@admin.register(AsdaProduct)
class AsdaProductAdmin(admin.ModelAdmin):
    """
    Admin interface for ASDA products.
    
    Provides comprehensive product management with filtering, searching,
    and bulk operations for product data.
    """
    list_display = [
        'name', 
        'price_display', 
        'unit', 
        'category', 
        'in_stock', 
        'special_offer_display',
        'updated_at'
    ]
    list_filter = [
        'in_stock', 
        'category', 
        'created_at', 
        'updated_at'
    ]
    search_fields = ['name', 'asda_id', 'description']
    list_editable = ['in_stock']
    readonly_fields = ['asda_id', 'created_at', 'updated_at', 'price_per_unit_display']
    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'asda_id', 'description', 'category')
        }),
        ('Pricing & Availability', {
            'fields': ('price', 'unit', 'price_per_unit_display', 'in_stock', 'special_offer')
        }),
        ('Media & Links', {
            'fields': ('image_url', 'product_url')
        }),
        ('Additional Data', {
            'fields': ('nutritional_info',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def price_display(self, obj):
        """Display price with currency symbol."""
        return f"£{obj.price}"
    price_display.short_description = 'Price'
    
    def special_offer_display(self, obj):
        """Display special offer with highlight if present."""
        if obj.special_offer:
            return format_html(
                '<span style="background-color: #ffeaa7; padding: 2px 4px; border-radius: 3px;">{}</span>',
                obj.special_offer
            )
        return '-'
    special_offer_display.short_description = 'Special Offer'
    
    def price_per_unit_display(self, obj):
        """Display calculated price per unit."""
        price_per_unit = obj.get_price_per_unit()
        if price_per_unit:
            return f"£{price_per_unit:.2f}/kg"
        return 'N/A'
    price_per_unit_display.short_description = 'Price per Unit'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('category')


@admin.register(CrawlSession)
class CrawlSessionAdmin(admin.ModelAdmin):
    """
    Admin interface for crawl sessions.
    
    Provides monitoring and management of scraping sessions with
    detailed statistics and error tracking.
    """
    list_display = [
        'id',
        'user',
        'status_display',
        'start_time',
        'duration_display',
        'categories_crawled',
        'products_found',
        'products_updated'
    ]
    list_filter = ['status', 'start_time', 'user']
    readonly_fields = [
        'user', 
        'start_time', 
        'end_time', 
        'categories_crawled',
        'products_found', 
        'products_updated', 
        'duration_display',
        'crawl_settings'
    ]
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'status', 'start_time', 'end_time', 'duration_display')
        }),
        ('Statistics', {
            'fields': ('categories_crawled', 'products_found', 'products_updated')
        }),
        ('Configuration', {
            'fields': ('crawl_settings',),
            'classes': ('collapse',)
        }),
        ('Error Log', {
            'fields': ('error_log',),
            'classes': ('collapse',)
        }),
    )
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'PENDING': '#74b9ff',
            'RUNNING': '#fdcb6e',
            'COMPLETED': '#00b894',
            'FAILED': '#e17055',
            'CANCELLED': '#636e72'
        }
        color = colors.get(obj.status, '#ddd')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def duration_display(self, obj):
        """Display session duration in human-readable format."""
        duration = obj.get_duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return '-'
    duration_display.short_description = 'Duration'
    
    def has_add_permission(self, request):
        """Prevent manual creation of crawl sessions through admin."""
        return False