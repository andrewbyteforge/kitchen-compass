"""
Celery tasks for calendar synchronization.

Handles background synchronization of meal plans with Outlook calendar.
"""

import logging
from typing import List

from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone

from auth_hub.services.microsoft_auth import OutlookCalendarService
from meal_planner.models import MealSlot, CalendarEvent
from meal_planner.models import MealPlan

logger = logging.getLogger(__name__)


@shared_task
def sync_user_calendar(user_id: int) -> dict:
    """
    Synchronize a user's meal plan with their Outlook calendar.
    
    Args:
        user_id: ID of the user to sync
        
    Returns:
        Dictionary with sync results
    """
    try:
        user = User.objects.get(id=user_id)
        
        # Check if user has calendar sync enabled
        if not hasattr(user, 'microsoft_token') or not user.microsoft_token.calendar_sync_enabled:
            logger.info(f"Calendar sync not enabled for user {user.username}")
            return {'status': 'skipped', 'reason': 'sync_disabled'}
        
        # Initialize calendar service
        calendar_service = OutlookCalendarService(user)
        
        # Get meal slots that need syncing
        meal_slots = MealSlot.objects.filter(
            meal_plan__owner=user,
            meal_plan__is_active=True,
            date__gte=timezone.now().date()
        ).select_related('recipe', 'meal_type')
        
        results = {
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'errors': 0
        }
        
        # Process each meal slot
        for slot in meal_slots:
            try:
                # Check if event exists
                calendar_event = CalendarEvent.objects.filter(
                    meal_slot=slot,
                    user=user
                ).first()
                
                if calendar_event:
                    # Update existing event
                    if calendar_service.update_meal_event(
                        calendar_event.outlook_event_id,
                        slot
                    ):
                        calendar_event.sync_status = 'synced'
                        calendar_event.sync_error = ''
                        calendar_event.save()
                        results['updated'] += 1
                    else:
                        calendar_event.sync_status = 'error'
                        calendar_event.save()
                        results['errors'] += 1
                else:
                    # Create new event
                    event_id = calendar_service.create_meal_event(slot)
                    if event_id:
                        CalendarEvent.objects.create(
                            meal_slot=slot,
                            user=user,
                            outlook_event_id=event_id,
                            sync_status='synced'
                        )
                        results['created'] += 1
                    else:
                        results['errors'] += 1
                        
            except Exception as e:
                logger.error(f"Error syncing meal slot {slot.id}: {str(e)}")
                results['errors'] += 1
        
        # Update last sync time
        user.microsoft_token.last_sync = timezone.now()
        user.microsoft_token.save()
        
        logger.info(
            f"Calendar sync completed for user {user.username}: "
            f"Created: {results['created']}, Updated: {results['updated']}, "
            f"Errors: {results['errors']}"
        )
        
        return results
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {'status': 'error', 'reason': 'user_not_found'}
    except Exception as e:
        logger.error(f"Error in calendar sync task: {str(e)}")
        return {'status': 'error', 'reason': str(e)}


@shared_task
def sync_all_calendars() -> dict:
    """
    Sync calendars for all users with sync enabled.
    
    This task should be run periodically (e.g., every hour).
    
    Returns:
        Dictionary with overall sync results
    """
    try:
        # Get users with calendar sync enabled
        users = User.objects.filter(
            microsoft_token__isnull=False,
            microsoft_token__calendar_sync_enabled=True
        )
        
        results = {
            'users_synced': 0,
            'users_failed': 0,
            'total_events_created': 0,
            'total_events_updated': 0
        }
        
        for user in users:
            user_results = sync_user_calendar.delay(user.id)
            # Note: In production, you'd want to handle these results asynchronously
            
        logger.info(f"Initiated calendar sync for {users.count()} users")
        
        return {
            'status': 'initiated',
            'users_count': users.count()
        }
        
    except Exception as e:
        logger.error(f"Error in sync_all_calendars task: {str(e)}")
        return {'status': 'error', 'reason': str(e)}


