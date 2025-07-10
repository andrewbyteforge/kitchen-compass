"""
Error Recovery Manager for ASDA Scraper

This module provides automated error recovery mechanisms and resilience patterns
for the ASDA scraper to handle various failure scenarios gracefully.

File: asda_scraper/error_recovery.py
"""

import time
import random
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
import logging

from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException
)

from .logging_config import (
    get_scraper_logger,
    ErrorCategory,
    ErrorInfo,
    LogContext,
    log_error,
    log_info,
    log_warning
)

logger = logging.getLogger('asda_scraper.error_recovery')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    exceptions: Tuple[type, ...] = (Exception,)
    recovery_action: Optional[Callable] = None
    error_category: ErrorCategory = ErrorCategory.UNKNOWN


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Failing, reject calls
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = self.CLOSED
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == self.OPEN:
            if self._should_attempt_reset():
                self.state = self.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        return (self.last_failure_time and 
                datetime.now() - self.last_failure_time > 
                timedelta(seconds=self.recovery_timeout))
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = self.CLOSED
        
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            log_warning(f"Circuit breaker opened after {self.failure_count} failures")


class RecoveryManager:
    """Manages error recovery strategies for the scraper."""
    
    def __init__(self):
        """Initialize recovery manager."""
        self.logger = get_scraper_logger()
        self.recovery_strategies = {
            ErrorCategory.DRIVER_SETUP: self._recover_driver_error,
            ErrorCategory.NETWORK: self._recover_network_error,
            ErrorCategory.RATE_LIMIT: self._recover_rate_limit,
            ErrorCategory.TIMEOUT: self._recover_timeout,
            ErrorCategory.PARSING: self._recover_parsing_error,
            ErrorCategory.DATABASE: self._recover_database_error
        }
        self.circuit_breakers = {}
        
    def with_recovery(self, func: Callable, error_category: ErrorCategory = ErrorCategory.UNKNOWN,
                     context: Optional[LogContext] = None, **retry_kwargs) -> Callable:
        """
        Decorator to add error recovery to a function.
        
        Args:
            func: Function to wrap
            error_category: Category of errors to handle
            context: Logging context
            **retry_kwargs: Additional retry configuration
        """
        retry_config = RetryConfig(
            error_category=error_category,
            recovery_action=self.recovery_strategies.get(error_category),
            **retry_kwargs
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self._execute_with_retry(func, args, kwargs, retry_config, context)
        
        return wrapper
    
    def _execute_with_retry(self, func: Callable, args: tuple, kwargs: dict,
                           retry_config: RetryConfig, context: Optional[LogContext]) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(retry_config.max_attempts):
            try:
                # Check circuit breaker
                breaker_key = f"{func.__name__}_{retry_config.error_category.value}"
                if breaker_key in self.circuit_breakers:
                    return self.circuit_breakers[breaker_key].call(func, *args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except retry_config.exceptions as e:
                last_exception = e
                
                # Log the error
                error_info = ErrorInfo(
                    error_type=type(e).__name__,
                    error_message=str(e),
                    error_category=retry_config.error_category,
                    context=context
                )
                
                log_error(
                    f"Attempt {attempt + 1}/{retry_config.max_attempts} failed: {str(e)}",
                    error=e,
                    category=retry_config.error_category
                )
                
                # Check if we should retry
                if attempt < retry_config.max_attempts - 1:
                    # Calculate delay
                    delay = self._calculate_delay(attempt, retry_config)
                    
                    # Execute recovery action if provided
                    if retry_config.recovery_action:
                        recovery_result = retry_config.recovery_action(error_info)
                        if recovery_result and 'delay' in recovery_result:
                            delay = recovery_result['delay']
                    
                    log_info(f"Retrying after {delay:.1f} seconds...")
                    time.sleep(delay)
                else:
                    # Final attempt failed
                    log_error(f"All {retry_config.max_attempts} attempts failed", 
                             error=last_exception,
                             category=retry_config.error_category)
                    
                    # Update circuit breaker
                    if breaker_key not in self.circuit_breakers:
                        self.circuit_breakers[breaker_key] = CircuitBreaker(
                            expected_exception=type(last_exception)
                        )
                    
                    raise last_exception
        
        return None
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        delay = min(
            config.initial_delay * (config.exponential_base ** attempt),
            config.max_delay
        )
        
        if config.jitter:
            jitter = random.uniform(0, delay * 0.1)
            delay += jitter
        
        return delay
    
    def _recover_driver_error(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for WebDriver errors."""
        log_info("Attempting driver recovery...")
        
        return {
            'action': 'restart_driver',
            'delay': 5.0,
            'clear_cache': True,
            'rotate_user_agent': True,
            'additional_options': ['--disable-blink-features=AutomationControlled']
        }
    
    def _recover_network_error(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for network errors."""
        log_info("Attempting network recovery...")
        
        return {
            'action': 'retry_with_backoff',
            'delay': 10.0,
            'check_connectivity': True,
            'rotate_proxy': False  # Implement if using proxies
        }
    
    def _recover_rate_limit(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for rate limiting."""
        log_warning("Rate limit detected, implementing cooldown...")
        
        return {
            'action': 'extended_cooldown',
            'delay': 300.0,  # 5 minutes
            'rotate_user_agent': True,
            'clear_cookies': True,
            'reduce_request_rate': True
        }
    
    def _recover_timeout(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for timeout errors."""
        log_info("Attempting timeout recovery...")
        
        return {
            'action': 'increase_timeout',
            'delay': 5.0,
            'timeout_multiplier': 1.5,
            'check_element_presence': True
        }
    
    def _recover_parsing_error(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for parsing errors."""
        log_info("Attempting parsing recovery...")
        
        return {
            'action': 'alternative_parsing',
            'delay': 2.0,
            'use_fallback_selectors': True,
            'capture_page_source': True
        }
    
    def _recover_database_error(self, error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for database errors."""
        log_info("Attempting database recovery...")
        
        return {
            'action': 'database_reconnect',
            'delay': 5.0,
            'check_connection': True,
            'use_batch_insert': True
        }


# Decorator functions for easy use
def with_retry(max_attempts: int = 3, exceptions: Tuple[type, ...] = (Exception,),
               error_category: ErrorCategory = ErrorCategory.UNKNOWN):
    """
    Decorator for adding retry logic to functions.
    
    Usage:
        @with_retry(max_attempts=3, exceptions=(WebDriverException,))
        def scrape_page():
            # scraping logic
    """
    def decorator(func):
        manager = RecoveryManager()
        return manager.with_recovery(
            func,
            error_category=error_category,
            max_attempts=max_attempts,
            exceptions=exceptions
        )
    return decorator


def resilient_find_element(driver, by: str, value: str, timeout: int = 10,
                          context: Optional[LogContext] = None):
    """
    Resilient element finding with automatic retry and recovery.
    
    Args:
        driver: Selenium WebDriver instance
        by: Locator strategy (By.ID, By.CSS_SELECTOR, etc.)
        value: Locator value
        timeout: Maximum wait time
        context: Optional logging context
    
    Returns:
        WebElement if found, None otherwise
    """
    @with_retry(
        max_attempts=3,
        exceptions=(NoSuchElementException, TimeoutException, StaleElementReferenceException),
        error_category=ErrorCategory.TIMEOUT
    )
    def find():
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        wait = WebDriverWait(driver, timeout)
        element = wait.until(EC.presence_of_element_located((by, value)))
        
        # Verify element is interactable
        if not element.is_displayed() or not element.is_enabled():
            raise NoSuchElementException(f"Element {value} not interactable")
        
        return element
    
    try:
        return find()
    except Exception as e:
        log_error(f"Failed to find element {value}", error=e, 
                 category=ErrorCategory.PARSING)
        return None


def resilient_click(element, driver=None, context: Optional[LogContext] = None):
    """
    Resilient clicking with fallback strategies.
    
    Args:
        element: WebElement to click
        driver: Optional WebDriver for JavaScript fallback
        context: Optional logging context
    """
    @with_retry(
        max_attempts=3,
        exceptions=(Exception,),
        error_category=ErrorCategory.UNKNOWN
    )
    def click():
        try:
            element.click()
        except Exception as e:
            if driver:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", element)
            else:
                raise e
    
    return click()


class ResilientScraper:
    """
    Mixin class to add resilience to scrapers.
    
    Usage:
        class MyScraper(ResilientScraper):
            def scrape(self):
                with self.error_boundary():
                    # scraping logic
    """
    
    def __init__(self):
        """Initialize resilient scraper."""
        self.recovery_manager = RecoveryManager()
        self.error_count = 0
        self.success_count = 0
        
    def error_boundary(self, error_category: ErrorCategory = ErrorCategory.UNKNOWN):
        """
        Context manager for error boundary.
        
        Usage:
            with self.error_boundary(ErrorCategory.NETWORK):
                # code that might fail
        """
        class ErrorBoundary:
            def __init__(self, scraper, category):
                self.scraper = scraper
                self.category = category
                
            def __enter__(self):
                return self
                
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type:
                    self.scraper.error_count += 1
                    error_info = ErrorInfo(
                        error_type=exc_type.__name__,
                        error_message=str(exc_val),
                        error_category=self.category
                    )
                    
                    # Try recovery
                    recovery = self.scraper.recovery_manager.recovery_strategies.get(
                        self.category
                    )
                    if recovery:
                        recovery_result = recovery(error_info)
                        log_info(f"Recovery attempted: {recovery_result}")
                    
                    # Don't suppress the exception
                    return False
                else:
                    self.scraper.success_count += 1
                    return True
        
        return ErrorBoundary(self, error_category)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the scraper."""
        total_operations = self.error_count + self.success_count
        
        if total_operations == 0:
            success_rate = 0
        else:
            success_rate = (self.success_count / total_operations) * 100
        
        return {
            'total_operations': total_operations,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'success_rate': success_rate,
            'is_healthy': success_rate > 80  # 80% success rate threshold
        }