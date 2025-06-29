"""
ASDA Scraper Custom Exceptions

This module defines custom exceptions for the ASDA scraper to provide
better error handling and debugging capabilities.

File: asda_scraper/exceptions.py
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ScraperException(Exception):
    """
    Base exception class for all scraper-related errors.
    
    This is the parent class for all custom scraper exceptions and provides
    common functionality for logging and error tracking.
    
    Attributes:
        message: Error message describing what went wrong
        error_code: Optional error code for categorizing errors
        context: Additional context information about the error
    """
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the scraper exception.
        
        Args:
            message: Error message describing what went wrong
            error_code: Optional error code for categorizing errors
            context: Additional context information about the error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        
        # Log the exception
        logger.error(f"ScraperException: {message}")
        if error_code:
            logger.error(f"Error Code: {error_code}")
        if context:
            logger.error(f"Context: {context}")
    
    def __str__(self) -> str:
        """Return string representation of the exception."""
        parts = [self.message]
        if self.error_code:
            parts.append(f"Code: {self.error_code}")
        return " | ".join(parts)


class DriverSetupException(ScraperException):
    """
    Exception raised when WebDriver setup fails.
    
    This exception is raised when the Selenium WebDriver cannot be
    initialized properly, which prevents the scraper from running.
    """
    
    def __init__(self, message: str, driver_type: str = "Chrome", **kwargs):
        """
        Initialize the driver setup exception.
        
        Args:
            message: Error message describing the setup failure
            driver_type: Type of driver that failed to setup
            **kwargs: Additional context passed to parent class
        """
        super().__init__(
            message=f"WebDriver setup failed for {driver_type}: {message}",
            error_code="DRIVER_SETUP_FAILED",
            context={"driver_type": driver_type, **kwargs.get('context', {})}
        )


class CategoryDiscoveryException(ScraperException):
    """
    Exception raised when category discovery fails.
    
    This exception is raised when the scraper cannot discover or
    validate ASDA product categories.
    """
    
    def __init__(self, message: str, category_name: Optional[str] = None, **kwargs):
        """
        Initialize the category discovery exception.
        
        Args:
            message: Error message describing the discovery failure
            category_name: Name of the category that failed (if applicable)
            **kwargs: Additional context passed to parent class
        """
        context = {"category_name": category_name} if category_name else {}
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Category discovery failed: {message}",
            error_code="CATEGORY_DISCOVERY_FAILED",
            context=context
        )


class ProductExtractionException(ScraperException):
    """
    Exception raised when product data extraction fails.
    
    This exception is raised when the scraper cannot extract product
    information from a page or when product data is invalid.
    """
    
    def __init__(
        self, 
        message: str, 
        product_name: Optional[str] = None,
        category_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the product extraction exception.
        
        Args:
            message: Error message describing the extraction failure
            product_name: Name of the product that failed (if applicable)
            category_name: Name of the category being processed
            **kwargs: Additional context passed to parent class
        """
        context = {}
        if product_name:
            context["product_name"] = product_name
        if category_name:
            context["category_name"] = category_name
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Product extraction failed: {message}",
            error_code="PRODUCT_EXTRACTION_FAILED",
            context=context
        )


class NavigationException(ScraperException):
    """
    Exception raised when page navigation fails.
    
    This exception is raised when the scraper cannot navigate to a
    specific page or when page loading fails.
    """
    
    def __init__(self, message: str, url: Optional[str] = None, **kwargs):
        """
        Initialize the navigation exception.
        
        Args:
            message: Error message describing the navigation failure
            url: URL that failed to load (if applicable)
            **kwargs: Additional context passed to parent class
        """
        context = {"url": url} if url else {}
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Navigation failed: {message}",
            error_code="NAVIGATION_FAILED",
            context=context
        )


class DataValidationException(ScraperException):
    """
    Exception raised when scraped data fails validation.
    
    This exception is raised when extracted data doesn't meet
    the required format or validation criteria.
    """
    
    def __init__(
        self, 
        message: str, 
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize the data validation exception.
        
        Args:
            message: Error message describing the validation failure
            field_name: Name of the field that failed validation
            field_value: Value that failed validation
            **kwargs: Additional context passed to parent class
        """
        context = {}
        if field_name:
            context["field_name"] = field_name
        if field_value is not None:
            context["field_value"] = str(field_value)[:100]  # Truncate long values
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Data validation failed: {message}",
            error_code="DATA_VALIDATION_FAILED",
            context=context
        )


class DatabaseException(ScraperException):
    """
    Exception raised when database operations fail.
    
    This exception is raised when the scraper cannot save data
    to the database or when database queries fail.
    """
    
    def __init__(
        self, 
        message: str, 
        operation: Optional[str] = None,
        model_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the database exception.
        
        Args:
            message: Error message describing the database failure
            operation: Database operation that failed (e.g., 'create', 'update')
            model_name: Name of the model being operated on
            **kwargs: Additional context passed to parent class
        """
        context = {}
        if operation:
            context["operation"] = operation
        if model_name:
            context["model_name"] = model_name
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Database operation failed: {message}",
            error_code="DATABASE_OPERATION_FAILED",
            context=context
        )


