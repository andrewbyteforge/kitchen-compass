"""
Management command to update dashboard to use stealth approach.

File: asda_scraper/management/commands/update_dashboard_stealth.py
"""

import logging
import os
from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Update the dashboard crawler to use stealth approach.
    """
    
    help = 'Update dashboard crawler to use stealth anti-bot detection'
    
    def handle(self, *args, **options):
        """Execute the update."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("UPDATING DASHBOARD TO USE STEALTH"))
            self.stdout.write("="*60)
            
            # Check if files exist
            scrapers_dir = os.path.join(settings.BASE_DIR, 'asda_scraper', 'scrapers')
            
            # Files we need to check/update
            files_to_check = [
                'stealth_webdriver_manager.py',
                'selenium_scraper_stealth.py',
                'enhanced_popup_handler.py'
            ]
            
            missing_files = []
            for file_name in files_to_check:
                file_path = os.path.join(scrapers_dir, file_name)
                if not os.path.exists(file_path):
                    missing_files.append(file_name)
                else:
                    self.stdout.write(f"Found: {file_name}")
            
            if missing_files:
                self.stdout.write(self.style.ERROR("Missing required stealth files:"))
                for file_name in missing_files:
                    self.stdout.write(f"   • {file_name}")
                self.stdout.write("")
                self.stdout.write("Please create these files first using the artifacts provided.")
                return
            
            # Update the scrapers __init__.py to use stealth by default
            init_file = os.path.join(scrapers_dir, '__init__.py')
            
            # Read current content
            if os.path.exists(init_file):
                with open(init_file, 'r') as f:
                    current_content = f.read()
            else:
                current_content = ""
            
            # Updated content that imports stealth scraper
            updated_content = '''"""
ASDA Scrapers Package with Stealth Anti-Bot Detection

File: asda_scraper/scrapers/__init__.py
"""

# Import stealth components
from .stealth_webdriver_manager import StealthWebDriverManager
from .selenium_scraper_stealth import StealthSeleniumAsdaScraper
from .enhanced_popup_handler import EnhancedPopupHandler

# Import other components
from .models import ScrapingResult, ProductData
from .exceptions import ScraperException, DriverSetupException

# Factory function for dashboard compatibility
def create_selenium_scraper(crawl_session, headless=False):
    """
    Create a stealth scraper instance for dashboard use.
    
    Args:
        crawl_session: CrawlSession instance
        headless: Whether to run in headless mode (default: False for better stealth)
        
    Returns:
        StealthSeleniumAsdaScraper: Configured stealth scraper
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Creating stealth scraper for dashboard session {crawl_session.pk}")
    
    # Force visible mode for better stealth unless explicitly requested
    if headless and not crawl_session.crawl_settings.get('force_headless', False):
        logger.warning("Using visible mode for better stealth performance")
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
    'SeleniumAsdaScraper'  # Alias for compatibility
]
'''
            
            # Write updated content
            with open(init_file, 'w') as f:
                f.write(updated_content)
            
            self.stdout.write(f"Updated: {init_file}")
            
            # Instructions
            self.stdout.write("")
            self.stdout.write("="*60)
            self.stdout.write("DASHBOARD UPDATE COMPLETE")
            self.stdout.write("="*60)
            
            self.stdout.write("The dashboard will now use stealth anti-bot detection!")
            self.stdout.write("")
            self.stdout.write("WHAT CHANGED:")
            self.stdout.write("   • Dashboard crawler now uses StealthWebDriverManager")
            self.stdout.write("   • Automatically handles ASDA bot detection")
            self.stdout.write("   • Uses enhanced popup handling")
            self.stdout.write("   • Runs in visible mode by default for better stealth")
            self.stdout.write("")
            self.stdout.write("NEXT STEPS:")
            self.stdout.write("   1. Restart your Django development server")
            self.stdout.write("   2. Go to the ASDA Scraper dashboard")
            self.stdout.write("   3. Start a nutrition crawl")
            self.stdout.write("   4. You should see the browser window open (not blank!)")
            self.stdout.write("")
            self.stdout.write("DASHBOARD SETTINGS RECOMMENDATIONS:")
            self.stdout.write("   • Crawl Type: NUTRITION (to test nutrition extraction)")
            self.stdout.write("   • Max Products: 5-10 (for testing)")
            self.stdout.write("   • Delay: 6-8 seconds (to avoid rate limiting)")
            self.stdout.write("   • Headless: NO (visible mode works better)")
            
        except Exception as e:
            logger.error(f"Update failed: {e}")
            self.stdout.write(self.style.ERROR(f"❌ Update failed: {e}"))