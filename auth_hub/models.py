"""
Models for the AuthHub application.

This module contains models for user profiles, subscriptions, and menu sharing
functionality in the KitchenCompass application.
"""

import logging
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class SubscriptionTier(models.Model):
    """
    Model representing subscription tiers available in the application.
    
    Attributes:
        name: The display name of the tier (e.g., 'Home Cook', 'Sous Chef')
        slug: URL-friendly version of the name
        price: Price in cents (integer to avoid floating point issues)
        stripe_price_id: Stripe's price ID for recurring subscriptions
        features: JSON field storing list of features
        max_shared_menus: Maximum number of people user can share menus with
        max_menu_days: Maximum days of menu planning allowed
        is_active: Whether this tier is currently available
    """
    
    TIER_CHOICES = [
        ('FREE', 'Home Cook'),
        ('STARTER', 'Sous Chef'),
        ('PREMIUM', 'Master Chef'),
    ]
    
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)
    tier_type = models.CharField(max_length=20, choices=TIER_CHOICES, unique=True)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    stripe_price_id = models.CharField(max_length=255, blank=True)
    features = models.JSONField(default=list)
    max_shared_menus = models.IntegerField(default=0, help_text="0 means unlimited for paid tiers, none for free")
    max_menu_days = models.IntegerField(default=7, help_text="Maximum days for menu planning")
    max_recipes = models.IntegerField(default=-1, help_text="-1 means unlimited")
    max_menus = models.IntegerField(default=-1, help_text="-1 means unlimited")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @classmethod
    def get_free_tier(cls):
        """
        Get or create the free tier.
        
        This method ensures there's always a free tier available
        for new users or as a fallback.
        
        Returns:
            SubscriptionTier: The free tier instance
        """
        free_tier, created = cls.objects.get_or_create(
            tier_type='FREE',
            defaults={
                'name': 'Home Cook',
                'slug': 'home-cook',
                'price': 0.00,
                'max_recipes': 10,
                'max_menus': 3,
                'max_shared_menus': 0,
                'max_menu_days': 7,
                'features': [
                    'Store up to 10 recipes',
                    'Create up to 3 meal plans',
                    '7-day meal planning',
                    'Basic shopping lists',
                    'Community support'
                ],
                'is_active': True
            }
        )
        if created:
            logger.info("Created free subscription tier")
        return free_tier
    
    class Meta:
        ordering = ['price']
        verbose_name = "Subscription Tier"
        verbose_name_plural = "Subscription Tiers"
    
    def __str__(self):
        """String representation of the subscription tier."""
        return f"{self.name} - ${self.price}/month"
    
    def save(self, *args, **kwargs):
        """Override save to log tier changes."""
        if self.pk:
            logger.info(f"Subscription tier '{self.name}' updated by user")
        else:
            logger.info(f"New subscription tier '{self.name}' created")
        super().save(*args, **kwargs)

    


