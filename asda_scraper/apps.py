# asda_scraper/apps.py
import os
from django.apps import AppConfig
from . import setup_logger_with_handlers


class AsdaScraperConfig(AppConfig):
    name = 'asda_scraper'

    def ready(self):
        # Only log once, in the autoreload child
        if os.environ.get('RUN_MAIN') == 'true':
            logger = setup_logger_with_handlers('asda_scraper')
            logger.info("ASDA Scraper module initialized with SafeUnicodeFormatter")
