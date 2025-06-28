"""
Calendar Views - Calendar Display and Meal Slot AJAX Operations

This module contains views for calendar functionality including
the main calendar view and all AJAX endpoints for meal slot management.
"""

import json
import logging
import traceback
from datetime import datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View

from auth_hub.models import ActivityLog
from recipe_hub.models import Recipe
from ..models import MealPlan, MealSlot, MealType
from ..forms import QuickMealSlotForm

logger = logging.getLogger(__name__)


class MealPlanCalendarView(LoginRequiredMixin, View):
    """
    Calendar view for meal planning with FullCalendar integration.
    """
    
    def get(self, request):
        """Render calendar view with meal plans and recipes."""
        try:
            # Get user's meal slots (only ones with recipes assigned)
            try:
                meal_slots = MealSlot.objects.filter(
                    meal_plan__owner=request.user,
                    meal_plan__is_active=True,
                    recipe__isnull=False
                ).select_related('recipe', 'meal_type', 'meal_plan')
                
                logger.info(f"Found {meal_slots.count()} meal slots for user {request.user.username}")
            except Exception as e:
                logger.error(f"Error querying meal slots: {str(e)}")
                meal_slots = []
            
            # Get user's recipes AND public recipes for the recipe selector
            try:
                user_recipes = Recipe.objects.filter(
                    Q(author=request.user) | Q(is_public=True)
                ).select_related('author').distinct()[:100]
                
                logger.info(f"Found {user_recipes.count()} recipes available for user {request.user.username}")
            except Exception as e:
                logger.error(f"Error querying recipes: {str(e)}")
                user_recipes = []
            
            # Serialize meal slots for calendar events
            calendar_events = []
            try:
                for slot in meal_slots:
                    if hasattr(slot, 'meal_type') and hasattr(slot, 'recipe'):
                        calendar_events.append({
                            'id': slot.id,
                            'title': f"{slot.meal_type.name}: {slot.recipe.title}",
                            'start': slot.date.isoformat(),
                            'backgroundColor': _get_meal_color(slot.meal_type.name.lower()),
                            'borderColor': _get_meal_color(slot.meal_type.name.lower()),
                            'extendedProps': {
                                'mealType': slot.meal_type.name.lower(),
                                'mealTypeId': slot.meal_type.id,
                                'recipeId': slot.recipe.id,
                                'recipeTitle': slot.recipe.title,
                                'recipeSlug': getattr(slot.recipe, 'slug', ''),
                                'servings': slot.servings,
                                'notes': slot.notes or '',
                                'mealPlanId': slot.meal_plan.id,
                                'mealPlanName': slot.meal_plan.name,
                            }
                        })
            except Exception as e:
                logger.error(f"Error serializing meal slots: {str(e)}")
                calendar_events = []
            
            # Serialize recipes for the recipe selector
            recipes_data = []
            try:
                for recipe in user_recipes:
                    recipes_data.append({
                        'id': recipe.id,
                        'title': recipe.title,
                        'slug': getattr(recipe, 'slug', ''),
                        'prep_time': getattr(recipe, 'prep_time', 0),
                        'cook_time': getattr(recipe, 'cook_time', 0),
                        'total_time': getattr(recipe, 'prep_time', 0) + getattr(recipe, 'cook_time', 0),
                        'servings': getattr(recipe, 'servings', 1),
                        'difficulty': getattr(recipe, 'difficulty', 'medium'),
                        'difficulty_display': recipe.get_difficulty_display() if hasattr(recipe, 'get_difficulty_display') else 'Medium',
                        'image_url': recipe.image.url if hasattr(recipe, 'image') and recipe.image else None,
                        'author': recipe.author.username,
                        'is_public': getattr(recipe, 'is_public', False),
                    })
            except Exception as e:
                logger.error(f"Error serializing recipes: {str(e)}")
                recipes_data = []
            
            # Get meal types
            meal_types_data = []
            try:
                meal_types = MealType.objects.all().order_by('display_order')
                meal_types_data = [
                    {
                        'id': mt.id,
                        'name': mt.name,
                        'display_name': mt.name
                    }
                    for mt in meal_types
                ]
                logger.info(f"Found {len(meal_types_data)} meal types in database")
            except Exception as e:
                logger.error(f"Error getting meal types: {str(e)}")
                # Create default meal types if none exist
                meal_types_data = [
                    {'id': 1, 'name': 'Breakfast', 'display_name': 'Breakfast'},
                    {'id': 2, 'name': 'Lunch', 'display_name': 'Lunch'},
                    {'id': 3, 'name': 'Dinner', 'display_name': 'Dinner'},
                    {'id': 4, 'name': 'Snack', 'display_name': 'Snack'},
                ]
            
            context = {
                'calendar_events': json.dumps(calendar_events),
                'recipes_data': json.dumps(recipes_data),
                'meal_types': json.dumps(meal_types_data),
                'today': timezone.now().date().isoformat(),
                'total_events': len(calendar_events),
                'total_recipes': len(recipes_data),
            }
            
            logger.info(f"Calendar view loaded successfully for user {request.user.username}")
            logger.info(f"Events: {len(calendar_events)}, Recipes: {len(recipes_data)}, Meal Types: {len(meal_types_data)}")
            
            return render(request, 'meal_planner/calendar.html', context)
            
        except Exception as e:
            logger.error(f"Unexpected error in calendar view for user {request.user.username}: {str(e)}")
            logger.error(traceback.format_exc())
            messages.error(request, "An error occurred while loading the calendar.")
            return redirect('meal_planner:meal_plan_list')


