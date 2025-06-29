"""
ASDA Scraper Admin Configuration

This module configures the Django admin interface for the ASDA scraper models
with enhanced link mapping capabilities. Provides comprehensive admin views 
for managing categories, products, crawl sessions, URL mapping, and link relationships.
"""

import logging
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.contrib import messages
from .models import (
    AsdaCategory, AsdaProduct, CrawlSession, 
    UrlMap, LinkRelationship, CrawlQueue
)

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


# Add this to your asda_scraper/admin.py file in the AsdaProductAdmin class

from django.contrib import admin, messages
from django.db.models import Count
from .models import AsdaProduct, AsdaCategory

@admin.register(AsdaProduct)
class AsdaProductAdmin(admin.ModelAdmin):
    """
    Admin interface for ASDA products with enhanced delete capabilities.
    """
    list_display = [
        'name', 
        'price', 
        'category', 
        'in_stock',
        'created_at',
        'updated_at'
    ]
    list_filter = [
        'category',
        'in_stock',
        'created_at',
    ]
    search_fields = ['name', 'asda_id']
    list_per_page = 50
    
    actions = [
        'delete_all_products',
        'delete_out_of_stock',
        'delete_by_category',
    ]
    
    def delete_all_products(self, request, queryset):
        """Delete ALL products in the database (use with caution)."""
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can perform this action.", messages.ERROR)
            return
            
        # Get total count
        total_count = AsdaProduct.objects.count()
        
        if total_count > 100:
            self.message_user(
                request, 
                f"Cannot delete {total_count} products via admin. Use management command instead.",
                messages.WARNING
            )
            return
        
        # Delete all products
        deleted = AsdaProduct.objects.all().delete()
        
        # Reset category counts
        AsdaCategory.objects.update(product_count=0)
        
        self.message_user(
            request,
            f"Successfully deleted {deleted[0]} products and reset category counts.",
            messages.SUCCESS
        )
    
    delete_all_products.short_description = "⚠️ DELETE ALL PRODUCTS (Use with caution!)"
    
    def delete_out_of_stock(self, request, queryset):
        """Delete all out of stock products."""
        out_of_stock = AsdaProduct.objects.filter(in_stock=False)
        count = out_of_stock.count()
        
        if count == 0:
            self.message_user(request, "No out of stock products found.", messages.INFO)
            return
            
        out_of_stock.delete()
        
        # Update category counts
        for category in AsdaCategory.objects.all():
            category.product_count = category.products.count()
            category.save()
        
        self.message_user(
            request,
            f"Successfully deleted {count} out of stock products.",
            messages.SUCCESS
        )
    
    delete_out_of_stock.short_description = "Delete all out of stock products"
    
    def delete_by_category(self, request, queryset):
        """Delete products from selected items' categories."""
        categories = set(queryset.values_list('category', flat=True))
        
        total_deleted = 0
        for category_id in categories:
            if category_id:
                count = AsdaProduct.objects.filter(category_id=category_id).delete()[0]
                total_deleted += count
                
                # Update category count
                try:
                    category = AsdaCategory.objects.get(pk=category_id)
                    category.product_count = 0
                    category.save()
                except AsdaCategory.DoesNotExist:
                    pass
        
        self.message_user(
            request,
            f"Deleted {total_deleted} products from {len(categories)} categories.",
            messages.SUCCESS
        )
    
    delete_by_category.short_description = "Delete all products in selected categories"













