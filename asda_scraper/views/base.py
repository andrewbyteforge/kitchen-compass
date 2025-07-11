"""
Base views utilities and common functions.

File: asda_scraper/views/base.py
"""

import logging
from typing import Dict, Any
from django.contrib.auth.decorators import user_passes_test
from django.db import connection
from django.utils import timezone
from asda_scraper.models import AsdaProduct, AsdaCategory, CrawlSession

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """
    Check if user has admin privileges for ASDA scraper.
    
    Args:
        user: Django user object
        
    Returns:
        bool: True if user has admin access
    """
    ADMIN_EMAILS = [
        'acartwright39@hotmail.com',  # Your actual email
    ]
    return user.is_authenticated and (user.email in ADMIN_EMAILS or user.is_superuser)


def get_dashboard_statistics() -> Dict[str, Any]:
    """
    Get comprehensive dashboard statistics.

    Returns:
        Dict[str, Any]: Dictionary containing various statistics
    """
    try:
        return {
            'total_products': AsdaProduct.objects.count(),
            'total_categories': AsdaCategory.objects.count(),
            'active_categories': AsdaCategory.objects.filter(is_active=True).count(),
            'products_with_images': AsdaProduct.objects.exclude(image_url='').count(),
            'products_on_sale': AsdaProduct.objects.filter(was_price__isnull=False).count(),
            'recent_products': AsdaProduct.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'total_sessions': CrawlSession.objects.count(),
            'successful_sessions': CrawlSession.objects.filter(status='COMPLETED').count(),
            'failed_sessions': CrawlSession.objects.filter(status='FAILED').count(),
        }
    except Exception as e:
        logger.error(f"Error getting dashboard statistics: {e}")
        return {}


def check_system_health() -> Dict[str, Any]:
    """
    Check system health for scraper components.
    
    Returns:
        Dict[str, Any]: System health status
    """
    health = {
        'overall': 'healthy',
        'issues': [],
        'warnings': []
    }
    
    try:
        # Check if Chrome/ChromeDriver is available
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            
            driver = webdriver.Chrome(options=options)
            driver.quit()
            
        except Exception as e:
            health['issues'].append('Chrome WebDriver not available')
            health['overall'] = 'degraded'
        
        # Check for stuck sessions
        stuck_sessions = CrawlSession.objects.filter(
            status__in=['PENDING', 'RUNNING'],
            start_time__lt=timezone.now() - timezone.timedelta(hours=2)
        ).count()
        
        if stuck_sessions > 0:
            health['warnings'].append(f'{stuck_sessions} sessions appear to be stuck')
            if health['overall'] == 'healthy':
                health['overall'] = 'warning'
        
        # Check database connectivity
        try:
            AsdaCategory.objects.count()
        except Exception:
            health['issues'].append('Database connectivity issues')
            health['overall'] = 'critical'
        
    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        health['issues'].append('Health check failed')
        health['overall'] = 'unknown'
    
    return health


def parse_error_message(error_log: str) -> Dict[str, Any]:
    """
    Parse error log to extract useful information.
    
    Args:
        error_log: Raw error log string
        
    Returns:
        Dict[str, Any]: Parsed error information
    """
    try:
        # Try to extract structured error information
        if 'Error Code:' in error_log:
            lines = error_log.split('\n')
            error_info = {}
            
            for line in lines:
                if 'Error Code:' in line:
                    error_info['code'] = line.split('Error Code:')[1].strip()
                elif 'Context:' in line:
                    error_info['context'] = line.split('Context:')[1].strip()
            
            return error_info
        else:
            return {'message': error_log[:200]}  # Truncate long messages
    except Exception:
        return {'message': 'Error parsing error log'}