class MealSlotAjaxView(LoginRequiredMixin, View):
    """
    AJAX endpoints for meal slot operations.
    """
    
    def post(self, request):
        """Create or update meal slot."""
        try:
            data = json.loads(request.body)
            
            recipe_id = data.get('recipe_id')
            slot_date = data.get('date')
            meal_type_id = data.get('meal_type_id')
            servings = data.get('servings', 1)
            notes = data.get('notes', '')
            
            # Validate required fields
            if not all([recipe_id, slot_date, meal_type_id]):
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required fields'
                }, status=400)
            
            # Get recipe
            recipe = get_object_or_404(Recipe, id=recipe_id)
            # Check access
            if not recipe.is_public and recipe.author != request.user:
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have access to this recipe'
                }, status=403)
            
            # Parse date
            try:
                slot_date = datetime.fromisoformat(slot_date.replace('Z', '+00:00')).date()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid date format'
                }, status=400)
            
            # Get meal type
            meal_type = get_object_or_404(MealType, id=meal_type_id)
            
            # Find or create meal plan for this date
            meal_plan = MealPlan.objects.filter(
                owner=request.user,
                start_date__lte=slot_date,
                end_date__gte=slot_date,
                is_active=True
            ).first()
            
            if not meal_plan:
                # Create a weekly meal plan
                start_date = slot_date - timedelta(days=slot_date.weekday())
                end_date = start_date + timedelta(days=6)
                
                meal_plan = MealPlan.objects.create(
                    owner=request.user,
                    name=f"Week of {start_date.strftime('%B %d, %Y')}",
                    start_date=start_date,
                    end_date=end_date
                )
            
            # Create or update meal slot
            meal_slot, created = MealSlot.objects.update_or_create(
                meal_plan=meal_plan,
                date=slot_date,
                meal_type=meal_type,
                defaults={
                    'recipe': recipe,
                    'servings': servings,
                    'notes': notes
                }
            )
            
            logger.info(
                f"Meal slot {'created' if created else 'updated'}: {recipe.title} for "
                f"{slot_date} by {request.user.username}"
            )
            
            return JsonResponse({
                'success': True,
                'meal_slot': {
                    'id': meal_slot.id,
                    'title': f"{meal_slot.meal_type.name}: {meal_slot.recipe.title}",
                    'start': meal_slot.date.isoformat(),
                    'backgroundColor': _get_meal_color(meal_slot.meal_type.name.lower()),
                    'borderColor': _get_meal_color(meal_slot.meal_type.name.lower()),
                    'extendedProps': {
                        'mealType': meal_slot.meal_type.name.lower(),
                        'mealTypeId': meal_slot.meal_type.id,
                        'recipeId': meal_slot.recipe.id,
                        'recipeTitle': meal_slot.recipe.title,
                        'recipeSlug': getattr(meal_slot.recipe, 'slug', ''),
                        'servings': meal_slot.servings,
                        'notes': meal_slot.notes or '',
                        'mealPlanId': meal_slot.meal_plan.id,
                        'mealPlanName': meal_slot.meal_plan.name,
                    }
                }
            })
            
        except Exception as e:
            logger.error(f"Error creating/updating meal slot: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred while saving the meal slot'
            }, status=500)
    
    def delete(self, request):
        """Delete meal slot."""
        try:
            data = json.loads(request.body)
            meal_slot_id = data.get('meal_slot_id')
            
            if not meal_slot_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Meal slot ID required'
                }, status=400)
            
            meal_slot = get_object_or_404(
                MealSlot, 
                id=meal_slot_id, 
                meal_plan__owner=request.user
            )
            
            meal_slot_title = f"{meal_slot.meal_type.name}: {meal_slot.recipe.title if meal_slot.recipe else 'Empty'}"
            
            # Clear the slot instead of deleting it
            meal_slot.recipe = None
            meal_slot.servings = 1
            meal_slot.notes = ''
            meal_slot.save()
            
            logger.info(f"Meal slot cleared: {meal_slot_title} by {request.user.username}")
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            logger.error(f"Error clearing meal slot: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred while clearing the meal slot'
            }, status=500)