class UserProfile(models.Model):
    """
    Extended user profile for KitchenCompass users.
    
    Attributes:
        user: One-to-one relationship with Django User model
        subscription_tier: Current subscription tier
        stripe_customer_id: Stripe customer ID for payment processing
        subscription_status: Current status of subscription
        subscription_end_date: When current subscription period ends
        trial_end_date: When free trial ends (if applicable)
        preferences: JSON field for user preferences
    """
    
    SUBSCRIPTION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('past_due', 'Past Due'),
        ('trial', 'Trial'),
        ('inactive', 'Inactive'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    subscription_tier = models.ForeignKey(
        SubscriptionTier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscribers'
    )
    
    # Downgrade support fields
    pending_subscription_tier = models.ForeignKey(
        SubscriptionTier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_profiles',
        help_text='Tier to switch to at the end of billing period'
    )
    
    pending_tier_change_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date when the tier change will take effect'
    )

    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='inactive'
    )
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    subscription_updated_at = models.DateTimeField(auto_now=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    
    # User preferences
    preferences = models.JSONField(default=dict, blank=True)
    dietary_restrictions = models.JSONField(default=list, blank=True)
    
    # Profile stats
    menus_created = models.IntegerField(default=0)
    recipes_saved = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        """String representation of the user profile."""
        return f"{self.user.email} - {self.subscription_tier.name if self.subscription_tier else 'No subscription'}"
    
    @property
    def is_subscription_active(self):
        """Check if user has an active subscription."""
        if self.subscription_status != 'active':
            return False
        if self.subscription_end_date and self.subscription_end_date < timezone.now():
            return False
        return True
    
    @property
    def can_share_menus(self):
        """Check if user can share menus based on their subscription."""
        if not self.subscription_tier:
            return False
        # Free tier (tier_type='FREE') cannot share
        if self.subscription_tier.tier_type == 'FREE':
            return False
        return self.subscription_tier.max_shared_menus != 0
    
    @property
    def remaining_shares(self):
        """Calculate remaining menu shares for the user."""
        if not self.subscription_tier:
            return 0
        
        # Free tier cannot share
        if self.subscription_tier.tier_type == 'FREE':
            return 0
            
        # Unlimited sharing for paid tiers with max_shared_menus = 0
        if self.subscription_tier.max_shared_menus == 0:
            return float('inf')
        
        active_shares = self.shared_menus.filter(is_active=True).count()
        return max(0, self.subscription_tier.max_shared_menus - active_shares)
    
    def upgrade_subscription(self, new_tier, stripe_subscription_id=None):
        """
        Upgrade user's subscription to a new tier.
        
        Args:
            new_tier: The new SubscriptionTier instance
            stripe_subscription_id: Stripe subscription ID if applicable
        """
        old_tier = self.subscription_tier
        self.subscription_tier = new_tier
        self.subscription_status = 'active'
        self.stripe_subscription_id = stripe_subscription_id or ''
        
        if new_tier.price > 0:
            # Paid subscription - set end date to 30 days from now
            self.subscription_end_date = timezone.now() + timedelta(days=30)
        else:
            # Free tier - no end date
            self.subscription_end_date = None
            
        self.save()
        
        logger.info(
            f"User {self.user.email} upgraded from "
            f"{old_tier.name if old_tier else 'None'} to {new_tier.name}"
        )
    
    def process_pending_subscription_change(self):
        """
        Process any pending subscription changes if the date has passed.
        This should be called by a periodic task (e.g., Celery beat).
        """
        if (self.pending_subscription_tier and 
            self.pending_tier_change_date and 
            timezone.now() >= self.pending_tier_change_date):
            
            old_tier = self.subscription_tier
            self.subscription_tier = self.pending_subscription_tier
            self.pending_subscription_tier = None
            self.pending_tier_change_date = None
            self.subscription_updated_at = timezone.now()
            self.save()
            
            # Log the automatic downgrade
            from .views import log_activity
            log_activity(
                self.user,
                'subscription_downgraded',
                {
                    'from_tier': old_tier.name,
                    'to_tier': self.subscription_tier.name,
                    'automatic': True
                }
            )
            
            return True
        return False
    
    def cancel_subscription(self):
        """Cancel the user's subscription."""
        self.subscription_status = 'cancelled'
        self.save()
        logger.info(f"User {self.user.email} cancelled their subscription")
    
    def save(self, *args, **kwargs):
        """Override save to ensure free tier is assigned to new users."""
        if not self.pk and not self.subscription_tier:
            # New user - assign free tier
            try:
                free_tier = SubscriptionTier.objects.get(tier_type='FREE')
                self.subscription_tier = free_tier
                self.subscription_status = 'active'
                logger.info(f"New user {self.user.email} assigned free tier")
            except SubscriptionTier.DoesNotExist:
                logger.warning("Free tier not found for new user")
                
        super().save(*args, **kwargs)


class MenuShare(models.Model):
    """
    Model for sharing menus between users.
    
    Attributes:
        owner: The user who owns and shares the menu
        shared_with_email: Email address of the person to share with
        shared_with_user: The user account if they're registered
        token: Unique token for accepting the share invitation
        is_active: Whether the share is currently active
        accepted_at: When the invitation was accepted
    """
    
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shared_menus'
    )
    shared_with_email = models.EmailField()
    shared_with_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_menus',
        null=True,
        blank=True
    )
    token = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    # Menu access permissions
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_reshare = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Menu Share"
        verbose_name_plural = "Menu Shares"
        unique_together = ['owner', 'shared_with_email']
        ordering = ['-created_at']
    
    def __str__(self):
        """String representation of the menu share."""
        return f"{self.owner.email} → {self.shared_with_email}"
    
    def accept_invitation(self, user):
        """
        Accept a menu share invitation.
        
        Args:
            user: The user accepting the invitation
        """
        self.shared_with_user = user
        self.accepted_at = timezone.now()
        self.save()
        
        logger.info(
            f"Menu share invitation from {self.owner.email} "
            f"accepted by {user.email}"
        )
    
    def revoke(self):
        """Revoke a menu share."""
        self.is_active = False
        self.save()
        
        logger.info(
            f"Menu share from {self.owner.email} to "
            f"{self.shared_with_email} revoked"
        )
    
    @property
    def is_expired(self):
        """Check if the invitation has expired."""
        return timezone.now() > self.expires_at
    
    @property
    def status(self):
        """Get the current status of the menu share."""
        if not self.is_active:
            return "Revoked"
        elif self.is_expired:
            return "Expired"
        elif self.accepted_at:
            return "Accepted"
        else:
            return "Pending"
    
    def save(self, *args, **kwargs):
        """Override save to generate token and set expiration."""
        if not self.token:
            # Generate a unique token for the invitation
            import secrets
            self.token = secrets.token_urlsafe(48)
            
        if not self.expires_at:
            # Set expiration to 7 days from now
            self.expires_at = timezone.now() + timedelta(days=7)
            
        super().save(*args, **kwargs)


