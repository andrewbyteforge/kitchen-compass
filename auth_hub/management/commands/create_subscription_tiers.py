"""
Django management command to create subscription tiers for KitchenCompass.

This command creates the three subscription tiers: Home Cook (Free), 
Sous Chef ($4.99), and Master Chef ($9.99).

Usage:
    python manage.py create_subscription_tiers
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from auth_hub.models import SubscriptionTier


class Command(BaseCommand):
    help = 'Creates the subscription tiers for KitchenCompass'

    def handle(self, *args, **options):
        """Create or update subscription tiers."""
        
        self.stdout.write('Creating subscription tiers...')
        
        with transaction.atomic():
            # Home Cook (Free Tier)
            home_cook, created = SubscriptionTier.objects.update_or_create(
                tier_type='FREE',
                defaults={
                    'name': 'Home Cook',
                    'slug': 'home-cook',
                    'price': 0.00,
                    'max_recipes': 10,
                    'max_menus': 3,
                    'max_shared_menus': 0,  # Cannot share on free tier
                    'max_menu_days': 7,
                    'features': [
                        'Store up to 10 recipes',
                        'Create up to 3 meal plans',
                        '7-day meal planning',
                        'Basic shopping lists',
                        'Community support'
                    ],
                    'stripe_price_id': '',  # No Stripe ID for free tier
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created {home_cook.name} tier')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated {home_cook.name} tier')
                )
            
            # Sous Chef (Starter Tier)
            sous_chef, created = SubscriptionTier.objects.update_or_create(
                tier_type='STARTER',
                defaults={
                    'name': 'Sous Chef',
                    'slug': 'sous-chef',
                    'price': 4.99,
                    'max_recipes': 50,
                    'max_menus': 10,
                    'max_shared_menus': 5,  # Can share with up to 5 people
                    'max_menu_days': 14,
                    'features': [
                        'Store up to 50 recipes',
                        'Create up to 10 meal plans',
                        '14-day meal planning',
                        'Share menus with up to 5 people',
                        'Advanced shopping lists',
                        'Basic nutrition tracking',
                        'Email support'
                    ],
                    'stripe_price_id': '',  # TODO: Add Stripe price ID
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created {sous_chef.name} tier')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated {sous_chef.name} tier')
                )
            
            # Master Chef (Premium Tier)
            master_chef, created = SubscriptionTier.objects.update_or_create(
                tier_type='PREMIUM',
                defaults={
                    'name': 'Master Chef',
                    'slug': 'master-chef',
                    'price': 9.99,
                    'max_recipes': -1,  # Unlimited
                    'max_menus': -1,    # Unlimited
                    'max_shared_menus': 0,  # 0 means unlimited for paid tiers
                    'max_menu_days': 30,
                    'features': [
                        'Unlimited recipe storage',
                        'Unlimited meal plans',
                        '30-day meal planning',
                        'Unlimited menu sharing',
                        'Advanced nutrition tracking',
                        'Recipe import/export',
                        'Priority customer support',
                        'Custom meal plan templates',
                        'Shopping list optimization',
                        'Outlook calendar integration'
                    ],
                    'stripe_price_id': '',  # TODO: Add Stripe price ID
                    'is_active': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created {master_chef.name} tier')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'↻ Updated {master_chef.name} tier')
                )
        
        # Display summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('\nSubscription Tiers Summary:'))
        
        all_tiers = SubscriptionTier.objects.filter(is_active=True).order_by('price')
        
        for tier in all_tiers:
            self.stdout.write(f'\n{tier.name} (${tier.price}/month):')
            self.stdout.write(f'  - Type: {tier.get_tier_type_display()}')
            self.stdout.write(f'  - Recipes: {"Unlimited" if tier.max_recipes == -1 else tier.max_recipes}')
            self.stdout.write(f'  - Meal Plans: {"Unlimited" if tier.max_menus == -1 else tier.max_menus}')
            self.stdout.write(f'  - Sharing: {"Not available" if tier.tier_type == "FREE" else ("Unlimited" if tier.max_shared_menus == 0 else f"Up to {tier.max_shared_menus} people")}')
            self.stdout.write(f'  - Planning Days: {tier.max_menu_days}')
            self.stdout.write(f'  - Active: {"Yes" if tier.is_active else "No"}')
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS('\n✓ Successfully created/updated all subscription tiers!')
        )
        
        # Reminder about Stripe
        self.stdout.write(
            self.style.WARNING(
                '\n⚠ Remember to update Stripe price IDs in the admin panel '
                'before going to production!'
            )
        )