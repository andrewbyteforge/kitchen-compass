"""
Admin configuration for the AuthHub application.

This module configures the Django admin interface for managing users,
subscriptions, and menu sharing functionality.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import (
    SubscriptionTier,
    UserProfile,
    MenuShare,
    ActivityLog
)


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile to be displayed with User."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = (
        'subscription_tier',
        'subscription_status',
        'subscription_end_date',
        'stripe_customer_id',
        'dietary_restrictions',
        'menus_created',
        'recipes_saved',
    )
    readonly_fields = ('menus_created', 'recipes_saved')


class UserAdmin(BaseUserAdmin):
    """Extended User admin to include profile information."""
    inlines = (UserProfileInline,)
    list_display = (
        'email',
        'first_name',
        'last_name',
        'is_active',
        'subscription_tier_display',
        'subscription_status_display',
        'date_joined',
    )
    list_filter = (
        'is_active',
        'is_staff',
        'profile__subscription_tier',
        'profile__subscription_status',
        'date_joined',
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    def subscription_tier_display(self, obj):
        """Display user's subscription tier."""
        if hasattr(obj, 'profile') and obj.profile.subscription_tier:
            return obj.profile.subscription_tier.name
        return "No subscription"
    subscription_tier_display.short_description = 'Subscription Tier'
    
    def subscription_status_display(self, obj):
        """Display user's subscription status with color coding."""
        if hasattr(obj, 'profile'):
            status = obj.profile.subscription_status
            colors = {
                'active': 'green',
                'trial': 'blue',
                'cancelled': 'orange',
                'past_due': 'red',
                'inactive': 'gray',
            }
            color = colors.get(status, 'black')
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                status.title()
            )
        return "No profile"
    subscription_status_display.short_description = 'Status'


@admin.register(SubscriptionTier)
class SubscriptionTierAdmin(admin.ModelAdmin):
    """Admin configuration for SubscriptionTier model."""
    list_display = (
        'name',
        'tier_type',
        'price_display',
        'max_shared_menus',
        'max_menu_days',
        'subscriber_count',
        'is_active',
    )
    list_filter = ('is_active', 'tier_type')
    search_fields = ('name', 'stripe_price_id')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('price',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'tier_type', 'is_active')
        }),
        ('Pricing', {
            'fields': ('price', 'stripe_price_id')
        }),
        ('Features & Limits', {
            'fields': ('features', 'max_shared_menus', 'max_menu_days')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
    
    def price_display(self, obj):
        """Display price in dollars."""
        return f"${obj.price/100:.2f}"
    price_display.short_description = 'Price'
    
    def subscriber_count(self, obj):
        """Count of active subscribers for this tier."""
        return obj.subscribers.filter(
            subscription_status='active'
        ).count()
    subscriber_count.short_description = 'Active Subscribers'


@admin.register(MenuShare)
class MenuShareAdmin(admin.ModelAdmin):
    """Admin configuration for MenuShare model."""
    list_display = (
        'owner_email',
        'shared_with_email',
        'status_display',
        'permissions_display',
        'created_at',
        'expires_at',
    )
    list_filter = (
        'is_active',
        'accepted_at',
        'can_view',
        'can_edit',
        'can_reshare',
        'created_at',
    )
    search_fields = (
        'owner__email',
        'shared_with_email',
        'shared_with_user__email',
    )
    readonly_fields = (
        'token',
        'created_at',
        'updated_at',
        'status_display',
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Share Information', {
            'fields': (
                'owner',
                'shared_with_email',
                'shared_with_user',
                'status_display',
            )
        }),
        ('Permissions', {
            'fields': ('can_view', 'can_edit', 'can_reshare')
        }),
        ('Status & Tokens', {
            'fields': (
                'is_active',
                'token',
                'accepted_at',
                'expires_at',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['revoke_shares', 'extend_expiration']
    
    def owner_email(self, obj):
        """Display owner's email."""
        return obj.owner.email
    owner_email.short_description = 'Owner'
    owner_email.admin_order_field = 'owner__email'
    
    def status_display(self, obj):
        """Display share status with color coding."""
        status = obj.status
        colors = {
            'Accepted': 'green',
            'Pending': 'blue',
            'Expired': 'orange',
            'Revoked': 'red',
        }
        color = colors.get(status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            status
        )
    status_display.short_description = 'Status'
    
    def permissions_display(self, obj):
        """Display permissions as icons."""
        perms = []
        if obj.can_view:
            perms.append('👁️ View')
        if obj.can_edit:
            perms.append('✏️ Edit')
        if obj.can_reshare:
            perms.append('🔄 Reshare')
        return ' | '.join(perms)
    permissions_display.short_description = 'Permissions'
    
    def revoke_shares(self, request, queryset):
        """Admin action to revoke selected shares."""
        count = 0
        for share in queryset:
            if share.is_active:
                share.revoke()
                count += 1
        self.message_user(
            request,
            f"{count} menu share(s) revoked successfully."
        )
    revoke_shares.short_description = "Revoke selected menu shares"
    
    def extend_expiration(self, request, queryset):
        """Admin action to extend expiration by 7 days."""
        count = queryset.update(
            expires_at=timezone.now() + timezone.timedelta(days=7)
        )
        self.message_user(
            request,
            f"{count} menu share(s) extended by 7 days."
        )
    extend_expiration.short_description = "Extend expiration by 7 days"


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Admin configuration for ActivityLog model."""
    list_display = (
        'user_email',
        'action',
        'ip_address',
        'created_at',
    )
    list_filter = (
        'action',
        'created_at',
    )
    search_fields = (
        'user__email',
        'ip_address',
        'details',
    )
    readonly_fields = (
        'user',
        'action',
        'details',
        'ip_address',
        'user_agent',
        'created_at',
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    def user_email(self, obj):
        """Display user's email with link to user admin."""
        url = reverse(
            'admin:auth_user_change',
            args=[obj.user.pk]
        )
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.user.email
        )
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def has_add_permission(self, request):
        """Disable manual creation of activity logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Disable editing of activity logs."""
        return False


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Customize admin site header
admin.site.site_header = "KitchenCompass Administration"
admin.site.site_title = "KitchenCompass Admin"
admin.site.index_title = "Welcome to KitchenCompass Administration"