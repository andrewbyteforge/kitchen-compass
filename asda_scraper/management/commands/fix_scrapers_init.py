"""
Simple command to fix the scrapers __init__.py file.

File: asda_scraper/management/commands/fix_scrapers_init.py
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Fix scrapers __init__.py to use stealth approach'
    
    def handle(self, *args, **options):
        """Fix the scrapers init file."""
        try:
            # Path to the __init__.py file
            init_file_path = os.path.join(
                settings.BASE_DIR, 
                'asda_scraper', 
                'scrapers', 
                '__init__.py'
            )
            
            self.stdout.write("Fixing scrapers __init__.py for stealth support...")
            
            # New content for __init__.py
            new_content = '''"""
ASDA Scrapers Package with Stealth Anti-Bot Detection
"""

# Import stealth components
from .stealth_webdriver_manager import StealthWebDriverManager
from .selenium_scraper_stealth import StealthSeleniumAsdaScraper
from .enhanced_popup_handler import EnhancedPopupHandler

# Import other components
from .models import ScrapingResult, ProductData
from .exceptions import ScraperException, DriverSetupException

def create_selenium_scraper(crawl_session, headless=False):
    """Create stealth scraper for dashboard."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Creating stealth scraper for session {crawl_session.pk}")
    
    # Use visible mode for better stealth
    if headless and not crawl_session.crawl_settings.get('force_headless', False):
        logger.warning("Using visible mode for better stealth")
        headless = False
    
    return StealthSeleniumAsdaScraper(crawl_session, headless=headless)

# Backwards compatibility
SeleniumAsdaScraper = StealthSeleniumAsdaScraper

__all__ = [
    'StealthWebDriverManager',
    'StealthSeleniumAsdaScraper', 
    'EnhancedPopupHandler',
    'ScrapingResult',
    'ProductData', 
    'ScraperException',
    'DriverSetupException',
    'create_selenium_scraper',
    'SeleniumAsdaScraper'
]
'''
            
            # Create backup
            if os.path.exists(init_file_path):
                backup_path = init_file_path + '.backup'
                with open(init_file_path, 'r', encoding='utf-8') as f:
                    backup_content = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(backup_content)
                self.stdout.write(f"Backup created: {backup_path}")
            
            # Write new content
            with open(init_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.stdout.write(self.style.SUCCESS(f"Successfully updated: {init_file_path}"))
            self.stdout.write("")
            self.stdout.write("NEXT STEPS:")
            self.stdout.write("1. Restart Django server: python manage.py runserver")
            self.stdout.write("2. Test dashboard - should now use stealth approach")
            self.stdout.write("3. Try a NUTRITION crawl with 5 products")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))