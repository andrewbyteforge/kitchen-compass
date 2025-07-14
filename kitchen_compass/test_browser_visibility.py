"""
Test script to verify browser window visibility.
Run this from your Django project root to test if the browser opens visibly.

Usage:
    python test_browser_visibility.py
"""

import sys
import os
import time
import logging

# Add Django project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitchen_compass.settings')
import django
django.setup()

from asda_scraper.scrapers.base_scraper import BaseScraper
from asda_scraper.models import CrawlSession

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class TestScraper(BaseScraper):
    """Test scraper to check browser visibility."""
    
    def scrape(self):
        """Test scrape method."""
        try:
            logger.info("Starting browser visibility test")
            
            # Navigate to a test page
            test_url = "https://groceries.asda.com"
            logger.info(f"Navigating to: {test_url}")
            
            success = self.get_page(test_url)
            if success:
                logger.info("Successfully loaded page!")
                
                # Get page title to confirm it's working
                title = self.driver.title
                logger.info(f"Page title: {title}")
                
                # Wait for 10 seconds so you can see the browser
                logger.info("Browser should be visible now. Waiting 10 seconds...")
                time.sleep(10)
                
                logger.info("Test completed successfully!")
            else:
                logger.error("Failed to load page")
                
        except Exception as e:
            logger.error(f"Error during test: {str(e)}")


def main():
    """Run the browser visibility test."""
    try:
        logger.info("="*50)
        logger.info("BROWSER VISIBILITY TEST")
        logger.info("="*50)
        
        # Create test session
        session = CrawlSession.objects.create(
            crawler_type='TEST',
            status='RUNNING'
        )
        
        # Create and run test scraper
        scraper = TestScraper(session=session)
        
        # Setup driver
        scraper.setup_driver()
        
        # Run test
        scraper.scrape()
        
        # Update session
        session.status = 'COMPLETED'
        session.save()
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        if 'session' in locals():
            session.status = 'FAILED'
            session.save()
    
    finally:
        # Cleanup
        if 'scraper' in locals() and scraper.driver:
            logger.info("Cleaning up driver...")
            scraper.teardown_driver()
        
        logger.info("Test finished")


if __name__ == "__main__":
    main()