"""
Script to create template directory structure for KitchenCompass.
Run this from your project root directory.
"""

import os
from pathlib import Path

# Create directories
directories = [
    'templates/auth_hub',
    'templates/auth_hub/emails',
    'static/css',
    'static/js',
    'static/images',
]

for directory in directories:
    Path(directory).mkdir(parents=True, exist_ok=True)
    print(f"✅ Created directory: {directory}")

# Create empty __init__.py files for template directories (not needed but good practice)
init_files = [
    'templates/__init__.py',
    'templates/auth_hub/__init__.py',
]

for init_file in init_files:
    Path(init_file).touch()
    print(f"✅ Created {init_file}")

print("\n🎉 Template directory structure created successfully!")
print("\nNext steps:")
print("1. Copy the template content from the artifacts to their respective files")
print("2. Run: python manage.py collectstatic")
print("3. Run: python manage.py runserver")
print("4. Visit: http://127.0.0.1:8000/auth/register/ to create an account")