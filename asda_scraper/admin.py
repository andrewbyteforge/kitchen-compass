"""
Admin configuration for ASDA scraper models.

Provides Django admin interface for managing products and crawl sessions.
"""

import logging
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import Category, Product, NutritionInfo, CrawlSession, CrawledURL, CrawlQueue

logger = logging.getLogger(__name__)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model."""

    list_display = [
        'name',
        'level',
        'parent',
        'product_count',
        'is_active',
        'updated_at'
    ]
    list_filter = ['level', 'is_active', 'created_at']
    search_fields = ['name', 'url']
    ordering = ['level', 'name']
    readonly_fields = ['created_at', 'updated_at']

    def product_count(self, obj):
        """Return number of products in category."""
        return obj.products.count()
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin interface for Product model."""

    list_display = [
        'name',
        'brand',
        'formatted_price',
        'on_offer',
        'nutrition_status',
        'is_available',
        'last_scraped'
    ]
    list_filter = [
        'on_offer',
        'nutrition_scraped',
        'is_available',
        'categories',
        'last_scraped'
    ]
    search_fields = ['name', 'brand', 'asda_id', 'description']
    readonly_fields = [
        'asda_id',
        'created_at',
        'updated_at',
        'last_scraped'
    ]
    filter_horizontal = ['categories']

    def formatted_price(self, obj):
        """Format price display."""
        if obj.price:
            return f"£{obj.price}"
        return "-"
    formatted_price.short_description = 'Price'
    formatted_price.admin_order_field = 'price'

    def nutrition_status(self, obj):
        """Display nutrition scraping status."""
        if obj.nutrition_scraped:
            return format_html(
                '<span style="color: green;">✓ Scraped</span>'
            )
        return format_html(
            '<span style="color: orange;">⚠ Pending</span>'
        )
    nutrition_status.short_description = 'Nutrition'


@admin.register(NutritionInfo)
class NutritionInfoAdmin(admin.ModelAdmin):
    """Admin interface for NutritionInfo model."""

    list_display = [
        'product',
        'energy_kcal',
        'fat',
        'carbohydrates',
        'protein',
        'salt',
        'updated_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['product__name', 'product__brand']
    readonly_fields = ['created_at', 'updated_at', 'raw_nutrition_text']


@admin.register(CrawlSession)
class CrawlSessionAdmin(admin.ModelAdmin):
    """Admin interface for CrawlSession model."""

    list_display = [
        'crawler_type',
        'status_badge',
        'processed_items',
        'failed_items',
        'success_rate_display',
        'duration_display',
        'started_at'
    ]
    list_filter = ['crawler_type', 'status', 'started_at']
    readonly_fields = [
        'started_at',
        'completed_at',
        'duration_display',
        'success_rate_display'
    ]
    ordering = ['-started_at']

    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            'RUNNING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'STOPPED': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        """Format duration for display."""
        duration = obj.duration
        if duration:
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return "-"
    duration_display.short_description = 'Duration'

    def success_rate_display(self, obj):
        """Format success rate for display."""
        return f"{obj.success_rate:.1f}%"
    success_rate_display.short_description = 'Success Rate'


@admin.register(CrawledURL)
class CrawledURLAdmin(admin.ModelAdmin):
    """Admin interface for CrawledURL model."""

    list_display = [
        'url',
        'crawler_type',
        'times_crawled',
        'last_crawled'
    ]
    list_filter = ['crawler_type', 'last_crawled']
    search_fields = ['url']
    readonly_fields = ['url_hash', 'last_crawled']
    ordering = ['-last_crawled']


@admin.register(CrawlQueue)
class CrawlQueueAdmin(admin.ModelAdmin):
    """Admin interface for CrawlQueue model."""

    list_display = [
        'url_preview',
        'queue_type',
        'status',
        'priority',
        'attempts',
        'created_at'
    ]
    list_filter = ['queue_type', 'status', 'priority']
    search_fields = ['url']
    readonly_fields = ['url_hash', 'created_at', 'updated_at', 'processed_at']
    ordering = ['-priority', 'created_at']
    
    def url_preview(self, obj):
        """Show truncated URL."""
        return obj.url[:80] + '...' if len(obj.url) > 80 else obj.url
    url_preview.short_description = 'URL'