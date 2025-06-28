"""
Script to create the necessary auth_hub files.
Run this from your project root directory.
"""

import os
from pathlib import Path

# Management command content
management_command_content = '''"""
Management command to create initial subscription tiers.

This command sets up the three subscription tiers defined in settings.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from auth_hub.models import SubscriptionTier
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Create initial subscription tiers from settings."""
    
    help = 'Creates the initial subscription tiers (Home Cook, Sous Chef, Master Chef)'
    
    def handle(self, *args, **options):
        """Execute the command to create subscription tiers."""
        tiers_created = 0
        tiers_updated = 0
        
        # Define tier configurations
        tier_configs = {
            'FREE': {
                'name': 'Home Cook',
                'slug': 'home-cook',
                'price': 0,
                'features': settings.SUBSCRIPTION_TIERS['FREE']['features'],
                'max_shared_menus': 0,
                'max_menu_days': 7,
                'stripe_price_id': '',
            },
            'STARTER': {
                'name': 'Sous Chef',
                'slug': 'sous-chef',
                'price': 499,
                'features': settings.SUBSCRIPTION_TIERS['STARTER']['features'],
                'max_shared_menus': 5,
                'max_menu_days': 30,
                'stripe_price_id': settings.SUBSCRIPTION_TIERS['STARTER'].get('stripe_price_id', ''),
            },
            'PREMIUM': {
                'name': 'Master Chef',
                'slug': 'master-chef',
                'price': 999,
                'features': settings.SUBSCRIPTION_TIERS['PREMIUM']['features'],
                'max_shared_menus': 0,  # 0 means unlimited
                'max_menu_days': 365,  # Effectively unlimited
                'stripe_price_id': settings.SUBSCRIPTION_TIERS['PREMIUM'].get('stripe_price_id', ''),
            },
        }
        
        for tier_type, config in tier_configs.items():
            tier, created = SubscriptionTier.objects.update_or_create(
                tier_type=tier_type,
                defaults={
                    'name': config['name'],
                    'slug': config['slug'],
                    'price': config['price'],
                    'features': config['features'],
                    'max_shared_menus': config['max_shared_menus'],
                    'max_menu_days': config['max_menu_days'],
                    'stripe_price_id': config['stripe_price_id'],
                    'is_active': True,
                }
            )
            
            if created:
                tiers_created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created subscription tier: {tier.name}"
                    )
                )
                logger.info(f"Created subscription tier: {tier.name}")
            else:
                tiers_updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated subscription tier: {tier.name}"
                    )
                )
                logger.info(f"Updated subscription tier: {tier.name}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"\\nSummary: {tiers_created} tiers created, "
                f"{tiers_updated} tiers updated."
            )
        )
        
        # Display all tiers
        self.stdout.write("\\nCurrent subscription tiers:")
        for tier in SubscriptionTier.objects.all():
            self.stdout.write(
                f"  - {tier.name}: ${tier.price/100:.2f}/month "
                f"(max {tier.max_shared_menus or 'unlimited'} shares, "
                f"{tier.max_menu_days} day planning)"
            )
'''

# Create the management command file
command_path = Path('auth_hub/management/commands/create_subscription_tiers.py')
command_path.parent.mkdir(parents=True, exist_ok=True)

with open(command_path, 'w', encoding='utf-8') as f:
    f.write(management_command_content)

print("✅ Created management command file")

# Also ensure __init__.py files exist
init_files = [
    'auth_hub/management/__init__.py',
    'auth_hub/management/commands/__init__.py'
]

for init_file in init_files:
    Path(init_file).touch()
    print(f"✅ Created {init_file}")

print("\n🎉 All files created successfully!")
print("\nNow you can run:")
print("python manage.py create_subscription_tiers")