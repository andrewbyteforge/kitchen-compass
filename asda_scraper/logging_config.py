"""
Enhanced Logging and Error Handling System for ASDA Scraper

This module provides comprehensive logging, error tracking, and recovery mechanisms
for the ASDA scraper with structured logging and error analytics.

File: asda_scraper/logging_config.py
"""

import logging
import logging.handlers
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import sys

# Create logs directory structure
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Create subdirectories for different log types
(LOGS_DIR / "errors").mkdir(exist_ok=True)
(LOGS_DIR / "performance").mkdir(exist_ok=True)
(LOGS_DIR / "sessions").mkdir(exist_ok=True)
(LOGS_DIR / "debug").mkdir(exist_ok=True)


class LogLevel(Enum):
    """Log level enumeration for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCategory(Enum):
    """Categories for error classification."""
    DRIVER_SETUP = "driver_setup"
    NETWORK = "network"
    PARSING = "parsing"
    DATABASE = "database"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


@dataclass
class LogContext:
    """Context information for structured logging."""
    session_id: Optional[int] = None
    category_name: Optional[str] = None
    category_id: Optional[str] = None
    page_number: Optional[int] = None
    product_count: Optional[int] = None
    error_count: Optional[int] = None
    duration: Optional[float] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ErrorInfo:
    """Detailed error information for tracking and analysis."""
    error_type: str
    error_message: str
    error_category: ErrorCategory
    traceback: Optional[str] = None
    context: Optional[LogContext] = None
    timestamp: datetime = field(default_factory=datetime.now)
    recovery_attempted: bool = False
    recovery_successful: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            'error_type': self.error_type,
            'error_message': self.error_message,
            'error_category': self.error_category.value,
            'timestamp': self.timestamp.isoformat(),
            'recovery_attempted': self.recovery_attempted,
            'recovery_successful': self.recovery_successful
        }
        
        if self.traceback:
            data['traceback'] = self.traceback
        
        if self.context:
            data['context'] = self.context.to_dict()
        
        return data


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log structure
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add context if present
        if hasattr(record, 'context') and isinstance(record.context, dict):
            log_data['context'] = record.context
        
        # Add error info if present
        if hasattr(record, 'error_info') and isinstance(record.error_info, ErrorInfo):
            log_data['error'] = record.error_info.to_dict()
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        return json.dumps(log_data, default=str)


class HumanReadableFormatter(logging.Formatter):
    """Formatter for human-readable console output with colors."""
    
    # Color codes for different log levels
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m'  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and readable structure."""
        # Get color for level
        color = self.COLORS.get(record.levelname, '')
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Build base message
        base_msg = f"{color}[{record.levelname}]{self.RESET} {timestamp} [{record.name}] {record.getMessage()}"
        
        # Add context if present
        if hasattr(record, 'context') and isinstance(record.context, dict):
            context_str = ' | '.join(f"{k}={v}" for k, v in record.context.items())
            base_msg += f" | {context_str}"
        
        # Add location info for errors
        if record.levelname in ['ERROR', 'CRITICAL']:
            base_msg += f" | {record.funcName}:{record.lineno}"
        
        return base_msg


