"""
Microsoft OAuth and Calendar Service

Handles authentication and calendar operations with Microsoft Graph API.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List

import msal
import requests
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User

from auth_hub.models import MicrosoftOAuthToken

logger = logging.getLogger(__name__)


class MicrosoftAuthService:
    """
    Service for handling Microsoft OAuth authentication.
    
    This class manages the OAuth flow for Microsoft accounts
    and provides methods for token management.
    """
    
    def __init__(self):
        """Initialize the Microsoft authentication service."""
        self.client_id = settings.MICROSOFT_AUTH['CLIENT_ID']
        self.client_secret = settings.MICROSOFT_AUTH['CLIENT_SECRET']
        self.tenant_id = settings.MICROSOFT_AUTH['TENANT_ID']
        self.redirect_uri = settings.MICROSOFT_AUTH['REDIRECT_URI']
        
        # Remove offline_access from the main scopes list as MSAL handles it automatically
        self.scopes = [scope for scope in settings.MICROSOFT_AUTH['SCOPES'] 
                    if scope not in ['offline_access', 'openid', 'profile']]
        
        self.authority = settings.MICROSOFT_AUTH['AUTHORITY']
        
        # Initialize MSAL client
        self.msal_app = msal.ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
        )
        
    def get_auth_url(self, state: str) -> str:
        """
        Generate the authorization URL for Microsoft OAuth.
        
        Args:
            state: A unique state parameter for CSRF protection
            
        Returns:
            The authorization URL to redirect the user to
        """
        try:
            # Debug logging
            logger.info(f"Generating auth URL with client_id: {self.client_id}")
            logger.info(f"Redirect URI: {self.redirect_uri}")
            logger.info(f"Scopes: {self.scopes}")
            
            auth_url = self.msal_app.get_authorization_request_url(
                self.scopes,
                state=state,
                redirect_uri=self.redirect_uri,
                prompt='select_account'  # ADD THIS LINE - Forces account selection
            )
            
            logger.info(f"Generated auth URL: {auth_url}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}")
            raise

    def get_token_from_code(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.
        
        Args:
            code: The authorization code from Microsoft
            
        Returns:
            Dictionary containing access token and related data
        """
        try:
            result = self.msal_app.acquire_token_by_authorization_code(
                code,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri
            )
            
            if "error" in result:
                logger.error(f"Error acquiring token: {result.get('error_description')}")
                raise Exception(result.get('error_description'))
            
            logger.info("Successfully acquired access token")
            return result
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            raise
    
    def refresh_access_token(self, user: User) -> Optional[str]:
        """
        Refresh the access token using the refresh token.
        
        Args:
            user: The user whose token needs refreshing
            
        Returns:
            New access token or None if refresh failed
        """
        try:
            token_obj = user.microsoft_token
            
            result = self.msal_app.acquire_token_by_refresh_token(
                token_obj.refresh_token,
                scopes=self.scopes
            )
            
            if "error" in result:
                logger.error(f"Error refreshing token: {result.get('error_description')}")
                return None
            
            # Update stored tokens
            token_obj.access_token = result['access_token']
            token_obj.refresh_token = result.get('refresh_token', token_obj.refresh_token)
            token_obj.token_expires = timezone.now() + timedelta(seconds=result['expires_in'])
            token_obj.save()
            
            logger.info(f"Refreshed access token for user {user.username}")
            return result['access_token']
            
        except Exception as e:
            logger.error(f"Error refreshing token for user {user.username}: {str(e)}")
            return None
    
    def save_tokens(self, user: User, token_data: Dict) -> MicrosoftOAuthToken:
        """
        Save or update OAuth tokens for a user.
        
        Args:
            user: The user to save tokens for
            token_data: Dictionary containing token information
            
        Returns:
            The created or updated MicrosoftOAuthToken object
        """
        try:
            token_obj, created = MicrosoftOAuthToken.objects.update_or_create(
                user=user,
                defaults={
                    'access_token': token_data['access_token'],
                    'refresh_token': token_data.get('refresh_token', ''),
                    'token_expires': timezone.now() + timedelta(seconds=token_data['expires_in'])
                }
            )
            
            action = "Created" if created else "Updated"
            logger.info(f"{action} Microsoft OAuth token for user {user.username}")
            
            return token_obj
            
        except Exception as e:
            logger.error(f"Error saving tokens for user {user.username}: {str(e)}")
            raise


