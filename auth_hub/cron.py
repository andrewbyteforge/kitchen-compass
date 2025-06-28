"""
Cron jobs for the AuthHub application.

This module contains automated tasks for processing subscription changes
and sending notification emails.
"""

import logging
from datetime import timedelta

from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import UserProfile, ActivityLog

logger = logging.getLogger(__name__)


def process_pending_downgrades():
    """
    Process any pending subscription downgrades that are due.
    
    This function runs daily and checks for any pending downgrades where
    the scheduled date has passed.
    """
    logger.info("Starting pending downgrades processing...")
    
    # Find all profiles with pending downgrades that are due
    profiles_to_process = UserProfile.objects.filter(
        pending_subscription_tier__isnull=False,
        pending_tier_change_date__lte=timezone.now()
    )
    
    processed_count = 0
    error_count = 0
    
    for profile in profiles_to_process:
        try:
            old_tier = profile.subscription_tier
            new_tier = profile.pending_subscription_tier
            
            # Process the downgrade
            profile.subscription_tier = new_tier
            profile.pending_subscription_tier = None
            profile.pending_tier_change_date = None
            profile.subscription_updated_at = timezone.now()
            profile.save()
            
            # Log the activity
            ActivityLog.objects.create(
                user=profile.user,
                action='subscription_downgraded',
                details={
                    'from_tier': old_tier.name,
                    'to_tier': new_tier.name,
                    'automatic': True,
                    'scheduled_date': profile.pending_tier_change_date.isoformat() if profile.pending_tier_change_date else None
                }
            )
            
            # Send confirmation email
            _send_downgrade_completed_email(profile.user, old_tier, new_tier)
            
            processed_count += 1
            logger.info(f"Processed downgrade for user {profile.user.email}: {old_tier.name} -> {new_tier.name}")
            
        except Exception as e:
            error_count += 1
            logger.error(f"Error processing downgrade for user {profile.user.email}: {str(e)}")
    
    logger.info(f"Downgrade processing completed. Processed: {processed_count}, Errors: {error_count}")
    return f"Processed {processed_count} downgrades with {error_count} errors"


def send_downgrade_reminders():
    """
    Send reminder emails to users with pending downgrades.
    
    This function runs daily and sends reminders at specific intervals
    before the downgrade takes effect.
    """
    logger.info("Starting downgrade reminder emails...")
    
    # Define reminder intervals (days before downgrade)
    reminder_days = [7, 3, 1]
    
    sent_count = 0
    error_count = 0
    
    for days in reminder_days:
        # Find profiles where downgrade is exactly X days away
        target_date = timezone.now().date() + timedelta(days=days)
        
        profiles_to_notify = UserProfile.objects.filter(
            pending_subscription_tier__isnull=False,
            pending_tier_change_date__date=target_date
        )
        
        for profile in profiles_to_notify:
            try:
                _send_downgrade_reminder_email(profile.user, profile, days)
                sent_count += 1
                logger.info(f"Sent {days}-day reminder to {profile.user.email}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error sending reminder to {profile.user.email}: {str(e)}")
    
    logger.info(f"Downgrade reminders completed. Sent: {sent_count}, Errors: {error_count}")
    return f"Sent {sent_count} reminder emails with {error_count} errors"


def _send_downgrade_completed_email(user, old_tier, new_tier):
    """Send email confirming the downgrade has been processed."""
    context = {
        'user': user,
        'old_tier': old_tier,
        'new_tier': new_tier,
        'current_date': timezone.now(),
        'settings': settings,  # Add settings to context
    }
    
    html_message = render_to_string('auth_hub/emails/downgrade_completed.html', context)
    plain_message = render_to_string('auth_hub/emails/downgrade_completed.txt', context)
    
    send_mail(
        subject='Your KitchenCompass subscription has been changed',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def _send_downgrade_reminder_email(user, profile, days_until_downgrade):
    """Send reminder email about upcoming downgrade."""
    context = {
        'user': user,
        'profile': profile,
        'current_tier': profile.subscription_tier,
        'new_tier': profile.pending_subscription_tier,
        'days_until_downgrade': days_until_downgrade,
        'downgrade_date': profile.pending_tier_change_date,
        'cancel_url': f"{settings.SITE_URL}/auth/subscription/",
        'settings': settings,  # Add settings to context
    }
    
    # Determine urgency for subject line
    if days_until_downgrade == 1:
        urgency = "Tomorrow"
    elif days_until_downgrade == 3:
        urgency = "In 3 days"
    else:
        urgency = f"In {days_until_downgrade} days"
    
    html_message = render_to_string('auth_hub/emails/downgrade_reminder.html', context)
    plain_message = render_to_string('auth_hub/emails/downgrade_reminder.txt', context)
    
    send_mail(
        subject=f'Reminder: Your KitchenCompass subscription changes {urgency}',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )