"""
Meal Planner Models

This module contains models for meal planning functionality including
meal plans, meal slots, and meal plan templates.
"""

import logging
from datetime import date, timedelta
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from recipe_hub.models import Recipe

logger = logging.getLogger(__name__)


class MealPlan(models.Model):
    """
    Represents a meal plan for a specific time period.
    
    Attributes:
        owner: User who owns this meal plan
        name: Name of the meal plan
        start_date: Starting date of the meal plan
        end_date: Ending date of the meal plan
        is_active: Whether this plan is currently active
        notes: Optional notes for the meal plan
        created_from_template: Template this plan was created from
    """
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='meal_plans'
    )
    name = models.CharField(
        max_length=200,
        help_text="Name for this meal plan"
    )
    start_date = models.DateField(
        default=date.today,
        help_text="Start date of the meal plan"
    )
    end_date = models.DateField(
        help_text="End date of the meal plan"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this meal plan is currently active"
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional notes for this meal plan"
    )
    created_from_template = models.ForeignKey(
        'MealPlanTemplate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_plans'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date', '-created_at']
        indexes = [
            models.Index(fields=['owner', '-start_date']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F('start_date')),
                name='end_date_after_start_date'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"

    def clean(self):
        """Validate meal plan data."""
        super().clean()
        
        # Check if end date is after start date
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'End date must be after or equal to start date.'
            })
        
        # REMOVED: meal plan limit checking is handled in the view

    def save(self, *args, **kwargs):
        """Save meal plan with validation."""
        # Skip full_clean() for now to avoid owner validation issues
        super().save(*args, **kwargs)
        logger.info(f"MealPlan saved: {self.name} for user {self.owner.username} (ID: {self.pk})")

    def get_absolute_url(self):
        """Get the URL for this meal plan."""
        return reverse('meal_planner:meal_plan_detail', kwargs={'pk': self.pk})

    @property
    def duration_days(self):
        """Calculate the duration of the meal plan in days."""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_current(self):
        """Check if the meal plan includes today's date."""
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def is_future(self):
        """Check if the meal plan is in the future."""
        return self.start_date > date.today()

    @property
    def is_past(self):
        """Check if the meal plan is in the past."""
        return self.end_date < date.today()

    def get_week_dates(self):
        """Get all dates in the meal plan grouped by week."""
        weeks = []
        current_date = self.start_date
        
        while current_date <= self.end_date:
            # Find the start of the week (Monday)
            week_start = current_date - timedelta(days=current_date.weekday())
            week_dates = []
            
            # Get all dates for this week that fall within the plan
            for i in range(7):
                day_date = week_start + timedelta(days=i)
                if self.start_date <= day_date <= self.end_date:
                    week_dates.append(day_date)
            
            if week_dates:
                weeks.append(week_dates)
            
            # Move to next week
            current_date = week_start + timedelta(days=7)
        
        return weeks

    def duplicate(self, new_start_date=None, new_name=None):
        """Create a duplicate of this meal plan with a new date range."""
        if not new_start_date:
            new_start_date = self.end_date + timedelta(days=1)
        
        duration = self.end_date - self.start_date
        new_end_date = new_start_date + duration
        
        new_plan = MealPlan.objects.create(
            owner=self.owner,
            name=new_name or f"{self.name} (Copy)",
            start_date=new_start_date,
            end_date=new_end_date,
            notes=self.notes,
            created_from_template=self.created_from_template
        )
        
        # Copy all meal slots
        for slot in self.meal_slots.all():
            days_offset = (slot.date - self.start_date).days
            new_date = new_start_date + timedelta(days=days_offset)
            
            MealSlot.objects.create(
                meal_plan=new_plan,
                date=new_date,
                meal_type=slot.meal_type,
                recipe=slot.recipe,
                servings=slot.servings,
                notes=slot.notes
            )
        
        return new_plan


