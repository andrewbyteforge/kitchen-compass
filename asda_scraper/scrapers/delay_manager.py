"""
Delay management for rate limiting prevention.

File: asda_scraper/scrapers/delay_manager.py
"""

import logging
import time
import random
from datetime import datetime
from typing import Optional

from .config import DELAY_CONFIG, SCRAPER_SETTINGS

logger = logging.getLogger(__name__)


class DelayManager:
    """
    Manages intelligent delays to avoid rate limiting.
    """
    
    def __init__(self):
        """
        Initialize delay manager.
        """
        self.last_request_time = None
        self.error_count = 0
        self.current_delay_multiplier = 1.0
        
    def wait(self, delay_type: str = 'between_requests', force_delay: Optional[float] = None) -> None:
        """
        Apply intelligent delay based on context.
        
        Args:
            delay_type: Type of delay from DELAY_CONFIG
            force_delay: Override with specific delay in seconds
        """
        if force_delay:
            delay = force_delay
        else:
            # Get base delay from config
            base_delay = DELAY_CONFIG.get(delay_type, 2.0)
            
            # Apply progressive delay if errors occurred
            delay = base_delay * self.current_delay_multiplier
            
            # Add random component
            random_addition = random.uniform(
                DELAY_CONFIG['random_delay_min'],
                DELAY_CONFIG['random_delay_max']
            )
            delay += random_addition
            
            # Cap at maximum
            delay = min(delay, DELAY_CONFIG['max_progressive_delay'])
        
        logger.info(f"[DELAY] Waiting {delay:.1f} seconds ({delay_type})")
        time.sleep(delay)
        self.last_request_time = datetime.now()
        
    def increase_delay(self) -> None:
        """
        Increase delay multiplier after errors.
        """
        self.error_count += 1
        self.current_delay_multiplier *= DELAY_CONFIG['progressive_delay_factor']
        logger.warning(
            f"[DELAY] Increased delay multiplier to {self.current_delay_multiplier:.2f} "
            f"after {self.error_count} errors"
        )
        
    def reset_delay(self) -> None:
        """
        Reset delay multiplier after successful operations.
        """
        if self.error_count > 0:
            logger.info("[DELAY] Resetting delay multiplier after successful operation")
        self.error_count = 0
        self.current_delay_multiplier = 1.0
        
    def check_rate_limit(self, page_source: str) -> bool:
        """
        Check if page indicates rate limiting.
        
        Args:
            page_source: HTML page source
            
        Returns:
            bool: True if rate limit detected
        """
        page_text = page_source.lower()
        for indicator in SCRAPER_SETTINGS['rate_limit_indicators']:
            if indicator in page_text:
                logger.error(f"[RATE LIMIT] Detected rate limit indicator: '{indicator}'")
                self.wait('after_rate_limit_detected')
                return True
        return False