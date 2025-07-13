"""
Quick patch to add stealth to existing selenium_scraper.py

File: asda_scraper/management/commands/patch_existing_scraper.py
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Patch existing selenium_scraper.py to use stealth approach'
    
    def handle(self, *args, **options):
        """Patch the existing scraper."""
        try:
            # First restore the original __init__.py to avoid import errors
            init_file_path = os.path.join(
                settings.BASE_DIR, 
                'asda_scraper', 
                'scrapers', 
                '__init__.py'
            )
            
            backup_path = init_file_path + '.backup'
            
            if os.path.exists(backup_path):
                self.stdout.write("Restoring original __init__.py...")
                with open(backup_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                with open(init_file_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                self.stdout.write("Original __init__.py restored")
            
            # Now patch the existing selenium_scraper.py to use stealth approach
            scraper_file_path = os.path.join(
                settings.BASE_DIR,
                'asda_scraper',
                'scrapers', 
                'selenium_scraper.py'
            )
            
            if not os.path.exists(scraper_file_path):
                self.stdout.write(self.style.ERROR(f"File not found: {scraper_file_path}"))
                return
            
            # Read existing content
            with open(scraper_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create backup
            backup_scraper_path = scraper_file_path + '.backup'
            with open(backup_scraper_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.stdout.write(f"Backup created: {backup_scraper_path}")
            
            # Add stealth imports and modify WebDriverManager usage
            stealth_patch = '''
# Stealth import patch
try:
    from .stealth_webdriver_manager import StealthWebDriverManager
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False
'''
            
            # Insert stealth import after existing imports
            if 'from .webdriver_manager import WebDriverManager' in content:
                content = content.replace(
                    'from .webdriver_manager import WebDriverManager',
                    'from .webdriver_manager import WebDriverManager' + stealth_patch
                )
            
            # Replace WebDriverManager initialization with stealth version
            old_driver_setup = '''self.driver_manager = WebDriverManager(headless=headless)
            self.driver = self.driver_manager.setup_driver()'''
            
            new_driver_setup = '''if STEALTH_AVAILABLE:
                logger.info("Using stealth WebDriver for anti-bot detection")
                self.stealth_manager = StealthWebDriverManager(headless=headless)
                self.driver = self.stealth_manager.setup_stealth_driver()
            else:
                logger.warning("Stealth mode not available, using regular WebDriver")
                self.driver_manager = WebDriverManager(headless=headless)
                self.driver = self.driver_manager.setup_driver()'''
            
            content = content.replace(old_driver_setup, new_driver_setup)
            
            # Add stealth navigation method
            stealth_navigation_patch = '''
    def _navigate_with_stealth(self, url):
        """Navigate to URL with stealth if available."""
        if hasattr(self, 'stealth_manager') and self.stealth_manager:
            return self.stealth_manager.navigate_like_human(self.driver, url)
        else:
            self.driver.get(url)
            return True
'''
            
            # Add the method before the cleanup method
            if 'def cleanup(self):' in content:
                content = content.replace(
                    'def cleanup(self):',
                    stealth_navigation_patch + '\n    def cleanup(self):'
                )
            
            # Write patched content
            with open(scraper_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.stdout.write(self.style.SUCCESS("Successfully patched selenium_scraper.py"))
            self.stdout.write("")
            self.stdout.write("WHAT WAS PATCHED:")
            self.stdout.write("• Added stealth WebDriver import (if available)")  
            self.stdout.write("• Modified driver setup to use stealth when possible")
            self.stdout.write("• Added stealth navigation method")
            self.stdout.write("• Falls back to regular WebDriver if stealth not available")
            self.stdout.write("")
            self.stdout.write("NEXT STEPS:")
            self.stdout.write("1. Restart Django server: python manage.py runserver")
            self.stdout.write("2. Test dashboard - should have better bot detection handling")
            self.stdout.write("3. If stealth files are available, it will use stealth mode")
            self.stdout.write("4. If not, it will use regular mode with warning")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            self.stdout.write("You can restore from backup if needed")