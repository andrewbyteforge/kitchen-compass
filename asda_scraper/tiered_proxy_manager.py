"""
Enhanced Proxy Manager with Tiered Support (Paid/Free)

This module provides intelligent proxy management with paid and free proxy tiers.

File: asda_scraper/tiered_proxy_manager.py
"""

import random
import time
import logging
import requests
from typing import dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import schedule
from bs4 import BeautifulSoup
from django.db import models
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class ProxyTier(Enum):
    """Proxy tier levels."""
    PREMIUM = "premium"      # Paid residential/datacenter proxies
    STANDARD = "standard"    # Paid datacenter proxies
    FREE = "free"           # Free public proxies
    DIRECT = "direct"       # No proxy (direct connection)


class ProxyProvider(Enum):
    """Supported proxy providers."""
    # Paid providers
    BRIGHT_DATA = "bright_data"
    SMARTPROXY = "smartproxy"
    OXYLABS = "oxylabs"
    BLAZING_SEO = "blazing_seo"
    STORM_PROXIES = "storm_proxies"
    
    # Free proxy sources
    FREE_PROXY_LIST = "free_proxy_list"
    PROXY_SCRAPE = "proxy_scrape"
    SSL_PROXIES = "ssl_proxies"
    CUSTOM = "custom"


@dataclass
class ProxyProviderConfig:
    """Configuration for proxy providers."""
    provider: ProxyProvider
    tier: ProxyTier
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    refresh_interval: int = 3600  # 1 hour for paid, more frequent for free
    max_concurrent: int = 10
    cost_per_gb: float = 0.0  # Cost tracking for paid proxies
    
    # Provider-specific settings
    sticky_sessions: bool = False
    session_duration: int = 600  # 10 minutes
    country_filter: Optional[List[str]] = None
    city_filter: Optional[List[str]] = None


class EnhancedProxyModel(models.Model):
    """
    Enhanced Django model for tiered proxy management.
    
    Add this to your models.py, replacing the previous ProxyModel
    """
    PROXY_TYPES = [
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
        ('socks5', 'SOCKS5'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('blacklisted', 'Blacklisted'),
        ('testing', 'Testing'),
        ('exhausted', 'Exhausted'),  # For paid proxies with usage limits
    ]
    
    TIER_CHOICES = [
        ('premium', 'Premium (Paid Residential)'),
        ('standard', 'Standard (Paid Datacenter)'),
        ('free', 'Free Public'),
    ]
    
    # Basic Information
    ip_address = models.GenericIPAddressField(help_text="IP address of the proxy server")
    port = models.PositiveIntegerField(help_text="Port number of the proxy server")
    proxy_type = models.CharField(max_length=10, choices=PROXY_TYPES, default='http')
    
    # Tier and Provider Information
    tier = models.CharField(
        max_length=20, 
        choices=TIER_CHOICES, 
        default='free',
        help_text="Proxy tier level"
    )
    provider = models.CharField(
        max_length=50,
        default='custom',
        help_text="Proxy provider name"
    )
    
    # Authentication
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    
    # Status and Performance
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='testing')
    last_checked = models.DateTimeField(null=True, blank=True)
    response_time = models.FloatField(null=True, blank=True)
    success_rate = models.FloatField(default=0.0)
    
    # Usage Statistics
    total_requests = models.PositiveIntegerField(default=0)
    failed_requests = models.PositiveIntegerField(default=0)
    bytes_used = models.BigIntegerField(default=0, help_text="Bandwidth used in bytes")
    last_used = models.DateTimeField(null=True, blank=True)
    
    # Cost Tracking (for paid proxies)
    cost_per_request = models.DecimalField(
        max_digits=10, 
        decimal_places=6, 
        default=0,
        help_text="Cost per request in USD"
    )
    total_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Total cost incurred"
    )
    
    # Limits (for paid proxies)
    daily_request_limit = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="Daily request limit for this proxy"
    )
    daily_requests_used = models.PositiveIntegerField(default=0)
    bandwidth_limit_gb = models.FloatField(
        null=True,
        blank=True,
        help_text="Bandwidth limit in GB"
    )
    
    # Additional Metadata
    country = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True)
    asn = models.CharField(max_length=100, blank=True, help_text="Autonomous System Number")
    is_residential = models.BooleanField(default=False)
    supports_https = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this proxy expires (for temporary proxies)"
    )
    
    class Meta:
        verbose_name = "Enhanced Proxy"
        verbose_name_plural = "Enhanced Proxies"
        unique_together = ['ip_address', 'port', 'provider']
        indexes = [
            models.Index(fields=['tier', 'status', 'success_rate']),
            models.Index(fields=['provider', 'status']),
            models.Index(fields=['last_used']),
        ]
    
    def __str__(self):
        return f"{self.tier.upper()} - {self.proxy_type}://{self.ip_address}:{self.port}"
    
    def is_paid(self) -> bool:
        """Check if this is a paid proxy."""
        return self.tier in ['premium', 'standard']
    
    def has_bandwidth_remaining(self) -> bool:
        """Check if proxy has bandwidth remaining."""
        if not self.bandwidth_limit_gb:
            return True
        used_gb = self.bytes_used / (1024 ** 3)
        return used_gb < self.bandwidth_limit_gb
    
    def has_requests_remaining(self) -> bool:
        """Check if proxy has daily requests remaining."""
        if not self.daily_request_limit:
            return True
        return self.daily_requests_used < self.daily_request_limit
    
    def reset_daily_limits(self):
        """Reset daily usage limits."""
        self.daily_requests_used = 0
        self.save(update_fields=['daily_requests_used'])