class MealType(models.Model):
    """
    Types of meals (breakfast, lunch, dinner, snack).
    
    Attributes:
        name: Name of the meal type
        display_order: Order in which to display meal types
        default_time: Default time for this meal type
        icon: Icon to represent this meal type
    """
    name = models.CharField(max_length=50, unique=True)
    display_order = models.IntegerField(default=0)
    default_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Default time for this meal"
    )
    icon = models.CharField(
        max_length=50,
        default='bi-egg-fried',
        help_text="Bootstrap icon class"
    )
    
    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class MealSlot(models.Model):
    """
    Represents a single meal slot in a meal plan.
    
    Attributes:
        meal_plan: Parent meal plan
        date: Date of this meal
        meal_type: Type of meal (breakfast, lunch, etc.)
        recipe: Recipe assigned to this slot
        servings: Number of servings to prepare
        notes: Optional notes for this meal
    """
    meal_plan = models.ForeignKey(
        MealPlan,
        on_delete=models.CASCADE,
        related_name='meal_slots'
    )
    date = models.DateField()
    meal_type = models.ForeignKey(
        MealType,
        on_delete=models.PROTECT,
        related_name='meal_slots'
    )
    recipe = models.ForeignKey(
        'recipe_hub.Recipe',  # Make sure it references the correct Recipe model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meal_slots'
    )
    servings = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        help_text="Number of servings to prepare"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes for this meal"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['date', 'meal_type__display_order']
        unique_together = ['meal_plan', 'date', 'meal_type']
        indexes = [
            models.Index(fields=['meal_plan', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        recipe_name = self.recipe.title if self.recipe else "Empty"
        return f"{self.date} - {self.meal_type.name}: {recipe_name}"

    def clean(self):
        """Validate meal slot data."""
        super().clean()
        
        # Ensure date is within meal plan range
        if self.meal_plan and self.date:
            if self.date < self.meal_plan.start_date or self.date > self.meal_plan.end_date:
                raise ValidationError({
                    'date': 'Meal date must be within the meal plan date range.'
                })

    @property
    def is_empty(self):
        """Check if this meal slot has no recipe assigned."""
        return self.recipe is None

    @property
    def total_servings(self):
        """Calculate total servings based on recipe servings and multiplier."""
        if self.recipe:
            return self.recipe.servings * self.servings
        return 0


class MealPlanTemplate(models.Model):
    """
    Reusable meal plan templates.
    
    Attributes:
        owner: User who owns this template
        name: Name of the template
        description: Description of what this template contains
        duration_days: How many days this template covers
        is_public: Whether this template can be used by others
    """
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='meal_plan_templates'
    )
    name = models.CharField(
        max_length=200,
        help_text="Name for this template"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this meal plan template"
    )
    duration_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Number of days this template covers"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Allow other users to use this template"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['owner', 'name']

    def __str__(self):
        return f"{self.name} ({self.duration_days} days)"

    def create_meal_plan(self, start_date, name=None):
        """Create a new meal plan from this template."""
        end_date = start_date + timedelta(days=self.duration_days - 1)
        
        meal_plan = MealPlan.objects.create(
            owner=self.owner,
            name=name or f"{self.name} - {start_date}",
            start_date=start_date,
            end_date=end_date,
            created_from_template=self
        )
        
        # Copy template slots to meal plan
        for template_slot in self.template_slots.all():
            slot_date = start_date + timedelta(days=template_slot.day_offset)
            
            MealSlot.objects.create(
                meal_plan=meal_plan,
                date=slot_date,
                meal_type=template_slot.meal_type,
                recipe=template_slot.recipe,
                servings=template_slot.servings,
                notes=template_slot.notes
            )
        
        logger.info(
            f"Created meal plan '{meal_plan.name}' from template '{self.name}' "
            f"for user {self.owner.username}"
        )
        
        return meal_plan


class MealPlanTemplateSlot(models.Model):
    """
    Represents a meal slot in a template.
    
    Attributes:
        template: Parent template
        day_offset: Day offset from start (0 = first day)
        meal_type: Type of meal
        recipe: Recipe for this slot
        servings: Number of servings
        notes: Optional notes
    """
    template = models.ForeignKey(
        MealPlanTemplate,
        on_delete=models.CASCADE,
        related_name='template_slots'
    )
    day_offset = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Days from start of plan (0 = first day)"
    )
    meal_type = models.ForeignKey(
        MealType,
        on_delete=models.PROTECT,
        related_name='template_slots'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='template_slots',
        null=True,
        blank=True
    )
    servings = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['day_offset', 'meal_type__display_order']
        unique_together = ['template', 'day_offset', 'meal_type']

    def __str__(self):
        recipe_name = self.recipe.title if self.recipe else "Empty"
        return f"Day {self.day_offset + 1} - {self.meal_type.name}: {recipe_name}"
    




# Add this model to track calendar events

class CalendarEvent(models.Model):
    """
    Tracks Outlook calendar events created from meal plans.
    
    This allows us to update or delete calendar events
    when meal plans change.
    """
    meal_slot = models.OneToOneField(
        MealSlot,
        on_delete=models.CASCADE,
        related_name='calendar_event'
    )
    outlook_event_id = models.CharField(
        max_length=255,
        help_text="ID of the event in Outlook calendar"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='calendar_events'
    )
    
    # Sync status
    last_synced = models.DateTimeField(auto_now=True)
    sync_status = models.CharField(
        max_length=20,
        choices=[
            ('synced', 'Synced'),
            ('pending', 'Pending Sync'),
            ('error', 'Sync Error'),
        ],
        default='pending'
    )
    sync_error = models.TextField(
        blank=True,
        help_text="Error message if sync failed"
    )
    
    class Meta:
        db_table = 'meal_planner_calendar_event'
        unique_together = ['meal_slot', 'user']
        indexes = [
            models.Index(fields=['outlook_event_id']),
            models.Index(fields=['sync_status']),
        ]
    
    def __str__(self):
        return f"Calendar event for {self.meal_slot}"
    

# Add these imports at the top of your meal_planner/models.py file if not already present:
import os
from django.core.validators import FileExtensionValidator

# Add this function before the RecipeCSVUpload class:
def csv_upload_path(instance, filename):
    """Generate upload path for CSV files."""
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    base_filename = os.path.splitext(filename)[0]
    extension = os.path.splitext(filename)[1]
    return f'csv_uploads/recipes/{timestamp}_{base_filename}{extension}'


# Add this model class at the end of your meal_planner/models.py file:
class RecipeCSVUpload(models.Model):
    """
    Track CSV file uploads for recipe imports.
    
    Attributes:
        uploaded_by: Admin user who uploaded the file
        file: The CSV file
        uploaded_at: When the file was uploaded
        processed_at: When processing completed
        status: Current processing status
        total_rows: Total rows in CSV
        successful_imports: Number of successful imports
        failed_imports: Number of failed imports
        error_log: JSON field containing processing errors
        notes: Admin notes about the upload
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partially Completed'),
    ]
    
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='csv_uploads'
    )
    file = models.FileField(
        upload_to=csv_upload_path,
        validators=[FileExtensionValidator(allowed_extensions=['csv'])],
        help_text="CSV file containing recipe data"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Processing statistics
    total_rows = models.IntegerField(default=0)
    successful_imports = models.IntegerField(default=0)
    failed_imports = models.IntegerField(default=0)
    
    # Error tracking
    error_log = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed error information for failed imports"
    )
    
    # Admin notes
    notes = models.TextField(
        blank=True,
        help_text="Admin notes about this upload"
    )
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = "Recipe CSV Upload"
        verbose_name_plural = "Recipe CSV Uploads"
    
    def __str__(self):
        return f"CSV Upload by {self.uploaded_by} on {self.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def filename(self):
        """Get the original filename."""
        return os.path.basename(self.file.name) if self.file else "No file"
    
    @property
    def success_rate(self):
        """Calculate success rate percentage."""
        if self.total_rows == 0:
            return 0
        return round((self.successful_imports / self.total_rows) * 100, 1)
    
    def mark_completed(self):
        """Mark upload as completed."""
        self.processed_at = timezone.now()
        if self.failed_imports == 0:
            self.status = 'completed'
        elif self.successful_imports == 0:
            self.status = 'failed'
        else:
            self.status = 'partial'
        self.save()
        
        logger.info(
            f"CSV processing completed: {self.successful_imports} successful, "
            f"{self.failed_imports} failed out of {self.total_rows} total"
        )