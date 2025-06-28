"""
Management command to test cron jobs manually.

Usage:
    python manage.py test_cron --downgrades
    python manage.py test_cron --reminders
    python manage.py test_cron --create-test
    python manage.py test_cron --test-now
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from auth_hub.cron import process_pending_downgrades, send_downgrade_reminders
from auth_hub.models import UserProfile


class Command(BaseCommand):
    help = 'Test cron jobs manually'

    def add_arguments(self, parser):
        parser.add_argument(
            '--downgrades',
            action='store_true',
            help='Test processing pending downgrades',
        )
        parser.add_argument(
            '--reminders',
            action='store_true',
            help='Test sending downgrade reminders',
        )
        parser.add_argument(
            '--create-test',
            action='store_true',
            help='Create a test downgrade scenario for tomorrow',
        )
        parser.add_argument(
            '--test-now',
            action='store_true',
            help='Create a test downgrade that processes immediately',
        )

    def handle(self, *args, **options):
        if options['create_test']:
            self._create_test_scenario()
        
        if options['test_now']:
            self._create_immediate_test()
        
        if options['downgrades']:
            self.stdout.write('Testing downgrade processing...')
            result = process_pending_downgrades()
            self.stdout.write(self.style.SUCCESS(f'Result: {result}'))
        
        if options['reminders']:
            self.stdout.write('Testing reminder emails...')
            result = send_downgrade_reminders()
            self.stdout.write(self.style.SUCCESS(f'Result: {result}'))
        
        if not any([options['downgrades'], options['reminders'], options['create_test'], options['test_now']]):
            self.stdout.write(self.style.WARNING('No option specified. Use --help for options.'))
    
    def _create_test_scenario(self):
        """Create a test downgrade scenario for tomorrow."""
        try:
            profile = UserProfile.objects.filter(
                subscription_tier__tier_type__in=['STARTER', 'PREMIUM']
            ).first()
            
            if not profile:
                self.stdout.write(self.style.ERROR('No user with paid subscription found.'))
                return
            
            # Get the free tier
            from auth_hub.models import SubscriptionTier
            free_tier = SubscriptionTier.objects.get(tier_type='FREE')
            
            # Schedule a downgrade for tomorrow
            profile.pending_subscription_tier = free_tier
            profile.pending_tier_change_date = timezone.now() + timedelta(days=1)
            profile.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created test downgrade for {profile.user.email}: '
                    f'{profile.subscription_tier.name} -> {free_tier.name} '
                    f'scheduled for {profile.pending_tier_change_date}'
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating test scenario: {str(e)}'))
    
    def _create_immediate_test(self):
        """Create a test downgrade that will process immediately."""
        try:
            profile = UserProfile.objects.filter(
                subscription_tier__tier_type__in=['STARTER', 'PREMIUM']
            ).first()
            
            if not profile:
                self.stdout.write(self.style.ERROR('No user with paid subscription found.'))
                return
            
            # Get the free tier
            from auth_hub.models import SubscriptionTier
            free_tier = SubscriptionTier.objects.get(tier_type='FREE')
            
            # Schedule a downgrade for RIGHT NOW (in the past)
            profile.pending_subscription_tier = free_tier
            profile.pending_tier_change_date = timezone.now() - timedelta(minutes=1)
            profile.save()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created immediate test downgrade for {profile.user.email}: '
                    f'{profile.subscription_tier.name} -> {free_tier.name} '
                    f'(will process immediately)'
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating test scenario: {str(e)}'))