# In meal_planner/views/calendar_views.py
# Replace the create_meal_slot function with this corrected version:

@login_required
def create_meal_slot(request):
    """Create a meal slot and save to database."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        # Parse JSON data
        data = json.loads(request.body)
        logger.info(f"Creating meal slot for user {request.user.username} with data: {data}")
        
        # Extract and validate data
        recipe_id = data.get('recipe_id')
        date_str = data.get('date')
        meal_type_id = data.get('meal_type_id')
        servings = data.get('servings', 1)
        notes = data.get('notes', '')
        
        if not all([recipe_id, date_str, meal_type_id]):
            return JsonResponse({
                'success': False, 
                'error': 'Missing required fields'
            }, status=400)
        
        # Parse date
        try:
            slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': f'Invalid date format: {date_str}'
            }, status=400)
        
        # Get meal type - FIXED: Handle both numeric ID and string name
        try:
            # First try to get by ID if it's numeric
            if str(meal_type_id).isdigit():
                meal_type = MealType.objects.get(id=int(meal_type_id))
            else:
                # If not numeric, try to get by name (case-insensitive)
                meal_type = MealType.objects.get(name__iexact=meal_type_id)
        except MealType.DoesNotExist:
            # If meal type doesn't exist, create default meal types
            logger.warning(f"Meal type not found: {meal_type_id}. Creating default meal types.")
            
            # Create default meal types
            from datetime import time
            default_meal_types = [
                {'name': 'Breakfast', 'display_order': 1, 'default_time': time(7, 0), 'icon': 'bi-sunrise'},
                {'name': 'Lunch', 'display_order': 2, 'default_time': time(12, 0), 'icon': 'bi-sun'},
                {'name': 'Dinner', 'display_order': 3, 'default_time': time(18, 0), 'icon': 'bi-moon'},
                {'name': 'Snack', 'display_order': 4, 'default_time': time(15, 0), 'icon': 'bi-cup-straw'}
            ]
            
            for mt_data in default_meal_types:
                MealType.objects.get_or_create(
                    name=mt_data['name'],
                    defaults={
                        'display_order': mt_data['display_order'],
                        'default_time': mt_data['default_time'],
                        'icon': mt_data['icon']
                    }
                )
            
            # Try again to get the meal type
            try:
                if str(meal_type_id).isdigit():
                    meal_type = MealType.objects.get(id=int(meal_type_id))
                else:
                    meal_type = MealType.objects.get(name__iexact=meal_type_id)
            except MealType.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Meal type not found: {meal_type_id}'
                }, status=400)
        except ValueError as e:
            logger.error(f"ValueError when processing meal_type_id: {meal_type_id} - {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Invalid meal type ID: {meal_type_id}'
            }, status=400)
        
        # Get recipe
        try:
            recipe = Recipe.objects.get(id=recipe_id)
            # Check access
            if not recipe.is_public and recipe.author != request.user:
                return JsonResponse({
                    'success': False,
                    'error': 'You do not have access to this recipe'
                }, status=403)
        except Recipe.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Recipe not found: {recipe_id}'
            }, status=400)
        
        # Find or create meal plan
        meal_plan = MealPlan.objects.filter(
            owner=request.user,
            start_date__lte=slot_date,
            end_date__gte=slot_date,
            is_active=True
        ).first()
        
        if not meal_plan:
            # Create a weekly meal plan
            start_date = slot_date - timedelta(days=slot_date.weekday())
            end_date = start_date + timedelta(days=6)
            
            meal_plan = MealPlan.objects.create(
                owner=request.user,
                name=f"Week of {start_date.strftime('%B %d, %Y')}",
                start_date=start_date,
                end_date=end_date
            )
            logger.info(f"Created new meal plan: {meal_plan.name}")
        
        # Create or update meal slot
        meal_slot, created = MealSlot.objects.get_or_create(
            meal_plan=meal_plan,
            date=slot_date,
            meal_type=meal_type,
            defaults={
                'recipe': recipe,
                'servings': servings,
                'notes': notes
            }
        )
        
        if not created:
            # Update existing slot
            meal_slot.recipe = recipe
            meal_slot.servings = servings
            meal_slot.notes = notes
            meal_slot.save()
            logger.info(f"Updated existing meal slot {meal_slot.id}")
        else:
            logger.info(f"Created new meal slot {meal_slot.id}")
        
        # Prepare response for calendar
        response_data = {
            'success': True,
            'message': 'Meal slot created successfully',
            'meal_slot': {
                'id': meal_slot.id,
                'title': f"{meal_type.name}: {recipe.title}",
                'start': slot_date.isoformat(),
                'backgroundColor': _get_meal_color(meal_type.name.lower()),
                'borderColor': _get_meal_color(meal_type.name.lower()),
                'extendedProps': {
                    'mealType': meal_type.name.lower(),
                    'mealTypeId': meal_type.id,
                    'recipeId': recipe.id,
                    'recipeTitle': recipe.title,
                    'recipeSlug': getattr(recipe, 'slug', ''),
                    'servings': meal_slot.servings,
                    'notes': meal_slot.notes or '',
                    'mealPlanId': meal_plan.id,
                    'mealPlanName': meal_plan.name,
                }
            }
        }
        
        logger.info(f"Successfully created meal slot {meal_slot.id} for user {request.user.username}")
        return JsonResponse(response_data)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Error creating meal slot for user {request.user.username}: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred'
        }, status=500)

@login_required
def update_meal_slot(request, pk):
    """AJAX endpoint to update a meal slot."""
    if request.method != 'POST':
        return HttpResponseForbidden()
    
    meal_slot = get_object_or_404(MealSlot, pk=pk)
    
    # Check ownership
    if meal_slot.meal_plan.owner != request.user:
        return HttpResponseForbidden()
    
    form = QuickMealSlotForm(request.POST, user=request.user)
    
    if form.is_valid():
        try:
            # Update meal slot
            recipe_id = form.cleaned_data.get('recipe_id')
            if recipe_id:
                meal_slot.recipe_id = recipe_id
            else:
                meal_slot.recipe = None
            
            if form.cleaned_data.get('servings'):
                meal_slot.servings = form.cleaned_data['servings']
            
            if 'notes' in form.cleaned_data:
                meal_slot.notes = form.cleaned_data['notes']
            
            meal_slot.save()
            
            # Prepare response data
            response_data = {
                'success': True,
                'slot': {
                    'id': meal_slot.id,
                    'recipe': {
                        'id': meal_slot.recipe.id,
                        'title': meal_slot.recipe.title,
                        'prep_time': meal_slot.recipe.prep_time,
                        'cook_time': meal_slot.recipe.cook_time,
                        'servings': meal_slot.recipe.servings,
                        'difficulty': meal_slot.recipe.difficulty,
                        'image_url': meal_slot.recipe.image.url if meal_slot.recipe.image else None,
                    } if meal_slot.recipe else None,
                    'servings': meal_slot.servings,
                    'notes': meal_slot.notes,
                }
            }
            
            logger.info(
                f"Meal slot updated: {meal_slot.date} - {meal_slot.meal_type.name} "
                f"by {request.user.username}"
            )
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(
                f"Error updating meal slot {pk} for user {request.user.username}: {str(e)}"
            )
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    else:
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required
def delete_meal_slot(request, pk):
    """AJAX endpoint to clear a meal slot."""
    if request.method != 'POST':
        return HttpResponseForbidden()
    
    try:
        data = json.loads(request.body)
        meal_slot_id = data.get('meal_slot_id')
        
        if not meal_slot_id:
            return JsonResponse({
                'success': False,
                'error': 'Meal slot ID required'
            }, status=400)
        
        meal_slot = get_object_or_404(
            MealSlot, 
            id=meal_slot_id, 
            meal_plan__owner=request.user
        )
        
        meal_slot_title = f"{meal_slot.meal_type.name}: {meal_slot.recipe.title if meal_slot.recipe else 'Empty'}"
        
        # Clear the slot instead of deleting it
        meal_slot.recipe = None
        meal_slot.servings = 1
        meal_slot.notes = ''
        meal_slot.save()
        
        logger.info(f"Meal slot cleared: {meal_slot_title} by {request.user.username}")
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error clearing meal slot: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while clearing the meal slot'
        }, status=500)


@login_required
def test_endpoint(request):
    """Simple test endpoint to check if routing works."""
    logger.info("=== TEST ENDPOINT CALLED ===")
    
    return JsonResponse({
        'success': True,
        'message': 'Test endpoint working',
        'method': request.method,
        'user': str(request.user)
    })


def _get_meal_color(meal_type_name):
    """Helper function to get color for meal type."""
    colors = {
        'breakfast': '#28a745',  # Green
        'lunch': '#ffc107',      # Yellow
        'dinner': '#dc3545',     # Red
        'snack': '#6c757d',      # Gray
    }
    return colors.get(meal_type_name.lower(), '#007bff')  # Default blue


def serialize_recipe_for_json(recipe):
    """Serialize a recipe object for JSON output."""
    return {
        'id': recipe.id,
        'title': recipe.title,
        'slug': getattr(recipe, 'slug', ''),
        'description': getattr(recipe, 'description', ''),
        'prep_time': getattr(recipe, 'prep_time', 0),
        'cook_time': getattr(recipe, 'cook_time', 0),
        'total_time': getattr(recipe, 'total_time', 0),
        'servings': getattr(recipe, 'servings', 1),
        'difficulty': getattr(recipe, 'difficulty', 'medium'),
        'difficulty_display': recipe.get_difficulty_display() if hasattr(recipe, 'get_difficulty_display') else 'Medium',
        'categories': [cat.name for cat in recipe.categories.all()] if hasattr(recipe, 'categories') else [],
        'image_url': recipe.image.url if hasattr(recipe, 'image') and recipe.image else None,
        'author': recipe.author.username,
        'is_public': getattr(recipe, 'is_public', False),
        'average_rating': getattr(recipe, 'average_rating', 0),
        'rating_count': getattr(recipe, 'rating_count', 0),
        'created_at': recipe.created_at.isoformat(),
    }