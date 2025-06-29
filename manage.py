#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    import io
    import locale
    
    # Set UTF-8 as default encoding
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # Reconfigure stdout and stderr to use UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        # Fallback for older Python versions
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    # Set console code page to UTF-8
    try:
        import subprocess
        # Use /K to keep the setting
        subprocess.run(['cmd', '/c', 'chcp', '65001'], shell=False, capture_output=True)
    except:
        pass
    
    # Alternative: Set Windows console mode
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Enable ANSI escape sequences
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitchen_compass.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()