"""
Django admin configuration for Asda product and category models.

This module provides a comprehensive admin interface for managing
scraped Asda grocery data with filtering, searching, and bulk actions.

File: auth_hub/admin.py (add to existing admin.py)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg, Min, Max
from django.utils import timezone
from datetime import timedelta

from .models import AsdaCategory, AsdaProduct, AsdaPriceHistory, UserAsdaPreferences


@admin.register(AsdaCategory)
class AsdaCategoryAdmin(admin.ModelAdmin):
    """
    Admin interface for Asda categories with hierarchical display.
    
    Provides tree-like view of categories with product counts
    and last scrape information.
    """
    
    list_display = [
        'name_with_level',
        'parent',
        'level',
        'product_count',
        'is_active',
        'last_scraped',
        'view_products_link'
    ]
    
    list_filter = [
        'level',
        'is_active',
        'last_scraped',
        'created_at'
    ]
    
    search_fields = [
        'name',
        'description',
        'parent__name'
    ]
    
    list_editable = [
        'is_active'
    ]
    
    readonly_fields = [
        'slug',
        'product_count',
        'created_at',
        'updated_at',
        'last_scraped'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'parent', 'level')
        }),
        ('URL and Scraping', {
            'fields': ('url', 'is_active', 'last_scraped')
        }),
        ('Statistics', {
            'fields': ('product_count',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = [
        'activate_categories',
        'deactivate_categories',
        'update_product_counts'
    ]
    
    def name_with_level(self, obj):
        """Display category name with indentation based on level."""
        indent = '&nbsp;&nbsp;' * (obj.level - 1) * 4
        return format_html(f'{indent}<strong>{obj.name}</strong>')
    name_with_level.short_description = 'Category Name'
    name_with_level.allow_tags = True
    
    def view_products_link(self, obj):
        """Create link to view products in this category."""
        if obj.product_count > 0:
            url = reverse('admin:auth_hub_asdaproduct_changelist')
            return format_html(
                '<a href="{}?category__id__exact={}">View {} products</a>',
                url, obj.id, obj.product_count
            )
        return '-'
    view_products_link.short_description = 'Products'
    
    def activate_categories(self, request, queryset):
        """Bulk action to activate selected categories."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} categories activated.')
    activate_categories.short_description = "Activate selected categories"
    
    def deactivate_categories(self, request, queryset):
        """Bulk action to deactivate selected categories."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} categories deactivated.')
    deactivate_categories.short_description = "Deactivate selected categories"
    
    def update_product_counts(self, request, queryset):
        """Bulk action to update product counts for selected categories."""
        for category in queryset:
            category.update_product_count()
        self.message_user(request, f'Product counts updated for {queryset.count()} categories.')
    update_product_counts.short_description = "Update product counts"


@admin.register(AsdaProduct)
class AsdaProductAdmin(admin.ModelAdmin):
    """
    Admin interface for Asda products with comprehensive filtering and search.
    
    Provides detailed product management with price history tracking
    and availability monitoring.
    """
    
    list_display = [
        'name_truncated',
        'category',
        'price_display',
        'brand',
        'is_available',
        'is_on_offer',
        'last_scraped',
        'times_scraped',
        'view_price_history'
    ]
    
    list_filter = [
        'is_available',
        'is_on_offer',
        'category__level',
        'category',
        'brand',
        'last_scraped',
        'first_seen'
    ]
    
    search_fields = [
        'name',
        'brand',
        'description',
        'category__name',
        'barcode'
    ]
    
    list_editable = [
        'is_available',
        'brand'
    ]
    
    readonly_fields = [
        'slug',
        'times_scraped',
        'first_seen',
        'last_scraped',
        'price_trend_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'brand', 'description', 'category')
        }),
        ('Pricing', {
            'fields': (
                'price', 'price_text', 'price_per_unit', 'unit_type',
                'is_on_offer', 'original_price', 'offer_text'
            )
        }),
        ('Product Details', {
            'fields': ('barcode', 'ingredients', 'allergens', 'nutritional_info'),
            'classes': ('collapse',)
        }),
        ('URLs and Media', {
            'fields': ('url', 'image_url'),
            'classes': ('collapse',)
        }),
        ('Availability', {
            'fields': ('is_available',)
        }),
        ('Scraping Info', {
            'fields': ('times_scraped', 'first_seen', 'last_scraped', 'price_trend_display'),
            'classes': ('collapse',)
        })
    )
    
    actions = [
        'mark_available',
        'mark_unavailable',
        'update_scrape_count',
        'export_to_csv'
    ]
    
    def name_truncated(self, obj):
        """Display truncated product name for list view."""
        if len(obj.name) > 50:
            return f"{obj.name[:47]}..."
        return obj.name
    name_truncated.short_description = 'Product Name'
    
    def price_display(self, obj):
        """Display formatted price with offer indication."""
        if obj.price:
            price_html = f'£{obj.price:.2f}'
            if obj.is_on_offer:
                price_html = format_html(
                    '<span style="color: red; font-weight: bold;">{}</span>',
                    price_html
                )
            return mark_safe(price_html)
        return '-'
    price_display.short_description = 'Price'
    
    def view_price_history(self, obj):
        """Create link to view price history for this product."""
        count = obj.price_history.count()
        if count > 0:
            url = reverse('admin:auth_hub_asdapricehistory_changelist')
            return format_html(
                '<a href="{}?product__id__exact={}">View {} records</a>',
                url, obj.id, count
            )
        return '-'
    view_price_history.short_description = 'Price History'
    
    def price_trend_display(self, obj):
        """Display price trend information."""
        history = obj.price_history.all()[:5]
        if not history:
            return "No price history"
        
        trend_html = []
        for record in history:
            date_str = record.recorded_at.strftime('%d/%m')
            price_str = f'£{record.price:.2f}'
            if record.is_on_offer:
                price_str = f'<span style="color: red;">{price_str}*</span>'
            trend_html.append(f'{date_str}: {price_str}')
        
        return mark_safe('<br>'.join(trend_html))
    price_trend_display.short_description = 'Recent Price Trend'
    
    def mark_available(self, request, queryset):
        """Bulk action to mark products as available."""
        updated = queryset.update(is_available=True)
        self.message_user(request, f'{updated} products marked as available.')
    mark_available.short_description = "Mark selected products as available"
    
    def mark_unavailable(self, request, queryset):
        """Bulk action to mark products as unavailable."""
        updated = queryset.update(is_available=False)
        self.message_user(request, f'{updated} products marked as unavailable.')
    mark_unavailable.short_description = "Mark selected products as unavailable"
    
    def update_scrape_count(self, request, queryset):
        """Bulk action to reset scrape count."""
        for product in queryset:
            product.times_scraped += 1
            product.save()
        self.message_user(request, f'Scrape count updated for {queryset.count()} products.')
    update_scrape_count.short_description = "Increment scrape count"
    
    def export_to_csv(self, request, queryset):
        """Export selected products to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="asda_products.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Category', 'Brand', 'Price', 'Unit Type', 
            'Available', 'On Offer', 'URL', 'Last Scraped'
        ])
        
        for product in queryset:
            writer.writerow([
                product.name,
                product.category.name,
                product.brand,
                product.price,
                product.unit_type,
                product.is_available,
                product.is_on_offer,
                product.url,
                product.last_scraped.strftime('%Y-%m-%d %H:%M') if product.last_scraped else ''
            ])
        
        return response
    export_to_csv.short_description = "Export selected products to CSV"


