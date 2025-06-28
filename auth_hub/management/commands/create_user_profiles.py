"""
Management command to create user profiles for existing users.

This command ensures all users have associated profiles.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from auth_hub.models import UserProfile, SubscriptionTier
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Create user profiles for existing users who don't have one."""
    
    help = 'Creates user profiles for all existing users'
    
    def handle(self, *args, **options):
        """Execute the command to create missing user profiles."""
        users_without_profiles = User.objects.filter(profile__isnull=True)
        profiles_created = 0
        
        # Get the free tier
        try:
            free_tier = SubscriptionTier.objects.get(tier_type='FREE')
        except SubscriptionTier.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    'Free tier not found! Please run create_subscription_tiers first.'
                )
            )
            return
        
        for user in users_without_profiles:
            UserProfile.objects.create(
                user=user,
                subscription_tier=free_tier,
                subscription_status='active'
            )
            profiles_created += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created profile for user: {user.email or user.username}'
                )
            )
            logger.info(f'Created profile for existing user: {user.email or user.username}')
        
        if profiles_created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully created {profiles_created} user profile(s).'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    'All users already have profiles. No action needed.'
                )
            )