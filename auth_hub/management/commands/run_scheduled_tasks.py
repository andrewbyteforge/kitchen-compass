"""
Management command to run all scheduled tasks.

This is designed to be run by Windows Task Scheduler or any other scheduler.

Usage:
    python manage.py run_scheduled_tasks
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from auth_hub.cron import process_pending_downgrades, send_downgrade_reminders


class Command(BaseCommand):
    help = 'Run all scheduled tasks (downgrades and reminders)'

    def handle(self, *args, **options):
        self.stdout.write('='*50)
        self.stdout.write(f'Running scheduled tasks at {timezone.now()}')
        self.stdout.write('='*50)
        
        # Process pending downgrades
        self.stdout.write('\n1. Processing pending downgrades...')
        try:
            result = process_pending_downgrades()
            self.stdout.write(self.style.SUCCESS(f'   ✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error: {str(e)}'))
        
        # Send reminder emails
        self.stdout.write('\n2. Sending reminder emails...')
        try:
            result = send_downgrade_reminders()
            self.stdout.write(self.style.SUCCESS(f'   ✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'   ✗ Error: {str(e)}'))
        
        self.stdout.write('\n' + '='*50)
        self.stdout.write('Scheduled tasks completed')
        self.stdout.write('='*50 + '\n')