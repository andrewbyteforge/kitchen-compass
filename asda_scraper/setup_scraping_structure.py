"""
Setup script to create the management command directory structure.
Run this from your Django project root directory.

File: setup_scraping_structure.py
"""

import os
from pathlib import Path

def create_management_structure():
    """Create the Django management command directory structure."""
    
    # Define directories to create
    directories = [
        'auth_hub/management',
        'auth_hub/management/commands',
        'logs',  # For logging output
    ]
    
    # Create directories
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    # Create __init__.py files
    init_files = [
        'auth_hub/management/__init__.py',
        'auth_hub/management/commands/__init__.py',
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
        print(f"✅ Created {init_file}")
    
    # Create .env file template if it doesn't exist
    env_file = Path('.env')
    if not env_file.exists():
        env_content = """# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Settings
DATABASE_NAME=kitchen_compass
DATABASE_USER=postgres
DATABASE_PASSWORD=your-password-here

# Chrome WebDriver Settings (optional)
# CHROME_DRIVER_PATH=/path/to/chromedriver
# CHROME_BINARY_LOCATION=/path/to/chrome

# Scraping Settings
SCRAPING_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
SCRAPING_DELAY=2
SCRAPING_TIMEOUT=30
"""
        
        env_file.write_text(env_content)
        print(f"✅ Created .env template file")
    
    print("\n🎉 Management command structure created successfully!")
    print("\nNext steps:")
    print("1. Install scraping requirements: pip install selenium webdriver-manager beautifulsoup4")
    print("2. Add the Asda models to your auth_hub/models.py file")
    print("3. Create and run migrations: python manage.py makemigrations && python manage.py migrate")
    print("4. Save the scrape_asda.py command to auth_hub/management/commands/")
    print("5. Test the scraper: python manage.py scrape_asda --max-categories 2 --max-products 10")


if __name__ == "__main__":
    create_management_structure()