class OutlookCalendarService:
    """
    Service for interacting with Outlook Calendar via Microsoft Graph API.
    
    This class provides methods to create, update, and delete
    calendar events in a user's Outlook calendar.
    """
    
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    
    def __init__(self, user: User):
        """
        Initialize the calendar service for a specific user.
        
        Args:
            user: The user whose calendar to interact with
        """
        self.user = user
        self.auth_service = MicrosoftAuthService()
        self._access_token = None
    
    @property
    def access_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if necessary.
        
        Returns:
            Valid access token or None if unavailable
        """
        try:
            token_obj = self.user.microsoft_token
            
            # Check if token exists
            if not token_obj:
                logger.warning(f"No Microsoft token found for user {self.user.username}")
                return None
            
            # Refresh if expired
            if token_obj.is_token_expired():
                logger.info(f"Token expired for user {self.user.username}, refreshing...")
                new_token = self.auth_service.refresh_access_token(self.user)
                if not new_token:
                    return None
                self._access_token = new_token
            else:
                self._access_token = token_obj.access_token
            
            return self._access_token
            
        except Exception as e:
            logger.error(f"Error getting access token: {str(e)}")
            return None
    
    def create_meal_event(self, meal_slot):
        """Create a calendar event for a meal slot."""
        try:
            # FIXED: Check if meal_slot has a recipe before proceeding
            if not meal_slot.recipe:
                logger.warning(
                    f"Skipping calendar event creation for meal slot {meal_slot.id} - no recipe assigned"
                )
                return None
            
            # Log the date being used
            logger.info(f"Creating calendar event for meal on {meal_slot.date}")
            
            # Format event time based on meal type
            meal_times = {
                'breakfast': '08:00',
                'lunch': '12:00',
                'dinner': '18:00',
                'snack': '15:00'
            }
            
            time_str = meal_times.get(
                meal_slot.meal_type.name.lower(),
                '12:00'
            )
            
            # Create datetime for the event
            event_datetime = datetime.combine(
                meal_slot.date,
                datetime.strptime(time_str, '%H:%M').time()
            )
            
            # Log the full datetime
            logger.info(f"Event datetime: {event_datetime}")
            
            # Convert to ISO format
            start_time = event_datetime.isoformat()
            end_time = (event_datetime + timedelta(hours=1)).isoformat()
            
            # FIXED: Safe access to recipe attributes
            recipe_title = meal_slot.recipe.title if meal_slot.recipe else "No Recipe"
            prep_time = getattr(meal_slot.recipe, 'prep_time', 0) or 0
            cook_time = getattr(meal_slot.recipe, 'cook_time', 0) or 0
            
            # Create the event body
            event = {
                'subject': f'{meal_slot.meal_type.name}: {recipe_title}',
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'Europe/London'  # Change this to your timezone
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'Europe/London'  # Change this to your timezone
                },
                'body': {
                    'contentType': 'HTML',
                    'content': f'''
                        <h3>{recipe_title}</h3>
                        <p><strong>Servings:</strong> {meal_slot.servings}</p>
                        <p><strong>Prep Time:</strong> {prep_time} minutes</p>
                        <p><strong>Cook Time:</strong> {cook_time} minutes</p>
                        {f'<p><strong>Notes:</strong> {meal_slot.notes}</p>' if meal_slot.notes else ''}
                        <p><em>Created by KitchenCompass</em></p>
                    '''
                },
                'showAs': 'busy',  # This makes it more visible
                'isReminderOn': True,
                'reminderMinutesBeforeStart': 30
            }
            
            # Make the API request
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f'{self.GRAPH_API_BASE}/me/events',
                headers=headers,
                json=event
            )
            
            if response.status_code == 201:
                event_data = response.json()
                logger.info(f"Created calendar event {event_data['id']}")
                return event_data['id']
            else:
                logger.error(f"Failed to create event: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating calendar event: {str(e)}")
            return None

    def update_meal_event(self, event_id: str, meal_slot) -> bool:
        """
        Update an existing calendar event.
        
        Args:
            event_id: The Outlook event ID to update
            meal_slot: Updated MealSlot object
            
        Returns:
            True if successful, False otherwise
        """
        if not self.access_token:
            logger.error("No valid access token available")
            return False
        
        try:
            # FIXED: Check if meal_slot has a recipe before proceeding
            if not meal_slot.recipe:
                logger.warning(
                    f"Cannot update calendar event {event_id} - meal slot {meal_slot.id} has no recipe"
                )
                # If recipe was removed, delete the event instead
                return self.delete_meal_event(event_id)
            
            # FIXED: Safe access to recipe attributes
            recipe_title = meal_slot.recipe.title if meal_slot.recipe else "No Recipe"
            prep_time = getattr(meal_slot.recipe, 'prep_time', 0) or 0
            cook_time = getattr(meal_slot.recipe, 'cook_time', 0) or 0
            
            # Build updated event data using the existing create method's structure
            event = {
                'subject': f'{meal_slot.meal_type.name}: {recipe_title}',
                'body': {
                    'contentType': 'HTML',
                    'content': f'''
                        <h3>{recipe_title}</h3>
                        <p><strong>Servings:</strong> {meal_slot.servings}</p>
                        <p><strong>Prep Time:</strong> {prep_time} minutes</p>
                        <p><strong>Cook Time:</strong> {cook_time} minutes</p>
                        {f'<p><strong>Notes:</strong> {meal_slot.notes}</p>' if meal_slot.notes else ''}
                        <p><em>Updated by KitchenCompass</em></p>
                    '''
                }
            }
            
            # Make API request
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.patch(
                f"{self.GRAPH_API_BASE}/me/events/{event_id}",
                headers=headers,
                json=event
            )
            
            if response.status_code == 200:
                logger.info(f"Updated calendar event {event_id}")
                return True
            elif response.status_code == 404:
                logger.warning(f"Calendar event {event_id} not found in Outlook")
                return False
            else:
                logger.error(f"Failed to update calendar event: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating calendar event: {str(e)}")
            return False

    def delete_meal_event(self, event_id: str) -> bool:
        """
        Delete a calendar event from Outlook via Microsoft Graph.

        Args:
            event_id: Outlook event ID to delete.

        Returns:
            True if deletion succeeded (HTTP 200 or 204), False otherwise.
        """
        token = self.access_token
        if not token:
            logger.error(f"Cannot delete event {event_id}: no valid access token")
            return False

        url = f"{self.GRAPH_API_BASE}/me/events/{event_id}"
        headers = {
            'Authorization': f'Bearer {token}'
        }

        try:
            logger.info(f"Sending DELETE to Outlook event {event_id} at {url}")
            response = requests.delete(url, headers=headers)
            status = response.status_code

            if status in (200, 204):
                logger.info(f"Successfully deleted Outlook event {event_id} (status {status})")
                return True
            elif status == 404:
                logger.warning(f"Outlook event {event_id} not found (may already be deleted)")
                return True  # Consider as success since goal is achieved
            else:
                logger.error(
                    f"Failed to delete Outlook event {event_id}: "
                    f"status={status}, response={response.text}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Exception while deleting Outlook event {event_id}: {e}",
                exc_info=True
            )
            return False

    def _build_event_data(self, meal_slot) -> Dict:
        """
        Build event data for Microsoft Graph API.
        
        Args:
            meal_slot: MealSlot object
            
        Returns:
            Dictionary with event data
        """
        # FIXED: Check if recipe exists before accessing attributes
        if not meal_slot.recipe:
            logger.warning(f"Building event data for meal slot {meal_slot.id} without recipe")
            recipe_title = "No Recipe Selected"
            prep_time = 0
            cook_time = 0
        else:
            recipe_title = meal_slot.recipe.title
            prep_time = getattr(meal_slot.recipe, 'prep_time', 0) or 0
            cook_time = getattr(meal_slot.recipe, 'cook_time', 0) or 0
        
        # Calculate event time based on meal type
        meal_times = {
            'breakfast': (7, 0),   # 7:00 AM
            'lunch': (12, 0),      # 12:00 PM
            'dinner': (18, 0),     # 6:00 PM
            'snack': (15, 0),      # 3:00 PM
        }
        
        hour, minute = meal_times.get(
            meal_slot.meal_type.name.lower(),
            (12, 0)  # Default to noon
        )
        
        # Build start and end times
        start_datetime = datetime.combine(
            meal_slot.date,
            datetime.min.time().replace(hour=hour, minute=minute)
        )
        end_datetime = start_datetime + timedelta(hours=1)
        
        # Build event title and body
        title = f"{meal_slot.meal_type.name}: {recipe_title}"
        
        body_content = f"<h3>🍽️ {meal_slot.meal_type.name}</h3>"
        body_content += f"<p><strong>Recipe:</strong> {recipe_title}</p>"
        body_content += f"<p><strong>Servings:</strong> {meal_slot.servings}</p>"
        
        if prep_time or cook_time:
            total_time = prep_time + cook_time
            body_content += f"<p><strong>Total Time:</strong> {total_time} minutes</p>"
        
        if meal_slot.notes:
            body_content += f"<p><strong>Notes:</strong> {meal_slot.notes}</p>"
        
        body_content += '<p><em>Created by KitchenCompass</em></p>'
        
        return {
            "subject": title,
            "body": {
                "contentType": "HTML",
                "content": body_content
            },
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": "UTC"
            },
            "categories": ["KitchenCompass", "Meal Planning"],
            "showAs": "free",
            "isReminderOn": True,
            "reminderMinutesBeforeStart": 30
        }