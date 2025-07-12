"""
Django management command to cleanup stuck crawl sessions.

File: asda_scraper/management/commands/cleanup_sessions.py
"""

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from asda_scraper.models import CrawlSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to cleanup stuck crawl sessions.
    
    This command identifies and cleans up sessions that are stuck in 
    RUNNING or PENDING status but are no longer actually running.
    """
    
    help = 'Cleanup stuck crawl sessions that are no longer running'
    
    def add_arguments(self, parser):
        """
        Add command arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--hours',
            type=int,
            default=2,
            help='Sessions older than this many hours will be considered stuck (default: 2)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup of all RUNNING/PENDING sessions regardless of age',
        )
        parser.add_argument(
            '--status',
            choices=['PENDING', 'RUNNING', 'ALL'],
            default='ALL',
            help='Only cleanup sessions with specific status (default: ALL)',
        )
    
    def handle(self, *args, **options):
        """
        Execute the command.
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        try:
            self.stdout.write(self.style.SUCCESS('='*60))
            self.stdout.write(self.style.SUCCESS('CRAWL SESSION CLEANUP TOOL'))
            self.stdout.write(self.style.SUCCESS('='*60))
            
            dry_run = options['dry_run']
            hours = options['hours']
            force = options['force']
            status_filter = options['status']
            
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
            
            # Show current status
            self._show_current_status()
            
            # Find stuck sessions
            stuck_sessions = self._find_stuck_sessions(hours, force, status_filter)
            
            # Show what will be cleaned up
            self._show_cleanup_plan(stuck_sessions)
            
            # Execute cleanup if not dry run
            if not dry_run and stuck_sessions.exists():
                self._execute_cleanup(stuck_sessions)
            
            # Show final status
            self._show_final_status()
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise CommandError(f"Cleanup failed: {e}")
    
    def _show_current_status(self):
        """
        Show current session status.
        """
        try:
            total_sessions = CrawlSession.objects.count()
            pending_sessions = CrawlSession.objects.filter(status='PENDING').count()
            running_sessions = CrawlSession.objects.filter(status='RUNNING').count()
            completed_sessions = CrawlSession.objects.filter(status='COMPLETED').count()
            failed_sessions = CrawlSession.objects.filter(status='FAILED').count()
            cancelled_sessions = CrawlSession.objects.filter(status='CANCELLED').count()
            
            self.stdout.write(f"\nCURRENT SESSION STATUS:")
            self.stdout.write(f"  Total sessions: {total_sessions}")
            self.stdout.write(f"  PENDING: {pending_sessions}")
            self.stdout.write(f"  RUNNING: {running_sessions}")
            self.stdout.write(f"  COMPLETED: {completed_sessions}")
            self.stdout.write(f"  FAILED: {failed_sessions}")
            self.stdout.write(f"  CANCELLED: {cancelled_sessions}")
            
            # Show recent activity
            recent_sessions = CrawlSession.objects.filter(
                start_time__gte=timezone.now() - timedelta(hours=24)
            ).count()
            self.stdout.write(f"  Recent (24h): {recent_sessions}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing current status: {e}"))
    
    def _find_stuck_sessions(self, hours: int, force: bool, status_filter: str):
        """
        Find sessions that appear to be stuck.
        
        Args:
            hours: Sessions older than this are considered stuck
            force: Force cleanup regardless of age
            status_filter: Status filter to apply
            
        Returns:
            QuerySet: Stuck sessions
        """
        try:
            # Base query for problematic statuses
            if status_filter == 'ALL':
                base_query = CrawlSession.objects.filter(status__in=['PENDING', 'RUNNING'])
            else:
                base_query = CrawlSession.objects.filter(status=status_filter)
            
            if force:
                # Force cleanup of all matching sessions
                stuck_sessions = base_query
                self.stdout.write(f"\nFORCE MODE: Found {stuck_sessions.count()} sessions to cleanup")
            else:
                # Only cleanup old sessions
                cutoff_time = timezone.now() - timedelta(hours=hours)
                stuck_sessions = base_query.filter(start_time__lt=cutoff_time)
                self.stdout.write(f"\nFound {stuck_sessions.count()} sessions older than {hours} hours")
            
            return stuck_sessions
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error finding stuck sessions: {e}"))
            return CrawlSession.objects.none()
    
    def _show_cleanup_plan(self, stuck_sessions):
        """
        Show the cleanup plan.
        
        Args:
            stuck_sessions: QuerySet of sessions to cleanup
        """
        try:
            if not stuck_sessions.exists():
                self.stdout.write(f"\n✓ No stuck sessions found - nothing to cleanup!")
                return
            
            self.stdout.write(f"\nSESSIONS TO CLEANUP:")
            self.stdout.write("-" * 50)
            
            for session in stuck_sessions.order_by('-start_time')[:10]:  # Show first 10
                duration = timezone.now() - session.start_time
                self.stdout.write(
                    f"  ID: {session.pk:3d} | Status: {session.status:8s} | "
                    f"Started: {session.start_time.strftime('%m/%d %H:%M')} | "
                    f"Age: {duration.total_seconds()/3600:.1f}h | "
                    f"User: {session.user.username}"
                )
            
            if stuck_sessions.count() > 10:
                self.stdout.write(f"  ... and {stuck_sessions.count() - 10} more sessions")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing cleanup plan: {e}"))
    
    def _execute_cleanup(self, stuck_sessions):
        """
        Execute the cleanup by marking sessions as cancelled.
        
        Args:
            stuck_sessions: QuerySet of sessions to cleanup
        """
        try:
            if not stuck_sessions.exists():
                return
            
            self.stdout.write(f"\nEXECUTING CLEANUP...")
            
            cleanup_count = 0
            
            with transaction.atomic():
                for session in stuck_sessions:
                    try:
                        # Mark as cancelled with cleanup note
                        session.status = 'CANCELLED'
                        session.end_time = timezone.now()
                        
                        # Add cleanup note to error log
                        cleanup_note = f"[{timezone.now().isoformat()}] Session cleaned up by management command - was stuck in {session.status} status"
                        if session.error_log:
                            session.error_log = f"{session.error_log}\n\n{cleanup_note}"
                        else:
                            session.error_log = cleanup_note
                        
                        session.save(update_fields=['status', 'end_time', 'error_log'])
                        cleanup_count += 1
                        
                        self.stdout.write(f"  ✓ Cleaned up session {session.pk}")
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  ✗ Error cleaning session {session.pk}: {e}"))
            
            self.stdout.write(self.style.SUCCESS(f"\n✓ Successfully cleaned up {cleanup_count} sessions"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error executing cleanup: {e}"))
    
    def _show_final_status(self):
        """
        Show final status after cleanup.
        """
        try:
            pending_sessions = CrawlSession.objects.filter(status='PENDING').count()
            running_sessions = CrawlSession.objects.filter(status='RUNNING').count()
            
            self.stdout.write(f"\nFINAL STATUS:")
            self.stdout.write(f"  PENDING sessions: {pending_sessions}")
            self.stdout.write(f"  RUNNING sessions: {running_sessions}")
            
            if pending_sessions == 0 and running_sessions == 0:
                self.stdout.write(self.style.SUCCESS("✓ No stuck sessions remaining!"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠ Still have {pending_sessions + running_sessions} active sessions"))
            
            self.stdout.write(f"\nYou can now start a new crawl session.")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing final status: {e}"))