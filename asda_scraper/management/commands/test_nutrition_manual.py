# Create this as: asda_scraper/management/commands/test_nutrition_manual.py

from django.core.management.base import BaseCommand
from asda_scraper.models import AsdaProduct
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

class Command(BaseCommand):
    help = 'Manually test nutrition extraction on a product'
    
    def handle(self, *args, **options):
        # Get a product with URL
        product = AsdaProduct.objects.filter(
            product_url__isnull=False
        ).exclude(product_url='').first()
        
        if not product:
            self.stdout.write(self.style.ERROR("No products with URLs found"))
            return
        
        self.stdout.write(f"Testing product: {product.name}")
        self.stdout.write(f"URL: {product.product_url}")
        
        # Setup Chrome
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            # Make sure URL is complete
            url = product.product_url
            if not url.startswith('http'):
                url = f"https://groceries.asda.com{url}"
            
            self.stdout.write(f"\nNavigating to: {url}")
            driver.get(url)
            time.sleep(5)  # Wait for page to load
            
            # Look for any nutrition-related elements
            self.stdout.write("\n=== Searching for Nutrition Elements ===")
            
            # Get all text on page to search for nutrition keywords
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Check if nutrition keywords exist
            nutrition_keywords = ['nutrition', 'energy', 'fat', 'protein', 'carbohydrate', 'kcal', 'salt']
            found_keywords = [kw for kw in nutrition_keywords if kw.lower() in page_text.lower()]
            self.stdout.write(f"Found nutrition keywords: {found_keywords}")
            
            # Try various selectors
            selectors = [
                "table",
                "[class*='nutrition']",
                "[id*='nutrition']",
                "[data-testid*='nutrition']",
                "[class*='nutritional']",
                "div.pdp__nutritional-information",
                "[aria-label*='nutrition']",
                "section h2",
                "section h3"
            ]
            
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    self.stdout.write(f"\nFound {len(elements)} elements with selector: {selector}")
                    for i, elem in enumerate(elements[:3]):
                        text = elem.text.strip()
                        if text and any(kw in text.lower() for kw in ['nutrition', 'energy', 'fat', 'protein']):
                            self.stdout.write(f"  Element {i+1}: {text[:200]}...")
                            
                            # If it's a table, show structure
                            if elem.tag_name == 'table':
                                rows = elem.find_elements(By.TAG_NAME, "tr")
                                self.stdout.write(f"  Table has {len(rows)} rows")
                                for row in rows[:5]:
                                    cells = row.find_elements(By.TAG_NAME, "td")
                                    if cells:
                                        row_text = " | ".join([cell.text.strip() for cell in cells])
                                        self.stdout.write(f"    Row: {row_text}")
            
            # Interactive inspection
            self.stdout.write("\n" + "="*50)
            self.stdout.write("Browser is open. Inspect the page manually.")
            self.stdout.write("Look for nutritional information section.")
            self.stdout.write("="*50)
            
            input("\nPress Enter to close browser...")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback
            traceback.print_exc()
        finally:
            driver.quit()