"""
Management command to stop all running crawler sessions.

File: asda_scraper/management/commands/stop_all_crawlers.py
"""

import logging
import psutil
import os
from django.core.management.base import BaseCommand
from django.utils import timezone

from asda_scraper.models import CrawlSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Stop all running crawler sessions and related browser processes.
    """
    
    help = 'Stop all running crawler sessions and browser processes'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force kill browser processes even if they seem unrelated'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be stopped without actually stopping'
        )
    
    def handle(self, *args, **options):
        """Execute the stop all crawlers command."""
        try:
            self.stdout.write("="*60)
            self.stdout.write(self.style.WARNING("STOPPING ALL CRAWLERS"))
            self.stdout.write("="*60)
            
            force = options['force']
            dry_run = options['dry_run']
            
            if dry_run:
                self.stdout.write(self.style.WARNING("DRY RUN MODE - Nothing will actually be stopped"))
                self.stdout.write("")
            
            # Step 1: Update database sessions
            stopped_sessions = self._stop_database_sessions(dry_run)
            
            # Step 2: Kill browser processes
            killed_processes = self._kill_browser_processes(force, dry_run)
            
            # Step 3: Summary
            self._display_summary(stopped_sessions, killed_processes, dry_run)
            
        except Exception as e:
            logger.error(f"Stop all crawlers failed: {e}")
            self.stdout.write(self.style.ERROR(f"Command failed: {e}"))
    
    def _stop_database_sessions(self, dry_run=False):
        """Stop all running crawl sessions in database."""
        try:
            # Find running sessions
            running_sessions = CrawlSession.objects.filter(
                status__in=['PENDING', 'RUNNING', 'PAUSED']
            )
            
            session_count = running_sessions.count()
            
            if session_count == 0:
                self.stdout.write("No running crawl sessions found in database")
                return 0
            
            self.stdout.write(f"Found {session_count} running crawl sessions:")
            
            for session in running_sessions:
                self.stdout.write(f"  • Session {session.pk}: {session.crawl_type} - {session.status}")
                self.stdout.write(f"    Started: {session.start_time}")
                self.stdout.write(f"    User: {session.user.username}")
            
            if not dry_run:
                # Update all running sessions to CANCELLED
                updated_count = running_sessions.update(
                    status='CANCELLED',
                    end_time=timezone.now(),
                    error_log='Stopped by stop_all_crawlers command'
                )
                
                self.stdout.write(f"✅ Cancelled {updated_count} database sessions")
                return updated_count
            else:
                self.stdout.write(f"Would cancel {session_count} database sessions")
                return session_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error stopping database sessions: {e}"))
            return 0
    
    def _kill_browser_processes(self, force=False, dry_run=False):
        """Kill browser processes that might be running crawlers."""
        try:
            browser_processes = []
            
            # Look for Chrome/Chromium processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower()
                    cmdline = ' '.join(proc_info['cmdline'] or []).lower()
                    
                    # Check if this looks like a crawler browser process
                    is_crawler_browser = False
                    
                    if 'chrome' in proc_name or 'chromium' in proc_name:
                        # Look for signs this is a crawler browser
                        crawler_indicators = [
                            'asda', 'groceries.asda.com', 'selenium', 'webdriver',
                            'kitchencompass', 'nutrition', 'stealth', 'crawler'
                        ]
                        
                        if any(indicator in cmdline for indicator in crawler_indicators):
                            is_crawler_browser = True
                        elif force:
                            # If force flag is set, consider all Chrome processes
                            is_crawler_browser = True
                    
                    if is_crawler_browser:
                        browser_processes.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'cmdline': cmdline[:100] + '...' if len(cmdline) > 100 else cmdline
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if not browser_processes:
                self.stdout.write("No crawler browser processes found")
                return 0
            
            self.stdout.write(f"Found {len(browser_processes)} browser processes:")
            
            killed_count = 0
            for proc in browser_processes:
                self.stdout.write(f"  • PID {proc['pid']}: {proc['name']}")
                self.stdout.write(f"    Command: {proc['cmdline']}")
                
                if not dry_run:
                    try:
                        process = psutil.Process(proc['pid'])
                        process.terminate()  # Try graceful termination first
                        
                        # Wait a bit for graceful termination
                        try:
                            process.wait(timeout=3)
                            self.stdout.write(f"    ✅ Terminated gracefully")
                        except psutil.TimeoutExpired:
                            # Force kill if graceful termination failed
                            process.kill()
                            self.stdout.write(f"    💥 Force killed")
                        
                        killed_count += 1
                        
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        self.stdout.write(f"    ❌ Could not kill: {e}")
                else:
                    self.stdout.write(f"    Would terminate this process")
                    killed_count += 1
            
            if not dry_run and killed_count > 0:
                self.stdout.write(f"✅ Killed {killed_count} browser processes")
            
            return killed_count
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error killing browser processes: {e}"))
            return 0
    
    def _display_summary(self, stopped_sessions, killed_processes, dry_run):
        """Display summary of what was stopped."""
        self.stdout.write("")
        self.stdout.write("="*60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN SUMMARY"))
            self.stdout.write(f"Would stop {stopped_sessions} crawl sessions")
            self.stdout.write(f"Would kill {killed_processes} browser processes")
        else:
            self.stdout.write(self.style.SUCCESS("STOP SUMMARY"))
            self.stdout.write(f"Stopped {stopped_sessions} crawl sessions")
            self.stdout.write(f"Killed {killed_processes} browser processes")
        
        self.stdout.write("="*60)
        
        if not dry_run:
            if stopped_sessions > 0 or killed_processes > 0:
                self.stdout.write("✅ All crawlers have been stopped")
            else:
                self.stdout.write("ℹ️  No active crawlers were found")
            
            self.stdout.write("")
            self.stdout.write("NEXT STEPS:")
            self.stdout.write("• Check dashboard to verify sessions are stopped")
            self.stdout.write("• Wait a moment before starting new crawls")
            self.stdout.write("• Use 'python manage.py stealth_nutrition_crawler' to start fresh")
        else:
            self.stdout.write("")
            self.stdout.write("Run without --dry-run to actually stop the crawlers")