@shared_task
def delete_calendar_event(event_id: str, user_id: int) -> bool:
    """
    Delete a calendar event from Outlook.
    
    Args:
        event_id: Outlook event ID to delete
        user_id: ID of the user who owns the event
        
    Returns:
        True if successful, False otherwise
    """
    try:
        user = User.objects.get(id=user_id)
        calendar_service = OutlookCalendarService(user)
        
        success = calendar_service.delete_meal_event(event_id)
        
        if success:
            # Remove from database
            CalendarEvent.objects.filter(
                outlook_event_id=event_id,
                user=user
            ).delete()
            
            logger.info(f"Deleted calendar event {event_id} for user {user.username}")
        
        return success
        
    except Exception as e:
        logger.error(f"Error deleting calendar event: {str(e)}")
        return False
    
@shared_task
def sync_meal_plan_to_outlook(meal_plan_id: int, user_id: int) -> dict:
    """
    Sync a specific meal plan to Outlook calendar, including:
      - Deleting remote events for slots that no longer have a recipe.
      - Updating existing events for slots with recipes.
      - Creating new events for new recipe slots.

    Args:
        meal_plan_id: ID of the meal plan to sync
        user_id: ID of the user

    Returns:
        dict with keys:
          success (bool),
          events_created (int),
          events_updated (int),
          events_deleted (int),
          errors (list of str)
    """
    from django.contrib.auth.models import User
    from auth_hub.services.microsoft_auth import OutlookCalendarService
    from meal_planner.models import MealPlan, CalendarEvent

    results = {
        'success': True,
        'events_created': 0,
        'events_updated': 0,
        'events_deleted': 0,
        'errors': []
    }

    try:
        user = User.objects.get(id=user_id)
        meal_plan = MealPlan.objects.get(id=meal_plan_id, owner=user)
        service = OutlookCalendarService(user)

        # 1) Gather existing CalendarEvent records for this plan
        existing = CalendarEvent.objects.filter(
            user=user,
            meal_slot__meal_plan=meal_plan
        )

        # 2) Build list of slots that still have recipes
        valid_slots = list(meal_plan.meal_slots.filter(recipe__isnull=False)
                                           .select_related('recipe', 'meal_type'))

        valid_ids = {slot.id for slot in valid_slots}

        # 3) Delete stale events (slots cleared in the app)
        stale_events = existing.exclude(meal_slot__id__in=valid_ids)
        for evt in stale_events:
            if service.delete_meal_event(evt.outlook_event_id):
                evt.delete()
                results['events_deleted'] += 1
                logger.info(f"Deleted stale Outlook event {evt.outlook_event_id} for slot {evt.meal_slot.id}")
            else:
                msg = f"Failed to delete stale event {evt.outlook_event_id}"
                results['errors'].append(msg)
                logger.error(msg)

        # 4) Create/update current slots
        for slot in valid_slots:
            cal_evt = existing.filter(meal_slot=slot).first()
            if cal_evt:
                ok = service.update_meal_event(cal_evt.outlook_event_id, slot)
                if ok:
                    cal_evt.sync_status = 'synced'
                    cal_evt.sync_error = ''
                    cal_evt.save()
                    results['events_updated'] += 1
                else:
                    err = f"Failed to update event for slot {slot.id}"
                    results['errors'].append(err)
                    logger.error(err)
            else:
                new_id = service.create_meal_event(slot)
                if new_id:
                    CalendarEvent.objects.create(
                        meal_slot=slot,
                        user=user,
                        outlook_event_id=new_id,
                        sync_status='synced'
                    )
                    results['events_created'] += 1
                else:
                    err = f"Failed to create event for slot {slot.id}"
                    results['errors'].append(err)
                    logger.error(err)

        # 5) Update last-sync timestamp
        token = user.microsoft_token
        token.last_sync = timezone.now()
        token.save()

    except Exception as e:
        logger.error(f"Error in sync_meal_plan_to_outlook: {e}", exc_info=True)
        results['success'] = False
        results['errors'].append(str(e))

    return results
