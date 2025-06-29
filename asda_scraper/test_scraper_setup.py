"""
Test script to validate Asda scraper setup and dependencies.

This script checks all requirements and performs a basic test
of the scraping functionality without saving to database.

File: test_scraper_setup.py
"""

import sys
import importlib
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible."""
    print("🔍 Checking Python version...")
    
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    return True

def check_dependencies():
    """Check if all required packages are installed."""
    print("\n🔍 Checking dependencies...")
    
    required_packages = [
        'selenium',
        'webdriver_manager',
        'django',
        'psycopg2',  # or psycopg2-binary
        'beautifulsoup4',
        'requests',
        'lxml'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'psycopg2':
                # Try both variants
                try:
                    importlib.import_module('psycopg2')
                except ImportError:
                    importlib.import_module('psycopg2_binary')
            else:
                importlib.import_module(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NOT INSTALLED")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n📦 To install missing packages, run:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_chrome_installation():
    """Check if Chrome browser is available."""
    print("\n🔍 Checking Chrome installation...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        # Try to get ChromeDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.quit()
        
        print("✅ Chrome and ChromeDriver available")
        return True
        
    except Exception as e:
        print(f"❌ Chrome setup failed: {str(e)}")
        print("💡 Install Chrome browser: https://www.google.com/chrome/")
        return False

def check_django_setup():
    """Check Django project structure."""
    print("\n🔍 Checking Django project structure...")
    
    required_files = [
        'manage.py',
        'kitchen_compass/settings.py',
        'auth_hub/models.py',
        'auth_hub/__init__.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ {file_path} - NOT FOUND")
            missing_files.append(file_path)
        else:
            print(f"✅ {file_path}")
    
    if missing_files:
        print("\n📁 Missing Django project files. Make sure you're running from project root.")
        return False
    
    return True

def check_database_connection():
    """Test database connection."""
    print("\n🔍 Checking database connection...")
    
    try:
        import os
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitchen_compass.settings')
        
        import django
        django.setup()
        
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        
        print("✅ Database connection successful")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        print("💡 Check your database settings in settings.py")
        print("💡 Make sure PostgreSQL is running")
        print("💡 Run migrations: python manage.py migrate")
        return False

def test_basic_scraping():
    """Test basic web scraping functionality."""
    print("\n🔍 Testing basic scraping functionality...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        # Setup Chrome in headless mode for testing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        try:
            print("📡 Connecting to Asda website...")
            driver.get("https://groceries.asda.com/")
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            page_title = driver.title
            print(f"✅ Successfully loaded: {page_title}")
            
            # Check if cookie banner appears
            try:
                cookie_elements = driver.find_elements(By.CSS_SELECTOR, "button[data-testid*='cookie'], button[id*='cookie']")
                if cookie_elements:
                    print("✅ Cookie banner detected (normal for first visit)")
                else:
                    print("ℹ️  No cookie banner found")
            except:
                pass
            
            print("✅ Basic scraping test successful")
            return True
            
        finally:
            driver.quit()
            
    except Exception as e:
        print(f"❌ Scraping test failed: {str(e)}")
        return False

def create_management_directories():
    """Create necessary directory structure."""
    print("\n🔍 Creating management command directories...")
    
    directories = [
        'auth_hub/management',
        'auth_hub/management/commands',
        'logs'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created: {directory}")
    
    # Create __init__.py files
    init_files = [
        'auth_hub/management/__init__.py',
        'auth_hub/management/commands/__init__.py'
    ]
    
    for init_file in init_files:
        Path(init_file).touch()
        print(f"✅ Created: {init_file}")
    
    return True

def run_all_checks():
    """Run all validation checks."""
    print("🚀 KitchenCompass Asda Scraper Setup Validation")
    print("=" * 50)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies), 
        ("Chrome Installation", check_chrome_installation),
        ("Django Structure", check_django_setup),
        ("Database Connection", check_database_connection),
        ("Basic Scraping", test_basic_scraping),
        ("Directory Setup", create_management_directories)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        try:
            if check_func():
                passed += 1
            else:
                print(f"\n❌ {check_name} check failed")
        except Exception as e:
            print(f"\n❌ {check_name} check error: {str(e)}")
    
    print("\n" + "=" * 50)
    print(f"📊 Results: {passed}/{total} checks passed")
    
    if passed == total:
        print("🎉 All checks passed! Your scraper setup is ready.")
        print("\n📝 Next steps:")
        print("1. Add the Asda models to auth_hub/models.py")
        print("2. Run: python manage.py makemigrations")
        print("3. Run: python manage.py migrate")
        print("4. Save scrape_asda.py to auth_hub/management/commands/")
        print("5. Test scraper: python manage.py scrape_asda --max-categories 2 --max-products 5")
    else:
        print("⚠️  Some checks failed. Please resolve the issues above.")
        print("💡 Run this script again after fixing the issues.")
    
    return passed == total

def install_requirements():
    """Install required packages automatically."""
    print("\n📦 Installing required packages...")
    
    packages = [
        'selenium==4.15.2',
        'webdriver-manager==4.0.1',
        'beautifulsoup4==4.12.2',
        'lxml==4.9.3',
        'requests==2.31.0'
    ]
    
    for package in packages:
        try:
            print(f"Installing {package}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', package], 
                         check=True, capture_output=True, text=True)
            print(f"✅ {package} installed")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
            return False
    
    print("✅ All packages installed successfully")
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Asda scraper setup')
    parser.add_argument('--install', action='store_true', 
                       help='Automatically install required packages')
    parser.add_argument('--quick', action='store_true',
                       help='Skip time-consuming checks')
    
    args = parser.parse_args()
    
    if args.install:
        if install_requirements():
            print("\n🔄 Running setup validation after installation...")
            run_all_checks()
    else:
        run_all_checks()