class ConfigurationException(ScraperException):
    """
    Exception raised when configuration is invalid or missing.
    
    This exception is raised when the scraper configuration
    is invalid, missing required settings, or misconfigured.
    """
    
    def __init__(
        self, 
        message: str, 
        config_key: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the configuration exception.
        
        Args:
            message: Error message describing the configuration issue
            config_key: Configuration key that is invalid/missing
            **kwargs: Additional context passed to parent class
        """
        context = {"config_key": config_key} if config_key else {}
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Configuration error: {message}",
            error_code="CONFIGURATION_ERROR",
            context=context
        )


class TimeoutException(ScraperException):
    """
    Exception raised when operations timeout.
    
    This exception is raised when the scraper times out waiting
    for pages to load, elements to appear, or operations to complete.
    """
    
    def __init__(
        self, 
        message: str, 
        timeout_duration: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the timeout exception.
        
        Args:
            message: Error message describing the timeout
            timeout_duration: How long the operation waited before timing out
            operation: What operation timed out
            **kwargs: Additional context passed to parent class
        """
        context = {}
        if timeout_duration:
            context["timeout_duration"] = timeout_duration
        if operation:
            context["operation"] = operation
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Operation timed out: {message}",
            error_code="OPERATION_TIMEOUT",
            context=context
        )


