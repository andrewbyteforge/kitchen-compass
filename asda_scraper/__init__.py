"""
ASDA Scraper Package Initialization

This file ensures logging is properly configured for the asda_scraper module.
File: asda_scraper/__init__.py
"""

import os
import logging
import logging.handlers
import sys
from pathlib import Path

# Store our handlers globally so they can be reused
_console_handler = None
_file_handler = None

def setup_logger_with_handlers(logger_name):
    """Setup a specific logger with our SafeUnicodeFormatter handlers."""
    global _console_handler, _file_handler

    try:
        from .logging_config import SafeUnicodeFormatter

        # Create handlers only once
        if _console_handler is None:
            logs_dir = Path(__file__).resolve().parent.parent / "logs"
            logs_dir.mkdir(exist_ok=True)

            # Console handler
            _console_handler = logging.StreamHandler(sys.stdout)
            _console_handler.setLevel(logging.DEBUG)
            console_formatter = SafeUnicodeFormatter(
                '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            _console_handler.setFormatter(console_formatter)

            # File handler (lazy open)
            _file_handler = logging.handlers.RotatingFileHandler(
                logs_dir / 'asda_scraper.log',
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                delay=True,                # ← ensure lazy open
                encoding='utf-8'
            )
            _file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                '[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            _file_handler.setFormatter(file_formatter)

        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(_console_handler)
        logger.addHandler(_file_handler)
        logger.setLevel(logging.DEBUG)

        return logger

    except ImportError as e:
        print(f"Warning: Could not import SafeUnicodeFormatter: {e}")
        logger = logging.getLogger(logger_name)
        if not logger.handlers:
            logging.basicConfig(
                level=logging.DEBUG,
                format='[%(levelname)s] %(asctime)s [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        return logger

    except Exception as e:
        print(f"Error setting up logger for {logger_name}: {e}")
        import traceback
        traceback.print_exc()
        return logging.getLogger(logger_name)