@admin.register(CrawlSession)
class CrawlSessionAdmin(admin.ModelAdmin):
    """
    Enhanced admin interface for crawl sessions with link mapping statistics.
    
    Provides monitoring and management of scraping sessions with
    detailed statistics, error tracking, and link mapping insights.
    """
    list_display = [
        'session_display',
        'user',
        'status_display',
        'progress_display',
        'products_found',
        'urls_stats_display',
        'duration_display',
        'start_time'
    ]
    list_filter = [
        'status',
        'user',
        ('start_time', admin.DateFieldListFilter),
        ('end_time', admin.DateFieldListFilter)
    ]
    search_fields = ['session_id', 'start_url', 'notes']
    readonly_fields = [
        'session_id',
        'start_time', 
        'end_time', 
        'get_duration_display',
        'get_products_per_minute_display',
        'get_progress_percentage_display',
        'link_mapping_summary',
        'urls_discovered',
        'urls_crawled',
        'errors_count'
    ]
    fieldsets = (
        ('Session Information', {
            'fields': (
                'session_id',
                'user',
                'status',
                'start_url',
                'start_time',
                'end_time'
            )
        }),
        ('Crawl Configuration', {
            'fields': (
                'max_depth',
                'delay_seconds',
                'user_agent'
            ),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'categories_crawled',
                'products_found',
                'products_updated',
                'urls_discovered',
                'urls_crawled',
                'errors_count'
            )
        }),
        ('Performance', {
            'fields': (
                'get_duration_display',
                'get_products_per_minute_display',
                'get_progress_percentage_display'
            ),
            'classes': ('collapse',)
        }),
        ('Link Mapping Statistics', {
            'fields': ('link_mapping_summary',),
            'classes': ('collapse',)
        }),
        ('Configuration & Logs', {
            'fields': (
                'crawl_settings',
                'error_log',
                'notes'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_as_completed',
        'mark_as_failed', 
        'restart_session'
    ]
    
    def session_display(self, obj):
        """Display session ID with link."""
        return obj.session_id or f"Session {obj.pk}"
    session_display.short_description = 'Session ID'
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'PENDING': '#ff9800',
            'RUNNING': '#2196f3',
            'COMPLETED': '#4caf50',
            'FAILED': '#f44336',
            'CANCELLED': '#607d8b',
            'PAUSED': '#9c27b0',
        }
        
        color = colors.get(obj.status, '#616161')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def progress_display(self, obj):
        """Display crawling progress."""
        if obj.urls_discovered > 0:
            percentage = obj.get_progress_percentage()
            return format_html(
                '<div style="width: 100px; background: #eee; border-radius: 3px;">'
                '<div style="width: {}%; background: #4caf50; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 12px; line-height: 20px;">'
                '{}%</div></div>',
                percentage,
                int(percentage)
            )
        return '-'
    progress_display.short_description = 'Progress'
    
    def urls_stats_display(self, obj):
        """Display URL statistics."""
        return format_html(
            '<span title="Discovered / Crawled">{} / {}</span>',
            obj.urls_discovered,
            obj.urls_crawled
        )
    urls_stats_display.short_description = 'URLs (D/C)'
    
    def duration_display(self, obj):
        """Display session duration."""
        duration = obj.get_duration()
        if duration:
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return '-'
    duration_display.short_description = 'Duration'
    
    def get_duration_display(self, obj):
        """Get formatted duration display."""
        return self.duration_display(obj)
    get_duration_display.short_description = 'Duration'
    
    def get_products_per_minute_display(self, obj):
        """Get products per minute display."""
        rate = obj.get_products_per_minute()
        return f"{rate} products/min" if rate > 0 else "N/A"
    get_products_per_minute_display.short_description = 'Products per Minute'
    
    def get_progress_percentage_display(self, obj):
        """Get progress percentage display."""
        percentage = obj.get_progress_percentage()
        return f"{percentage:.1f}%" if percentage > 0 else "0%"
    get_progress_percentage_display.short_description = 'Progress Percentage'
    
    def get_link_mapping_stats(self, obj):
        """Get link mapping statistics for the session."""
        url_maps = UrlMap.objects.filter(crawl_session=obj)
        
        stats = {
            'total_urls': url_maps.count(),
            'by_type': {},
            'by_status': {},
            'total_links': LinkRelationship.objects.filter(
                from_url__crawl_session=obj
            ).count(),
            'queue_size': CrawlQueue.objects.filter(crawl_session=obj).count(),
        }
        
        # URL type breakdown
        for item in url_maps.values('url_type').annotate(count=Count('id')):
            url_type = item['url_type']
            count = item['count']
            type_display = dict(UrlMap.URL_TYPE_CHOICES).get(url_type, url_type)
            stats['by_type'][type_display] = count
        
        # Status breakdown
        for item in url_maps.values('status').annotate(count=Count('id')):
            status = item['status']
            count = item['count']
            status_display = dict(UrlMap.STATUS_CHOICES).get(status, status)
            stats['by_status'][status_display] = count
        
        return stats
    
    def link_mapping_summary(self, obj):
        """Display link mapping summary."""
        stats = self.get_link_mapping_stats(obj)
        
        html = f"""
        <div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">
            <strong>Link Mapping Statistics:</strong><br>
            <strong>URLs:</strong> {stats['total_urls']} discovered<br>
            <strong>Links:</strong> {stats['total_links']} relationships<br>
            <strong>Queue:</strong> {stats['queue_size']} pending
            
            <details style="margin-top: 10px;">
                <summary><strong>URL Types</strong></summary>
                <ul style="margin: 5px 0;">
        """
        
        for url_type, count in stats['by_type'].items():
            html += f"<li>{url_type}: {count}</li>"
        
        html += """
                </ul>
            </details>
            
            <details>
                <summary><strong>Status Breakdown</strong></summary>
                <ul style="margin: 5px 0;">
        """
        
        for status, count in stats['by_status'].items():
            html += f"<li>{status}: {count}</li>"
        
        html += """
                </ul>
            </details>
        </div>
        """
        
        return format_html(html)
    
    link_mapping_summary.short_description = 'Link Mapping Summary'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')
    
    def mark_as_completed(self, request, queryset):
        """Mark selected sessions as completed."""
        updated = 0
        for session in queryset:
            if session.status in ['RUNNING', 'PAUSED']:
                session.mark_completed()
                updated += 1
        
        self.message_user(
            request,
            f"Marked {updated} sessions as completed.",
            messages.SUCCESS
        )
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_failed(self, request, queryset):
        """Mark selected sessions as failed."""
        updated = 0
        for session in queryset:
            if session.status in ['RUNNING', 'PAUSED']:
                session.mark_failed("Manually marked as failed via admin")
                updated += 1
        
        self.message_user(
            request,
            f"Marked {updated} sessions as failed.",
            messages.WARNING
        )
    mark_as_failed.short_description = "Mark as failed"


@admin.register(UrlMap)
class UrlMapAdmin(admin.ModelAdmin):
    """
    Admin interface for URL mapping with comprehensive filtering and analysis.
    
    Provides detailed views of discovered URLs, their relationships,
    and crawling status with advanced filtering capabilities.
    """
    list_display = [
        'url_display',
        'url_type_display', 
        'status_display',
        'depth',
        'priority',
        'links_found',
        'products_found',
        'crawl_count',
        'last_crawled_display',
        'parent_url_display'
    ]
    list_filter = [
        'crawl_session',
        'url_type',
        'status',
        'depth',
        ('last_crawled', admin.DateFieldListFilter),
        ('discovered_at', admin.DateFieldListFilter),
        'robots_txt_allowed'
    ]
    search_fields = [
        'url',
        'normalized_url',
        'page_title',
        'meta_description'
    ]
    readonly_fields = [
        'url_hash',
        'normalized_url',
        'discovered_at',
        'last_crawled',
        'crawl_count',
        'response_code',
        'response_time',
        'content_length',
        'links_found',
        'products_found',
        'categories_found'
    ]
    fieldsets = (
        ('URL Information', {
            'fields': (
                'crawl_session',
                'url',
                'url_hash',
                'normalized_url',
                'url_type',
                'priority'
            )
        }),
        ('Hierarchy', {
            'fields': ('parent_url', 'depth')
        }),
        ('Crawling Status', {
            'fields': (
                'status',
                'discovered_at',
                'last_crawled',
                'next_crawl',
                'crawl_count',
                'robots_txt_allowed'
            )
        }),
        ('Response Data', {
            'fields': (
                'response_code',
                'response_time',
                'content_length',
                'content_type',
                'last_modified',
                'etag'
            ),
            'classes': ('collapse',)
        }),
        ('Page Content', {
            'fields': (
                'page_title',
                'meta_description',
                'links_found',
                'products_found',
                'categories_found'
            ),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_for_recrawl',
        'mark_as_skipped',
        'analyze_link_relationships',
    ]
    
    def url_display(self, obj):
        """Display URL with truncation and link."""
        url_text = obj.url[:80] + "..." if len(obj.url) > 80 else obj.url
        return format_html(
            '<a href="{}" target="_blank" title="{}">{}</a>',
            obj.url,
            obj.url,
            url_text
        )
    url_display.short_description = 'URL'
    
    def url_type_display(self, obj):
        """Display URL type with color coding."""
        colors = {
            'homepage': '#2e7d32',
            'category_main': '#1976d2',
            'category_sub': '#1565c0',
            'product_list': '#7b1fa2',
            'product_detail': '#d32f2f',
            'pagination': '#f57c00',
            'search_results': '#5d4037',
            'unknown': '#616161',
        }
        
        color = colors.get(obj.url_type, '#616161')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_url_type_display()
        )
    url_type_display.short_description = 'Type'
    
    def status_display(self, obj):
        """Display status with color coding."""
        colors = {
            'discovered': '#ff9800',
            'queued': '#2196f3',
            'in_progress': '#9c27b0',
            'completed': '#4caf50',
            'failed': '#f44336',
            'skipped': '#607d8b',
            'duplicate': '#795548',
            'blocked': '#e91e63',
        }
        
        color = colors.get(obj.status, '#616161')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
    
    def last_crawled_display(self, obj):
        """Display last crawled time with relative formatting."""
        if not obj.last_crawled:
            return format_html('<span style="color: #999;">Never</span>')
        
        now = timezone.now()
        diff = now - obj.last_crawled
        
        if diff.days > 7:
            color = '#f44336'  # Red for old
            text = obj.last_crawled.strftime('%Y-%m-%d')
        elif diff.days > 1:
            color = '#ff9800'  # Orange for recent
            text = f"{diff.days} days ago"
        elif diff.seconds > 3600:
            color = '#4caf50'  # Green for very recent
            text = f"{diff.seconds // 3600}h ago"
        else:
            color = '#4caf50'
            text = f"{diff.seconds // 60}m ago"
        
        return format_html(
            '<span style="color: {};" title="{}">{}</span>',
            color,
            obj.last_crawled.strftime('%Y-%m-%d %H:%M:%S'),
            text
        )
    last_crawled_display.short_description = 'Last Crawled'
    
    def parent_url_display(self, obj):
        """Display parent URL with link to admin."""
        if not obj.parent_url:
            return '-'
        
        url = reverse('admin:asda_scraper_urlmap_change', args=[obj.parent_url.pk])
        parent_text = obj.parent_url.url[:50] + "..." if len(obj.parent_url.url) > 50 else obj.parent_url.url
        
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            url,
            obj.parent_url.url,
            parent_text
        )
    parent_url_display.short_description = 'Parent URL'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'crawl_session', 'parent_url'
        ).prefetch_related('child_urls')
    
    def mark_for_recrawl(self, request, queryset):
        """Mark selected URLs for re-crawling."""
        count = 0
        for url_map in queryset:
            if url_map.status in ['completed', 'failed']:
                url_map.status = 'queued'
                url_map.next_crawl = timezone.now()
                url_map.save(update_fields=['status', 'next_crawl'])
                count += 1
        
        self.message_user(
            request,
            f"Marked {count} URLs for re-crawling.",
            messages.SUCCESS
        )
    mark_for_recrawl.short_description = "Mark selected URLs for re-crawling"
    
    def mark_as_skipped(self, request, queryset):
        """Mark selected URLs as skipped."""
        updated = queryset.update(status='skipped')
        self.message_user(
            request,
            f"Marked {updated} URLs as skipped.",
            messages.SUCCESS
        )
    mark_as_skipped.short_description = "Mark selected URLs as skipped"
    
    def analyze_link_relationships(self, request, queryset):
        """Analyze link relationships for selected URLs."""
        total_links = 0
        for url_map in queryset:
            outbound_count = url_map.outbound_links.count()
            inbound_count = url_map.inbound_links.count()
            total_links += outbound_count + inbound_count
        
        self.message_user(
            request,
            f"Selected URLs have {total_links} total link relationships.",
            messages.INFO
        )
    analyze_link_relationships.short_description = "Analyze link relationships"


