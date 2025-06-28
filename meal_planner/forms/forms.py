"""
Meal Planner Forms

This module contains forms for creating and managing meal plans,
meal slots, and meal plan templates.
"""

import logging
from datetime import date, timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from ..models import MealPlan, MealSlot, MealType, MealPlanTemplate, MealPlanTemplateSlot
from recipe_hub.models import Recipe

logger = logging.getLogger(__name__)


"""
Safe MealPlan Form that won't trigger owner validation issues
"""

from datetime import date, timedelta
from django import forms
from django.core.exceptions import ValidationError


class MealPlanForm(forms.ModelForm):
    """
    Form for creating and editing meal plans.
    """
    
    duration_weeks = forms.IntegerField(
        min_value=1,
        max_value=4,
        initial=1,
        required=False,
        label="Duration (weeks)",
        help_text="Number of weeks for the meal plan",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '1'
        })
    )
    
    class Meta:
        model = MealPlan
        fields = ['name', 'start_date', 'end_date', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'My Weekly Meal Plan'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional notes for this meal plan'
            })
        }
    
    def __init__(self, *args, **kwargs):
        """Initialize form with calculated end date."""
        super().__init__(*args, **kwargs)
        
        # Set default start date to next Monday
        if not self.instance.pk and not self.initial.get('start_date'):
            today = date.today()
            days_until_monday = (7 - today.weekday()) % 7
            if days_until_monday == 0:  # Today is Monday
                days_until_monday = 7
            next_monday = today + timedelta(days=days_until_monday)
            self.fields['start_date'].initial = next_monday
        
        # Calculate duration in weeks if editing
        if self.instance.pk:
            duration_days = (self.instance.end_date - self.instance.start_date).days + 1
            self.fields['duration_weeks'].initial = duration_days // 7
    
    def clean(self):
        """Validate form data."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        duration_weeks = cleaned_data.get('duration_weeks')
        
        # If duration_weeks is provided, calculate end_date
        if start_date and duration_weeks and not end_date:
            cleaned_data['end_date'] = start_date + timedelta(days=(duration_weeks * 7) - 1)
        
        # Validate date range
        if start_date and end_date:
            if end_date < start_date:
                raise ValidationError({
                    'end_date': 'End date must be after start date.'
                })
            
            # Check maximum duration (4 weeks)
            duration_days = (end_date - start_date).days + 1
            if duration_days > 28:
                raise ValidationError(
                    'Meal plans cannot exceed 4 weeks. Please create separate plans for longer periods.'
                )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Override save to prevent model validation issues."""
        instance = super().save(commit=False)
        
        if commit:
            # Save without calling full_clean() to avoid owner validation
            instance.save(force_insert=not instance.pk)
        
        return instance


class MealSlotForm(forms.ModelForm):
    """
    Form for individual meal slots.
    """
    
    recipe = forms.ModelChoiceField(
        queryset=Recipe.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select recipe-select',
            'data-live-search': 'true'
        })
    )
    
    class Meta:
        model = MealSlot
        fields = ['recipe', 'servings', 'notes']
        widgets = {
            'servings': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 20
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional notes'
            })
        }
    
    def __init__(self, *args, **kwargs):
        """Initialize form with user's recipes."""
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Show user's recipes and public recipes
            self.fields['recipe'].queryset = Recipe.objects.filter(
                models.Q(author=user) | models.Q(is_public=True)
            ).select_related('author').prefetch_related('categories')


class QuickMealSlotForm(forms.Form):
    """
    Simplified form for quick meal slot updates via AJAX.
    """
    
    recipe_id = forms.IntegerField(required=False)
    servings = forms.IntegerField(min_value=1, max_value=20, required=False)
    notes = forms.CharField(required=False, widget=forms.Textarea)
    
    def clean_recipe_id(self):
        """Validate recipe exists and user has access."""
        recipe_id = self.cleaned_data.get('recipe_id')
        if recipe_id:
            try:
                recipe = Recipe.objects.get(pk=recipe_id)
                if not recipe.is_public and recipe.author != self.user:
                    raise ValidationError("You don't have access to this recipe.")
                return recipe_id
            except Recipe.DoesNotExist:
                raise ValidationError("Recipe not found.")
        return None
    
    def __init__(self, *args, **kwargs):
        """Store user for validation."""
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)


class MealPlanTemplateForm(forms.ModelForm):
    """
    Form for creating meal plan templates.
    """
    
    create_from_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Create from existing meal plan",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    source_meal_plan = forms.ModelChoiceField(
        queryset=MealPlan.objects.none(),
        required=False,
        label="Select meal plan to copy",
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    class Meta:
        model = MealPlanTemplate
        fields = ['name', 'description', 'duration_days', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Weekly Vegetarian Plan'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of this template'
            }),
            'duration_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 30
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        """Initialize form with user's meal plans."""
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            self.fields['source_meal_plan'].queryset = MealPlan.objects.filter(
                owner=user
            ).order_by('-start_date')
    
    def save(self, commit=True):
        """Save template and optionally copy from existing meal plan."""
        template = super().save(commit=False)
        
        if commit:
            template.save()
            
            # Copy from existing meal plan if requested
            if self.cleaned_data.get('create_from_existing') and self.cleaned_data.get('source_meal_plan'):
                source_plan = self.cleaned_data['source_meal_plan']
                
                # Copy all meal slots as template slots
                for slot in source_plan.meal_slots.all():
                    day_offset = (slot.date - source_plan.start_date).days
                    
                    MealPlanTemplateSlot.objects.create(
                        template=template,
                        day_offset=day_offset,
                        meal_type=slot.meal_type,
                        recipe=slot.recipe,
                        servings=slot.servings,
                        notes=slot.notes
                    )
                
                logger.info(
                    f"Created template '{template.name}' from meal plan '{source_plan.name}' "
                    f"for user {template.owner.username}"
                )
        
        return template


class ApplyTemplateForm(forms.Form):
    """
    Form for applying a template to create a new meal plan.
    """
    
    template = forms.ModelChoiceField(
        queryset=MealPlanTemplate.objects.none(),
        label="Select template",
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    name = forms.CharField(
        max_length=200,
        required=False,
        label="Meal plan name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave blank to use template name'
        })
    )
    
    start_date = forms.DateField(
        label="Start date",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    def __init__(self, *args, **kwargs):
        """Initialize form with available templates."""
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Show user's templates and public templates
            self.fields['template'].queryset = MealPlanTemplate.objects.filter(
                models.Q(owner=user) | models.Q(is_public=True)
            ).order_by('-created_at')
        
        # Set default start date to next Monday
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:  # Today is Monday
            days_until_monday = 7
        next_monday = today + timedelta(days=days_until_monday)
        self.fields['start_date'].initial = next_monday


class MealPlanFilterForm(forms.Form):
    """
    Form for filtering meal plans.
    """
    
    STATUS_CHOICES = [
        ('', 'All Plans'),
        ('current', 'Current'),
        ('future', 'Future'),
        ('past', 'Past'),
        ('active', 'Active Only'),
        ('inactive', 'Inactive Only'),
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search meal plans...'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


# Import models to avoid circular import
from django.db import models