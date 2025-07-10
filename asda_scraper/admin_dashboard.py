"""
Enhanced Admin Dashboard with Proxy Management

File: asda_scraper/admin_dashboard.py (update your existing admin.py)
"""

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html
from django.db.models import Sum, Count, Avg
from datetime import datetime, timedelta
from decimal import Decimal
import json


class ProxyManagementAdminSite(AdminSite):
    """Custom admin site with proxy management dashboard."""
    
    site_header = "KitchenCompass Admin - Proxy Management"
    site_title = "KitchenCompass"
    index_title = "Dashboard"
    
    def get_urls(self):
        """Add custom dashboard URLs."""
        urls = super().get_urls()
        custom_urls = [
            path('proxy-dashboard/', self.admin_view(self.proxy_dashboard_view), 
                 name='proxy_dashboard'),
            path('proxy-quick-setup/', self.admin_view(self.proxy_quick_setup), 
                 name='proxy_quick_setup'),
        ]
        return custom_urls + urls
    
    def proxy_dashboard_view(request):
        """
        Comprehensive proxy management dashboard view.
        
        Displays proxy statistics, provider status, and cost information.
        """
        from .models import ProxyConfiguration, ProxyProviderSettings, EnhancedProxyModel
        
        context = {
            'title': 'Proxy Management Dashboard',
            'site_header': admin.site.site_header,
            'site_title': admin.site.site_title,
            'has_permission': True,
        }
        
        try:
            # Get active configuration
            config = ProxyConfiguration.objects.filter(is_active=True).first()
            context['config'] = config
            
            # Get provider statistics
            providers = ProxyProviderSettings.objects.all()
            context['providers'] = providers
            
            # Get proxy statistics - check if EnhancedProxyModel exists
            try:
                proxy_stats = {
                    'total_proxies': EnhancedProxyModel.objects.count(),
                    'active_proxies': EnhancedProxyModel.objects.filter(status='active').count(),
                    'failed_proxies': EnhancedProxyModel.objects.filter(status='failed').count(),
                }
            except:
                # If EnhancedProxyModel doesn't exist yet
                proxy_stats = {
                    'total_proxies': 0,
                    'active_proxies': 0,
                    'failed_proxies': 0,
                }
            context['proxy_stats'] = proxy_stats
            
            # Calculate costs
            today = datetime.now().date()
            today_cost = ProxyProviderSettings.objects.aggregate(
                total=Sum('total_cost')
            )['total'] or Decimal('0.00')
            context['today_cost'] = today_cost
            
            # Prepare chart data (empty for now to avoid errors)
            context['charts_data'] = {
                'success_by_tier': json.dumps([]),
                'cost_trend': json.dumps([]),
            }
            
        except Exception as e:
            logger.error(f"Error in proxy dashboard: {str(e)}")
            context['error'] = str(e)
        
        return TemplateResponse(
            request,
            'asda_scraper/admin/proxy_dashboard.html',
            context
        )
    
    def proxy_quick_setup_view(request):
        """
        Quick setup view for common proxy scenarios.
        
        Allows administrators to quickly configure proxy settings
        with predefined configurations.
        """
        from .models import ProxyConfiguration
        from django.shortcuts import redirect
        
        if request.method == 'POST':
            setup_type = request.POST.get('setup_type')
            
            try:
                # Get or create configuration
                config, created = ProxyConfiguration.objects.get_or_create(
                    is_active=True,
                    defaults={'name': 'Default Configuration'}
                )
                
                if setup_type == 'free_only':
                    # Configure for free proxies only
                    config.prefer_paid_proxies = False
                    config.enable_free_proxy_fetching = True
                    config.daily_budget_limit = Decimal('0.00')
                    config.enable_proxy_service = True
                    config.save()
                    messages.success(request, "Configured for free proxies only.")
                    
                elif setup_type == 'paid_priority':
                    # Configure to prioritize paid proxies
                    config.prefer_paid_proxies = True
                    config.fallback_to_free = True
                    config.enable_free_proxy_fetching = True
                    config.daily_budget_limit = Decimal('100.00')
                    config.enable_proxy_service = True
                    config.save()
                    messages.success(request, "Configured to prioritize paid proxies.")
                    
                elif setup_type == 'balanced':
                    # Configure balanced proxy usage
                    config.prefer_paid_proxies = True
                    config.fallback_to_free = True
                    config.enable_free_proxy_fetching = True
                    config.daily_budget_limit = Decimal('50.00')
                    config.rotation_strategy = 'performance_based'
                    config.enable_proxy_service = True
                    config.save()
                    messages.success(request, "Configured for balanced proxy usage.")
                    
                elif setup_type == 'disable':
                    # Disable proxy service
                    config.enable_proxy_service = False
                    config.save()
                    messages.info(request, "Proxy service disabled.")
                    
            except Exception as e:
                logger.error(f"Error in proxy quick setup: {str(e)}")
                messages.error(request, f"Setup failed: {str(e)}")
            
            return redirect('admin:proxy_dashboard')
        
        context = {
            'title': 'Quick Proxy Setup',
            'site_header': admin.site.site_header,
            'site_title': admin.site.site_title,
            'has_permission': True,
        }
        
        return TemplateResponse(
            request,
            'asda_scraper/admin/proxy_quick_setup.html',
            context
        )


    # Add custom URLs to the admin site
    # This should be added after all the view functions but before the model admin classes
    original_get_urls = admin.site.get_urls

    def get_urls_with_proxy():
        """
        Add proxy dashboard URLs to admin.
        
        This function extends the default admin URLs with custom
        proxy management views.
        """
        urls = original_get_urls()
        custom_urls = [
            path('proxy-dashboard/', admin.site.admin_view(proxy_dashboard_view), name='proxy_dashboard'),
            path('proxy-quick-setup/', admin.site.admin_view(proxy_quick_setup_view), name='proxy_quick_setup'),
        ]
        return custom_urls + urls

    # Apply the custom URLs
    admin.site.get_urls = get_urls_with_proxy
    


    
    def proxy_quick_setup(self, request):
        """Quick setup for common proxy scenarios."""
        if request.method == 'POST':
            setup_type = request.POST.get('setup_type')
            
            if setup_type == 'free_only':
                self._setup_free_only_config()
            elif setup_type == 'paid_priority':
                self._setup_paid_priority_config()
            elif setup_type == 'balanced':
                self._setup_balanced_config()
            
            messages.success(request, f"Proxy configuration '{setup_type}' applied successfully!")
            return redirect('admin:proxy_dashboard')
        
        return TemplateResponse(
            request,
            'admin/proxy_quick_setup.html',
            {'title': 'Quick Proxy Setup'}
        )
    
    def _get_proxy_dashboard_context(self):
        """Get context data for proxy dashboard."""
        from asda_scraper.models import (
            ProxyConfiguration, ProxyProviderSettings, 
            EnhancedProxyModel
        )
        
        # Get active configuration
        config = ProxyConfiguration.objects.filter(is_active=True).first()
        
        # Provider statistics
        providers = ProxyProviderSettings.objects.all()
        provider_stats = []
        
        for provider in providers:
            stats = {
                'provider': provider,
                'proxy_count': EnhancedProxyModel.objects.filter(
                    provider=provider.provider
                ).count(),
                'active_count': EnhancedProxyModel.objects.filter(
                    provider=provider.provider,
                    status='active'
                ).count(),
                'success_rate': EnhancedProxyModel.objects.filter(
                    provider=provider.provider
                ).aggregate(
                    avg_success=Avg('success_rate')
                )['avg_success'] or 0,
                'daily_cost': self._get_provider_daily_cost(provider),
            }
            provider_stats.append(stats)
        
        # Overall statistics
        total_proxies = EnhancedProxyModel.objects.count()
        active_proxies = EnhancedProxyModel.objects.filter(status='active').count()
        
        # Cost analysis
        today = datetime.now().date()
        daily_costs = self._get_daily_cost_breakdown()
        
        # Performance metrics
        performance_metrics = self._get_performance_metrics()
        
        return {
            'config': config,
            'provider_stats': provider_stats,
            'total_proxies': total_proxies,
            'active_proxies': active_proxies,
            'daily_costs': daily_costs,
            'performance_metrics': performance_metrics,
            'charts_data': self._get_charts_data(),
        }
    
    def _get_provider_daily_cost(self, provider):
        """Calculate daily cost for a provider."""
        today = datetime.now().date()
        
        return EnhancedProxyModel.objects.filter(
            provider=provider.provider,
            last_used__date=today
        ).aggregate(
            total=Sum('total_cost')
        )['total'] or Decimal('0.00')
    
    def _get_daily_cost_breakdown(self):
        """Get cost breakdown by tier for the last 7 days."""
        costs = []
        for i in range(7):
            date = datetime.now().date() - timedelta(days=i)
            
            daily_cost = {
                'date': date,
                'premium': EnhancedProxyModel.objects.filter(
                    tier='premium',
                    last_used__date=date
                ).aggregate(Sum('total_cost'))['total_cost__sum'] or 0,
                'standard': EnhancedProxyModel.objects.filter(
                    tier='standard',
                    last_used__date=date
                ).aggregate(Sum('total_cost'))['total_cost__sum'] or 0,
                'free': 0,  # Free proxies have no cost
            }
            costs.append(daily_cost)
        
        return costs
    
    def _get_performance_metrics(self):
        """Get performance metrics for all proxy tiers."""
        metrics = {}
        
        for tier in ['premium', 'standard', 'free']:
            tier_metrics = EnhancedProxyModel.objects.filter(
                tier=tier,
                status='active'
            ).aggregate(
                avg_response_time=Avg('response_time'),
                avg_success_rate=Avg('success_rate'),
                total_requests=Sum('total_requests'),
                failed_requests=Sum('failed_requests'),
            )
            
            metrics[tier] = {
                'avg_response_time': tier_metrics['avg_response_time'] or 0,
                'avg_success_rate': tier_metrics['avg_success_rate'] or 0,
                'total_requests': tier_metrics['total_requests'] or 0,
                'failed_requests': tier_metrics['failed_requests'] or 0,
            }
        
        return metrics
    
    def _get_charts_data(self):
        """Prepare data for dashboard charts."""
        # Success rate by tier
        success_by_tier = []
        for tier in ['premium', 'standard', 'free']:
            avg_success = EnhancedProxyModel.objects.filter(
                tier=tier,
                status='active'
            ).aggregate(
                avg=Avg('success_rate')
            )['avg'] or 0
            
            success_by_tier.append({
                'tier': tier.capitalize(),
                'success_rate': round(avg_success, 1)
            })
        
        # Cost trend (last 30 days)
        cost_trend = []
        for i in range(30):
            date = datetime.now().date() - timedelta(days=i)
            daily_total = EnhancedProxyModel.objects.filter(
                tier__in=['premium', 'standard'],
                last_used__date=date
            ).aggregate(
                total=Sum('total_cost')
            )['total'] or 0
            
            cost_trend.append({
                'date': date.strftime('%Y-%m-%d'),
                'cost': float(daily_total)
            })
        
        cost_trend.reverse()  # Chronological order
        
        return {
            'success_by_tier': json.dumps(success_by_tier),
            'cost_trend': json.dumps(cost_trend),
        }
    
    def _setup_free_only_config(self):
        """Configure system to use only free proxies."""
        config = ProxyConfiguration.objects.filter(is_active=True).first()
        if config:
            config.prefer_paid_proxies = False
            config.enable_free_proxy_fetching = True
            config.daily_budget_limit = Decimal('0.00')
            config.save()
    
    def _setup_paid_priority_config(self):
        """Configure system to prioritize paid proxies."""
        config = ProxyConfiguration.objects.filter(is_active=True).first()
        if config:
            config.prefer_paid_proxies = True
            config.fallback_to_free = True
            config.enable_free_proxy_fetching = True
            config.daily_budget_limit = Decimal('100.00')
            config.save()
    
    def _setup_balanced_config(self):
        """Configure balanced proxy usage."""
        config = ProxyConfiguration.objects.filter(is_active=True).first()
        if config:
            config.prefer_paid_proxies = True
            config.fallback_to_free = True
            config.enable_free_proxy_fetching = True
            config.daily_budget_limit = Decimal('50.00')
            config.rotation_strategy = 'performance_based'
            config.save()


# Update your main admin.py to include proxy dashboard
def setup_proxy_admin(admin_site):
    """Setup proxy management in admin interface."""
    
    # Add dashboard link to admin index
    original_index = admin_site.index
    
    def proxy_aware_index(request, extra_context=None):
        extra_context = extra_context or {}
        
        # Add proxy status widget
        from asda_scraper.proxy_admin import ProxyStatusDashboard
        extra_context['proxy_status'] = ProxyStatusDashboard.get_status_html()
        
        # Add quick actions
        extra_context['proxy_quick_actions'] = format_html(
            '''
            <div class="proxy-quick-actions">
                <a href="/admin/proxy-dashboard/" class="button">Proxy Dashboard</a>
                <a href="/admin/asda_scraper/proxyconfiguration/" class="button">Configuration</a>
                <a href="/admin/asda_scraper/proxyprovidersettings/" class="button">Providers</a>
            </div>
            '''
        )
        
        return original_index(request, extra_context)
    
    admin_site.index = proxy_aware_index