class ErrorTracker:
    """Tracks and analyzes errors for patterns and recovery strategies."""
    
    def __init__(self, max_history: int = 1000):
        """Initialize error tracker."""
        self.max_history = max_history
        self.error_history: List[ErrorInfo] = []
        self.error_counts: Dict[str, int] = {}
        self.recovery_strategies: Dict[ErrorCategory, List[callable]] = {
            ErrorCategory.DRIVER_SETUP: [self._recover_driver_setup],
            ErrorCategory.NETWORK: [self._recover_network],
            ErrorCategory.RATE_LIMIT: [self._recover_rate_limit],
            ErrorCategory.TIMEOUT: [self._recover_timeout],
        }
    
    def track_error(self, error_info: ErrorInfo) -> None:
        """Track an error occurrence."""
        self.error_history.append(error_info)
        
        # Maintain history size
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
        
        # Update counts
        error_key = f"{error_info.error_category.value}:{error_info.error_type}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
    
    def get_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns."""
        if not self.error_history:
            return {}
        
        # Time-based analysis
        recent_errors = [e for e in self.error_history 
                        if (datetime.now() - e.timestamp).seconds < 300]  # Last 5 minutes
        
        # Category distribution
        category_dist = {}
        for error in recent_errors:
            cat = error.error_category.value
            category_dist[cat] = category_dist.get(cat, 0) + 1
        
        # Most common errors
        top_errors = sorted(self.error_counts.items(), 
                          key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_errors': len(self.error_history),
            'recent_errors_count': len(recent_errors),
            'category_distribution': category_dist,
            'top_errors': top_errors,
            'error_rate_per_minute': len(recent_errors) / 5
        }
    
    def suggest_recovery(self, error_info: ErrorInfo) -> Optional[callable]:
        """Suggest recovery strategy based on error type."""
        strategies = self.recovery_strategies.get(error_info.error_category, [])
        return strategies[0] if strategies else None
    
    @staticmethod
    def _recover_driver_setup(error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for driver setup errors."""
        return {
            'action': 'restart_driver',
            'delay': 5,
            'retry_count': 3,
            'fallback_options': ['headless_mode', 'different_driver']
        }
    
    @staticmethod
    def _recover_network(error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for network errors."""
        return {
            'action': 'retry_with_backoff',
            'initial_delay': 2,
            'max_delay': 60,
            'retry_count': 5
        }
    
    @staticmethod
    def _recover_rate_limit(error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for rate limit errors."""
        return {
            'action': 'extended_delay',
            'delay': 300,  # 5 minutes
            'rotate_user_agent': True,
            'clear_cookies': True
        }
    
    @staticmethod
    def _recover_timeout(error_info: ErrorInfo) -> Dict[str, Any]:
        """Recovery strategy for timeout errors."""
        return {
            'action': 'increase_timeout',
            'timeout_multiplier': 2,
            'max_timeout': 60,
            'retry_count': 3
        }


class ScraperLogger:
    """Enhanced logger for ASDA scraper with structured logging."""
    
    def __init__(self, name: str = 'asda_scraper'):
        """Initialize scraper logger."""
        self.logger = logging.getLogger(name)
        self.error_tracker = ErrorTracker()
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up logging handlers."""
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        # Console handler with human-readable format
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(HumanReadableFormatter())
        self.logger.addHandler(console_handler)
        
        # Main log file with structured format
        main_handler = logging.handlers.RotatingFileHandler(
            LOGS_DIR / 'asda_scraper.log',
            maxBytes=50*1024*1024,  # 50MB
            backupCount=10,
            delay=True
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(main_handler)
        
        # Error log file
        error_handler = logging.handlers.RotatingFileHandler(
            LOGS_DIR / 'errors' / 'errors.log',
            maxBytes=20*1024*1024,  # 20MB
            backupCount=5,
            delay=True
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(error_handler)
        
        # Performance log file
        self.performance_logger = logging.getLogger(f"{self.logger.name}.performance")
        performance_handler = logging.handlers.RotatingFileHandler(
            LOGS_DIR / 'performance' / 'performance.log',
            maxBytes=20*1024*1024,  # 20MB
            backupCount=5,
            delay=True
        )
        performance_handler.setFormatter(StructuredFormatter())
        self.performance_logger.addHandler(performance_handler)
        
        # Prevent propagation
        self.logger.propagate = False
        self.performance_logger.propagate = False
    
    def log(self, level: LogLevel, message: str, context: Optional[LogContext] = None, 
            error_info: Optional[ErrorInfo] = None):
        """Log a message with optional context and error info."""
        extra = {}
        
        if context:
            extra['context'] = context.to_dict()
        
        if error_info:
            extra['error_info'] = error_info
            self.error_tracker.track_error(error_info)
        
        self.logger.log(
            getattr(logging, level.value),
            message,
            extra=extra
        )
    
    def log_performance(self, metric_name: str, value: float, unit: str = 'seconds',
                       context: Optional[LogContext] = None):
        """Log performance metrics."""
        extra = {
            'metric': {
                'name': metric_name,
                'value': value,
                'unit': unit,
                'timestamp': datetime.now().isoformat()
            }
        }
        
        if context:
            extra['context'] = context.to_dict()
        
        self.performance_logger.info(
            f"Performance metric: {metric_name}={value}{unit}",
            extra=extra
        )
    
    def log_session_start(self, session_id: int, config: Dict[str, Any]):
        """Log session start with configuration."""
        session_file = LOGS_DIR / 'sessions' / f'session_{session_id}.log'
        session_handler = logging.FileHandler(session_file)
        session_handler.setFormatter(StructuredFormatter())
        
        session_logger = logging.getLogger(f"{self.logger.name}.session.{session_id}")
        session_logger.addHandler(session_handler)
        session_logger.setLevel(logging.DEBUG)
        
        session_logger.info(
            "Session started",
            extra={
                'session_id': session_id,
                'config': config,
                'start_time': datetime.now().isoformat()
            }
        )
        
        return session_logger
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error analysis summary."""
        return self.error_tracker.get_error_patterns()
    
    def suggest_recovery_for_error(self, error_info: ErrorInfo) -> Optional[Dict[str, Any]]:
        """Get recovery suggestion for an error."""
        strategy_func = self.error_tracker.suggest_recovery(error_info)
        return strategy_func(error_info) if strategy_func else None


# Singleton instance
_scraper_logger = None


def get_scraper_logger(name: str = 'asda_scraper') -> ScraperLogger:
    """Get or create the scraper logger instance."""
    global _scraper_logger
    if _scraper_logger is None:
        _scraper_logger = ScraperLogger(name)
    return _scraper_logger


# Utility functions for easy logging
def log_debug(message: str, **kwargs):
    """Log debug message."""
    logger = get_scraper_logger()
    context = LogContext(**kwargs) if kwargs else None
    logger.log(LogLevel.DEBUG, message, context)


def log_info(message: str, **kwargs):
    """Log info message."""
    logger = get_scraper_logger()
    context = LogContext(**kwargs) if kwargs else None
    logger.log(LogLevel.INFO, message, context)


def log_warning(message: str, **kwargs):
    """Log warning message."""
    logger = get_scraper_logger()
    context = LogContext(**kwargs) if kwargs else None
    logger.log(LogLevel.WARNING, message, context)


def log_error(message: str, error: Optional[Exception] = None, 
              category: ErrorCategory = ErrorCategory.UNKNOWN, **kwargs):
    """Log error message with optional exception."""
    logger = get_scraper_logger()
    context = LogContext(**kwargs) if kwargs else None
    
    error_info = None
    if error:
        error_info = ErrorInfo(
            error_type=type(error).__name__,
            error_message=str(error),
            error_category=category,
            traceback=traceback.format_exc() if error else None,
            context=context
        )
    
    logger.log(LogLevel.ERROR, message, context, error_info)


def log_critical(message: str, **kwargs):
    """Log critical message."""
    logger = get_scraper_logger()
    context = LogContext(**kwargs) if kwargs else None
    logger.log(LogLevel.CRITICAL, message, context)


def log_performance(metric_name: str, value: float, unit: str = 'seconds', **kwargs):
    """Log performance metric."""
    logger = get_scraper_logger()
    context = LogContext(**kwargs) if kwargs else None
    logger.log_performance(metric_name, value, unit, context)


class SafeUnicodeFormatter(logging.Formatter):
    """
    Custom formatter that safely handles Unicode characters for Windows consoles.
    
    This formatter will replace emoji characters with ASCII equivalents
    when outputting to consoles that don't support Unicode.
    """
    
    # Emoji to ASCII mapping
    # Emoji to ASCII mapping
    EMOJI_MAP = {
        '🔍': '[SEARCH]',
        '📦': '[PRODUCTS]',
        '⏹️': '[STOP]',
        '🛒': '[CART]',
        '🎯': '[TARGET]',
        '✅': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[WARNING]',
        '📊': '[STATS]',
        '🔗': '[LINK]',
        '📍': '[LOCATION]',
        '📄': '[PAGE]',
        '🌿': '[CATEGORY]',
        '🏁': '[FINISH]',
        '🧪': '[TEST]',
        '🚫': '[BLOCKED]',
        '🔚': '[END]',
        '🎉': '[SUCCESS]',
        '⏰': '[TIMEOUT]',
        '➡️': '[ARROW]',
        '🏪': '[STORE]',
        '🍪': '[COOKIE]',
        '🎯': '[TARGET]',
        '✅': '[OK]',
        '🔄': '[REFRESH]',
        '⏳': '[WAIT]',
        '💰': '[PRICE]',
        '🏷️': '[TAG]',
        '🔢': '[NUMBER]',
        '📁': '[FOLDER]',
        '🆕': '[NEW]',
        '📝': '[UPDATE]',
        '🚀': '[START]',
        '⏭️': '[SKIP]',
        '📂': '[DIRECTORY]',
        '🛍️': '[SHOPPING]',
        '🔴': '[RED]',
        '🟢': '[GREEN]',
        '🟡': '[YELLOW]',
        '🔵': '[BLUE]',
        '⭐': '[STAR]',
        '📈': '[CHART]',
        '📉': '[DECLINE]',
        '🔧': '[TOOL]',
        '🔨': '[BUILD]',
        '🗄️': '[STORAGE]',
        '📌': '[PIN]',
        '🎪': '[EVENT]',
        '🏷': '[LABEL]',
        'ℹ️': '[INFO]',
        '📋': '[CLIPBOARD]',
        '📐': '[MEASURE]',
        '🗂️': '[INDEX]',
        '📑': '[BOOKMARK]',
        '🔎': '[ZOOM]',
        '🌐': '[WEB]',
        '💡': '[IDEA]',
        '🔒': '[LOCK]',
        '🔓': '[UNLOCK]',
        '📨': '[MAIL]',
        '📬': '[MAILBOX]',
        '📮': '[POSTBOX]',
        '🚨': '[ALERT]',
        '🔔': '[BELL]',
        '📢': '[ANNOUNCE]',
        '⏯️': '[PLAY/PAUSE]',
        '⏸️': '[PAUSE]',
        '⏺️': '[RECORD]',
        '⏏️': '[EJECT]',
        '🔀': '[SHUFFLE]',
        '🔁': '[REPEAT]',
        '🔂': '[REPEAT_ONE]',
        '▶️': '[PLAY]',
        '⏩': '[FAST_FORWARD]',
        '⏪': '[REWIND]',
        '🔼': '[UP]',
        '🔽': '[DOWN]',
        '⬅️': '[LEFT]',
        '➡': '[RIGHT]',
        '↩️': '[RETURN]',
        '↪️': '[FORWARD]',
        '🔃': '[RELOAD]',
        '🔄': '[SYNC]',
        '✅': '[DONE]',
        '☑️': '[CHECKED]',
        '✔️': '[CHECK]',
        '⏹': '[STOP]',
        '⚠': '[WARN]',
        '🛑': '[STOP_SIGN]',
        '⏱️': '[TIMER]',
        '⏲️': '[TIMER_CLOCK]',
        '🕐': '[CLOCK]',
        '🕑': '[CLOCK_1]',
        '🕒': '[CLOCK_2]',
        '🕓': '[CLOCK_3]',
        '🕔': '[CLOCK_4]',
        '🕕': '[CLOCK_5]',
        '🕖': '[CLOCK_6]',
        '🕗': '[CLOCK_7]',
        '🕘': '[CLOCK_8]',
        '🕙': '[CLOCK_9]',
        '🕚': '[CLOCK_10]',
        '🕛': '[CLOCK_11]',
        '🕜': '[CLOCK_12]',
    }
    
    def format(self, record):
            """
            Format the record, replacing emojis if needed.
            
            Args:
                record: LogRecord to format
                
            Returns:
                str: Formatted log message
            """
            # Get the formatted message
            msg = super().format(record)
            
            # Always replace emojis on Windows to avoid encoding issues
            if sys.platform == 'win32':
                # Replace all known emojis
                for emoji, ascii_text in self.EMOJI_MAP.items():
                    msg = msg.replace(emoji, ascii_text)
                
                # Additional safety: try to encode and catch any remaining issues
                try:
                    # Test encoding with cp1252 (Windows default)
                    msg.encode('cp1252')
                except UnicodeEncodeError:
                    # If there are still unicode issues, do a more aggressive cleanup
                    # Replace any non-ASCII characters with '?'
                    msg = msg.encode('cp1252', errors='replace').decode('cp1252')
            
            return msg


def setup_asda_logging():
    """
    Setup logging for ASDA scraper with console and file handlers.
    
    This function configures logging with:
    - Console output with SafeUnicodeFormatter for Windows compatibility
    - File output with standard formatter supporting full Unicode
    - Proper handling of emoji characters in log messages
    
    Returns:
        logging.Logger: Configured logger instance
    """
    
    # Create formatters
    console_formatter = SafeUnicodeFormatter(
        '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler with SafeUnicodeFormatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(console_formatter)
    
    # File handler with UTF-8 encoding
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / 'asda_scraper.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        delay=True,
        encoding='utf-8'  # Ensure file handler uses UTF-8
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Get the asda_scraper logger and configure it
    asda_logger = logging.getLogger('asda_scraper')
    asda_logger.setLevel(logging.DEBUG)
    asda_logger.handlers.clear()  # Remove any existing handlers
    asda_logger.addHandler(console_handler)
    asda_logger.addHandler(file_handler)
    asda_logger.propagate = False
    
    # Also configure submodule loggers
    for submodule in ['selenium_scraper', 'asda_link_crawler', 'management.commands.run_asda_crawl']:
        sublogger = logging.getLogger(f'asda_scraper.{submodule}')
        sublogger.setLevel(logging.DEBUG)
        sublogger.handlers.clear()
        sublogger.addHandler(console_handler)
        sublogger.addHandler(file_handler)
        sublogger.propagate = False
    
    # Log successful configuration
    asda_logger.info("ASDA scraper logging configured successfully")
    
    return asda_logger