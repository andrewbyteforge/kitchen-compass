"""
Django management command to debug ASDA page content and selectors.

Create this file as: asda_scraper/management/commands/debug_asda_page.py
"""

import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from asda_scraper.models import CrawlSession, AsdaCategory
from asda_scraper.scrapers.webdriver_manager import WebDriverManager
from asda_scraper.scrapers.category_manager import CategoryManager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to debug ASDA page content and identify correct selectors.
    """
    
    help = 'Debug ASDA page content to identify correct product selectors'
    
    def add_arguments(self, parser):
        """
        Add command arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--category',
            type=str,
            default='Bakery',
            help='Category name to debug (default: Bakery)',
        )
        parser.add_argument(
            '--headless',
            action='store_true',
            default=False,
            help='Run browser in headless mode',
        )
        parser.add_argument(
            '--save-html',
            action='store_true',
            help='Save page HTML to file for inspection',
        )
    
    def handle(self, *args, **options):
        """
        Execute the command.
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        try:
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS('ASDA PAGE CONTENT DEBUG TOOL'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
            category_name = options['category']
            headless = options['headless']
            save_html = options['save_html']
            
            # Find the category
            category = self._find_category(category_name)
            if not category:
                raise CommandError(f"Category '{category_name}' not found")
            
            # Setup WebDriver
            driver_manager = WebDriverManager(headless=headless)
            driver = None
            
            try:
                driver = driver_manager.setup_driver()
                self.stdout.write(self.style.SUCCESS("✓ WebDriver setup successful"))
                
                # Create temporary session for debugging
                user = User.objects.filter(is_superuser=True).first()
                session = CrawlSession.objects.create(
                    user=user,
                    status='RUNNING',
                    crawl_settings={'debug_mode': True}
                )
                
                # Debug the page
                self._debug_category_page(driver, session, category, save_html)
                
                # Cleanup session
                session.status = 'COMPLETED'
                session.save()
                
            finally:
                if driver:
                    driver.quit()
                    
        except Exception as e:
            logger.error(f"Debug command failed: {e}")
            raise CommandError(f"Debug failed: {e}")
    
    def _find_category(self, category_name: str):
        """
        Find category by name.
        
        Args:
            category_name: Name of category to find
            
        Returns:
            AsdaCategory or None
        """
        try:
            # Try exact match first
            category = AsdaCategory.objects.filter(
                name__iexact=category_name,
                is_active=True
            ).first()
            
            if not category:
                # Try partial match
                category = AsdaCategory.objects.filter(
                    name__icontains=category_name,
                    is_active=True
                ).first()
            
            if category:
                self.stdout.write(f"Found category: {category.name} ({category.url_code})")
            else:
                self.stdout.write(self.style.ERROR(f"Category '{category_name}' not found"))
                self.stdout.write("Available categories:")
                for cat in AsdaCategory.objects.filter(is_active=True)[:10]:
                    self.stdout.write(f"  - {cat.name}")
            
            return category
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error finding category: {e}"))
            return None
    
    def _debug_category_page(self, driver, session, category, save_html):
        """
        Debug the category page content.
        
        Args:
            driver: WebDriver instance
            session: CrawlSession instance
            category: AsdaCategory to debug
            save_html: Whether to save HTML to file
        """
        try:
            # Get category URL
            category_manager = CategoryManager(driver, session)
            category_url = category_manager.get_category_url(category)
            
            if not category_url:
                raise CommandError(f"Could not get URL for category {category.name}")
            
            self.stdout.write(f"\nTesting URL: {category_url}")
            
            # Navigate to page
            self.stdout.write("Navigating to category page...")
            driver.get(category_url)
            time.sleep(5)  # Wait for page to load
            
            # Handle popups
            self.stdout.write("Handling popups...")
            from asda_scraper.scrapers.popup_handler import PopupHandler
            popup_handler = PopupHandler(driver)
            popup_handler.handle_popups()
            time.sleep(3)
            
            # Get page info
            self._analyze_page_content(driver, category, save_html)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error debugging page: {e}"))
    
    def _analyze_page_content(self, driver, category, save_html):
        """
        Analyze the page content and test selectors.
        
        Args:
            driver: WebDriver instance
            category: AsdaCategory being debugged
            save_html: Whether to save HTML to file
        """
        try:
            # Basic page info
            self.stdout.write(f"\nPAGE ANALYSIS:")
            self.stdout.write(f"  Title: {driver.title}")
            self.stdout.write(f"  URL: {driver.current_url}")
            
            # Test product selectors
            self.stdout.write(f"\nTESTING PRODUCT SELECTORS:")
            
            selectors_to_test = [
                'div.co-product',
                'div[class*="co-product"]',
                'div[class*="product-tile"]',
                'div[class*="product-item"]',
                'article[class*="product"]',
                '[data-testid*="product"]',
                'div.product-card',
                'li.product-list-item',
                '[data-auto-id*="product"]',
                '.pdp-product-card',
                '.product-container',
                '.item-tile',
                '.co-item',
                '[data-testid="product-tile"]'
            ]
            
            found_products = False
            best_selector = None
            max_count = 0
            
            for selector in selectors_to_test:
                try:
                    elements = driver.find_elements("css selector", selector)
                    count = len(elements)
                    
                    if count > 0:
                        self.stdout.write(f"  ✓ {selector}: {count} elements")
                        found_products = True
                        
                        if count > max_count:
                            max_count = count
                            best_selector = selector
                        
                        # Show sample element details for first few
                        if count > 0:
                            sample_element = elements[0]
                            try:
                                sample_text = sample_element.text[:100].replace('\n', ' ')
                                sample_class = sample_element.get_attribute('class')
                                self.stdout.write(f"    Sample: {sample_text}...")
                                self.stdout.write(f"    Classes: {sample_class}")
                                
                                # Check for price and title elements within
                                try:
                                    price_elements = sample_element.find_elements("css selector", "strong, .price, [class*='price']")
                                    if price_elements:
                                        price_text = price_elements[0].text
                                        self.stdout.write(f"    Price found: {price_text}")
                                except:
                                    pass
                                    
                            except:
                                pass
                    else:
                        self.stdout.write(f"  ✗ {selector}: 0 elements")
                        
                except Exception as e:
                    self.stdout.write(f"  ✗ {selector}: Error - {e}")
            
            if found_products:
                self.stdout.write(f"\n🎯 BEST SELECTOR: {best_selector} ({max_count} products)")
            else:
                self.stdout.write(self.style.WARNING("\n⚠ No products found with any selector!"))
                
                # Try to find any potentially relevant elements
                self.stdout.write("\nLOOKING FOR ANY PRODUCT-LIKE ELEMENTS:")
                try:
                    # Check for common product indicators
                    all_divs = driver.find_elements("css selector", "div")
                    product_divs = []
                    
                    for div in all_divs[:50]:  # Check first 50 divs
                        try:
                            class_attr = div.get_attribute('class') or ''
                            if any(keyword in class_attr.lower() for keyword in ['product', 'item', 'tile', 'card']):
                                product_divs.append(div)
                        except:
                            continue
                    
                    if product_divs:
                        self.stdout.write(f"  Found {len(product_divs)} divs with product-like classes")
                        for i, div in enumerate(product_divs[:3]):
                            try:
                                class_name = div.get_attribute('class')
                                text_sample = div.text[:100].replace('\n', ' ')
                                self.stdout.write(f"    {i+1}. Class: {class_name}")
                                self.stdout.write(f"       Text: {text_sample}...")
                            except:
                                pass
                    else:
                        self.stdout.write("  No product-like elements found")
                        
                except Exception as e:
                    self.stdout.write(f"  Error searching for elements: {e}")
            
            # Check for loading indicators
            self.stdout.write(f"\nCHECKING PAGE STATUS:")
            loading_selectors = [
                '.loading',
                '.spinner',
                '[data-testid="loading"]',
                '.skeleton',
                '.placeholder'
            ]
            
            for selector in loading_selectors:
                try:
                    elements = driver.find_elements("css selector", selector)
                    if elements:
                        self.stdout.write(f"  ⚠ Loading indicator found: {selector} ({len(elements)} elements)")
                except:
                    pass
            
            # Save HTML if requested
            if save_html:
                self._save_page_html(driver, category)
            
            # Test basic page elements
            self.stdout.write(f"\nPAGE STRUCTURE:")
            try:
                h1_elements = driver.find_elements("css selector", "h1")
                if h1_elements:
                    self.stdout.write(f"  H1: {h1_elements[0].text}")
                
                # Look for any error messages
                error_selectors = ['.error', '.not-found', '.404', '[class*="error"]']
                for error_sel in error_selectors:
                    try:
                        error_elements = driver.find_elements("css selector", error_sel)
                        if error_elements:
                            self.stdout.write(f"  ⚠ Error element found: {error_sel}")
                    except:
                        pass
                
            except Exception as e:
                self.stdout.write(f"  Error checking page structure: {e}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error analyzing page content: {e}"))
    
    def _save_page_html(self, driver, category):
        """
        Save page HTML to file for manual inspection.
        
        Args:
            driver: WebDriver instance
            category: AsdaCategory being debugged
        """
        try:
            import os
            from datetime import datetime
            
            # Create debug directory
            debug_dir = "debug_html"
            os.makedirs(debug_dir, exist_ok=True)
            
            # Save HTML
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{debug_dir}/asda_{category.name}_{timestamp}.html"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            
            self.stdout.write(f"  💾 HTML saved to: {filename}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error saving HTML: {e}"))