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


# First, let's create models for storing proxy configuration
class ProxyConfiguration(models.Model):
    """
    Global proxy configuration settings.
    
    File: asda_scraper/models.py (add to existing file)
    """
    name = models.CharField(
        max_length=100,
        default="Default Configuration",
        help_text="Configuration name"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this configuration is currently active"
    )
    
    # Proxy Behavior
    enable_proxy_service = models.BooleanField(
        default=False,
        help_text="Enable proxy service for scraping"
    )
    prefer_paid_proxies = models.BooleanField(
        default=True,
        help_text="Use paid proxies before trying free ones"
    )
    fallback_to_free = models.BooleanField(
        default=True,
        help_text="Use free proxies when paid proxies fail"
    )
    allow_direct_connection = models.BooleanField(
        default=False,
        help_text="Allow direct connection when all proxies fail"
    )
    
    # Performance Settings
    rotation_strategy = models.CharField(
        max_length=50,
        choices=[
            ('round_robin', 'Round Robin'),
            ('random', 'Random'),
            ('least_used', 'Least Used'),
            ('performance_based', 'Performance Based'),
        ],
        default='performance_based',
        help_text="How to select the next proxy"
    )
    max_requests_per_proxy = models.PositiveIntegerField(
        default=100,
        help_text="Rotate proxy after this many requests"
    )
    proxy_timeout_seconds = models.PositiveIntegerField(
        default=10,
        help_text="Timeout for proxy connections in seconds"
    )
    health_check_interval_minutes = models.PositiveIntegerField(
        default=5,
        help_text="Check proxy health every N minutes"
    )
    
    # Cost Management
    daily_budget_limit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        help_text="Maximum daily spend on paid proxies (USD)"
    )
    cost_alert_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=80.00,
        help_text="Alert when daily cost exceeds this amount (USD)"
    )
    
    # Free Proxy Settings
    enable_free_proxy_fetching = models.BooleanField(
        default=True,
        help_text="Automatically fetch and validate free proxies"
    )
    free_proxy_update_hours = models.PositiveIntegerField(
        default=1,
        help_text="Update free proxy list every N hours"
    )
    max_free_proxies = models.PositiveIntegerField(
        default=200,
        help_text="Maximum number of free proxies to maintain"
    )
    
    # Monitoring
    enable_monitoring = models.BooleanField(
        default=True,
        help_text="Enable proxy performance monitoring"
    )
    alert_email = models.EmailField(
        blank=True,
        help_text="Email for proxy alerts (leave blank to disable)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Proxy Configuration"
        verbose_name_plural = "Proxy Configurations"
    
    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"
    
    def save(self, *args, **kwargs):
        """Ensure only one configuration is active at a time."""
        if self.is_active:
            ProxyConfiguration.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class ProxyProviderSettings(models.Model):
    """
    Settings for individual proxy providers.
    
    File: asda_scraper/models.py (add to existing file)
    """
    PROVIDER_CHOICES = [
        ('bright_data', 'Bright Data (Luminati)'),
        ('smartproxy', 'SmartProxy'),
        ('oxylabs', 'Oxylabs'),
        ('blazing_seo', 'Blazing SEO'),
        ('storm_proxies', 'Storm Proxies'),
        ('proxy_cheap', 'Proxy-Cheap'),
        ('hydraproxy', 'HydraProxy'),
        ('custom', 'Custom Provider'),
    ]
    
    TIER_CHOICES = [
        ('premium', 'Premium (Residential)'),
        ('standard', 'Standard (Datacenter)'),
    ]
    
    # Basic Information
    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        unique=True,
        help_text="Proxy provider service"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Display name for this provider"
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text="Enable this proxy provider"
    )
    tier = models.CharField(
        max_length=20,
        choices=TIER_CHOICES,
        default='standard',
        help_text="Proxy quality tier"
    )
    
    # API Configuration
    api_endpoint = models.CharField(
        max_length=255,
        blank=True,
        help_text="API endpoint URL (e.g., gate.smartproxy.com:10000)"
    )
    api_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="API key for provider"
    )
    
    # Authentication (encrypted)
    username = models.CharField(
        max_length=100,
        blank=True,
        help_text="Username for proxy authentication"
    )
    password_encrypted = models.TextField(
        blank=True,
        help_text="Encrypted password"
    )
    
    # Cost Configuration
    cost_per_gb = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1.00,
        help_text="Cost per GB of data (USD)"
    )
    cost_per_request = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=0.0001,
        help_text="Cost per request (USD)"
    )
    minimum_monthly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Minimum monthly commitment (USD)"
    )
    
    # Limits
    monthly_bandwidth_gb = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Monthly bandwidth limit in GB"
    )
    concurrent_connections = models.PositiveIntegerField(
        default=100,
        help_text="Maximum concurrent connections"
    )
    
    # Features
    supports_countries = models.BooleanField(
        default=True,
        help_text="Supports country-level targeting"
    )
    supports_cities = models.BooleanField(
        default=False,
        help_text="Supports city-level targeting"
    )
    supports_sticky_sessions = models.BooleanField(
        default=True,
        help_text="Supports sticky/persistent sessions"
    )
    supports_residential = models.BooleanField(
        default=False,
        help_text="Offers residential IPs"
    )
    
    # Advanced Settings (JSON)
    extra_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional provider-specific settings (JSON)"
    )
    
    # Usage Tracking
    total_requests = models.BigIntegerField(
        default=0,
        help_text="Total requests made through this provider"
    )
    total_bandwidth_bytes = models.BigIntegerField(
        default=0,
        help_text="Total bandwidth used in bytes"
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Total cost incurred (USD)"
    )
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this provider was used"
    )
    
    # Status
    is_working = models.BooleanField(
        default=True,
        help_text="Whether the provider is currently working"
    )
    last_error = models.TextField(
        blank=True,
        help_text="Last error message from this provider"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Proxy Provider"
        verbose_name_plural = "Proxy Providers"
        ordering = ['provider']
    
    def __str__(self):
        return f"{self.display_name} ({'Enabled' if self.is_enabled else 'Disabled'})"
    
    def set_password(self, password):
        """Encrypt and store password."""
        if password:
            # Generate key if not exists
            key = getattr(settings, 'PROXY_ENCRYPTION_KEY', None)
            if not key:
                key = Fernet.generate_key()
                # Store this key in your settings or environment variable
            
            f = Fernet(key)
            self.password_encrypted = f.encrypt(password.encode()).decode()
    
    def get_password(self):
        """Decrypt and return password."""
        if self.password_encrypted:
            key = getattr(settings, 'PROXY_ENCRYPTION_KEY', None)
            if key:
                f = Fernet(key)
                return f.decrypt(self.password_encrypted.encode()).decode()
        return ''
    
    def get_monthly_cost(self):
        """Calculate estimated monthly cost."""
        if self.minimum_monthly_cost > 0:
            return self.minimum_monthly_cost
        
        # Estimate based on usage
        days_used = (timezone.now() - self.created_at).days or 1
        daily_cost = float(self.total_cost) / days_used
        return Decimal(daily_cost * 30)
    
    def clean(self):
        """Validate the provider settings."""
        if self.is_enabled:
            if not self.api_endpoint and self.provider != 'custom':
                raise ValidationError("API endpoint is required for enabled providers")
            
            if self.provider in ['bright_data', 'smartproxy', 'oxylabs']:
                if not self.username or not self.password_encrypted:
                    raise ValidationError(
                        f"{self.get_provider_display()} requires username and password"
                    )


# Admin Configuration
@admin.register(ProxyConfiguration)
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
    
    list_filter = ['is_enabled', 'tier', 'is_working', 'provider']
    
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
        ('Advanced Settings', {
            'fields': ('extra_settings',),
            'classes': ('collapse',),
            'description': 'JSON format for provider-specific settings'
        }),
        ('Usage & Status', {
            'fields': (
                'total_requests', 'total_bandwidth_bytes', 'total_cost',
                'last_used', 'is_working', 'last_error'
            ),
            'classes': ('collapse',),
            'description': 'Read-only usage statistics'
        })
    )
    
    readonly_fields = [
        'total_requests', 'total_bandwidth_bytes', 'total_cost',
        'last_used', 'created_at', 'updated_at'
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
        gb_used = obj.total_bandwidth_bytes / (1024**3)
        return format_html(
            '{:,} requests<br>{:.2f} GB<br>${:.2f} total',
            obj.total_requests,
            gb_used,
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


