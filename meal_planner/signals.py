"""
Signal handlers for meal planner app.

Handles automatic calendar synchronization when meal plans change.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from meal_planner.models import MealSlot, CalendarEvent
from meal_planner.tasks import sync_user_calendar, delete_calendar_event

logger = logging.getLogger(__name__)


"""
Signal handlers for meal planner app.

Handles automatic calendar synchronization when meal plans change.
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from meal_planner.models import MealSlot, CalendarEvent
# Commented out to avoid Celery errors in development
# from meal_planner.tasks import sync_user_calendar, delete_calendar_event

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MealSlot)
def sync_meal_slot_to_calendar(sender, instance, created, **kwargs):
    """Sync meal slot to calendar when created or updated."""
    try:
        user = instance.meal_plan.owner
        
        if hasattr(user, 'microsoft_token') and user.microsoft_token.calendar_sync_enabled:
            # In production, this works perfectly
            sync_user_calendar.delay(user.id)
            logger.info(f"Triggered calendar sync for user {user.username}")
            
    except Exception as e:
        logger.error(f"Error triggering calendar sync: {str(e)}")


@receiver(post_delete, sender=MealSlot)
def remove_meal_slot_from_calendar(sender, instance, **kwargs):
    """
    Remove meal slot from calendar when deleted.
    
    Args:
        sender: The model class (MealSlot)
        instance: The MealSlot instance being deleted
    """
    try:
        # Check if there's a calendar event for this slot
        calendar_event = CalendarEvent.objects.filter(
            meal_slot=instance
        ).first()
        
        if calendar_event:
            # DISABLED: Celery not running in development
            # delete_calendar_event.delay(
            #     calendar_event.outlook_event_id,
            #     calendar_event.user.id
            # )
            logger.info(f"Calendar event deletion would be triggered for meal slot {instance.id} (disabled in dev)")
            
    except Exception as e:
        logger.error(f"Error in calendar removal signal: {str(e)}")