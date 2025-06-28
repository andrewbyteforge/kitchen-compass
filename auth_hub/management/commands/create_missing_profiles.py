from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from auth_hub.models import UserProfile, SubscriptionTier


class Command(BaseCommand):
    help = 'Creates missing user profiles'

    def handle(self, *args, **options):
        # Use 'profile' instead of 'userprofile'
        users_without_profiles = User.objects.filter(profile__isnull=True)
        
        if not users_without_profiles.exists():
            self.stdout.write(self.style.SUCCESS('All users have profiles!'))
            return
        
        # Get or create free tier
        free_tier, created = SubscriptionTier.objects.get_or_create(
            tier_type='FREE',
            defaults={
                'name': 'Home Cook',
                'price': 0,
                'max_recipes': 10,
                'max_menus': 5,
                'max_shares': 0,
                'can_share': False,
            }
        )
        
        for user in users_without_profiles:
            UserProfile.objects.create(
                user=user,
                subscription_tier=free_tier
            )
            self.stdout.write(
                self.style.SUCCESS(f'Created profile for user: {user.username}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {users_without_profiles.count()} missing profiles'
            )
        )