# Create this as: asda_scraper/management/commands/test_extraction_direct.py

from django.core.management.base import BaseCommand
from asda_scraper.models import AsdaProduct, CrawlSession
from asda_scraper.selenium_scraper import create_selenium_scraper
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Test nutrition extraction method directly'
    
    def handle(self, *args, **options):
        # Get a product
        product = AsdaProduct.objects.filter(
            product_url__contains='/product/'
        ).first()
        
        if not product:
            self.stdout.write(self.style.ERROR("No products found"))
            return
            
        self.stdout.write(f"Testing with: {product.name}")
        self.stdout.write(f"URL: {product.product_url}")
        
        # Create a test session
        user, _ = User.objects.get_or_create(
            username='test_user',
            defaults={'email': 'test@example.com'}
        )
        
        session = CrawlSession.objects.create(
            user=user,
            status='PENDING',
            crawl_type='NUTRITION',
            crawl_settings={'test_mode': True}
        )
        
        # Create scraper
        self.stdout.write("\nCreating scraper...")
        scraper = create_selenium_scraper(session, headless=False)
        
        try:
            # Get the product extractor
            if hasattr(scraper, 'product_extractor'):
                extractor = scraper.product_extractor
                self.stdout.write("Found product_extractor")
                
                # Check if method exists
                if hasattr(extractor, '_extract_nutritional_info_from_product_page'):
                    self.stdout.write("Method exists! Calling it...")
                    
                    # Call the method
                    nutrition_data = extractor._extract_nutritional_info_from_product_page(product.product_url)
                    
                    if nutrition_data:
                        self.stdout.write(self.style.SUCCESS(f"\nExtracted nutrition data:"))
                        for key, value in nutrition_data.items():
                            self.stdout.write(f"  {key}: {value}")
                            
                        # Save to product
                        product.nutritional_info = nutrition_data
                        product.save()
                        self.stdout.write(self.style.SUCCESS(f"\nSaved to product!"))
                    else:
                        self.stdout.write(self.style.ERROR("\nNo nutrition data returned"))
                else:
                    self.stdout.write(self.style.ERROR("Method _extract_nutritional_info_from_product_page not found!"))
            else:
                self.stdout.write(self.style.ERROR("No product_extractor found on scraper"))
                
            # Also check if it exists on scraper itself
            if hasattr(scraper, '_extract_nutritional_info_from_product_page'):
                self.stdout.write("\nMethod exists on scraper itself! Trying that...")
                nutrition_data = scraper._extract_nutritional_info_from_product_page(product.product_url)
                if nutrition_data:
                    self.stdout.write(self.style.SUCCESS(f"Got data from scraper method: {nutrition_data}"))
            
            input("\nPress Enter to close browser...")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback
            traceback.print_exc()
        finally:
            scraper.cleanup()
            session.status = 'COMPLETED'
            session.save()