@admin.register(AsdaPriceHistory)
class AsdaPriceHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for Asda price history tracking.
    
    Provides chronological view of price changes with
    filtering and analysis capabilities.
    """
    
    list_display = [
        'product_name',
        'price_display',
        'is_on_offer',
        'offer_text_truncated',
        'recorded_at',
        'price_change'
    ]
    
    list_filter = [
        'is_on_offer',
        'recorded_at',
        'product__category',
        'product__brand'
    ]
    
    search_fields = [
        'product__name',
        'product__brand',
        'offer_text'
    ]
    
    readonly_fields = [
        'recorded_at',
        'price_change_amount',
        'days_since_last_change'
    ]
    
    fieldsets = (
        ('Price Information', {
            'fields': ('product', 'price', 'price_text')
        }),
        ('Offer Details', {
            'fields': ('is_on_offer', 'offer_text')
        }),
        ('Timing', {
            'fields': ('recorded_at', 'days_since_last_change')
        }),
        ('Analysis', {
            'fields': ('price_change_amount',),
            'classes': ('collapse',)
        })
    )
    
    date_hierarchy = 'recorded_at'
    
    def product_name(self, obj):
        """Display product name with link to product admin."""
        url = reverse('admin:auth_hub_asdaproduct_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name[:50])
    product_name.short_description = 'Product'
    
    def price_display(self, obj):
        """Display formatted price with offer indication."""
        price_html = f'£{obj.price:.2f}'
        if obj.is_on_offer:
            price_html = format_html(
                '<span style="color: red; font-weight: bold;">{}</span>',
                price_html
            )
        return mark_safe(price_html)
    price_display.short_description = 'Price'
    
    def offer_text_truncated(self, obj):
        """Display truncated offer text."""
        if obj.offer_text and len(obj.offer_text) > 30:
            return f"{obj.offer_text[:27]}..."
        return obj.offer_text or '-'
    offer_text_truncated.short_description = 'Offer'
    
    def price_change(self, obj):
        """Show price change compared to previous record."""
        previous = AsdaPriceHistory.objects.filter(
            product=obj.product,
            recorded_at__lt=obj.recorded_at
        ).first()
        
        if previous:
            change = obj.price - previous.price
            if change > 0:
                return format_html(
                    '<span style="color: red;">+£{:.2f}</span>', change
                )
            elif change < 0:
                return format_html(
                    '<span style="color: green;">-£{:.2f}</span>', abs(change)
                )
            else:
                return 'No change'
        return 'First record'
    price_change.short_description = 'Change'
    
    def price_change_amount(self, obj):
        """Calculate price change amount for readonly field."""
        previous = AsdaPriceHistory.objects.filter(
            product=obj.product,
            recorded_at__lt=obj.recorded_at
        ).first()
        
        if previous:
            change = obj.price - previous.price
            return f'£{change:.2f}'
        return 'First record'
    price_change_amount.short_description = 'Price Change Amount'
    
    def days_since_last_change(self, obj):
        """Calculate days since last price change."""
        previous = AsdaPriceHistory.objects.filter(
            product=obj.product,
            recorded_at__lt=obj.recorded_at
        ).first()
        
        if previous:
            delta = obj.recorded_at - previous.recorded_at
            return f'{delta.days} days'
        return 'N/A'
    days_since_last_change.short_description = 'Days Since Last Change'


@admin.register(UserAsdaPreferences)
class UserAsdaPreferencesAdmin(admin.ModelAdmin):
    """
    Admin interface for user Asda preferences.
    
    Manages user-specific settings for product filtering,
    price alerts, and shopping preferences.
    """
    
    list_display = [
        'user',
        'price_alert_threshold',
        'enable_price_alerts',
        'max_budget_per_item',
        'preferred_categories_count',
        'updated_at'
    ]
    
    list_filter = [
        'enable_price_alerts',
        'price_alert_threshold',
        'created_at',
        'updated_at'
    ]
    
    search_fields = [
        'user__username',
        'user__email',
        'preferred_brands',
        'dietary_restrictions'
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'preferred_brands_list'
    ]
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Price Preferences', {
            'fields': (
                'price_alert_threshold', 'enable_price_alerts', 
                'max_budget_per_item'
            )
        }),
        ('Category Preferences', {
            'fields': ('preferred_categories',)
        }),
        ('Brand and Dietary', {
            'fields': (
                'preferred_brands', 'preferred_brands_list',
                'dietary_restrictions'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    filter_horizontal = ['preferred_categories']
    
    def preferred_categories_count(self, obj):
        """Display count of preferred categories."""
        return obj.preferred_categories.count()
    preferred_categories_count.short_description = 'Preferred Categories'
    
    def preferred_brands_list(self, obj):
        """Display formatted list of preferred brands."""
        brands = obj.get_preferred_brand_list()
        if brands:
            return ', '.join(brands)
        return 'None specified'
    preferred_brands_list.short_description = 'Brand List'


# Custom admin site configuration
class AsdaAdminSite(admin.AdminSite):
    """Custom admin site for Asda data management."""
    
    site_header = "KitchenCompass - Asda Data Management"
    site_title = "Asda Admin"
    index_title = "Manage Asda Grocery Data"
    
    def get_app_list(self, request, app_label=None):
        """Custom app list ordering."""
        app_list = super().get_app_list(request, app_label)
        
        # Custom ordering for Asda models
        asda_models_order = [
            'AsdaCategory',
            'AsdaProduct', 
            'AsdaPriceHistory',
            'UserAsdaPreferences'
        ]
        
        for app in app_list:
            if app['app_label'] == 'auth_hub':
                # Sort models according to our preference
                def model_sort_key(model):
                    model_name = model['object_name']
                    if model_name in asda_models_order:
                        return asda_models_order.index(model_name)
                    return 999
                
                app['models'].sort(key=model_sort_key)
        
        return app_list


# Additional admin customizations
def admin_changelist_stats(modeladmin, request, queryset):
    """Add statistics to changelist view."""
    from django.contrib import messages
    
    if hasattr(queryset.model, '_meta'):
        model_name = queryset.model._meta.verbose_name_plural
        
        if queryset.model == AsdaProduct:
            total_count = queryset.count()
            available_count = queryset.filter(is_available=True).count()
            offer_count = queryset.filter(is_on_offer=True).count()
            avg_price = queryset.filter(price__isnull=False).aggregate(Avg('price'))['price__avg']
            
            stats_msg = (
                f"{model_name} Statistics: "
                f"Total: {total_count}, Available: {available_count}, "
                f"On Offer: {offer_count}, Avg Price: £{avg_price:.2f if avg_price else 0}"
            )
            messages.info(request, stats_msg)
        
        elif queryset.model == AsdaCategory:
            total_count = queryset.count()
            active_count = queryset.filter(is_active=True).count()
            with_products = queryset.filter(product_count__gt=0).count()
            
            stats_msg = (
                f"{model_name} Statistics: "
                f"Total: {total_count}, Active: {active_count}, "
                f"With Products: {with_products}"
            )
            messages.info(request, stats_msg)


# Register the custom admin site if needed
# asda_admin_site = AsdaAdminSite(name='asda_admin')
# asda_admin_site.register(AsdaCategory, AsdaCategoryAdmin)
# asda_admin_site.register(AsdaProduct, AsdaProductAdmin)
# asda_admin_site.register(AsdaPriceHistory, AsdaPriceHistoryAdmin)
# asda_admin_site.register(UserAsdaPreferences, UserAsdaPreferencesAdmin)