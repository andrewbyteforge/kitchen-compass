"""
Logging configuration for ASDA scraper.

File: asda_scraper/scrapers/logging_config.py
"""

import logging
import logging.handlers
import sys
from pathlib import Path


class SafeUnicodeFormatter(logging.Formatter):
    """
    Custom formatter that handles Unicode characters safely on Windows.
    """
    
    def format(self, record):
        """
        Format log record with Unicode safety.
        
        Args:
            record: LogRecord to format
            
        Returns:
            str: Formatted log string
        """
        msg = super().format(record)
        
        # Replace emojis with text equivalents on Windows console
        if sys.platform == 'win32' and hasattr(sys.stdout, 'encoding'):
            if sys.stdout.encoding != 'utf-8':
                emoji_replacements = {
                    '🛒': '[CART]',
                    '🔍': '[SEARCH]',
                    '✅': '[OK]',
                    '❌': '[ERROR]',
                    '⚠️': '[WARN]',
                    '📦': '[PACKAGE]',
                    '🏪': '[STORE]',
                    '🔗': '[LINK]',
                    '📋': '[INFO]',
                    '🎯': '[TARGET]',
                    '🍎': '[FOOD]',
                    '💰': '[PRICE]',
                    '🏷️': '[TAG]',
                    '📄': '[PAGE]',
                    '🏁': '[FINISH]',
                    '🎉': '[SUCCESS]',
                    '⏳': '[WAIT]',
                    '🌐': '[WEB]',
                    '📊': '[STATS]',
                    '🔚': '[END]',
                    '➡️': '->',
                    '⬅️': '<-',
                    '⬆️': '^',
                    '⬇️': 'v',
                }
                
                for emoji, replacement in emoji_replacements.items():
                    msg = msg.replace(emoji, replacement)
        
        return msg


def setup_logging():
    """
    Set up logging configuration for ASDA scraper.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Create formatter
    console_formatter = SafeUnicodeFormatter(
        '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_formatter = logging.Formatter(
        '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # File handler
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / 'asda_scraper.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Get the asda_scraper logger
    logger = logging.getLogger('asda_scraper')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    
    # Configure submodule loggers
    for submodule in ['scrapers', 'views', 'management']:
        sublogger = logging.getLogger(f'asda_scraper.{submodule}')
        sublogger.setLevel(logging.DEBUG)
        sublogger.handlers.clear()
        sublogger.addHandler(console_handler)
        sublogger.addHandler(file_handler)
        sublogger.propagate = False
    
    return logger