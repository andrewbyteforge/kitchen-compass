"""
Custom template tags for meal planner app.

Provides utility tags for calendar navigation, meal plan display, and JSON serialization.
"""

import json
import logging
from datetime import timedelta
from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)
register = template.Library()


# Date utility filters
@register.filter
def add_days(value, days):
    """
    Add days to a date.
    
    Usage: {{ date|add_days:7 }}
    """
    try:
        return value + timedelta(days=int(days))
    except (ValueError, TypeError):
        return value


@register.filter
def subtract_days(value, days):
    """
    Subtract days from a date.
    
    Usage: {{ date|subtract_days:7 }}
    """
    try:
        return value - timedelta(days=int(days))
    except (ValueError, TypeError):
        return value


@register.filter
def add_months(value, months):
    """
    Add months to a date (approximate - uses 30 days per month).
    
    Usage: {{ date|add_months:1 }}
    """
    try:
        # Simple approximation
        return value + timedelta(days=int(months) * 30)
    except (ValueError, TypeError):
        return value


@register.filter
def start_of_month(value):
    """
    Get the first day of the month for a given date.
    
    Usage: {{ date|start_of_month }}
    """
    try:
        return value.replace(day=1)
    except AttributeError:
        return value


@register.filter
def end_of_month(value):
    """
    Get the last day of the month for a given date.
    
    Usage: {{ date|end_of_month }}
    """
    try:
        if value.month == 12:
            next_month = value.replace(year=value.year + 1, month=1, day=1)
        else:
            next_month = value.replace(month=value.month + 1, day=1)
        return next_month - timedelta(days=1)
    except AttributeError:
        return value


@register.simple_tag
def get_previous_month(date):
    """
    Get the first day of the previous month.
    
    Usage: {% get_previous_month date as prev_month %}
    """
    try:
        first_day = date.replace(day=1)
        if first_day.month == 1:
            return first_day.replace(year=first_day.year - 1, month=12)
        else:
            return first_day.replace(month=first_day.month - 1)
    except AttributeError:
        return date


@register.simple_tag
def get_next_month(date):
    """
    Get the first day of the next month.
    
    Usage: {% get_next_month date as next_month %}
    """
    try:
        first_day = date.replace(day=1)
        if first_day.month == 12:
            return first_day.replace(year=first_day.year + 1, month=1)
        else:
            return first_day.replace(month=first_day.month + 1)
    except AttributeError:
        return date


@register.filter
def meal_type_icon(meal_type_name):
    """
    Get the appropriate icon for a meal type.
    
    Usage: {{ meal_type|meal_type_icon }}
    """
    icons = {
        'breakfast': 'bi-sunrise',
        'lunch': 'bi-sun',
        'dinner': 'bi-moon',
        'snack': 'bi-cup-straw',
    }
    return icons.get(meal_type_name.lower(), 'bi-egg-fried')


@register.filter
def recipe_to_json(recipe):
    """
    Convert a recipe object to JSON for JavaScript consumption.
    
    Usage: {{ recipe|recipe_to_json }}
    """
    try:
        data = {
            'id': recipe.id,
            'title': recipe.title,
            'slug': recipe.slug,
            'description': recipe.description,
            'prep_time': recipe.prep_time,
            'cook_time': recipe.cook_time,
            'total_time': recipe.total_time,
            'servings': recipe.servings,
            'difficulty': recipe.difficulty,
            'difficulty_display': recipe.get_difficulty_display(),
            'categories': [cat.name for cat in recipe.categories.all()],
            'image_url': recipe.image.url if recipe.image else None,
            'author': recipe.author.username,
            'is_public': recipe.is_public,
            'average_rating': getattr(recipe, 'avg_rating', 0) or 0,
            'rating_count': getattr(recipe, 'rating_count', 0) or 0,
            'created_at': recipe.created_at.isoformat(),
        }
        return mark_safe(json.dumps(data))
    except Exception as e:
        logger.error(f"Error converting recipe to JSON: {str(e)}")
        # Return empty object if there's an error
        return mark_safe('{}')


@register.filter
def to_json(value):
    """
    Convert any Python object to JSON.
    
    Usage: {{ value|to_json }}
    """
    try:
        return mark_safe(json.dumps(value, cls=DjangoJSONEncoder))
    except (TypeError, ValueError):
        return mark_safe('null')


@register.filter
def meal_slot_to_json(meal_slot):
    """
    Convert a MealSlot object to JSON string for calendar events.
    
    Usage: {{ meal_slot|meal_slot_to_json }}
    """
    try:
        if not meal_slot.recipe:
            return mark_safe('{}')
            
        meal_slot_data = {
            'id': meal_slot.id,
            'title': f"{meal_slot.meal_type.name}: {meal_slot.recipe.title}",
            'start': meal_slot.date.isoformat(),
            'backgroundColor': get_meal_color(meal_slot.meal_type.name),
            'borderColor': get_meal_color(meal_slot.meal_type.name),
            'extendedProps': {
                'mealType': meal_slot.meal_type.name,
                'recipeId': meal_slot.recipe.id,
                'recipeTitle': meal_slot.recipe.title,
                'recipeSlug': meal_slot.recipe.slug,
                'servings': meal_slot.servings,
                'notes': meal_slot.notes or '',
            }
        }
        return mark_safe(json.dumps(meal_slot_data, cls=DjangoJSONEncoder))
    except Exception as e:
        logger.error(f"Error serializing meal slot to JSON: {str(e)}")
        return mark_safe('{}')


@register.simple_tag
def meal_slots_to_json(meal_slots):
    """
    Convert a queryset of meal slots to JSON string for calendar.
    
    Usage: {% meal_slots_to_json user_meal_slots as events_json %}
    """
    try:
        events = []
        for meal_slot in meal_slots:
            if meal_slot.recipe:  # Only include slots with recipes
                events.append({
                    'id': meal_slot.id,
                    'title': f"{meal_slot.meal_type.name}: {meal_slot.recipe.title}",
                    'start': meal_slot.date.isoformat(),
                    'backgroundColor': get_meal_color(meal_slot.meal_type.name),
                    'borderColor': get_meal_color(meal_slot.meal_type.name),
                    'extendedProps': {
                        'mealType': meal_slot.meal_type.name,
                        'recipeId': meal_slot.recipe.id,
                        'recipeTitle': meal_slot.recipe.title,
                        'recipeSlug': meal_slot.recipe.slug,
                        'servings': meal_slot.servings,
                        'notes': meal_slot.notes or '',
                    }
                })
        return json.dumps(events, cls=DjangoJSONEncoder)
    except Exception as e:
        logger.error(f"Error serializing meal slots to JSON: {str(e)}")
        return '[]'


@register.simple_tag
def meal_type_colors():
    """
    Get all meal type colors as JSON for JavaScript.
    
    Usage: {% meal_type_colors as colors %}
    """
    colors = {
        'breakfast': '#28a745',
        'lunch': '#ffc107', 
        'dinner': '#dc3545',
        'snack': '#6c757d',
    }
    return json.dumps(colors)


def get_meal_color(meal_type):
    """
    Get color for meal type.
    
    Helper function for consistent meal type colors across the app.
    """
    colors = {
        'breakfast': '#28a745',  # Green
        'lunch': '#ffc107',      # Yellow  
        'dinner': '#dc3545',     # Red
        'snack': '#6c757d',      # Gray
    }
    return colors.get(meal_type.lower(), '#007bff')  # Default blue