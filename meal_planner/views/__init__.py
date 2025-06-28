"""
Meal Planner Views Package

This package splits the large views.py into organized modules:
- meal_plan_views: Core meal plan CRUD operations
- calendar_views: Calendar display and meal slot AJAX operations
- template_views: Template management and calendar sync features
"""

# Import all views to maintain backward compatibility with existing URLs
from .meal_plan_views import (
    MealPlanListView,
    MealPlanDetailView,
    MealPlanCreateView,
    MealPlanUpdateView,
    MealPlanDeleteView,
    generate_shopping_list,  # Add this
    download_shopping_list,  # Add this
)

from .calendar_views import (
    MealPlanCalendarView,
    MealSlotAjaxView,
    create_meal_slot,
    update_meal_slot,
    delete_meal_slot,
    test_endpoint,
)

from .template_views import (
    MealPlanTemplateListView,
    MealPlanTemplateCreateView,
    MealPlanTemplateUpdateView,
    MealPlanTemplateDeleteView,
    CalendarSyncSettingsView,
    apply_template,
    create_meal_slots_for_plan,
    sync_meal_plan,
    outlook_sync_status,
    sync_all_meal_plans,
    microsoft_switch_account,
    get_connected_account,
)

# Utility functions
from .calendar_views import _get_meal_color, serialize_recipe_for_json

__all__ = [
    # Meal Plan Views
    'MealPlanListView',
    'MealPlanDetailView', 
    'MealPlanCreateView',
    'MealPlanUpdateView',
    'MealPlanDeleteView',
    'generate_shopping_list',
    'download_shopping_list',
    
    # Calendar Views
    'MealPlanCalendarView',
    'MealSlotAjaxView',
    'create_meal_slot',
    'update_meal_slot', 
    'delete_meal_slot',
    'test_endpoint',
    
    # Template Views
    'MealPlanTemplateListView',
    'MealPlanTemplateCreateView',
    'MealPlanTemplateUpdateView',
    'MealPlanTemplateDeleteView',
    'CalendarSyncSettingsView',
    'apply_template',
    'create_meal_slots_for_plan',
    'sync_meal_plan',
    'outlook_sync_status',
    'sync_all_meal_plans',
    'microsoft_switch_account',
    'get_connected_account',
    
    # Utilities
    '_get_meal_color',
    'serialize_recipe_for_json',
]