@admin.register(LinkRelationship)
class LinkRelationshipAdmin(admin.ModelAdmin):
    """
    Admin interface for link relationships between pages.
    
    Provides analysis of how pages link to each other with
    context about link types and anchor text.
    """
    list_display = [
        'from_url_display',
        'to_url_display',
        'link_type',
        'anchor_text_display',
        'position_on_page',
        'first_seen',
        'is_active'
    ]
    list_filter = [
        'link_type',
        'is_active',
        ('first_seen', admin.DateFieldListFilter),
        ('last_seen', admin.DateFieldListFilter)
    ]
    search_fields = [
        'from_url__url',
        'to_url__url',
        'anchor_text'
    ]
    readonly_fields = ['first_seen', 'last_seen']
    
    def from_url_display(self, obj):
        """Display truncated from URL with admin link."""
        url_text = obj.from_url.url[:50] + "..." if len(obj.from_url.url) > 50 else obj.from_url.url
        admin_url = reverse('admin:asda_scraper_urlmap_change', args=[obj.from_url.pk])
        
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            admin_url,
            obj.from_url.url,
            url_text
        )
    from_url_display.short_description = 'From URL'
    
    def to_url_display(self, obj):
        """Display truncated to URL with admin link."""
        url_text = obj.to_url.url[:50] + "..." if len(obj.to_url.url) > 50 else obj.to_url.url
        admin_url = reverse('admin:asda_scraper_urlmap_change', args=[obj.to_url.pk])
        
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            admin_url,
            obj.to_url.url,
            url_text
        )
    to_url_display.short_description = 'To URL'
    
    def anchor_text_display(self, obj):
        """Display truncated anchor text."""
        if not obj.anchor_text:
            return format_html('<span style="color: #999;">No text</span>')
        
        text = obj.anchor_text[:50] + "..." if len(obj.anchor_text) > 50 else obj.anchor_text
        return format_html(
            '<span title="{}">{}</span>',
            obj.anchor_text,
            text
        )
    anchor_text_display.short_description = 'Anchor Text'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'from_url', 'to_url', 'from_url__crawl_session', 'to_url__crawl_session'
        )


