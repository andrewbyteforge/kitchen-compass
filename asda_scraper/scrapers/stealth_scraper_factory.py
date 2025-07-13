"""
Patch to update the dashboard to use stealth scraper.

Create this file: asda_scraper/scrapers/stealth_scraper_factory.py
"""

import logging
from asda_scraper.models import CrawlSession
from .selenium_scraper_stealth import StealthSeleniumAsdaScraper

logger = logging.getLogger(__name__)


def create_selenium_scraper(crawl_session: CrawlSession, headless: bool = False) -> StealthSeleniumAsdaScraper:
    """
    Factory function to create a Stealth Selenium scraper instance.
    Updated to use stealth anti-bot detection by default.
    
    Args:
        crawl_session: CrawlSession instance
        headless: Whether to run browser in headless mode (default: False for better stealth)
        
    Returns:
        StealthSeleniumAsdaScraper: Configured stealth scraper instance
    """
    logger.info(f"🥷 Creating stealth scraper for session {crawl_session.pk}")
    logger.info(f"   Crawl type: {crawl_session.crawl_type}")
    logger.info(f"   Headless mode: {headless}")
    
    # Force visible mode for better stealth unless explicitly requested
    if headless and not crawl_session.crawl_settings.get('force_headless', False):
        logger.warning("⚠️  Forcing visible mode for better stealth performance")
        headless = False
    
    return StealthSeleniumAsdaScraper(crawl_session, headless=headless)


# Backwards compatibility aliases
SeleniumAsdaScraper = StealthSeleniumAsdaScraper