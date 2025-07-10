"""
Enhanced Django management command for tiered proxy management.

File: asda_scraper/management/commands/manage_tiered_proxies.py
"""

import logging
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings
from asda_scraper.tiered_proxy_manager import (
    TieredProxyManager, 
    ProxyTier, 
    ProxyProvider,
    EnhancedProxyModel
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Manage tiered proxy servers with paid/free support."""
    
    help = 'Manage tiered proxy servers for web scraping'
    
    def add_arguments(self, parser):
        """Add command line arguments."""
        parser.add_argument(
            'action',
            type=str,
            choices=[
                'list', 'add-paid', 'update-free', 'test', 
                'stats', 'costs', 'configure', 'balance'
            ],
            help='Action to perform'
        )
        
        # Proxy specification
        parser.add_argument(
            '--provider',
            type=str,
            choices=['bright_data', 'smartproxy', 'oxylabs', 'custom'],
            help='Proxy provider'
        )
        
        parser.add_argument(
            '--tier',
            type=str,
            choices=['premium', 'standard', 'free'],
            default='standard',
            help='Proxy tier level'
        )
        
        parser.add_argument(
            '--file',
            type=str,
            help='File containing proxy list'
        )
        
        # Filtering
        parser.add_argument(
            '--min-success-rate',
            type=float,
            default=0,
            help='Minimum success rate'
        )
        
        parser.add_argument(
            '--max-cost',
            type=float,
            help='Maximum cost per request'
        )
        
        # Configuration
        parser.add_argument(
            '--prefer-paid',
            action='store_true',
            default=True,
            help='Prefer paid proxies over free'
        )
        
        parser.add_argument(
            '--fallback-to-free',
            action='store_true',
            default=True,
            help='Fallback to free proxies when paid fail'
        )
        
        # Testing
        parser.add_argument(
            '--test-count',
            type=int,
            default=10,
            help='Number of proxies to test'
        )
        
        # Output
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json', 'summary'],
            default='table',
            help='Output format'
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        action = options['action']
        
        try:
            if action == 'list':
                self.list_proxies(options)
            elif action == 'add-paid':
                self.add_paid_proxies(options)
            elif action == 'update-free':
                self.update_free_proxies(options)
            elif action == 'test':
                self.test_proxies(options)
            elif action == 'stats':
                self.show_statistics(options)
            elif action == 'costs':
                self.show_costs(options)
            elif action == 'configure':
                self.configure_providers(options)
            elif action == 'balance':
                self.balance_proxy_usage(options)
                
        except Exception as e:
            raise CommandError(f'Error executing {action}: {str(e)}')
    
    def list_proxies(self, options):
        """List proxies by tier with filtering."""
        queryset = EnhancedProxyModel.objects.all()
        
        # Apply filters
        if options.get('tier'):
            queryset = queryset.filter(tier=options['tier'])
        
        if options['min_success_rate'] > 0:
            queryset = queryset.filter(
                success_rate__gte=options['min_success_rate']
            )
        
        if options.get('max_cost'):
            queryset = queryset.filter(
                cost_per_request__lte=options['max_cost']
            )
        
        # Group by tier
        tiers = {}
        for proxy in queryset.order_by('tier', '-success_rate'):
            if proxy.tier not in tiers:
                tiers[proxy.tier] = []
            tiers[proxy.tier].append(proxy)
        
        # Display results
        for tier_name, proxies in tiers.items():
            self.stdout.write(
                self.style.SUCCESS(f"\n{tier_name.upper()} TIER ({len(proxies)} proxies)")
            )
            
            if options['format'] == 'table':
                self._print_proxy_table(proxies[:20])  # Show top 20
            elif options['format'] == 'summary':
                self._print_tier_summary(tier_name, proxies)
    
    def add_paid_proxies(self, options):
        """Add paid proxies from provider."""
        provider_name = options.get('provider')
        if not provider_name:
            raise CommandError('--provider is required for add-paid action')
        
        file_path = options.get('file')
        if not file_path:
            raise CommandError('--file is required for add-paid action')
        
        try:
            provider = ProxyProvider(provider_name)
            manager = TieredProxyManager()
            
            # Read proxy list from file
            with open(file_path, 'r') as f:
                proxy_list = [line.strip() for line in f if line.strip()]
            
            # Import proxies
            imported = manager.import_paid_proxies(provider, proxy_list)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully imported {imported} paid proxies from {provider_name}"
                )
            )
            
        except FileNotFoundError:
            raise CommandError(f"File not found: {file_path}")
        except ValueError as e:
            raise CommandError(str(e))
    
    def update_free_proxies(self, options):
        """Update free proxy list from public sources."""
        self.stdout.write("Fetching free proxies from public sources...")
        
        manager = TieredProxyManager()
        
        # Force update free proxies
        initial_count = EnhancedProxyModel.objects.filter(tier='free').count()
        manager._fetch_free_proxies()
        final_count = EnhancedProxyModel.objects.filter(tier='free').count()
        
        added = final_count - initial_count
        self.stdout.write(
            self.style.SUCCESS(
                f"Free proxy update complete. Added {added} new proxies. "
                f"Total free proxies: {final_count}"
            )
        )
    
    def test_proxies(self, options):
        """Test proxy connectivity and performance."""
        tier = options.get('tier')
        test_count = options['test_count']
        
        # Get proxies to test
        queryset = EnhancedProxyModel.objects.filter(status='active')
        if tier:
            queryset = queryset.filter(tier=tier)
        
        proxies = list(queryset.order_by('?')[:test_count])  # Random selection
        
        if not proxies:
            self.stdout.write(self.style.WARNING("No proxies to test"))
            return
        
        self.stdout.write(f"Testing {len(proxies)} proxies...\n")
        
        passed = 0
        failed = 0
        
        for proxy in proxies:
            # Test proxy
            success = self._test_single_proxy(proxy)
            
            if success:
                passed += 1
                status_str = self.style.SUCCESS("✓ PASS")
            else:
                failed += 1
                status_str = self.style.ERROR("✗ FAIL")
            
            self.stdout.write(
                f"{status_str} {proxy.tier.upper()} - {proxy} "
                f"(Success: {proxy.success_rate:.1f}%)"
            )
        
        # Summary
        self.stdout.write(
            f"\nTest complete: {passed} passed, {failed} failed "
            f"({(passed/len(proxies)*100):.1f}% success rate)"
        )
    
    def show_statistics(self, options):
        """Show detailed proxy statistics."""
        from django.db.models import Count, Avg, Sum
        
        # Overall statistics
        total_stats = EnhancedProxyModel.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=models.Q(status='active')),
            avg_success=Avg('success_rate'),
            total_requests=Sum('total_requests'),
            total_cost=Sum('total_cost')
        )
        
        self.stdout.write(self.style.SUCCESS("\nOVERALL STATISTICS:"))
        self.stdout.write(f"Total Proxies: {total_stats['total']}")
        self.stdout.write(f"Active Proxies: {total_stats['active']}")
        self.stdout.write(f"Average Success Rate: {total_stats['avg_success']:.1f}%")
        self.stdout.write(f"Total Requests: {total_stats['total_requests']:,}")
        self.stdout.write(f"Total Cost: ${total_stats['total_cost']:.2f}")
        
        # Statistics by tier
        self.stdout.write(self.style.SUCCESS("\nSTATISTICS BY TIER:"))
        
        for tier in ['premium', 'standard', 'free']:
            tier_stats = EnhancedProxyModel.objects.filter(
                tier=tier
            ).aggregate(
                count=Count('id'),
                active=Count('id', filter=models.Q(status='active')),
                avg_success=Avg('success_rate'),
                avg_response=Avg('response_time'),
                total_requests=Sum('total_requests'),
                total_cost=Sum('total_cost')
            )
            
            if tier_stats['count'] > 0:
                self.stdout.write(f"\n{tier.upper()}:")
                self.stdout.write(f"  Count: {tier_stats['count']}")
                self.stdout.write(f"  Active: {tier_stats['active']}")
                self.stdout.write(f"  Avg Success: {tier_stats['avg_success']:.1f}%")
                self.stdout.write(
                    f"  Avg Response: {tier_stats['avg_response']:.2f}s"
                    if tier_stats['avg_response'] else "  Avg Response: N/A"
                )
                self.stdout.write(f"  Total Requests: {tier_stats['total_requests']:,}")
                
                if tier != 'free':
                    self.stdout.write(f"  Total Cost: ${tier_stats['total_cost']:.2f}")
                    if tier_stats['total_requests'] > 0:
                        avg_cost = tier_stats['total_cost'] / tier_stats['total_requests']
                        self.stdout.write(f"  Avg Cost/Request: ${avg_cost:.4f}")
    
    def show_costs(self, options):
        """Show detailed cost analysis for paid proxies."""
        manager = TieredProxyManager()
        cost_report = manager.get_cost_report()
        
        self.stdout.write(self.style.SUCCESS("\nPROXY COST ANALYSIS:"))
        
        total_cost = 0
        for tier, stats in cost_report.items():
            if stats['total_cost'] > 0:
                self.stdout.write(f"\n{tier.upper()} TIER:")
                self.stdout.write(f"  Total Cost: ${stats['total_cost']:.2f}")
                self.stdout.write(f"  Total Requests: {stats['total_requests']:,}")
                self.stdout.write(f"  Total Data: {stats['total_gb']:.2f} GB")
                self.stdout.write(f"  Avg Cost/Request: ${stats['avg_cost_per_request']:.4f}")
                self.stdout.write(f"  Active Proxies: {stats['proxy_count']}")
                
                total_cost += stats['total_cost']
        
        self.stdout.write(
            self.style.SUCCESS(f"\nTOTAL PROXY COSTS: ${total_cost:.2f}")
        )
        
        # Cost projections
        daily_avg = total_cost / 30  # Assuming 30 days of data
        self.stdout.write(f"\nProjected Daily Cost: ${daily_avg:.2f}")
        self.stdout.write(f"Projected Monthly Cost: ${daily_avg * 30:.2f}")
        
        # Alert if exceeding threshold
        threshold = getattr(settings, 'PROXY_COST_ALERT_THRESHOLD', 100)
        if daily_avg > threshold:
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Daily cost (${daily_avg:.2f}) exceeds "
                    f"alert threshold (${threshold:.2f})"
                )
            )
    
    def configure_providers(self, options):
        """Show current provider configuration."""
        proxy_settings = getattr(settings, 'PROXY_PROVIDERS', {})
        
        if not proxy_settings:
            self.stdout.write(
                self.style.WARNING("No proxy providers configured in settings")
            )
            return
        
        self.stdout.write(self.style.SUCCESS("\nCONFIGURED PROVIDERS:"))
        
        for provider, config in proxy_settings.items():
            self.stdout.write(f"\n{provider}:")
            self.stdout.write(f"  Tier: {config.get('tier', 'standard')}")
            self.stdout.write(f"  Cost/GB: ${config.get('cost_per_gb', 0)}")
            self.stdout.write(
                f"  API Key: {'✓ Set' if config.get('api_key') else '✗ Not set'}"
            )
            self.stdout.write(
                f"  Credentials: "
                f"{'✓ Set' if config.get('username') and config.get('password') else '✗ Not set'}"
            )
    
    def balance_proxy_usage(self, options):
        """Balance proxy usage to optimize costs."""
        # Reset proxies with low success rates
        low_performers = EnhancedProxyModel.objects.filter(
            success_rate__lt=50,
            total_requests__gt=10
        ).update(status='inactive')
        
        self.stdout.write(f"Deactivated {low_performers} low-performing proxies")
        
        # Reset exhausted paid proxies if they have daily limits
        exhausted = EnhancedProxyModel.objects.filter(
            status='exhausted',
            daily_request_limit__isnull=False
        ).update(
            status='active',
            daily_requests_used=0
        )
        
        self.stdout.write(f"Reset {exhausted} exhausted proxies with daily limits")
        
        # Promote high-performing free proxies
        good_free = EnhancedProxyModel.objects.filter(
            tier='free',
            success_rate__gte=90,
            total_requests__gte=50
        ).count()
        
        self.stdout.write(
            f"Found {good_free} high-performing free proxies "
            "(90%+ success rate with 50+ requests)"
        )
    
    def _test_single_proxy(self, proxy: EnhancedProxyModel) -> bool:
        """Test a single proxy."""
        import requests
        import time
        
        proxy_url = proxy.get_proxy_url()
        
        try:
            start_time = time.time()
            response = requests.get(
                'http://httpbin.org/ip',
                proxies={'http': proxy_url, 'https': proxy_url},
                timeout=10
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                # Update proxy stats
                proxy.last_checked = timezone.now()
                proxy.response_time = response_time
                proxy.save()
                return True
                
        except Exception:
            pass
        
        return False
    
    def _print_proxy_table(self, proxies):
        """Print proxies in table format."""
        from tabulate import tabulate
        
        headers = ['Type', 'Proxy', 'Success', 'Response', 'Requests', 'Cost']
        rows = []
        
        for proxy in proxies:
            cost_str = f"${proxy.cost_per_request:.4f}" if proxy.is_paid() else "Free"
            
            rows.append([
                proxy.tier.upper()[:4],
                f"{proxy.ip_address}:{proxy.port}",
                f"{proxy.success_rate:.1f}%",
                f"{proxy.response_time:.2f}s" if proxy.response_time else "N/A",
                f"{proxy.total_requests:,}",
                cost_str
            ])
        
        self.stdout.write(tabulate(rows, headers=headers, tablefmt='simple'))
    
    def _print_tier_summary(self, tier_name: str, proxies):
        """Print summary for a tier."""
        active = len([p for p in proxies if p.status == 'active'])
        total_requests = sum(p.total_requests for p in proxies)
        avg_success = sum(p.success_rate for p in proxies) / len(proxies) if proxies else 0
        
        self.stdout.write(f"  Active: {active}/{len(proxies)}")
        self.stdout.write(f"  Total Requests: {total_requests:,}")
        self.stdout.write(f"  Average Success Rate: {avg_success:.1f}%")
        
        if tier_name != 'free':
            total_cost = sum(p.total_cost for p in proxies)
            self.stdout.write(f"  Total Cost: ${total_cost:.2f}")


# Example usage commands:
"""
# Update free proxies
python manage.py manage_tiered_proxies update-free

# Add paid proxies from file
python manage.py manage_tiered_proxies add-paid --provider bright_data --file paid_proxies.txt

# List all active proxies
python manage.py manage_tiered_proxies list --format table

# Show cost analysis
python manage.py manage_tiered_proxies costs

# Test random proxies
python manage.py manage_tiered_proxies test --test-count 20

# Balance proxy usage
python manage.py manage_tiered_proxies balance
"""