class RateLimitException(ScraperException):
    """
    Exception raised when rate limits are exceeded.
    
    This exception is raised when the scraper encounters
    rate limiting from the target website.
    """
    
    def __init__(
        self, 
        message: str, 
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the rate limit exception.
        
        Args:
            message: Error message describing the rate limit
            retry_after: Seconds to wait before retrying (if known)
            **kwargs: Additional context passed to parent class
        """
        context = {"retry_after": retry_after} if retry_after else {}
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Rate limit exceeded: {message}",
            error_code="RATE_LIMIT_EXCEEDED",
            context=context
        )


class CrawlSessionException(ScraperException):
    """
    Exception raised when crawl session operations fail.
    
    This exception is raised when there are issues with
    crawl session management or state tracking.
    """
    
    def __init__(
        self, 
        message: str, 
        session_id: Optional[int] = None,
        session_status: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the crawl session exception.
        
        Args:
            message: Error message describing the session issue
            session_id: ID of the affected crawl session
            session_status: Current status of the session
            **kwargs: Additional context passed to parent class
        """
        context = {}
        if session_id:
            context["session_id"] = session_id
        if session_status:
            context["session_status"] = session_status
        context.update(kwargs.get('context', {}))
        
        super().__init__(
            message=f"Crawl session error: {message}",
            error_code="CRAWL_SESSION_ERROR",
            context=context
        )


# Exception utility functions
def handle_selenium_exception(e: Exception, context: dict = None) -> ScraperException:
    """
    Convert Selenium exceptions to appropriate custom exceptions.
    
    Args:
        e: The original Selenium exception
        context: Additional context information
        
    Returns:
        ScraperException: Appropriate custom exception
    """
    context = context or {}
    
    if "TimeoutException" in str(type(e)):
        return TimeoutException(
            message=str(e),
            context=context
        )
    elif "NoSuchElementException" in str(type(e)):
        return ProductExtractionException(
            message=f"Element not found: {str(e)}",
            context=context
        )
    elif "WebDriverException" in str(type(e)):
        return DriverSetupException(
            message=str(e),
            context=context
        )
    else:
        return ScraperException(
            message=f"Selenium error: {str(e)}",
            error_code="SELENIUM_ERROR",
            context=context
        )


def log_exception_with_context(exception: ScraperException, additional_context: dict = None):
    """
    Log an exception with full context information.
    
    Args:
        exception: The ScraperException to log
        additional_context: Additional context to include in the log
    """
    context = exception.context.copy()
    if additional_context:
        context.update(additional_context)
    
    logger.error(f"Exception: {exception.message}")
    logger.error(f"Error Code: {exception.error_code}")
    logger.error(f"Full Context: {context}")


def is_recoverable_error(exception: ScraperException) -> bool:
    """
    Determine if an error is recoverable and scraping should continue.
    
    Args:
        exception: The ScraperException to check
        
    Returns:
        bool: True if the error is recoverable
    """
    recoverable_codes = [
        "NAVIGATION_FAILED",
        "PRODUCT_EXTRACTION_FAILED",
        "OPERATION_TIMEOUT",
        "RATE_LIMIT_EXCEEDED"
    ]
    
    return exception.error_code in recoverable_codes


def should_retry_operation(exception: ScraperException, attempt_count: int, max_retries: int = 3) -> bool:
    """
    Determine if an operation should be retried based on the exception and attempt count.
    
    Args:
        exception: The ScraperException that occurred
        attempt_count: Current attempt number (1-based)
        max_retries: Maximum number of retries allowed
        
    Returns:
        bool: True if the operation should be retried
    """
    if attempt_count >= max_retries:
        return False
    
    retryable_codes = [
        "NAVIGATION_FAILED",
        "OPERATION_TIMEOUT",
        "RATE_LIMIT_EXCEEDED",
        "SELENIUM_ERROR"
    ]
    
    return exception.error_code in retryable_codes


class ExceptionHandler:
    """
    Centralized exception handling for the scraper.
    
    This class provides methods to handle different types of exceptions
    and determine appropriate responses.
    """
    
    def __init__(self, max_retries: int = 3, log_all_exceptions: bool = True):
        """
        Initialize the exception handler.
        
        Args:
            max_retries: Maximum number of retries for recoverable errors
            log_all_exceptions: Whether to log all exceptions
        """
        self.max_retries = max_retries
        self.log_all_exceptions = log_all_exceptions
        self.error_counts = {}
    
    def handle_exception(
        self, 
        exception: Exception, 
        operation_name: str,
        context: dict = None
    ) -> tuple[bool, ScraperException]:
        """
        Handle an exception and determine if operation should continue.
        
        Args:
            exception: The exception that occurred
            operation_name: Name of the operation that failed
            context: Additional context information
            
        Returns:
            tuple[bool, ScraperException]: (should_continue, custom_exception)
        """
        # Convert to custom exception if needed
        if isinstance(exception, ScraperException):
            custom_exception = exception
        else:
            custom_exception = handle_selenium_exception(exception, context)
        
        # Add operation context
        custom_exception.context.update({
            "operation_name": operation_name,
            **(context or {})
        })
        
        # Log if configured
        if self.log_all_exceptions:
            log_exception_with_context(custom_exception)
        
        # Track error counts
        error_key = f"{operation_name}:{custom_exception.error_code}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Determine if operation should continue
        should_continue = (
            is_recoverable_error(custom_exception) and 
            self.error_counts[error_key] <= self.max_retries
        )
        
        return should_continue, custom_exception
    
    def get_error_summary(self) -> dict:
        """
        Get a summary of all errors encountered.
        
        Returns:
            dict: Summary of error counts by type
        """
        return self.error_counts.copy()
    
    def reset_error_counts(self):
        """Reset all error counts."""
        self.error_counts.clear()


# Error recovery strategies
class ErrorRecoveryStrategy:
    """
    Defines strategies for recovering from different types of errors.
    """
    
    @staticmethod
    def recover_from_navigation_error(driver, url: str, max_attempts: int = 3) -> bool:
        """
        Attempt to recover from navigation errors.
        
        Args:
            driver: WebDriver instance
            url: URL that failed to load
            max_attempts: Maximum recovery attempts
            
        Returns:
            bool: True if recovery was successful
        """
        for attempt in range(max_attempts):
            try:
                logger.info(f"Attempting navigation recovery {attempt + 1}/{max_attempts}")
                
                # Try refreshing the page
                driver.refresh()
                time.sleep(2)
                
                # Try navigating again
                driver.get(url)
                time.sleep(3)
                
                # Check if page loaded successfully
                if "404" not in driver.title.lower() and "error" not in driver.title.lower():
                    logger.info("Navigation recovery successful")
                    return True
                    
            except Exception as e:
                logger.warning(f"Recovery attempt {attempt + 1} failed: {e}")
                continue
        
        logger.error("Navigation recovery failed")
        return False
    
    @staticmethod
    def recover_from_timeout_error(driver, wait_time: int = 5) -> bool:
        """
        Attempt to recover from timeout errors.
        
        Args:
            driver: WebDriver instance
            wait_time: Additional time to wait
            
        Returns:
            bool: True if recovery was successful
        """
        try:
            logger.info(f"Attempting timeout recovery with {wait_time}s wait")
            
            # Wait additional time
            time.sleep(wait_time)
            
            # Check if page is now ready
            if driver.execute_script("return document.readyState") == "complete":
                logger.info("Timeout recovery successful")
                return True
                
        except Exception as e:
            logger.warning(f"Timeout recovery failed: {e}")
        
        return False
    
    @staticmethod
    def recover_from_element_not_found(driver, alternative_selectors: list) -> bool:
        """
        Attempt to recover from element not found errors.
        
        Args:
            driver: WebDriver instance
            alternative_selectors: List of alternative selectors to try
            
        Returns:
            bool: True if recovery was successful
        """
        for selector in alternative_selectors:
            try:
                from selenium.webdriver.common.by import By
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    logger.info(f"Element recovery successful with selector: {selector}")
                    return True
            except:
                continue
        
        logger.warning("Element recovery failed")
        return False