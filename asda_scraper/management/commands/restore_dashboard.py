"""
Restore the dashboard to working state.

File: asda_scraper/management/commands/restore_dashboard.py
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Restore dashboard to working state'
    
    def handle(self, *args, **options):
        """Restore the dashboard."""
        try:
            # Restore the original __init__.py
            init_file_path = os.path.join(
                settings.BASE_DIR, 
                'asda_scraper', 
                'scrapers', 
                '__init__.py'
            )
            
            backup_path = init_file_path + '.backup'
            
            if os.path.exists(backup_path):
                self.stdout.write("Restoring original __init__.py...")
                with open(backup_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                with open(init_file_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                self.stdout.write(self.style.SUCCESS("Dashboard restored to working state"))
                
                self.stdout.write("")
                self.stdout.write("RECOMMENDATION:")
                self.stdout.write("Use the working stealth commands instead of dashboard for now:")
                self.stdout.write("")
                self.stdout.write("• Test nutrition extraction:")
                self.stdout.write("  python manage.py stealth_nutrition_test --max-products 3")
                self.stdout.write("")
                self.stdout.write("• Production nutrition crawling:")
                self.stdout.write("  python manage.py stealth_nutrition_crawler --max-products 10 --delay 8.0")
                self.stdout.write("")
                self.stdout.write("• Check products needing nutrition:")
                self.stdout.write("  python manage.py check_product_categories")
                self.stdout.write("")
                self.stdout.write("The stealth commands work perfectly and bypass ASDA's bot detection!")
                
            else:
                self.stdout.write(self.style.WARNING("No backup found - dashboard may already be restored"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))