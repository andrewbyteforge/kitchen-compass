"""
Test popup handler specifically for ASDA privacy popups.

File: asda_scraper/management/commands/test_popup_handler.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError

from asda_scraper.scrapers.webdriver_manager import WebDriverManager
from asda_scraper.scrapers.enhanced_popup_handler import EnhancedPopupHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Test the enhanced popup handler on ASDA site.
    """
    
    help = 'Test popup handler on ASDA website to debug privacy popup issues'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--url',
            type=str,
            default='https://groceries.asda.com/',
            help='URL to test popup handling (default: ASDA homepage)'
        )
        parser.add_argument(
            '--attempts',
            type=int,
            default=3,
            help='Maximum popup handling attempts (default: 3)'
        )
        parser.add_argument(
            '--timeout',
            type=float,
            default=15.0,
            help='Timeout for popup handling in seconds (default: 15.0)'
        )
        parser.add_argument(
            '--wait-after',
            type=int,
            default=10,
            help='Seconds to wait after popup handling for observation (default: 10)'
        )
    
    def handle(self, *args, **options):
        """Execute the popup handler test."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.SUCCESS("🚫 POPUP HANDLER TEST"))
            self.stdout.write("="*60)
            
            url = options['url']
            max_attempts = options['attempts']
            timeout = options['timeout']
            wait_time = options['wait_after']
            
            self.stdout.write(f"🎯 Target URL: {url}")
            self.stdout.write(f"⚡ Max attempts: {max_attempts}")
            self.stdout.write(f"⏰ Timeout: {timeout}s")
            self.stdout.write("")
            
            # Setup browser
            self.stdout.write("🔧 Setting up browser...")
            driver_manager = WebDriverManager(headless=False)
            driver = driver_manager.setup_driver()
            
            try:
                # Position browser for visibility
                driver.set_window_position(100, 100)
                driver.set_window_size(1400, 900)
                driver.execute_script("document.title = '🚫 Popup Handler Test - KitchenCompass';")
                
                # Navigate to URL
                self.stdout.write(f"🌐 Navigating to: {url}")
                driver.get(url)
                
                # Wait a moment for page to load
                time.sleep(3)
                
                # Initialize popup handler
                popup_handler = EnhancedPopupHandler(driver)
                
                # Test popup handling
                self.stdout.write("🚫 Testing popup handling...")
                start_time = time.time()
                
                results = popup_handler.handle_all_popups(
                    max_attempts=max_attempts,
                    timeout=timeout
                )
                
                # Display results
                self._display_popup_results(results)
                
                # Show current page state
                self._show_page_state(driver)
                
                # Wait for observation
                if wait_time > 0:
                    self.stdout.write(f"⏳ Waiting {wait_time}s for observation...")
                    self.stdout.write("   👀 Check the browser window for any remaining popups")
                    time.sleep(wait_time)
                
                # Final popup check
                self.stdout.write("🔍 Final popup check...")
                final_results = popup_handler.handle_all_popups(
                    max_attempts=1,
                    timeout=5.0
                )
                
                if final_results['popups_handled'] > 0:
                    self.stdout.write(self.style.WARNING(f"⚠️  Found {final_results['popups_handled']} additional popups"))
                else:
                    self.stdout.write(self.style.SUCCESS("✅ No additional popups found"))
                
                # Show handler stats
                stats = popup_handler.get_stats()
                self.stdout.write(f"\n📊 Handler stats: {stats}")
                
            finally:
                self.stdout.write("🧹 Closing browser...")
                driver.quit()
                
        except Exception as e:
            logger.error(f"Popup handler test failed: {e}")
            raise CommandError(f"Test failed: {e}")
    
    def _display_popup_results(self, results):
        """Display popup handling results."""
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.HTTP_INFO("📊 POPUP HANDLING RESULTS"))
        self.stdout.write("="*50)
        
        # Basic stats
        self.stdout.write(f"Popups handled: {results['popups_handled']}")
        self.stdout.write(f"Attempts made: {results['attempts']}")
        self.stdout.write(f"Time taken: {results['time_taken']:.2f} seconds")
        self.stdout.write(f"Success: {results['success']}")
        
        # Popup types
        if results['popup_types']:
            self.stdout.write(f"Popup types handled: {', '.join(results['popup_types'])}")
        
        # Status message
        if results['popups_handled'] > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ Successfully handled {results['popups_handled']} popup(s)"))
        else:
            if results['success']:
                self.stdout.write(self.style.WARNING("⚠️  No popups found to handle"))
            else:
                self.stdout.write(self.style.ERROR("❌ Popup handling failed"))
    
    def _show_page_state(self, driver):
        """Show current page state information."""
        try:
            self.stdout.write("\n" + "="*50)
            self.stdout.write(self.style.HTTP_INFO("📄 CURRENT PAGE STATE"))
            self.stdout.write("="*50)
            
            # Page title and URL
            self.stdout.write(f"Title: {driver.title}")
            self.stdout.write(f"URL: {driver.current_url}")
            
            # Check for common popup indicators
            popup_selectors = [
                "#onetrust-banner-sdk",
                "[class*='cookie']",
                "[class*='privacy']",
                "[class*='consent']",
                "[role='dialog']",
                "[aria-modal='true']",
                ".modal",
                ".popup"
            ]
            
            visible_popups = []
            for selector in popup_selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    for element in elements:
                        if element.is_displayed():
                            visible_popups.append(selector)
                            break
                except:
                    continue
            
            if visible_popups:
                self.stdout.write(self.style.WARNING("⚠️  Visible popup selectors found:"))
                for selector in visible_popups:
                    self.stdout.write(f"   • {selector}")
            else:
                self.stdout.write(self.style.SUCCESS("✅ No visible popups detected"))
            
            # Check body scroll
            body_overflow = driver.execute_script("return document.body.style.overflow;")
            if body_overflow in ['hidden', 'auto']:
                self.stdout.write(f"📋 Body overflow: {body_overflow}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error checking page state: {e}"))