@admin.register(CrawlQueue)
class CrawlQueueAdmin(admin.ModelAdmin):
    """
    Admin interface for the crawl queue management.
    
    Provides controls for managing which URLs are queued for crawling
    and their scheduling priorities.
    """
    list_display = [
        'url_display',
        'priority',
        'scheduled_time',
        'attempts',
        'last_attempt',
        'is_ready_display',
        'crawl_session'
    ]
    list_filter = [
        'crawl_session',
        'priority',
        ('scheduled_time', admin.DateFieldListFilter),
        ('last_attempt', admin.DateFieldListFilter),
        'attempts'
    ]
    search_fields = [
        'url_map__url',
        'url_map__page_title'
    ]
    readonly_fields = ['created_at', 'last_attempt']
    actions = [
        'reschedule_now',
        'increase_priority',
        'decrease_priority',
        'reset_attempts'
    ]
    
    def url_display(self, obj):
        """Display URL with link to URL map admin."""
        url_text = obj.url_map.url[:80] + "..." if len(obj.url_map.url) > 80 else obj.url_map.url
        admin_url = reverse('admin:asda_scraper_urlmap_change', args=[obj.url_map.pk])
        
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            admin_url,
            obj.url_map.url,
            url_text
        )
    url_display.short_description = 'URL'
    
    def is_ready_display(self, obj):
        """Display if URL is ready to crawl."""
        if obj.is_ready_to_crawl():
            return format_html('<span style="color: #4caf50;">✓ Ready</span>')
        else:
            time_until = obj.scheduled_time - timezone.now()
            if time_until.total_seconds() > 0:
                if time_until.days > 0:
                    return format_html(
                        '<span style="color: #ff9800;">⏰ {} days</span>',
                        time_until.days
                    )
                elif time_until.seconds > 3600:
                    return format_html(
                        '<span style="color: #ff9800;">⏰ {}h</span>',
                        time_until.seconds // 3600
                    )
                else:
                    return format_html(
                        '<span style="color: #ff9800;">⏰ {}m</span>',
                        time_until.seconds // 60
                    )
            else:
                return format_html('<span style="color: #4caf50;">✓ Ready</span>')
    is_ready_display.short_description = 'Ready?'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'url_map', 'crawl_session'
        )
    
    def reschedule_now(self, request, queryset):
        """Reschedule selected URLs for immediate crawling."""
        updated = queryset.update(scheduled_time=timezone.now())
        self.message_user(
            request,
            f"Rescheduled {updated} URLs for immediate crawling.",
            messages.SUCCESS
        )
    reschedule_now.short_description = "Reschedule for immediate crawling"
    
    def increase_priority(self, request, queryset):
        """Increase priority of selected URLs."""
        for queue_item in queryset:
            queue_item.priority += 10
            queue_item.save(update_fields=['priority'])
        
        self.message_user(
            request,
            f"Increased priority for {queryset.count()} URLs.",
            messages.SUCCESS
        )
    increase_priority.short_description = "Increase priority (+10)"
    
    def decrease_priority(self, request, queryset):
        """Decrease priority of selected URLs."""
        for queue_item in queryset:
            queue_item.priority = max(0, queue_item.priority - 10)
            queue_item.save(update_fields=['priority'])
        
        self.message_user(
            request,
            f"Decreased priority for {queryset.count()} URLs.",
            messages.SUCCESS
        )
    decrease_priority.short_description = "Decrease priority (-10)"
    
    def reset_attempts(self, request, queryset):
        """Reset attempt count for selected URLs."""
        updated = queryset.update(attempts=0, last_attempt=None)
        self.message_user(
            request,
            f"Reset attempts for {updated} URLs.",
            messages.SUCCESS
        )
    reset_attempts.short_description = "Reset attempt count"