class TieredProxyManager:
    """
    Advanced proxy manager with tiered proxy support.
    """
    
    def __init__(self, prefer_paid: bool = True, fallback_to_free: bool = True):
        """
        Initialize the tiered proxy manager.
        
        Args:
            prefer_paid: Whether to prefer paid proxies over free ones
            fallback_to_free: Whether to fallback to free proxies when paid ones fail
        """
        self.prefer_paid = prefer_paid
        self.fallback_to_free = fallback_to_free
        self.providers: Dict[ProxyProvider, ProxyProviderConfig] = {}
        self._last_free_proxy_update = None
        self._free_proxy_update_interval = 3600  # 1 hour
        
        # Initialize provider configurations from settings
        self._initialize_providers()
        
        # Start scheduled tasks
        self._schedule_tasks()
        
        logger.info(
            f"TieredProxyManager initialized. "
            f"Prefer paid: {prefer_paid}, Fallback to free: {fallback_to_free}"
        )
    
    def _initialize_providers(self):
        """Initialize proxy provider configurations from Django settings."""
        # Example settings structure:
        # PROXY_PROVIDERS = {
        #     'bright_data': {
        #         'tier': 'premium',
        #         'api_key': 'your-api-key',
        #         'username': 'your-username',
        #         'password': 'your-password',
        #     },
        #     'smartproxy': {...},
        # }
        
        proxy_settings = getattr(settings, 'PROXY_PROVIDERS', {})
        
        for provider_name, config in proxy_settings.items():
            try:
                provider = ProxyProvider(provider_name)
                tier = ProxyTier(config.get('tier', 'standard'))
                
                provider_config = ProxyProviderConfig(
                    provider=provider,
                    tier=tier,
                    api_key=config.get('api_key'),
                    username=config.get('username'),
                    password=config.get('password'),
                    api_endpoint=config.get('api_endpoint'),
                    cost_per_gb=config.get('cost_per_gb', 0),
                )
                
                self.providers[provider] = provider_config
                logger.info(f"Initialized provider: {provider.value} (Tier: {tier.value})")
                
            except (ValueError, KeyError) as e:
                logger.error(f"Error initializing provider {provider_name}: {e}")
    
    def get_proxy(self, tier_preference: Optional[List[ProxyTier]] = None) -> Optional[str]:
        """
        Get the next available proxy based on tier preferences.
        
        Args:
            tier_preference: List of tiers in order of preference
            
        Returns:
            Optional[str]: Proxy URL or None if no proxies available
        """
        if not tier_preference:
            if self.prefer_paid:
                tier_preference = [ProxyTier.PREMIUM, ProxyTier.STANDARD, ProxyTier.FREE]
            else:
                tier_preference = [ProxyTier.FREE, ProxyTier.STANDARD, ProxyTier.PREMIUM]
        
        # Try to get proxy from each tier in order
        for tier in tier_preference:
            proxy = self._get_proxy_from_tier(tier)
            if proxy:
                return proxy
        
        # If all tiers failed and fallback is enabled, try direct connection
        if self.fallback_to_free and ProxyTier.FREE not in tier_preference:
            logger.warning("All preferred tiers failed, trying free proxies...")
            return self._get_proxy_from_tier(ProxyTier.FREE)
        
        logger.error("No proxies available from any tier")
        return None
    
    def _get_proxy_from_tier(self, tier: ProxyTier) -> Optional[str]:
        """Get a proxy from a specific tier."""
        # Update free proxies if needed
        if tier == ProxyTier.FREE:
            self._update_free_proxies_if_needed()
        
        # Query available proxies from this tier
        proxies = EnhancedProxyModel.objects.filter(
            tier=tier.value,
            status='active'
        ).exclude(
            status='exhausted'
        ).order_by(
            '-success_rate',
            'response_time',
            'total_requests'  # Least used first
        )
        
        # Additional filters for paid proxies
        if tier in [ProxyTier.PREMIUM, ProxyTier.STANDARD]:
            proxies = proxies.filter(
                models.Q(daily_request_limit__isnull=True) |
                models.Q(daily_requests_used__lt=models.F('daily_request_limit')),
                models.Q(bandwidth_limit_gb__isnull=True) |
                models.Q(bytes_used__lt=models.F('bandwidth_limit_gb') * 1024 * 1024 * 1024)
            )
        
        if not proxies.exists():
            logger.warning(f"No available proxies in tier: {tier.value}")
            return None
        
        # Select proxy based on performance
        proxy = self._select_best_proxy(proxies)
        if proxy:
            # Update usage
            proxy.last_used = timezone.now()
            proxy.total_requests += 1
            if proxy.is_paid():
                proxy.daily_requests_used += 1
            proxy.save()
            
            return proxy.get_proxy_url()
        
        return None
    
    def _select_best_proxy(self, proxies) -> Optional[EnhancedProxyModel]:
        """Select the best proxy from a queryset based on multiple factors."""
        # For paid proxies, also consider cost
        if proxies.first() and proxies.first().is_paid():
            # Sort by cost-effectiveness (success_rate / cost_per_request)
            proxy_list = list(proxies[:10])  # Get top 10
            proxy_list.sort(
                key=lambda p: (
                    p.success_rate / (p.cost_per_request + 0.0001),  # Avoid division by zero
                    -p.response_time if p.response_time else float('inf')
                ),
                reverse=True
            )
            return proxy_list[0] if proxy_list else None
        else:
            # For free proxies, just use the first one (already ordered by performance)
            return proxies.first()
    
    def _update_free_proxies_if_needed(self):
        """Update free proxy list if needed."""
        now = datetime.now()
        
        if (not self._last_free_proxy_update or 
            (now - self._last_free_proxy_update).seconds > self._free_proxy_update_interval):
            
            logger.info("Updating free proxy list...")
            self._fetch_free_proxies()
            self._last_free_proxy_update = now
    
    def _fetch_free_proxies(self):
        """Fetch free proxies from various sources."""
        sources = [
            self._fetch_from_free_proxy_list,
            self._fetch_from_ssl_proxies,
            self._fetch_from_proxy_scrape,
        ]
        
        all_proxies = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(source) for source in sources]
            
            for future in as_completed(futures):
                try:
                    proxies = future.result()
                    all_proxies.extend(proxies)
                except Exception as e:
                    logger.error(f"Error fetching free proxies: {e}")
        
        # Validate and add proxies
        logger.info(f"Fetched {len(all_proxies)} free proxies, validating...")
        self._validate_and_add_free_proxies(all_proxies)
    
    def _fetch_from_free_proxy_list(self) -> List[Dict]:
        """Fetch proxies from free-proxy-list.net."""
        proxies = []
        try:
            response = requests.get(
                'https://www.free-proxy-list.net/',
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'id': 'proxylisttable'})
                
                if table:
                    for row in table.find_all('tr')[1:50]:  # Get first 50
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            proxies.append({
                                'ip': cols[0].text.strip(),
                                'port': cols[1].text.strip(),
                                'country': cols[3].text.strip(),
                                'https': cols[6].text.strip() == 'yes'
                            })
        except Exception as e:
            logger.error(f"Error fetching from free-proxy-list: {e}")
        
        return proxies
    
    def _fetch_from_ssl_proxies(self) -> List[Dict]:
        """Fetch proxies from sslproxies.org."""
        proxies = []
        try:
            response = requests.get(
                'https://www.sslproxies.org/',
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'id': 'proxylisttable'})
                
                if table:
                    for row in table.find_all('tr')[1:30]:  # Get first 30
                        cols = row.find_all('td')
                        if len(cols) >= 7:
                            proxies.append({
                                'ip': cols[0].text.strip(),
                                'port': cols[1].text.strip(),
                                'country': cols[3].text.strip(),
                                'https': True  # SSL proxies support HTTPS
                            })
        except Exception as e:
            logger.error(f"Error fetching from sslproxies: {e}")
        
        return proxies
    
    def _fetch_from_proxy_scrape(self) -> List[Dict]:
        """Fetch proxies from proxyscrape.com."""
        proxies = []
        try:
            response = requests.get(
                'https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
                timeout=10
            )
            
            if response.status_code == 200:
                for line in response.text.strip().split('\n')[:50]:  # Get first 50
                    if ':' in line:
                        ip, port = line.strip().split(':')
                        proxies.append({
                            'ip': ip,
                            'port': port,
                            'country': 'Unknown',
                            'https': True
                        })
        except Exception as e:
            logger.error(f"Error fetching from proxyscrape: {e}")
        
        return proxies
    
    def _validate_and_add_free_proxies(self, proxy_list: List[Dict]):
        """Validate and add free proxies to database."""
        valid_count = 0
        
        def validate_proxy(proxy_info: Dict) -> bool:
            """Validate a single proxy."""
            proxy_url = f"http://{proxy_info['ip']}:{proxy_info['port']}"
            
            try:
                response = requests.get(
                    'http://httpbin.org/ip',
                    proxies={'http': proxy_url, 'https': proxy_url},
                    timeout=5
                )
                
                if response.status_code == 200:
                    # Create or update proxy in database
                    EnhancedProxyModel.objects.update_or_create(
                        ip_address=proxy_info['ip'],
                        port=int(proxy_info['port']),
                        provider=ProxyProvider.FREE_PROXY_LIST.value,
                        defaults={
                            'tier': ProxyTier.FREE.value,
                            'proxy_type': 'https' if proxy_info.get('https') else 'http',
                            'country': proxy_info.get('country', ''),
                            'status': 'active',
                            'last_checked': timezone.now(),
                            'supports_https': proxy_info.get('https', False)
                        }
                    )
                    return True
            except:
                pass
            
            return False
        
        # Validate proxies in parallel
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(validate_proxy, proxy_info) 
                for proxy_info in proxy_list
            ]
            
            for future in as_completed(futures):
                if future.result():
                    valid_count += 1
        
        logger.info(f"Added {valid_count} valid free proxies")
    
    def _schedule_tasks(self):
        """Schedule periodic tasks."""
        # Reset daily limits at midnight
        schedule.every().day.at("00:00").do(self._reset_daily_limits)
        
        # Clean up expired proxies
        schedule.every().hour.do(self._cleanup_expired_proxies)
        
        # Update free proxies
        schedule.every().hour.do(self._fetch_free_proxies)
    
    def _reset_daily_limits(self):
        """Reset daily limits for all proxies."""
        EnhancedProxyModel.objects.filter(
            tier__in=[ProxyTier.PREMIUM.value, ProxyTier.STANDARD.value]
        ).update(daily_requests_used=0)
        logger.info("Reset daily proxy limits")
    
    def _cleanup_expired_proxies(self):
        """Remove expired proxies."""
        expired = EnhancedProxyModel.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        
        if expired[0] > 0:
            logger.info(f"Cleaned up {expired[0]} expired proxies")
    
    def get_cost_report(self) -> Dict:
        """Generate cost report for paid proxies."""
        from django.db.models import Sum, Count
        
        report = {}
        
        for tier in [ProxyTier.PREMIUM, ProxyTier.STANDARD]:
            tier_stats = EnhancedProxyModel.objects.filter(
                tier=tier.value
            ).aggregate(
                total_cost=Sum('total_cost'),
                total_requests=Sum('total_requests'),
                total_bytes=Sum('bytes_used'),
                proxy_count=Count('id')
            )
            
            report[tier.value] = {
                'total_cost': float(tier_stats['total_cost'] or 0),
                'total_requests': tier_stats['total_requests'] or 0,
                'total_gb': (tier_stats['total_bytes'] or 0) / (1024 ** 3),
                'proxy_count': tier_stats['proxy_count'] or 0,
                'avg_cost_per_request': (
                    float(tier_stats['total_cost'] or 0) / 
                    (tier_stats['total_requests'] or 1)
                )
            }
        
        return report
    
    def import_paid_proxies(self, provider: ProxyProvider, proxy_list: List[str]):
        """Import paid proxies from a provider."""
        if provider not in self.providers:
            raise ValueError(f"Provider {provider.value} not configured")
        
        config = self.providers[provider]
        imported = 0
        
        for proxy_url in proxy_list:
            try:
                parsed = urlparse(proxy_url)
                
                EnhancedProxyModel.objects.update_or_create(
                    ip_address=parsed.hostname,
                    port=parsed.port or 80,
                    provider=provider.value,
                    defaults={
                        'tier': config.tier.value,
                        'proxy_type': parsed.scheme or 'http',
                        'username': parsed.username or config.username,
                        'password': parsed.password or config.password,
                        'status': 'active',
                        'cost_per_request': config.cost_per_gb / 1000,  # Rough estimate
                        'is_residential': config.tier == ProxyTier.PREMIUM,
                    }
                )
                imported += 1
                
            except Exception as e:
                logger.error(f"Error importing proxy {proxy_url}: {e}")
        
        logger.info(f"Imported {imported} paid proxies from {provider.value}")
        return imported


