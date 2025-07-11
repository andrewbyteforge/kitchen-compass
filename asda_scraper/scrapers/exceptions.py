"""
Custom exception classes for ASDA scraper.

File: asda_scraper/scrapers/exceptions.py
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ScraperException(Exception):
    """
    Base exception class for scraper-related errors.
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize scraper exception.
        
        Args:
            message: Error message
            error_code: Optional error code for categorization
            context: Optional context dictionary with additional information
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        logger.error(f"ScraperException: {message}")


class DriverSetupException(ScraperException):
    """
    Exception raised when WebDriver setup fails.
    """
    
    def __init__(self, message: str, driver_type: str = "Chrome", **kwargs):
        """
        Initialize driver setup exception.
        
        Args:
            message: Error message
            driver_type: Type of driver that failed to setup
            **kwargs: Additional keyword arguments
        """
        super().__init__(
            message=f"WebDriver setup failed for {driver_type}: {message}",
            error_code="DRIVER_SETUP_FAILED",
            context={"driver_type": driver_type, **kwargs.get('context', {})}
        )


class ProductExtractionException(ScraperException):
    """
    Exception raised when product extraction fails.
    """
    
    def __init__(self, message: str, url: Optional[str] = None, **kwargs):
        """
        Initialize product extraction exception.
        
        Args:
            message: Error message
            url: URL where extraction failed
            **kwargs: Additional keyword arguments
        """
        context = {"url": url} if url else {}
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Product extraction failed: {message}",
            error_code="PRODUCT_EXTRACTION_FAILED",
            context=context
        )


class NavigationException(ScraperException):
    """
    Exception raised when page navigation fails.
    """
    
    def __init__(self, message: str, target_url: Optional[str] = None, **kwargs):
        """
        Initialize navigation exception.
        
        Args:
            message: Error message
            target_url: URL that failed to load
            **kwargs: Additional keyword arguments
        """
        context = {"target_url": target_url} if target_url else {}
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Navigation failed: {message}",
            error_code="NAVIGATION_FAILED",
            context=context
        )


class RateLimitException(ScraperException):
    """
    Exception raised when rate limiting is detected.
    """
    
    def __init__(self, message: str = "Rate limit detected", **kwargs):
        """
        Initialize rate limit exception.
        
        Args:
            message: Error message
            **kwargs: Additional keyword arguments
        """
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_DETECTED",
            context=kwargs.get('context', {})
        )