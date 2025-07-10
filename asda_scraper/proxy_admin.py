"""
Django Admin Interface for Proxy Configuration

This module provides admin interface for managing proxy settings dynamically.

File: asda_scraper/proxy_admin.py
"""

from django.contrib import admin
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from django import forms
from django.conf import settings
import json
from datetime import datetime, timedelta
from decimal import Decimal
from cryptography.fernet import Fernet
from django.utils import timezone

# Import the models from models.py instead of defining them here
from .models import ProxyConfiguration, ProxyProviderSettings, EnhancedProxyModel






# Admin Configuration
@admin.register
class ProxyConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for global proxy configuration."""
    
    list_display = [
        'name', 'is_active', 'enable_proxy_service', 
        'prefer_paid_proxies', 'daily_budget_limit', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Settings', {
            'fields': (
                'name', 'is_active', 'enable_proxy_service'
            )
        }),
        ('Proxy Strategy', {
            'fields': (
                'prefer_paid_proxies', 'fallback_to_free', 
                'allow_direct_connection', 'rotation_strategy'
            ),
            'description': 'Configure how proxies are selected and used'
        }),
        ('Performance', {
            'fields': (
                'max_requests_per_proxy', 'proxy_timeout_seconds',
                'health_check_interval_minutes'
            )
        }),
        ('Cost Management', {
            'fields': (
                'daily_budget_limit', 'cost_alert_threshold'
            ),
            'description': 'Set spending limits and alerts'
        }),
        ('Free Proxy Settings', {
            'fields': (
                'enable_free_proxy_fetching', 'free_proxy_update_hours',
                'max_free_proxies'
            ),
            'classes': ('collapse',)
        }),
        ('Monitoring', {
            'fields': (
                'enable_monitoring', 'alert_email'
            ),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        """Save the model and show success message."""
        super().save_model(request, obj, form, change)
        messages.success(
            request,
            f"Proxy configuration '{obj.name}' has been saved successfully."
        )


class ProxyProviderAdminForm(forms.ModelForm):
    """Custom form for proxy provider with password handling."""
    
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        help_text="Enter password (leave blank to keep existing)"
    )
    
    class Meta:
        model = ProxyProviderSettings
        fields = '__all__'
        exclude = ['password_encrypted']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Show masked password if exists
        if self.instance and self.instance.pk and self.instance.password_encrypted:
            self.fields['password'].widget.attrs['placeholder'] = '********'
    
    def save(self, commit=True):
        """Save the form with password encryption."""
        provider = super().save(commit=False)
        
        # Handle password
        password = self.cleaned_data.get('password')
        if password:  # Only update if new password provided
            provider.set_password(password)
        
        if commit:
            provider.save()
        
        return provider


@admin.register(ProxyProviderSettings)
class ProxyProviderSettingsAdmin(admin.ModelAdmin):
    """Admin interface for individual proxy providers."""
    
    form = ProxyProviderAdminForm
    
    list_display = [
        'provider_display', 'is_enabled', 'tier', 'cost_info',
        'usage_stats', 'status_display', 'actions_column'
    ]
    
    list_filter = ['is_enabled', 'tier', 'provider']
    
    search_fields = ['display_name', 'provider', 'api_endpoint']
    
    fieldsets = (
        ('Provider Information', {
            'fields': (
                'provider', 'display_name', 'is_enabled', 'tier'
            )
        }),
        ('API Configuration', {
            'fields': (
                'api_endpoint', 'api_key', 'username', 'password'
            ),
            'description': 'Enter API credentials for this provider'
        }),
        ('Cost Configuration', {
            'fields': (
                'cost_per_gb', 'cost_per_request', 'minimum_monthly_cost'
            )
        }),
        ('Limits & Features', {
            'fields': (
                'monthly_bandwidth_gb', 'concurrent_connections',
                'supports_countries', 'supports_cities',
                'supports_sticky_sessions', 'supports_residential'
            ),
            'classes': ('collapse',)
        }),
        ('Usage & Status', {
            'fields': (
                'total_requests', 'total_bandwidth_mb', 'total_cost',
                'success_rate', 'average_response_time', 'last_used'
            ),
            'classes': ('collapse',),
            'description': 'Read-only usage statistics'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = [
        'total_requests', 'total_cost',
        'last_used', 'updated_at'
    ]
    
    def provider_display(self, obj):
        """Display provider with icon."""
        icon_map = {
            'bright_data': '🌟',
            'smartproxy': '🔧',
            'oxylabs': '🐙',
            'blazing_seo': '🔥',
            'storm_proxies': '⛈️',
            'custom': '⚙️'
        }
        icon = icon_map.get(obj.provider, '📡')
        return format_html(
            '{} <strong>{}</strong>',
            icon,
            obj.display_name
        )
    provider_display.short_description = 'Provider'
    
    def cost_info(self, obj):
        """Display cost information."""
        return format_html(
            '${}/GB<br><small>${}/mo est.</small>',
            obj.cost_per_gb,
            obj.get_monthly_cost()
        )
    cost_info.short_description = 'Cost'
    
    def usage_stats(self, obj):
        """Display usage statistics."""
        return format_html(
            '{:,} requests<br>{:.2f} MB<br>${:.2f} total',
            obj.total_requests,
            obj.total_bandwidth_mb,  # Changed from calculation
            obj.total_cost
        )
    usage_stats.short_description = 'Usage'
    
    def status_display(self, obj):
        """Display provider status."""
        if obj.is_enabled and obj.is_working:
            return format_html(
                '<span style="color: green;">✓ Active</span>'
            )
        elif obj.is_enabled and not obj.is_working:
            return format_html(
                '<span style="color: red;">✗ Error</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">- Disabled</span>'
            )
    status_display.short_description = 'Status'
    
    def actions_column(self, obj):
        """Custom actions for each provider."""
        if obj.is_enabled:
            test_url = reverse('admin:test_proxy_provider', args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">Test Connection</a>',
                test_url
            )
        return '-'
    actions_column.short_description = 'Actions'
    
    def get_urls(self):
        """Add custom URLs for provider actions."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:provider_id>/test/',
                self.admin_site.admin_view(self.test_provider_view),
                name='test_proxy_provider'
            ),
            path(
                'setup-wizard/',
                self.admin_site.admin_view(self.setup_wizard_view),
                name='proxy_setup_wizard'
            ),
        ]
        return custom_urls + urls
    
    def test_provider_view(self, request, provider_id):
        """Test proxy provider connection."""
        provider = ProxyProviderSettings.objects.get(pk=provider_id)
        
        # Test the provider
        import requests
        test_successful = False
        error_message = None
        
        try:
            proxy_url = f"http://{provider.username}:{provider.get_password()}@{provider.api_endpoint}"
            response = requests.get(
                'http://httpbin.org/ip',
                proxies={'http': proxy_url, 'https': proxy_url},
                timeout=10
            )
            
            if response.status_code == 200:
                test_successful = True
                provider.is_working = True
                provider.last_error = ''
            else:
                error_message = f"HTTP {response.status_code}"
                
        except Exception as e:
            error_message = str(e)
            provider.is_working = False
            provider.last_error = error_message
        
        provider.save()
        
        # Show result
        if test_successful:
            messages.success(request, f"✓ {provider.display_name} is working correctly!")
        else:
            messages.error(request, f"✗ {provider.display_name} test failed: {error_message}")
        
        return redirect('admin:asda_scraper_proxyprovidersettings_changelist')
    
    def setup_wizard_view(self, request):
        """Proxy setup wizard for easy configuration."""
        if request.method == 'POST':
            # Process wizard form
            provider_type = request.POST.get('provider_type')
            
            # Create provider based on selection
            provider_configs = {
                'bright_data': {
                    'display_name': 'Bright Data',
                    'tier': 'premium',
                    'api_endpoint': 'zproxy.lum-superproxy.io:22225',
                    'cost_per_gb': 3.0,
                    'supports_residential': True,
                },
                'smartproxy': {
                    'display_name': 'SmartProxy',
                    'tier': 'standard',
                    'api_endpoint': 'gate.smartproxy.com:10000',
                    'cost_per_gb': 1.5,
                },
                'blazing_seo': {
                    'display_name': 'Blazing SEO',
                    'tier': 'standard',
                    'api_endpoint': 'premium.blazingseollc.com:5432',
                    'cost_per_gb': 0.5,
                }
            }
            
            if provider_type in provider_configs:
                config = provider_configs[provider_type]
                provider, created = ProxyProviderSettings.objects.update_or_create(
                    provider=provider_type,
                    defaults={
                        **config,
                        'username': request.POST.get('username', ''),
                        'api_key': request.POST.get('api_key', ''),
                        'is_enabled': True,
                    }
                )
                
                # Set password
                password = request.POST.get('password')
                if password:
                    provider.set_password(password)
                    provider.save()
                
                messages.success(
                    request,
                    f"✓ {provider.display_name} has been configured successfully!"
                )
                
                return redirect('admin:asda_scraper_proxyprovidersettings_changelist')
        
        # Render wizard template
        return render(request, 'admin/proxy_setup_wizard.html', {
            'title': 'Proxy Provider Setup Wizard',
        })


