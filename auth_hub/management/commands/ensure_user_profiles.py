"""
Management command to ensure all users have UserProfile instances.
"""

import logging
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from auth_hub.models import UserProfile, SubscriptionTier

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Ensure all users have associated UserProfile instances."""
    
    help = 'Creates UserProfile for any users missing one'
    
    def handle(self, *args, **options):
        """Execute the command."""
        # Get or create default subscription tier
        default_tier, created = SubscriptionTier.objects.get_or_create(
            tier_type='FREE',
            defaults={
                'name': 'Home Cook',
                'price': 0,
                'max_recipes': 10,
                'max_menus': 3,
                'max_shares': 0,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Created default subscription tier: Home Cook')
            )
        
        # Find users without profiles
        users_without_profiles = User.objects.filter(profile__isnull=True)
        count = users_without_profiles.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('All users already have profiles!')
            )
            return
        
        self.stdout.write(f'Found {count} users without profiles')
        
        # Create profiles
        created_count = 0
        for user in users_without_profiles:
            try:
                UserProfile.objects.create(
                    user=user,
                    subscription_tier=default_tier
                )
                created_count += 1
                self.stdout.write(f'Created profile for user: {user.username}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'Error creating profile for user {user.username}: {str(e)}'
                    )
                )
                logger.error(f"Error creating profile for user {user.username}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully created {created_count} user profiles'
            )
        )