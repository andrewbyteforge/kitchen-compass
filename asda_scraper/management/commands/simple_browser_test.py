"""
Simple browser test to check basic functionality.

File: asda_scraper/management/commands/simple_browser_test.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError

from asda_scraper.scrapers.webdriver_manager import WebDriverManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Simple browser test to check if browser setup is working.
    """
    
    help = 'Simple test to check browser functionality'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--wait-time',
            type=int,
            default=10,
            help='Seconds to keep browser open for observation (default: 10)'
        )
    
    def handle(self, *args, **options):
        """Execute the simple browser test."""
        try:
            self.stdout.write("="*50)
            self.stdout.write(self.style.SUCCESS("🧪 SIMPLE BROWSER TEST"))
            self.stdout.write("="*50)
            
            wait_time = options['wait_time']
            
            # Test 1: Basic browser setup
            self.stdout.write("🔧 Testing browser setup...")
            driver_manager = WebDriverManager(headless=False)
            driver = driver_manager.setup_driver()
            
            try:
                # Position browser
                driver.set_window_position(100, 100)
                driver.set_window_size(1200, 800)
                driver.execute_script("document.title = '🧪 Browser Test - KitchenCompass';")
                
                self.stdout.write("✅ Browser created successfully")
                
                # Test 2: Navigate to Google
                self.stdout.write("🌐 Testing navigation to Google...")
                driver.get("https://www.google.com")
                time.sleep(2)
                
                google_title = driver.title
                google_url = driver.current_url
                
                self.stdout.write(f"   Title: {google_title}")
                self.stdout.write(f"   URL: {google_url}")
                
                if "google" in google_url.lower():
                    self.stdout.write("✅ Google navigation successful")
                else:
                    self.stdout.write("❌ Google navigation failed - may indicate network issues")
                
                # Test 3: Navigate to ASDA
                self.stdout.write("🛒 Testing navigation to ASDA...")
                driver.get("https://groceries.asda.com/")
                time.sleep(5)  # Give more time for ASDA to load
                
                asda_title = driver.title
                asda_url = driver.current_url
                
                self.stdout.write(f"   Title: {asda_title}")
                self.stdout.write(f"   URL: {asda_url}")
                
                # Check if we're actually on ASDA
                if "asda" in asda_url.lower():
                    self.stdout.write("✅ ASDA navigation successful")
                    
                    # Check page content
                    try:
                        body = driver.find_element("tag name", "body")
                        body_text = body.text.strip()
                        
                        if len(body_text) < 50:
                            self.stdout.write("⚠️  Page appears blank or minimal content")
                            self.stdout.write("   This could indicate:")
                            self.stdout.write("   • JavaScript not loading")
                            self.stdout.write("   • Privacy popups blocking content")
                            self.stdout.write("   • Geographic restrictions")
                            self.stdout.write("   • ASDA anti-bot measures")
                        else:
                            self.stdout.write(f"✅ Page content loaded ({len(body_text)} characters)")
                    except Exception as e:
                        self.stdout.write(f"❌ Error checking page content: {e}")
                        
                else:
                    self.stdout.write("❌ ASDA navigation failed")
                    self.stdout.write("   Possible causes:")
                    self.stdout.write("   • Geographic blocking (ASDA UK only)")
                    self.stdout.write("   • Network/proxy issues")
                    self.stdout.write("   • Site blocking automated requests")
                
                # Test 4: Check for common elements
                self.stdout.write("🔍 Checking for page elements...")
                
                test_selectors = [
                    ("body", "Page body"),
                    ("nav", "Navigation"),
                    ("[class*='asda']", "ASDA elements"),
                    ("button", "Buttons"),
                    ("a", "Links")
                ]
                
                for selector, description in test_selectors:
                    try:
                        elements = driver.find_elements("css selector", selector)
                        if elements:
                            self.stdout.write(f"   ✅ {description}: {len(elements)} found")
                        else:
                            self.stdout.write(f"   ❌ {description}: None found")
                    except:
                        self.stdout.write(f"   ❌ {description}: Error checking")
                
                # Test 5: Take screenshot (optional)
                try:
                    screenshot_path = "browser_test_screenshot.png"
                    driver.save_screenshot(screenshot_path)
                    self.stdout.write(f"📸 Screenshot saved: {screenshot_path}")
                except:
                    self.stdout.write("📸 Screenshot failed")
                
                # Wait for observation
                if wait_time > 0:
                    self.stdout.write(f"⏳ Keeping browser open for {wait_time}s...")
                    self.stdout.write("   👀 Check the browser window manually")
                    time.sleep(wait_time)
                
            finally:
                self.stdout.write("🧹 Closing browser...")
                driver.quit()
                
            # Summary
            self.stdout.write("\n" + "="*50)
            self.stdout.write("📊 TEST SUMMARY")
            self.stdout.write("="*50)
            self.stdout.write("If ASDA page is blank, try:")
            self.stdout.write("1. Check your internet connection")
            self.stdout.write("2. Try accessing ASDA manually in browser")
            self.stdout.write("3. Check if you're in a supported region (UK)")
            self.stdout.write("4. Look for privacy/cookie popups")
            self.stdout.write("5. Try with different user agent or browser settings")
                
        except Exception as e:
            logger.error(f"Simple browser test failed: {e}")
            raise CommandError(f"Test failed: {e}")