class ActivityLog(models.Model):
    """
    Model for logging user activities in the application.
    
    This provides an audit trail for important user actions.
    """
    
    ACTION_CHOICES = [
        ('login', 'User Login'),
        ('logout', 'User Logout'),
        ('register', 'User Registration'),
        ('subscription_change', 'Subscription Change'),
        ('subscription_upgraded', 'Subscription Upgraded'),
        ('subscription_downgraded', 'Subscription Downgraded'),
        ('subscription_downgrade_scheduled', 'Downgrade Scheduled'),
        ('subscription_downgrade_cancelled', 'Downgrade Cancelled'),
        ('menu_shared', 'Menu Shared'),
        ('menu_accepted', 'Menu Share Accepted'),
        ('profile_updated', 'Profile Updated'),
        ('password_changed', 'Password Changed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
        ]
    
    def __str__(self):
        """String representation of the activity log."""
        return f"{self.user.email} - {self.get_action_display()} - {self.created_at}"
    


# Add this model to your existing models.py

class MicrosoftOAuthToken(models.Model):
    """
    Stores Microsoft OAuth tokens for calendar access.
    
    This model securely stores the access and refresh tokens
    needed to interact with a user's Outlook calendar.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='microsoft_token'
    )
    access_token = models.TextField(
        help_text="Encrypted access token for Microsoft Graph API"
    )
    refresh_token = models.TextField(
        help_text="Encrypted refresh token for token renewal"
    )
    token_expires = models.DateTimeField(
        help_text="When the access token expires"
    )
    calendar_sync_enabled = models.BooleanField(
        default=True,
        help_text="Whether calendar sync is enabled for this user"
    )
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time calendar was synchronized"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'auth_hub_microsoft_oauth_token'
        verbose_name = 'Microsoft OAuth Token'
        verbose_name_plural = 'Microsoft OAuth Tokens'
    
    def __str__(self):
        return f"Microsoft token for {self.user.username}"
    
    def is_token_expired(self):
        """Check if the access token has expired."""
        return timezone.now() >= self.token_expires