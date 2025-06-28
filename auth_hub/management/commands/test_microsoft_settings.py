"""
Management command to test Microsoft OAuth settings.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import msal


class Command(BaseCommand):
    help = 'Test Microsoft OAuth settings'

    def handle(self, *args, **options):
        self.stdout.write("Testing Microsoft OAuth Settings...")
        
        # Check if settings exist
        if not hasattr(settings, 'MICROSOFT_AUTH'):
            self.stdout.write(self.style.ERROR('MICROSOFT_AUTH not found in settings!'))
            return
        
        ms_settings = settings.MICROSOFT_AUTH
        
        # Check each required setting
        required_keys = ['CLIENT_ID', 'CLIENT_SECRET', 'REDIRECT_URI', 'SCOPES']
        for key in required_keys:
            if key in ms_settings:
                value = ms_settings[key]
                if key == 'CLIENT_SECRET':
                    # Don't print the full secret
                    display_value = f"{value[:4]}...{value[-4:]}" if value else "NOT SET"
                elif key == 'CLIENT_ID':
                    display_value = value if value else "NOT SET"
                else:
                    display_value = str(value)
                
                if value:
                    self.stdout.write(self.style.SUCCESS(f"✓ {key}: {display_value}"))
                else:
                    self.stdout.write(self.style.ERROR(f"✗ {key}: NOT SET"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ {key}: MISSING"))
        
        # Test MSAL initialization
        try:
            app = msal.ConfidentialClientApplication(
                ms_settings['CLIENT_ID'],
                authority=ms_settings.get('AUTHORITY', 'https://login.microsoftonline.com/common'),
                client_credential=ms_settings['CLIENT_SECRET'],
            )
            
            # Try to generate auth URL
            auth_url = app.get_authorization_request_url(
                ms_settings['SCOPES'],
                state="test",
                redirect_uri=ms_settings['REDIRECT_URI']
            )
            
            self.stdout.write(self.style.SUCCESS("\n✓ MSAL client initialized successfully"))
            self.stdout.write(f"\nSample auth URL: {auth_url[:100]}...")
            
            # Check if client_id is in the URL
            if 'client_id=' in auth_url:
                self.stdout.write(self.style.SUCCESS("✓ client_id parameter found in URL"))
            else:
                self.stdout.write(self.style.ERROR("✗ client_id parameter NOT found in URL"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Error initializing MSAL: {str(e)}"))