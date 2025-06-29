"""
ASDA Scraper Package Initialization

This file ensures logging is properly configured for the asda_scraper module.
File: asda_scraper/__init__.py
"""

import logging.config
from django.conf import settings

# Force Django to setup logging if it hasn't already
if hasattr(settings, 'LOGGING'):
    logging.config.dictConfig(settings.LOGGING)

# Get logger for this module
logger = logging.getLogger(__name__)
logger.info("ASDA Scraper module initialized with logging")