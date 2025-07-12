"""
Django management command to check crawler status and manage multiple crawlers.

File: asda_scraper/management/commands/crawler_status.py
"""

import logging
import threading
import time
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from asda_scraper.models import CrawlSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to check and manage crawler status.
    
    This command provides comprehensive information about running crawlers
    and helps identify if multiple crawlers are running simultaneously.
    """
    
    help = 'Check crawler status and manage multiple crawler instances'
    
    def add_arguments(self, parser):
        """
        Add command arguments.
        
        Args:
            parser: ArgumentParser instance
        """
        parser.add_argument(
            '--monitor',
            action='store_true',
            help='Monitor crawlers in real-time (updates every 10 seconds)',
        )
        parser.add_argument(
            '--show-threads',
            action='store_true',
            help='Show active Python threads that might be crawlers',
        )
        parser.add_argument(
            '--check-overlap',
            action='store_true',
            help='Check for overlapping crawler sessions',
        )
        parser.add_argument(
            '--kill-stuck',
            action='store_true',
            help='Mark stuck sessions as cancelled',
        )
        parser.add_argument(
            '--max-age-hours',
            type=int,
            default=2,
            help='Sessions older than this many hours are considered stuck (default: 2)',
        )
    
    def handle(self, *args, **options):
        """
        Execute the command.
        
        Args:
            *args: Command arguments
            **options: Command options
        """
        try:
            self.stdout.write(self.style.SUCCESS('='*80))
            self.stdout.write(self.style.SUCCESS('CRAWLER STATUS MONITOR'))
            self.stdout.write(self.style.SUCCESS('='*80))
            
            if options['monitor']:
                self._monitor_crawlers()
            elif options['check_overlap']:
                self._check_overlapping_sessions()
            elif options['kill_stuck']:
                self._kill_stuck_sessions(options['max_age_hours'])
            else:
                self._show_crawler_status(options['show_threads'])
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nMonitoring stopped by user"))
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise CommandError(f"Status check failed: {e}")
    
    def _show_crawler_status(self, show_threads: bool = False):
        """
        Show current crawler status.
        
        Args:
            show_threads: Whether to show thread information
        """
        try:
            # Show session status
            self._show_session_status()
            
            # Check for running crawlers
            running_crawlers = self._get_running_crawlers()
            
            # Show thread information if requested
            if show_threads:
                self._show_thread_information()
            
            # Show warnings if multiple crawlers detected
            if len(running_crawlers) > 1:
                self._show_multiple_crawler_warning(running_crawlers)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing crawler status: {e}"))
    
    def _show_session_status(self):
        """
        Show current session status with detailed information.
        """
        try:
            # Get session counts
            total_sessions = CrawlSession.objects.count()
            pending_sessions = CrawlSession.objects.filter(status='PENDING')
            running_sessions = CrawlSession.objects.filter(status='RUNNING')
            completed_sessions = CrawlSession.objects.filter(status='COMPLETED').count()
            failed_sessions = CrawlSession.objects.filter(status='FAILED').count()
            cancelled_sessions = CrawlSession.objects.filter(status='CANCELLED').count()
            
            self.stdout.write(f"\nSESSION STATUS OVERVIEW:")
            self.stdout.write(f"  Total sessions: {total_sessions}")
            self.stdout.write(f"  PENDING: {pending_sessions.count()}")
            self.stdout.write(f"  RUNNING: {running_sessions.count()}")
            self.stdout.write(f"  COMPLETED: {completed_sessions}")
            self.stdout.write(f"  FAILED: {failed_sessions}")
            self.stdout.write(f"  CANCELLED: {cancelled_sessions}")
            
            # Show active sessions in detail
            if pending_sessions.exists() or running_sessions.exists():
                self.stdout.write(f"\nACTIVE SESSIONS:")
                
                for session in pending_sessions:
                    age = timezone.now() - session.start_time
                    self.stdout.write(
                        f"  PENDING #{session.pk} - {session.get_crawl_type_display()} - "
                        f"Age: {self._format_duration(age)} - User: {session.user.username}"
                    )
                
                for session in running_sessions:
                    age = timezone.now() - session.start_time
                    # Get total categories from database
                    total_categories = self._get_total_categories()
                    self.stdout.write(
                        f"  RUNNING #{session.pk} - {session.get_crawl_type_display()} - "
                        f"Age: {self._format_duration(age)} - User: {session.user.username} - "
                        f"Categories: {session.categories_crawled}/{total_categories} - "
                        f"Products: {session.products_found}"
                    )
            else:
                self.stdout.write(f"\n✓ No active sessions currently running")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing session status: {e}"))
    
    def _get_running_crawlers(self):
        """
        Get list of currently running crawler sessions.
        
        Returns:
            list: List of running CrawlSession objects
        """
        return list(CrawlSession.objects.filter(status__in=['PENDING', 'RUNNING']))
    
    def _show_thread_information(self):
        """
        Show active Python threads that might be crawlers.
        """
        try:
            self.stdout.write(f"\nACTIVE THREADS:")
            
            active_threads = threading.enumerate()
            crawler_threads = []
            
            for thread in active_threads:
                thread_name = thread.name.lower()
                if any(keyword in thread_name for keyword in ['asda', 'crawler', 'scraper', 'selenium']):
                    crawler_threads.append(thread)
                
            if crawler_threads:
                for thread in crawler_threads:
                    self.stdout.write(f"  {thread.name} (ID: {thread.ident}) - Alive: {thread.is_alive()}")
            else:
                self.stdout.write(f"  No crawler-related threads detected")
            
            self.stdout.write(f"\nTotal active threads: {len(active_threads)}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing thread information: {e}"))
    
    def _show_multiple_crawler_warning(self, running_crawlers):
        """
        Show warning about multiple running crawlers.
        
        Args:
            running_crawlers: List of running crawler sessions
        """
        try:
            self.stdout.write(self.style.ERROR(f"\n⚠️  WARNING: MULTIPLE CRAWLERS DETECTED!"))
            self.stdout.write(self.style.ERROR(f"Found {len(running_crawlers)} active crawler sessions:"))
            
            for session in running_crawlers:
                age = timezone.now() - session.start_time
                self.stdout.write(
                    self.style.ERROR(
                        f"  - Session #{session.pk} ({session.status}) - "
                        f"Type: {session.get_crawl_type_display()} - "
                        f"Age: {self._format_duration(age)}"
                    )
                )
            
            self.stdout.write(self.style.ERROR(f"\nThis can cause:"))
            self.stdout.write(self.style.ERROR(f"  • Resource conflicts"))
            self.stdout.write(self.style.ERROR(f"  • Database locking"))
            self.stdout.write(self.style.ERROR(f"  • Rate limiting"))
            self.stdout.write(self.style.ERROR(f"  • Data corruption"))
            
            self.stdout.write(self.style.WARNING(f"\nRECOMMENDED ACTIONS:"))
            self.stdout.write(self.style.WARNING(f"  1. Stop unnecessary crawlers"))
            self.stdout.write(self.style.WARNING(f"  2. Use: python manage.py crawler_status --kill-stuck"))
            self.stdout.write(self.style.WARNING(f"  3. Wait for current session to complete"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error showing multiple crawler warning: {e}"))
    
    def _check_overlapping_sessions(self):
        """
        Check for overlapping crawler sessions that might conflict.
        """
        try:
            self.stdout.write(f"\nCHECKING FOR OVERLAPPING SESSIONS...")
            
            # Find sessions with overlapping time ranges
            running_sessions = CrawlSession.objects.filter(status='RUNNING')
            
            overlaps = []
            for i, session1 in enumerate(running_sessions):
                for session2 in running_sessions[i+1:]:
                    if self._sessions_overlap(session1, session2):
                        overlaps.append((session1, session2))
            
            if overlaps:
                self.stdout.write(self.style.ERROR(f"Found {len(overlaps)} overlapping session pairs:"))
                for session1, session2 in overlaps:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  - Session #{session1.pk} and #{session2.pk} are running simultaneously"
                        )
                    )
            else:
                self.stdout.write(self.style.SUCCESS("✓ No overlapping sessions detected"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error checking overlapping sessions: {e}"))
    
    def _sessions_overlap(self, session1, session2):
        """
        Check if two sessions have overlapping time ranges.
        
        Args:
            session1: First CrawlSession
            session2: Second CrawlSession
            
        Returns:
            bool: True if sessions overlap
        """
        try:
            # If both are currently running, they overlap
            if session1.status == 'RUNNING' and session2.status == 'RUNNING':
                return True
            
            # Check time ranges
            s1_start = session1.start_time
            s1_end = session1.end_time or timezone.now()
            s2_start = session2.start_time
            s2_end = session2.end_time or timezone.now()
            
            return not (s1_end <= s2_start or s2_end <= s1_start)
            
        except Exception:
            print("ERROR!!!!")



    def _format_duration(self, duration):
        """
        Format a timedelta as a human-readable string.
        
        Args:
            duration: timedelta object
            
        Returns:
            str: Formatted duration string
        """
        try:
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
                
        except Exception:
            return "Unknown"
    
    def _kill_stuck_sessions(self, max_age_hours: int):
        """
        Mark stuck sessions as cancelled.
        
        Args:
            max_age_hours: Maximum age in hours before session is considered stuck
        """
        try:
            cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
            
            stuck_sessions = CrawlSession.objects.filter(
                status__in=['PENDING', 'RUNNING'],
                start_time__lt=cutoff_time
            )
            
            if not stuck_sessions.exists():
                self.stdout.write(self.style.SUCCESS(f"✓ No stuck sessions found"))
                return
            
            self.stdout.write(f"Found {stuck_sessions.count()} stuck sessions:")
            
            for session in stuck_sessions:
                age = timezone.now() - session.start_time
                self.stdout.write(
                    f"  Session #{session.pk} - {session.status} - Age: {self._format_duration(age)}"
                )
            
            # Mark as cancelled
            with transaction.atomic():
                updated_count = stuck_sessions.update(
                    status='CANCELLED',
                    end_time=timezone.now(),
                    error_log=f"Marked as stuck by crawler_status command at {timezone.now()}"
                )
            
            self.stdout.write(self.style.SUCCESS(f"✓ Marked {updated_count} sessions as cancelled"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error killing stuck sessions: {e}"))
    
    def _monitor_crawlers(self):
        """
        Monitor crawlers in real-time with continuous updates.
        """
        try:
            self.stdout.write(f"Starting real-time crawler monitoring...")
            self.stdout.write(f"Press Ctrl+C to stop monitoring\n")
            
            while True:
                # Clear screen (basic version)
                self.stdout.write("\n" + "="*80)
                self.stdout.write(f"CRAWLER STATUS - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.stdout.write("="*80)
                
                # Show current status
                self._show_session_status()
                
                # Check for issues
                running_crawlers = self._get_running_crawlers()
                if len(running_crawlers) > 1:
                    self.stdout.write(self.style.ERROR(f"\n⚠️  {len(running_crawlers)} crawlers running simultaneously!"))
                
                # Wait before next update
                time.sleep(10)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nMonitoring stopped"))
    
    def _get_total_categories(self):
        """
        Get total number of active categories.
        
        Returns:
            int: Number of active categories
        """
        try:
            from asda_scraper.models import AsdaCategory
            return AsdaCategory.objects.filter(is_active=True).count()
        except Exception:
            return 0