# Admin dashboard widget for proxy status
class ProxyStatusDashboard:
    """Dashboard widget showing proxy system status."""
    
    @staticmethod
    def get_status_html():
        """Get HTML for proxy status dashboard."""
        config = ProxyConfiguration.objects.filter(is_active=True).first()
        
        if not config or not config.enable_proxy_service:
            return format_html(
                '<div class="proxy-status-disabled">'
                '<h3>🔴 Proxy Service Disabled</h3>'
                '<p>Enable proxy service in configuration to start using proxies.</p>'
                '</div>'
            )
        
        # Get statistics
        active_providers = ProxyProviderSettings.objects.filter(
            is_enabled=True, is_working=True
        ).count()
        
        total_proxies = EnhancedProxyModel.objects.filter(status='active').count()
        paid_proxies = EnhancedProxyModel.objects.filter(
            status='active', tier__in=['premium', 'standard']
        ).count()
        free_proxies = EnhancedProxyModel.objects.filter(
            status='active', tier='free'
        ).count()
        
        # Get today's cost
        today = timezone.now().date()
        today_cost = EnhancedProxyModel.objects.filter(
            tier__in=['premium', 'standard'],
            last_used__date=today
        ).aggregate(
            total=models.Sum('total_cost')
        )['total'] or 0
        
        budget_used_percent = (float(today_cost) / float(config.daily_budget_limit)) * 100
        
        return format_html(
            '''
            <div class="proxy-status-active">
                <h3>🟢 Proxy Service Active</h3>
                <div class="proxy-stats">
                    <div class="stat">
                        <strong>{}</strong> Active Providers
                    </div>
                    <div class="stat">
                        <strong>{}</strong> Total Proxies
                        ({} paid, {} free)
                    </div>
                    <div class="stat">
                        <strong>${:.2f}</strong> Today's Cost
                        <div class="progress">
                            <div class="progress-bar" style="width: {:.1f}%"></div>
                        </div>
                        <small>{:.1f}% of ${} daily budget</small>
                    </div>
                </div>
            </div>
            ''',
            active_providers,
            total_proxies, paid_proxies, free_proxies,
            today_cost,
            budget_used_percent,
            budget_used_percent, config.daily_budget_limit
        )


