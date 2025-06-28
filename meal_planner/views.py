# """
# Meal Planner Views

# This module contains views for meal planning functionality including
# calendar views, meal plan management, and template handling.
# """
# from django.db.models import Count
# import logging
# from django.views.generic import TemplateView
# from django.utils.decorators import method_decorator
# import logging
# import json
# from datetime import date, datetime, timedelta
# from django.contrib import messages
# from django.contrib.auth.decorators import login_required
# from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
# from django.core.exceptions import PermissionDenied
# from django.db import transaction
# from django.db.models import Q, Count, Prefetch
# from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
# from django.shortcuts import render, redirect, get_object_or_404
# from django.urls import reverse, reverse_lazy
# from django.utils import timezone
# from django.utils.decorators import method_decorator
# from django.views import View
# from django.views.generic import (
#     ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
# )

# from auth_hub.models import ActivityLog
# from recipe_hub.models import Recipe
# from .models import MealPlan, MealSlot, MealType, MealPlanTemplate, MealPlanTemplateSlot
# from .forms import (
#     MealPlanForm, MealSlotForm, QuickMealSlotForm, MealPlanTemplateForm,
#     ApplyTemplateForm, MealPlanFilterForm
# )
# import json
# import logging
# from datetime import date, datetime, timedelta
# from django.contrib.auth.mixins import LoginRequiredMixin
# from django.http import JsonResponse
# from django.shortcuts import get_object_or_404
# from django.views import View
# from recipe_hub.models import Recipe
# from .models import MealPlan, MealSlot, MealType
# import json
# import logging
# from django.contrib import messages
# from django.contrib.auth.mixins import LoginRequiredMixin
# from django.http import JsonResponse
# from django.shortcuts import render, redirect
# from django.utils import timezone
# from django.views import View

# logger = logging.getLogger(__name__)


# class MealPlanCalendarView(LoginRequiredMixin, View):
#     """
#     Calendar view for meal planning - corrected for your model structure.
#     """
    
#     def get(self, request):
#         """Render calendar view with meal plans and recipes."""
#         try:
#             # Import models with error handling
#             try:
#                 from .models import MealSlot, MealType
#                 from recipe_hub.models import Recipe
#             except ImportError as e:
#                 logger.error(f"Import error: {str(e)}")
#                 messages.error(request, "Configuration error. Please contact support.")
#                 return redirect('meal_planner:meal_plan_list')
            
#             # Get user's meal slots (only ones with recipes assigned)
#             try:
#                 meal_slots = MealSlot.objects.filter(
#                     meal_plan__owner=request.user,
#                     meal_plan__is_active=True,
#                     recipe__isnull=False
#                 ).select_related('recipe', 'meal_type', 'meal_plan')
                
#                 logger.info(f"Found {meal_slots.count()} meal slots for user {request.user.username}")
#             except Exception as e:
#                 logger.error(f"Error querying meal slots: {str(e)}")
#                 meal_slots = []
            
#             # Get user's recipes AND public recipes for the recipe selector
#             try:
#                 from django.db.models import Q
#                 user_recipes = Recipe.objects.filter(
#                     Q(author=request.user) | Q(is_public=True)
#                 ).select_related('author').distinct()[:100]  # Increased limit
                
#                 logger.info(f"Found {user_recipes.count()} recipes available for user {request.user.username}")
#             except Exception as e:
#                 logger.error(f"Error querying recipes: {str(e)}")
#                 user_recipes = []
            
#             # Serialize meal slots for calendar events
#             calendar_events = []
#             try:
#                 for slot in meal_slots:
#                     if hasattr(slot, 'meal_type') and hasattr(slot, 'recipe'):
#                         calendar_events.append({
#                             'id': slot.id,
#                             'title': f"{slot.meal_type.name}: {slot.recipe.title}",
#                             'start': slot.date.isoformat(),
#                             'backgroundColor': self._get_meal_color(slot.meal_type.name.lower()),
#                             'borderColor': self._get_meal_color(slot.meal_type.name.lower()),
#                             'extendedProps': {
#                                 'mealType': slot.meal_type.name.lower(),
#                                 'mealTypeId': slot.meal_type.id,
#                                 'recipeId': slot.recipe.id,
#                                 'recipeTitle': slot.recipe.title,
#                                 'recipeSlug': getattr(slot.recipe, 'slug', ''),
#                                 'servings': slot.servings,
#                                 'notes': slot.notes or '',
#                                 'mealPlanId': slot.meal_plan.id,
#                                 'mealPlanName': slot.meal_plan.name,
#                             }
#                         })
#             except Exception as e:
#                 logger.error(f"Error serializing meal slots: {str(e)}")
#                 calendar_events = []
            
#             # Serialize recipes for the recipe selector
#             recipes_data = []
#             try:
#                 for recipe in user_recipes:
#                     recipes_data.append({
#                         'id': recipe.id,
#                         'title': recipe.title,
#                         'slug': getattr(recipe, 'slug', ''),
#                         'prep_time': getattr(recipe, 'prep_time', 0),
#                         'cook_time': getattr(recipe, 'cook_time', 0),
#                         'total_time': getattr(recipe, 'prep_time', 0) + getattr(recipe, 'cook_time', 0),
#                         'servings': getattr(recipe, 'servings', 1),
#                         'difficulty': getattr(recipe, 'difficulty', 'medium'),
#                         'difficulty_display': recipe.get_difficulty_display() if hasattr(recipe, 'get_difficulty_display') else 'Medium',
#                         'image_url': recipe.image.url if hasattr(recipe, 'image') and recipe.image else None,
#                         'author': recipe.author.username,
#                         'is_public': getattr(recipe, 'is_public', False),
#                     })
#             except Exception as e:
#                 logger.error(f"Error serializing recipes: {str(e)}")
#                 recipes_data = []
            
#             # Get meal types - FIXED: Just use name, not display_name
#             meal_types_data = []
#             try:
#                 meal_types = MealType.objects.all().order_by('display_order')
#                 meal_types_data = [
#                     {
#                         'id': mt.id,
#                         'name': mt.name,
#                         'display_name': mt.name  # Use name for display_name
#                     }
#                     for mt in meal_types
#                 ]
#                 logger.info(f"Found {len(meal_types_data)} meal types in database")
#             except Exception as e:
#                 logger.error(f"Error getting meal types: {str(e)}")
#                 # Create default meal types if none exist
#                 meal_types_data = [
#                     {'id': 1, 'name': 'Breakfast', 'display_name': 'Breakfast'},
#                     {'id': 2, 'name': 'Lunch', 'display_name': 'Lunch'},
#                     {'id': 3, 'name': 'Dinner', 'display_name': 'Dinner'},
#                     {'id': 4, 'name': 'Snack', 'display_name': 'Snack'},
#                 ]
            
#             context = {
#                 'calendar_events': json.dumps(calendar_events),
#                 'recipes_data': json.dumps(recipes_data),
#                 'meal_types': json.dumps(meal_types_data),
#                 'today': timezone.now().date().isoformat(),
#                 'total_events': len(calendar_events),
#                 'total_recipes': len(recipes_data),
#             }
            
#             logger.info(f"Calendar view loaded successfully for user {request.user.username}")
#             logger.info(f"Events: {len(calendar_events)}, Recipes: {len(recipes_data)}, Meal Types: {len(meal_types_data)}")
            
#             return render(request, 'meal_planner/calendar.html', context)
            
#         except Exception as e:
#             logger.error(f"Unexpected error in calendar view for user {request.user.username}: {str(e)}")
#             import traceback
#             logger.error(traceback.format_exc())
#             messages.error(request, "An error occurred while loading the calendar.")
#             return redirect('meal_planner:meal_plan_list')
    
#     def _get_meal_color(self, meal_type_name):
#         """Get color for meal type."""
#         colors = {
#             'breakfast': '#28a745',  # Green
#             'lunch': '#ffc107',      # Yellow
#             'dinner': '#dc3545',     # Red
#             'snack': '#6c757d',      # Gray
#         }
#         return colors.get(meal_type_name.lower(), '#007bff')  # Default blue


# """
# Add this class to your meal_planner/views.py file
# """

# class MealSlotAjaxView(LoginRequiredMixin, View):
#     """
#     AJAX endpoints for meal slot operations.
#     """
    
#     def post(self, request):
#         """Create or update meal slot."""
#         try:
#             data = json.loads(request.body)
            
#             recipe_id = data.get('recipe_id')
#             slot_date = data.get('date')
#             meal_type_id = data.get('meal_type_id')
#             servings = data.get('servings', 1)
#             notes = data.get('notes', '')
            
#             # Validate required fields
#             if not all([recipe_id, slot_date, meal_type_id]):
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Missing required fields'
#                 }, status=400)
            
#             # Get recipe
#             recipe = get_object_or_404(Recipe, id=recipe_id, author=request.user)
            
#             # Parse date
#             try:
#                 slot_date = datetime.fromisoformat(slot_date.replace('Z', '+00:00')).date()
#             except ValueError:
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Invalid date format'
#                 }, status=400)
            
#             # Get meal type
#             meal_type = get_object_or_404(MealType, id=meal_type_id)
            
#             # Find or create meal plan for this date
#             meal_plan = MealPlan.objects.filter(
#                 owner=request.user,
#                 start_date__lte=slot_date,
#                 end_date__gte=slot_date,
#                 is_active=True
#             ).first()
            
#             if not meal_plan:
#                 # Create a weekly meal plan
#                 start_date = slot_date - timedelta(days=slot_date.weekday())
#                 end_date = start_date + timedelta(days=6)
                
#                 meal_plan = MealPlan.objects.create(
#                     owner=request.user,
#                     name=f"Week of {start_date.strftime('%B %d, %Y')}",
#                     start_date=start_date,
#                     end_date=end_date
#                 )
            
#             # Create or update meal slot
#             meal_slot, created = MealSlot.objects.update_or_create(
#                 meal_plan=meal_plan,
#                 date=slot_date,
#                 meal_type=meal_type,
#                 defaults={
#                     'recipe': recipe,
#                     'servings': servings,
#                     'notes': notes
#                 }
#             )
            
#             logger.info(
#                 f"Meal slot {'created' if created else 'updated'}: {recipe.title} for "
#                 f"{slot_date} by {request.user.username}"
#             )
            
#             return JsonResponse({
#                 'success': True,
#                 'meal_slot': {
#                     'id': meal_slot.id,
#                     'title': f"{meal_slot.meal_type.name}: {meal_slot.recipe.title}",
#                     'start': meal_slot.date.isoformat(),
#                     'backgroundColor': self._get_meal_color(meal_slot.meal_type.name.lower()),
#                     'borderColor': self._get_meal_color(meal_slot.meal_type.name.lower()),
#                     'extendedProps': {
#                         'mealType': meal_slot.meal_type.name.lower(),
#                         'mealTypeId': meal_slot.meal_type.id,
#                         'recipeId': meal_slot.recipe.id,
#                         'recipeTitle': meal_slot.recipe.title,
#                         'recipeSlug': meal_slot.recipe.slug,
#                         'servings': meal_slot.servings,
#                         'notes': meal_slot.notes or '',
#                         'mealPlanId': meal_slot.meal_plan.id,
#                         'mealPlanName': meal_slot.meal_plan.name,
#                     }
#                 }
#             })
            
#         except Exception as e:
#             logger.error(f"Error creating/updating meal slot: {str(e)}")
#             return JsonResponse({
#                 'success': False,
#                 'error': 'An error occurred while saving the meal slot'
#             }, status=500)
    
#     def delete(self, request):
#         """Delete meal slot."""
#         try:
#             data = json.loads(request.body)
#             meal_slot_id = data.get('meal_slot_id')
            
#             if not meal_slot_id:
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'Meal slot ID required'
#                 }, status=400)
            
#             meal_slot = get_object_or_404(
#                 MealSlot, 
#                 id=meal_slot_id, 
#                 meal_plan__owner=request.user
#             )
            
#             meal_slot_title = f"{meal_slot.meal_type.name}: {meal_slot.recipe.title if meal_slot.recipe else 'Empty'}"
            
#             # Clear the slot instead of deleting it
#             meal_slot.recipe = None
#             meal_slot.servings = 1
#             meal_slot.notes = ''
#             meal_slot.save()
            
#             logger.info(
#                 f"Meal slot cleared: {meal_slot_title} by {request.user.username}"
#             )
            
#             return JsonResponse({'success': True})
            
#         except Exception as e:
#             logger.error(f"Error clearing meal slot: {str(e)}")
#             return JsonResponse({
#                 'success': False,
#                 'error': 'An error occurred while clearing the meal slot'
#             }, status=500)
    
#     def _get_meal_color(self, meal_type_name):
#         """Get color for meal type."""
#         colors = {
#             'breakfast': '#28a745',  # Green
#             'lunch': '#ffc107',      # Yellow
#             'dinner': '#dc3545',     # Red
#             'snack': '#6c757d',      # Gray
#         }
#         return colors.get(meal_type_name.lower(), '#007bff')  # Default blue


# # Keep your existing views but fix the model field references
# class MealPlanDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
#     """Detailed view of a meal plan - corrected for your model structure."""
#     model = MealPlan
#     template_name = 'meal_planner/meal_plan_detail.html'
#     context_object_name = 'meal_plan'
    
#     def test_func(self):
#         """Check if user owns this meal plan."""
#         meal_plan = self.get_object()
#         return meal_plan.owner == self.request.user
    
# # Update your MealPlanDetailView.get_context_data method to include meal type filtering:

# def get_context_data(self, **kwargs):
#     """Add organized meal data and enhanced recipe information to context."""
#     context = super().get_context_data(**kwargs)
#     meal_plan = self.object
    
#     # Get all meal slots organized by date
#     meal_slots = meal_plan.meal_slots.select_related(
#         'recipe', 'meal_type', 'recipe__author'
#     ).prefetch_related(
#         'recipe__categories',
#         'recipe__meal_types'  # ADD THIS - prefetch meal types
#     ).order_by('date', 'meal_type__display_order')
    
#     # Get user's recipes AND public recipes for the recipe selector
#     try:
#         from django.db.models import Q, Avg, Count
#         from recipe_hub.models import Recipe
        
#         # Get recipes available to this user with meal type information
#         user_recipes = Recipe.objects.filter(
#             Q(author=self.request.user) | Q(is_public=True)
#         ).select_related(
#             'author'
#         ).prefetch_related(
#             'categories',
#             'meal_types'  # ADD THIS - prefetch meal types
#         ).annotate(
#             avg_rating=Avg('ratings__rating'),
#             rating_count=Count('ratings')
#         ).order_by('-created_at')
        
#         context['user_recipes'] = user_recipes
        
#         # NEW: Organize recipes by meal type for better filtering
#         recipes_by_meal_type = {}
#         for meal_type in MealType.objects.all():
#             recipes_by_meal_type[meal_type.name.lower()] = user_recipes.filter(
#                 meal_types=meal_type
#             ).distinct()
        
#         context['recipes_by_meal_type'] = recipes_by_meal_type
        
#         logger.info(f"Found {user_recipes.count()} recipes available for user {self.request.user.username}")
        
#     except Exception as e:
#         logger.error(f"Error fetching recipes for meal plan detail: {str(e)}")
#         context['user_recipes'] = Recipe.objects.none()
#         context['recipes_by_meal_type'] = {}
    
#     # Organize meal slots by week for better template display
#     weeks = []
#     current_date = meal_plan.start_date
    
#     while current_date <= meal_plan.end_date:
#         week_start = current_date - timedelta(days=current_date.weekday())
#         week_end = week_start + timedelta(days=6)
        
#         # Make sure we don't go beyond meal plan end date
#         if week_end > meal_plan.end_date:
#             week_end = meal_plan.end_date
        
#         week_data = {
#             'start_date': week_start,
#             'end_date': week_end,
#             'days': []
#         }
        
#         # Get dates for this week within meal plan range
#         week_date = max(week_start, meal_plan.start_date)
#         while week_date <= min(week_end, meal_plan.end_date):
#             day_slots = [slot for slot in meal_slots if slot.date == week_date]
#             week_data['days'].append({
#                 'date': week_date,
#                 'slots': day_slots,
#                 'is_today': week_date == date.today()
#             })
#             week_date += timedelta(days=1)
        
#         weeks.append(week_data)
#         current_date = week_end + timedelta(days=1)
    
#     context['organized_weeks'] = weeks
#     context['meal_types'] = MealType.objects.all().order_by('display_order')
    
#     # Recipe categories for filtering in the modal
#     try:
#         from recipe_hub.models import RecipeCategory
#         context['recipe_categories'] = RecipeCategory.objects.filter(
#             is_active=True
#         ).order_by('name')
#     except Exception as e:
#         logger.warning(f"Error fetching recipe categories: {str(e)}")
#         context['recipe_categories'] = []
    
#     # Shopping list preview (ingredients from all recipes)
#     ingredients = {}
#     for slot in meal_slots:
#         if slot.recipe:
#             try:
#                 # Handle the case where ingredients might not exist
#                 if hasattr(slot.recipe, 'ingredients'):
#                     for ingredient in slot.recipe.ingredients.all():
#                         key = f"{ingredient.name}_{ingredient.unit or 'unit'}"
#                         if key not in ingredients:
#                             ingredients[key] = {
#                                 'name': ingredient.name,
#                                 'unit': ingredient.unit or '',
#                                 'quantity': 0,
#                                 'recipes': []
#                             }
                        
#                         # Calculate quantity based on servings
#                         multiplier = slot.servings or 1
#                         try:
#                             quantity = float(ingredient.quantity) * multiplier
#                             ingredients[key]['quantity'] += quantity
#                         except (ValueError, TypeError):
#                             # Handle non-numeric quantities
#                             pass
                        
#                         if slot.recipe.title not in ingredients[key]['recipes']:
#                             ingredients[key]['recipes'].append(slot.recipe.title)
#             except Exception as e:
#                 logger.warning(f"Error processing ingredients for recipe {slot.recipe.id}: {str(e)}")
#                 continue
    
#     context['ingredients_preview'] = list(ingredients.values())[:10]
#     context['total_ingredients'] = len(ingredients)
    
#     # Meal plan statistics
#     total_slots = meal_slots.count()
#     filled_slots = meal_slots.filter(recipe__isnull=False).count()
#     context['meal_plan_stats'] = {
#         'total_slots': total_slots,
#         'filled_slots': filled_slots,
#         'empty_slots': total_slots - filled_slots,
#         'completion_percentage': round((filled_slots / total_slots) * 100, 1) if total_slots > 0 else 0
#     }
    
#     return context

# # Additional utility functions for templates
# def serialize_recipe_for_json(recipe):
#     """
#     Serialize a recipe object for JSON output.
#     """
#     return {
#         'id': recipe.id,
#         'title': recipe.title,
#         'slug': recipe.slug,
#         'description': recipe.description,
#         'prep_time': recipe.prep_time,
#         'cook_time': recipe.cook_time,
#         'total_time': recipe.total_time,
#         'servings': recipe.servings,
#         'difficulty': recipe.difficulty,
#         'difficulty_display': recipe.get_difficulty_display(),
#         'categories': [cat.name for cat in recipe.categories.all()],
#         'image_url': recipe.image.url if recipe.image else None,
#         'author': recipe.author.username,
#         'is_public': recipe.is_public,
#         'average_rating': recipe.average_rating,
#         'rating_count': recipe.rating_count,
#         'created_at': recipe.created_at.isoformat(),
#     }




# # Update your MealPlanListView.get_queryset() method with this:

# from django.db.models import Count

# # Replace your MealPlanListView class in meal_planner/views.py with this corrected version:

# class MealPlanListView(LoginRequiredMixin, ListView):
#     """
#     List view for meal plans - corrected to use actual model fields.
#     """
#     model = MealPlan
#     template_name = 'meal_planner/meal_plan_list.html'
#     context_object_name = 'meal_plans'
#     paginate_by = 20
    
#     def get_queryset(self):
#         """Get meal plans for current user with meal slot count."""
#         queryset = MealPlan.objects.filter(
#             owner=self.request.user
#         ).prefetch_related(
#             'meal_slots__recipe',
#             'meal_slots__meal_type'
#         ).annotate(
#             meal_count=Count('meal_slots')  # Add this annotation
#         ).order_by('-start_date')
        
#         # Filter by date range if provided
#         start_date = self.request.GET.get('start_date')
#         end_date = self.request.GET.get('end_date')
        
#         if start_date:
#             try:
#                 start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
#                 queryset = queryset.filter(start_date__gte=start_date)
#             except ValueError:
#                 pass
        
#         if end_date:
#             try:
#                 end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
#                 queryset = queryset.filter(end_date__lte=end_date)
#             except ValueError:
#                 pass
        
#         # Filter by active status
#         is_active = self.request.GET.get('is_active')
#         if is_active == 'true':
#             queryset = queryset.filter(is_active=True)
#         elif is_active == 'false':
#             queryset = queryset.filter(is_active=False)
        
#         return queryset
    
#     def get_context_data(self, **kwargs):
#         """Add additional context for meal plan list."""
#         context = super().get_context_data(**kwargs)
        
#         # Get meal types for filtering if MealType model exists
#         try:
#             meal_types = MealType.objects.all().order_by('display_order')
#             context['meal_types'] = meal_types
#         except:
#             context['meal_types'] = []
        
#         context['current_filters'] = {
#             'start_date': self.request.GET.get('start_date', ''),
#             'end_date': self.request.GET.get('end_date', ''),
#             'is_active': self.request.GET.get('is_active', ''),
#         }
        
#         # Add active count and limit info
#         context['active_count'] = MealPlan.objects.filter(
#             owner=self.request.user,
#             is_active=True
#         ).count()
        
#         try:
#             profile = self.request.user.profile
#             context['meal_plan_limit'] = profile.subscription_tier.max_menus
#             context['can_create_meal_plan'] = (
#                 context['meal_plan_limit'] == -1 or 
#                 context['active_count'] < context['meal_plan_limit']
#             )
#         except:
#             context['meal_plan_limit'] = -1
#             context['can_create_meal_plan'] = True
        
#         # Add filter form if you have one
#         try:
#             from .forms import MealPlanFilterForm
#             context['filter_form'] = MealPlanFilterForm(self.request.GET)
#         except:
#             context['filter_form'] = None
        
#         return context



# class MealPlanDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
#     """Detailed view of a meal plan."""
#     model = MealPlan
#     template_name = 'meal_planner/meal_plan_detail.html'
#     context_object_name = 'meal_plan'
    
#     def test_func(self):
#         """Check if user owns this meal plan."""
#         meal_plan = self.get_object()
#         return meal_plan.owner == self.request.user
    
#     def get_context_data(self, **kwargs):
#         """Add organized meal data to context."""
#         context = super().get_context_data(**kwargs)
#         meal_plan = self.object
        
#         # Get all meal slots organized by date
#         meal_slots = meal_plan.meal_slots.select_related(
#             'recipe', 'meal_type'
#         ).prefetch_related(
#             'recipe__categories'
#         ).order_by('date', 'meal_type__display_order')
        
#         # Organize by week
#         weeks = meal_plan.get_week_dates()
#         organized_weeks = []
        
#         for week_dates in weeks:
#             week_data = {
#                 'start_date': week_dates[0],
#                 'end_date': week_dates[-1],
#                 'days': []
#             }
            
#             for day_date in week_dates:
#                 day_slots = [slot for slot in meal_slots if slot.date == day_date]
#                 week_data['days'].append({
#                     'date': day_date,
#                     'slots': day_slots,
#                     'is_today': day_date == date.today()
#                 })
            
#             organized_weeks.append(week_data)
        
#         context['organized_weeks'] = organized_weeks
#         context['meal_types'] = MealType.objects.all().order_by('display_order')
        
#         # Shopping list preview (ingredients from all recipes)
#         ingredients = {}
#         for slot in meal_slots:
#             if slot.recipe:
#                 for ingredient in slot.recipe.ingredients.all():
#                     key = f"{ingredient.name}_{ingredient.unit}"
#                     if key not in ingredients:
#                         ingredients[key] = {
#                             'name': ingredient.name,
#                             'unit': ingredient.unit,
#                             'quantity': 0,
#                             'recipes': []
#                         }
                    
#                     # Calculate quantity based on servings
#                     multiplier = slot.servings
#                     try:
#                         quantity = float(ingredient.quantity) * multiplier
#                         ingredients[key]['quantity'] += quantity
#                     except ValueError:
#                         # Handle non-numeric quantities
#                         pass
                    
#                     ingredients[key]['recipes'].append(slot.recipe.title)
        
#         context['ingredients_preview'] = list(ingredients.values())[:10]
#         context['total_ingredients'] = len(ingredients)
        
#         return context


# import traceback
# from django.contrib.auth.decorators import login_required
# from django.contrib.auth.mixins import LoginRequiredMixin
# from django.views.generic import CreateView
# from django.urls import reverse_lazy
# from django.contrib import messages
# from django.shortcuts import redirect
# from django.utils.decorators import method_decorator

# # Add these imports at the top of your views.py file if they're missing:
# import logging
# from datetime import timedelta
# from django.db import transaction

# logger = logging.getLogger(__name__)

# # Replace your entire MealPlanCreateView class with this:

# @method_decorator(login_required, name='dispatch')
# class MealPlanCreateView(CreateView):
#     """Create a new meal plan with automatic meal slot generation."""
#     model = MealPlan
#     form_class = MealPlanForm
#     template_name = 'meal_planner/meal_plan_form.html'
#     success_url = reverse_lazy('meal_planner:meal_plan_list')
    
#     def dispatch(self, request, *args, **kwargs):
#         """Check if user can create meal plans."""
#         try:
#             profile = request.user.profile
#             subscription_tier = profile.subscription_tier
            
#             if subscription_tier.max_menus != -1:
#                 active_count = MealPlan.objects.filter(
#                     owner=request.user,
#                     is_active=True
#                 ).count()
#                 if active_count >= subscription_tier.max_menus:
#                     messages.error(
#                         request,
#                         f"You've reached your meal plan limit ({subscription_tier.max_menus}). "
#                         f"Please deactivate an existing plan or upgrade your subscription."
#                     )
#                     return redirect('meal_planner:meal_plan_list')
#         except Exception as e:
#             print(f"DEBUG: Error checking meal plan limits: {str(e)}")
#             logger.error(f"Error checking meal plan limits: {str(e)}")
#             # Continue anyway - don't block user if there's an error
        
#         return super().dispatch(request, *args, **kwargs)
    
#     def form_valid(self, form):
#         """
#         Create meal plan and automatically generate meal slots.
#         """
#         print("=== DEBUG: form_valid called ===")
#         print(f"DEBUG: User: {self.request.user.username}")
#         print(f"DEBUG: Form data: {form.cleaned_data}")
        
#         try:
#             # Set the owner
#             form.instance.owner = self.request.user
#             print(f"DEBUG: Set owner to {self.request.user}")
            
#             # Save the meal plan first
#             with transaction.atomic():
#                 response = super().form_valid(form)
#                 meal_plan = self.object
                
#                 print(f"DEBUG: Meal plan saved - ID: {meal_plan.pk}")
#                 print(f"DEBUG: Meal plan name: {meal_plan.name}")
#                 print(f"DEBUG: Start date: {meal_plan.start_date}")
#                 print(f"DEBUG: End date: {meal_plan.end_date}")
#                 print(f"DEBUG: Duration: {meal_plan.duration_days} days")
                
#                 # Get all meal types
#                 meal_types = MealType.objects.all().order_by('display_order')
#                 print(f"DEBUG: Found {meal_types.count()} meal types")
                
#                 if not meal_types.exists():
#                     print("DEBUG: ERROR - No meal types found!")
#                     messages.error(
#                         self.request,
#                         "No meal types configured. Please run: python manage.py create_meal_types"
#                     )
#                     return self.form_invalid(form)
                
#                 for mt in meal_types:
#                     print(f"DEBUG: Meal type - ID: {mt.id}, Name: {mt.name}, Order: {mt.display_order}")
                
#                 # Create meal slots for each day and meal type
#                 slots_created = 0
#                 current_date = meal_plan.start_date
                
#                 print(f"DEBUG: Starting slot creation from {current_date} to {meal_plan.end_date}")
                
#                 while current_date <= meal_plan.end_date:
#                     print(f"DEBUG: Processing date: {current_date}")
                    
#                     for meal_type in meal_types:
#                         try:
#                             print(f"DEBUG: Creating slot for {current_date} - {meal_type.name}")
                            
#                             slot, created = MealSlot.objects.get_or_create(
#                                 meal_plan=meal_plan,
#                                 date=current_date,
#                                 meal_type=meal_type,
#                                 defaults={
#                                     'servings': 1,
#                                     'notes': ''
#                                 }
#                             )
                            
#                             if created:
#                                 slots_created += 1
#                                 print(f"DEBUG: ✓ Created slot ID {slot.id} for {current_date} - {meal_type.name}")
#                             else:
#                                 print(f"DEBUG: - Slot already existed for {current_date} - {meal_type.name}")
                                
#                         except Exception as slot_error:
#                             print(f"DEBUG: ERROR creating slot: {str(slot_error)}")
#                             logger.error(
#                                 f"Error creating meal slot for {current_date} "
#                                 f"- {meal_type.name}: {str(slot_error)}"
#                             )
#                             continue
                    
#                     current_date += timedelta(days=1)
                
#                 print(f"DEBUG: Total slots created: {slots_created}")
                
#                 # Verify slots were created
#                 actual_slots = MealSlot.objects.filter(meal_plan=meal_plan)
#                 print(f"DEBUG: Slots in database for this meal plan: {actual_slots.count()}")
                
#                 for slot in actual_slots:
#                     print(f"DEBUG: Slot - Date: {slot.date}, Type: {slot.meal_type.name}, ID: {slot.id}")
                
#                 logger.info(
#                     f"Created {slots_created} meal slots for meal plan '{meal_plan.name}' "
#                     f"({meal_plan.duration_days} days × {meal_types.count()} meal types)"
#                 )
                
#                 # Success message
#                 messages.success(
#                     self.request,
#                     f"Meal plan '{meal_plan.name}' created successfully with "
#                     f"{slots_created} meal slots ready for planning!"
#                 )
                
#                 # Log activity
#                 try:
#                     ActivityLog.objects.create(
#                         user=self.request.user,
#                         action='create_meal_plan',
#                         details=f"Created meal plan: {meal_plan.name} with {slots_created} slots"
#                     )
#                 except Exception as log_error:
#                     print(f"DEBUG: Failed to log activity: {str(log_error)}")
#                     logger.warning(f"Failed to log activity: {str(log_error)}")
                
#                 return response
            
#         except Exception as e:
#             print(f"DEBUG: ERROR in form_valid: {str(e)}")
#             print(f"DEBUG: Exception type: {type(e)}")
#             import traceback
#             print(f"DEBUG: Traceback: {traceback.format_exc()}")
            
#             logger.error(
#                 f"Error creating meal plan for user {self.request.user.username}: {str(e)}"
#             )
#             logger.error(traceback.format_exc())
            
#             messages.error(
#                 self.request,
#                 f"Error creating meal plan: {str(e)}. Please try again."
#             )
#             return self.form_invalid(form)
    
#     def get_success_url(self):
#         """Redirect to the newly created meal plan's detail page."""
#         return reverse_lazy('meal_planner:meal_plan_detail', kwargs={'pk': self.object.pk})







# @method_decorator(login_required, name='dispatch')
# class MealPlanUpdateView(UserPassesTestMixin, UpdateView):
#     """Update an existing meal plan and adjust meal slots as needed."""
#     model = MealPlan
#     form_class = MealPlanForm
#     template_name = 'meal_planner/meal_plan_form.html'
    
#     def test_func(self):
#         """Check if user owns this meal plan."""
#         meal_plan = self.get_object()
#         return meal_plan.owner == self.request.user
    
#     @transaction.atomic
#     def form_valid(self, form):
#         """
#         Update meal plan and adjust meal slots if date range changed.
        
#         This method:
#         1. Compares old and new date ranges
#         2. Removes slots outside the new range
#         3. Creates slots for new dates
#         4. Handles errors gracefully
#         """
#         # Store original date range
#         old_start = self.object.start_date
#         old_end = self.object.end_date
        
#         logger.info(
#             f"Updating meal plan '{self.object.name}' for user {self.request.user.username}"
#         )
#         logger.info(f"Old range: {old_start} to {old_end}")
        
#         # Update the meal plan
#         response = super().form_valid(form)
#         meal_plan = self.object
        
#         logger.info(f"New range: {meal_plan.start_date} to {meal_plan.end_date}")
        
#         # Check if date range changed
#         date_range_changed = (
#             old_start != meal_plan.start_date or 
#             old_end != meal_plan.end_date
#         )
        
#         if date_range_changed:
#             logger.info("Date range changed, adjusting meal slots...")
#             slots_removed, slots_created = self._adjust_meal_slots(
#                 meal_plan, old_start, old_end
#             )
            
#             if slots_removed > 0 or slots_created > 0:
#                 messages.info(
#                     self.request,
#                     f"Date range updated: {slots_removed} slots removed, "
#                     f"{slots_created} slots added."
#                 )
        
#         # Log activity
#         try:
#             from auth_hub.models import ActivityLog
#             ActivityLog.objects.create(
#                 user=self.request.user,
#                 action='update_meal_plan',
#                 details=f"Updated meal plan: {meal_plan.name}"
#             )
#         except Exception as log_error:
#             logger.warning(f"Failed to log activity: {str(log_error)}")
        
#         messages.success(
#             self.request,
#             f"Meal plan '{meal_plan.name}' updated successfully!"
#         )
        
#         logger.info(
#             f"Meal plan updated: {meal_plan.name} by {self.request.user.username} "
#             f"(ID: {meal_plan.pk})"
#         )
        
#         return response
    
#     def _adjust_meal_slots(self, meal_plan, old_start, old_end):
#         """
#         Adjust meal slots when date range changes.
        
#         Args:
#             meal_plan: The updated meal plan
#             old_start: Previous start date
#             old_end: Previous end date
            
#         Returns:
#             tuple: (slots_removed, slots_created)
#         """
#         slots_removed = 0
#         slots_created = 0
        
#         try:
#             # Remove slots outside the new date range
#             removed_slots = MealSlot.objects.filter(
#                 meal_plan=meal_plan
#             ).exclude(
#                 date__gte=meal_plan.start_date,
#                 date__lte=meal_plan.end_date
#             )
            
#             slots_removed = removed_slots.count()
#             if slots_removed > 0:
#                 logger.info(f"Removing {slots_removed} slots outside new date range")
#                 removed_slots.delete()
            
#             # Get meal types
#             meal_types = MealType.objects.all().order_by('display_order')
#             if not meal_types.exists():
#                 logger.warning("No meal types found, creating default meal types")
#                 self._create_default_meal_types()
#                 meal_types = MealType.objects.all().order_by('display_order')
            
#             # Create missing slots for new dates
#             current_date = meal_plan.start_date
#             while current_date <= meal_plan.end_date:
#                 for meal_type in meal_types:
#                     try:
#                         slot, created = MealSlot.objects.get_or_create(
#                             meal_plan=meal_plan,
#                             date=current_date,
#                             meal_type=meal_type,
#                             defaults={
#                                 'servings': 1,
#                                 'notes': ''
#                             }
#                         )
#                         if created:
#                             slots_created += 1
                            
#                     except Exception as slot_error:
#                         logger.error(
#                             f"Error creating meal slot for {current_date} "
#                             f"- {meal_type.name}: {str(slot_error)}"
#                         )
#                         continue
                
#                 current_date += timedelta(days=1)
            
#             if slots_created > 0:
#                 logger.info(f"Created {slots_created} new meal slots")
            
#         except Exception as e:
#             logger.error(f"Error adjusting meal slots: {str(e)}")
#             # Don't raise the error - the meal plan update should still succeed
        
#         return slots_removed, slots_created
    
#     def _create_default_meal_types(self):
#         """
#         Create default meal types if none exist.
        
#         This ensures the system always has basic meal types available.
#         """
#         from datetime import time
        
#         default_meal_types = [
#             {
#                 'name': 'Breakfast',
#                 'display_order': 1,
#                 'default_time': time(7, 0),
#                 'icon': 'bi-sunrise'
#             },
#             {
#                 'name': 'Lunch',
#                 'display_order': 2,
#                 'default_time': time(12, 0),
#                 'icon': 'bi-sun'
#             },
#             {
#                 'name': 'Dinner',
#                 'display_order': 3,
#                 'default_time': time(18, 0),
#                 'icon': 'bi-moon'
#             },
#             {
#                 'name': 'Snack',
#                 'display_order': 4,
#                 'default_time': time(15, 0),
#                 'icon': 'bi-cup-straw'
#             }
#         ]
        
#         for meal_type_data in default_meal_types:
#             try:
#                 MealType.objects.get_or_create(
#                     name=meal_type_data['name'],
#                     defaults={
#                         'display_order': meal_type_data['display_order'],
#                         'default_time': meal_type_data['default_time'],
#                         'icon': meal_type_data['icon']
#                     }
#                 )
#                 logger.info(f"Created default meal type: {meal_type_data['name']}")
                
#             except Exception as e:
#                 logger.error(f"Error creating meal type {meal_type_data['name']}: {str(e)}")
    
#     def get_success_url(self):
#         """Redirect to the updated meal plan's detail page."""
#         return self.object.get_absolute_url()




# @method_decorator(login_required, name='dispatch')
# class MealPlanDeleteView(UserPassesTestMixin, DeleteView):
#     """Delete a meal plan."""
#     model = MealPlan
#     template_name = 'meal_planner/meal_plan_confirm_delete.html'
#     success_url = reverse_lazy('meal_planner:meal_plan_list')
    
#     def test_func(self):
#         """Check if user owns this meal plan."""
#         meal_plan = self.get_object()
#         return meal_plan.owner == self.request.user
    
#     def delete(self, request, *args, **kwargs):
#         """Log deletion and show success message."""
#         meal_plan = self.get_object()
#         meal_plan_name = meal_plan.name
        
#         try:
#             # Log activity
#             ActivityLog.objects.create(
#                 user=request.user,
#                 action='delete_meal_plan',
#                 details=f"Deleted meal plan: {meal_plan_name}"
#             )
            
#             response = super().delete(request, *args, **kwargs)
            
#             messages.success(
#                 request,
#                 f"Meal plan '{meal_plan_name}' deleted successfully."
#             )
            
#             logger.info(
#                 f"Meal plan deleted: {meal_plan_name} by {request.user.username}"
#             )
            
#             return response
            
#         except Exception as e:
#             logger.error(
#                 f"Error deleting meal plan {meal_plan.pk} for user "
#                 f"{request.user.username}: {str(e)}"
#             )
#             messages.error(
#                 request,
#                 "An error occurred while deleting the meal plan."
#             )
#             return redirect(meal_plan.get_absolute_url())


# @login_required
# def update_meal_slot(request, pk):
#     """AJAX endpoint to update a meal slot."""
#     if request.method != 'POST':
#         return HttpResponseForbidden()
    
#     meal_slot = get_object_or_404(MealSlot, pk=pk)
    
#     # Check ownership
#     if meal_slot.meal_plan.owner != request.user:
#         return HttpResponseForbidden()
    
#     form = QuickMealSlotForm(request.POST, user=request.user)
    
#     if form.is_valid():
#         try:
#             # Update meal slot
#             recipe_id = form.cleaned_data.get('recipe_id')
#             if recipe_id:
#                 meal_slot.recipe_id = recipe_id
#             else:
#                 meal_slot.recipe = None
            
#             if form.cleaned_data.get('servings'):
#                 meal_slot.servings = form.cleaned_data['servings']
            
#             if 'notes' in form.cleaned_data:
#                 meal_slot.notes = form.cleaned_data['notes']
            
#             meal_slot.save()
            
#             # Prepare response data
#             response_data = {
#                 'success': True,
#                 'slot': {
#                     'id': meal_slot.id,
#                     'recipe': {
#                         'id': meal_slot.recipe.id,
#                         'title': meal_slot.recipe.title,
#                         'prep_time': meal_slot.recipe.prep_time,
#                         'cook_time': meal_slot.recipe.cook_time,
#                         'servings': meal_slot.recipe.servings,
#                         'difficulty': meal_slot.recipe.difficulty,
#                         'image_url': meal_slot.recipe.image.url if meal_slot.recipe.image else None,
#                     } if meal_slot.recipe else None,
#                     'servings': meal_slot.servings,
#                     'notes': meal_slot.notes,
#                 }
#             }
            
#             logger.info(
#                 f"Meal slot updated: {meal_slot.date} - {meal_slot.meal_type.name} "
#                 f"by {request.user.username}"
#             )
            
#             return JsonResponse(response_data)
            
#         except Exception as e:
#             logger.error(
#                 f"Error updating meal slot {pk} for user {request.user.username}: {str(e)}"
#             )
#             return JsonResponse({'success': False, 'error': str(e)}, status=500)
#     else:
#         return JsonResponse({'success': False, 'errors': form.errors}, status=400)


# from django.views.decorators.csrf import csrf_exempt
# from django.http import HttpResponse
# import hashlib

# from django.contrib.auth.decorators import login_required

# from django.contrib.auth.decorators import login_required

# from django.contrib.auth.decorators import login_required

# @login_required
# def create_meal_slot(request):
#     """Create a meal slot and save to database."""
#     if request.method != 'POST':
#         return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
#     try:
#         # Parse JSON data
#         data = json.loads(request.body)
#         logger.info(f"Creating meal slot for user {request.user.username} with data: {data}")
        
#         # Extract and validate data
#         recipe_id = data.get('recipe_id')
#         date_str = data.get('date')
#         meal_type_id = data.get('meal_type_id')
#         servings = data.get('servings', 1)
#         notes = data.get('notes', '')
        
#         if not all([recipe_id, date_str, meal_type_id]):
#             return JsonResponse({
#                 'success': False, 
#                 'error': 'Missing required fields'
#             }, status=400)
        
#         # Parse date
#         try:
#             slot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
#         except ValueError:
#             return JsonResponse({
#                 'success': False,
#                 'error': f'Invalid date format: {date_str}'
#             }, status=400)
        
#         # Get meal type
#         try:
#             meal_type = MealType.objects.get(id=meal_type_id)
#         except MealType.DoesNotExist:
#             return JsonResponse({
#                 'success': False,
#                 'error': f'Meal type not found: {meal_type_id}'
#             }, status=400)
        
#         # Get recipe
#         try:
#             recipe = Recipe.objects.get(id=recipe_id)
#             # Check access
#             if not recipe.is_public and recipe.author != request.user:
#                 return JsonResponse({
#                     'success': False,
#                     'error': 'You do not have access to this recipe'
#                 }, status=403)
#         except Recipe.DoesNotExist:
#             return JsonResponse({
#                 'success': False,
#                 'error': f'Recipe not found: {recipe_id}'
#             }, status=400)
        
#         # Find or create meal plan
#         meal_plan = MealPlan.objects.filter(
#             owner=request.user,
#             start_date__lte=slot_date,
#             end_date__gte=slot_date,
#             is_active=True
#         ).first()
        
#         if not meal_plan:
#             # Create a weekly meal plan
#             start_date = slot_date - timedelta(days=slot_date.weekday())
#             end_date = start_date + timedelta(days=6)
            
#             meal_plan = MealPlan.objects.create(
#                 owner=request.user,
#                 name=f"Week of {start_date.strftime('%B %d, %Y')}",
#                 start_date=start_date,
#                 end_date=end_date
#             )
#             logger.info(f"Created new meal plan: {meal_plan.name}")
        
#         # Create or update meal slot
#         meal_slot, created = MealSlot.objects.get_or_create(
#             meal_plan=meal_plan,
#             date=slot_date,
#             meal_type=meal_type,
#             defaults={
#                 'recipe': recipe,
#                 'servings': servings,
#                 'notes': notes
#             }
#         )
        
#         if not created:
#             # Update existing slot
#             meal_slot.recipe = recipe
#             meal_slot.servings = servings
#             meal_slot.notes = notes
#             meal_slot.save()
#             logger.info(f"Updated existing meal slot {meal_slot.id}")
#         else:
#             logger.info(f"Created new meal slot {meal_slot.id}")
        
#         # Prepare response for calendar
#         response_data = {
#             'success': True,
#             'message': 'Meal slot created successfully',
#             'meal_slot': {
#                 'id': meal_slot.id,
#                 'title': f"{meal_type.name}: {recipe.title}",
#                 'start': slot_date.isoformat(),
#                 'backgroundColor': _get_meal_color(meal_type.name.lower()),
#                 'borderColor': _get_meal_color(meal_type.name.lower()),
#                 'extendedProps': {
#                     'mealType': meal_type.name.lower(),
#                     'mealTypeId': meal_type.id,
#                     'recipeId': recipe.id,
#                     'recipeTitle': recipe.title,
#                     'recipeSlug': getattr(recipe, 'slug', ''),
#                     'servings': meal_slot.servings,
#                     'notes': meal_slot.notes or '',
#                     'mealPlanId': meal_plan.id,
#                     'mealPlanName': meal_plan.name,
#                 }
#             }
#         }
        
#         logger.info(f"Successfully created meal slot {meal_slot.id} for user {request.user.username}")
#         return JsonResponse(response_data)
        
#     except json.JSONDecodeError:
#         return JsonResponse({
#             'success': False,
#             'error': 'Invalid JSON data'
#         }, status=400)
        
#     except Exception as e:
#         logger.error(f"Error creating meal slot for user {request.user.username}: {str(e)}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return JsonResponse({
#             'success': False,
#             'error': 'An unexpected error occurred'
#         }, status=500)








# def _get_meal_color(meal_type_name):
#     """Helper function to get color for meal type."""
#     colors = {
#         'breakfast': '#28a745',  # Green
#         'lunch': '#ffc107',      # Yellow
#         'dinner': '#dc3545',     # Red
#         'snack': '#6c757d',      # Gray
#     }
#     return colors.get(meal_type_name.lower(), '#007bff')  # Default blue





# from django.views.decorators.http import require_POST
# from django.http import JsonResponse, HttpResponseForbidden

# @require_POST
# @login_required
# def delete_meal_slot(request, pk):
#     """
#     AJAX endpoint to clear a meal slot locally and delete the corresponding
#     Outlook event if syncing is enabled.

#     Steps:
#       1. Verify method is POST and user owns the slot.
#       2. Clear recipe, notes, and servings on the MealSlot.
#       3. If Outlook sync is enabled, enqueue deletion of the remote event
#          and remove the CalendarEvent record.

#     Returns:
#         JsonResponse({'success': True}) on success,
#         or JsonResponse({'success': False, 'error': ...}, status=...) on failure.
#     """
#     # Fetch the slot and check ownership
#     meal_slot = get_object_or_404(MealSlot, pk=pk)
#     if meal_slot.meal_plan.owner != request.user:
#         logger.warning(
#             f"User {request.user.username} tried to clear slot {pk} they don't own"
#         )
#         return HttpResponseForbidden()

#     try:
#         # Clear the slot
#         meal_slot.recipe = None
#         meal_slot.notes = ''
#         meal_slot.servings = 1
#         meal_slot.save()
#         logger.info(
#             f"Cleared meal slot {pk}: date={meal_slot.date}, "
#             f"type={meal_slot.meal_type.name}, user={request.user.username}"
#         )

#         # If Outlook sync is on, delete remote event too
#         token = getattr(request.user, 'microsoft_token', None)
#         if token and token.calendar_sync_enabled:
#             from meal_planner.models import CalendarEvent
#             try:
#                 cal_evt = CalendarEvent.objects.get(
#                     meal_slot=meal_slot,
#                     user=request.user
#                 )
#                 # Enqueue remote deletion
#                 from meal_planner.tasks import delete_calendar_event
#                 delete_calendar_event.delay(cal_evt.outlook_event_id, request.user.id)
#                 # Remove local record
#                 cal_evt.delete()
#                 logger.info(
#                     f"Scheduled deletion of Outlook event {cal_evt.outlook_event_id} "
#                     f"for slot {pk}"
#                 )
#             except CalendarEvent.DoesNotExist:
#                 logger.debug(
#                     f"No CalendarEvent for slot {pk}; nothing to delete remotely"
#                 )

#         return JsonResponse({'success': True})

#     except Exception as e:
#         import traceback
#         tb = traceback.format_exc()
#         logger.error(
#             f"Error clearing meal slot {pk} for user {request.user.username}: {e}\n{tb}"
#         )
#         return JsonResponse(
#             {'success': False, 'error': 'Failed to clear meal slot.'},
#             status=500
#         )



# class MealPlanTemplateListView(LoginRequiredMixin, ListView):
#     """List view for meal plan templates."""
#     model = MealPlanTemplate
#     template_name = 'meal_planner/template_list.html'
#     context_object_name = 'templates'
#     paginate_by = 12
    
#     def get_queryset(self):
#         """Get templates available to user."""
#         return MealPlanTemplate.objects.filter(
#             Q(owner=self.request.user) | Q(is_public=True)
#         ).select_related('owner').annotate(
#             slot_count=Count('template_slots')
#         ).order_by('-created_at')
    
#     def get_context_data(self, **kwargs):
#         """Add user's templates count to context."""
#         context = super().get_context_data(**kwargs)
#         context['user_templates_count'] = MealPlanTemplate.objects.filter(
#             owner=self.request.user
#         ).count()
#         return context


# @login_required
# def apply_template(request):
#     """Apply a template to create a new meal plan."""
#     if request.method == 'POST':
#         form = ApplyTemplateForm(request.POST, user=request.user)
#         if form.is_valid():
#             try:
#                 template = form.cleaned_data['template']
#                 start_date = form.cleaned_data['start_date']
#                 name = form.cleaned_data.get('name') or None
                
#                 # Check if user can create meal plan
#                 profile = request.user.profile
#                 subscription_tier = profile.subscription_tier
                
#                 if subscription_tier.max_menus != -1:
#                     active_count = MealPlan.objects.filter(
#                         owner=request.user,
#                         is_active=True
#                     ).count()
#                     if active_count >= subscription_tier.max_menus:
#                         messages.error(
#                             request,
#                             f"You've reached your meal plan limit ({subscription_tier.max_menus})."
#                         )
#                         return redirect('meal_planner:template_list')
                
#                 # Create meal plan from template
#                 meal_plan = template.create_meal_plan(start_date, name)
                
#                 # Log activity
#                 ActivityLog.objects.create(
#                     user=request.user,
#                     action='apply_template',
#                     details=f"Created meal plan from template: {template.name}"
#                 )
                
#                 messages.success(
#                     request,
#                     f"Meal plan created from template '{template.name}'!"
#                 )
                
#                 return redirect('meal_planner:meal_plan_detail', pk=meal_plan.pk)
                
#             except Exception as e:
#                 logger.error(
#                     f"Error applying template for user {request.user.username}: {str(e)}"
#                 )
#                 messages.error(request, "An error occurred while applying the template.")
#     else:
#         form = ApplyTemplateForm(user=request.user)
    
#     return render(request, 'meal_planner/apply_template.html', {
#         'form': form
#     })


# # Add these views to your views.py

# @method_decorator(login_required, name='dispatch')
# class MealPlanTemplateCreateView(CreateView):
#     """Create a new meal plan template."""
#     model = MealPlanTemplate
#     form_class = MealPlanTemplateForm
#     template_name = 'meal_planner/template_form.html'
#     success_url = reverse_lazy('meal_planner:template_list')
    
#     def get_form_kwargs(self):
#         """Pass user to form."""
#         kwargs = super().get_form_kwargs()
#         kwargs['user'] = self.request.user
#         return kwargs
    
#     def form_valid(self, form):
#         """Set owner and create template."""
#         form.instance.owner = self.request.user
        
#         try:
#             response = super().form_valid(form)
            
#             # Log activity
#             ActivityLog.objects.create(
#                 user=self.request.user,
#                 action='create_template',
#                 details=f"Created template: {self.object.name}"
#             )
            
#             messages.success(
#                 self.request,
#                 f"Template '{self.object.name}' created successfully!"
#             )
            
#             return response
            
#         except Exception as e:
#             logger.error(
#                 f"Error creating template for user {self.request.user.username}: {str(e)}"
#             )
#             messages.error(
#                 self.request,
#                 "An error occurred while creating the template."
#             )
#             return self.form_invalid(form)


# @method_decorator(login_required, name='dispatch')
# class MealPlanTemplateUpdateView(UserPassesTestMixin, UpdateView):
#     """Update an existing meal plan template."""
#     model = MealPlanTemplate
#     form_class = MealPlanTemplateForm
#     template_name = 'meal_planner/template_form.html'
#     success_url = reverse_lazy('meal_planner:template_list')
    
#     def test_func(self):
#         """Check if user owns this template."""
#         template = self.get_object()
#         return template.owner == self.request.user
    
#     def get_form_kwargs(self):
#         """Pass user to form."""
#         kwargs = super().get_form_kwargs()
#         kwargs['user'] = self.request.user
#         return kwargs
    
#     def form_valid(self, form):
#         """Update template."""
#         try:
#             response = super().form_valid(form)
            
#             # Log activity
#             ActivityLog.objects.create(
#                 user=self.request.user,
#                 action='update_template',
#                 details=f"Updated template: {self.object.name}"
#             )
            
#             messages.success(
#                 self.request,
#                 f"Template '{self.object.name}' updated successfully!"
#             )
            
#             return response
            
#         except Exception as e:
#             logger.error(
#                 f"Error updating template for user {self.request.user.username}: {str(e)}"
#             )
#             messages.error(
#                 self.request,
#                 "An error occurred while updating the template."
#             )
#             return self.form_invalid(form)


# @method_decorator(login_required, name='dispatch')
# class MealPlanTemplateDeleteView(UserPassesTestMixin, DeleteView):
#     """Delete a meal plan template."""
#     model = MealPlanTemplate
#     template_name = 'meal_planner/template_confirm_delete.html'
#     success_url = reverse_lazy('meal_planner:template_list')
    
#     def test_func(self):
#         """Check if user owns this template."""
#         template = self.get_object()
#         return template.owner == self.request.user
    
#     def delete(self, request, *args, **kwargs):
#         """Log deletion and show success message."""
#         template = self.get_object()
#         template_name = template.name
        
#         try:
#             # Log activity
#             ActivityLog.objects.create(
#                 user=request.user,
#                 action='delete_template',
#                 details=f"Deleted template: {template_name}"
#             )
            
#             response = super().delete(request, *args, **kwargs)
            
#             messages.success(
#                 request,
#                 f"Template '{template_name}' deleted successfully."
#             )
            
#             return response
            
#         except Exception as e:
#             logger.error(
#                 f"Error deleting template {template.pk} for user "
#                 f"{request.user.username}: {str(e)}"
#             )
#             messages.error(
#                 request,
#                 "An error occurred while deleting the template."
#             )
#             return redirect(template.get_absolute_url())
        



# @login_required
# def create_meal_slots_for_plan(request):
#     """Create meal slots for an existing meal plan."""
#     if request.method != 'POST':
#         return JsonResponse({'success': False, 'error': 'POST required'})
    
#     try:
#         import json
#         data = json.loads(request.body)
#         meal_plan_id = data.get('meal_plan_id')
        
#         if not meal_plan_id:
#             return JsonResponse({'success': False, 'error': 'meal_plan_id required'})
        
#         # Get the meal plan
#         meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, owner=request.user)
        
#         # Get all meal types
#         meal_types = MealType.objects.all().order_by('display_order')
        
#         if not meal_types.exists():
#             # Create default meal types if none exist
#             meal_types = [
#                 MealType.objects.create(name='Breakfast', display_name='Breakfast', display_order=1),
#                 MealType.objects.create(name='Lunch', display_name='Lunch', display_order=2),
#                 MealType.objects.create(name='Dinner', display_name='Dinner', display_order=3),
#                 MealType.objects.create(name='Snack', display_name='Snack', display_order=4),
#             ]
        
#         # Create meal slots for each day and meal type
#         created_count = 0
#         current_date = meal_plan.start_date
        
#         while current_date <= meal_plan.end_date:
#             for meal_type in meal_types:
#                 # Create slot if it doesn't exist
#                 slot, created = MealSlot.objects.get_or_create(
#                     meal_plan=meal_plan,
#                     date=current_date,
#                     meal_type=meal_type,
#                     defaults={
#                         'servings': 1,
#                         'notes': ''
#                     }
#                 )
#                 if created:
#                     created_count += 1
            
#             current_date += timedelta(days=1)
        
#         logger.info(f"Created {created_count} meal slots for plan {meal_plan.name}")
        
#         return JsonResponse({
#             'success': True, 
#             'message': f'Created {created_count} meal slots',
#             'created_count': created_count
#         })
        
#     except Exception as e:
#         logger.error(f"Error creating meal slots: {str(e)}")
#         return JsonResponse({'success': False, 'error': str(e)})


# # Add this view

# @method_decorator(login_required, name='dispatch')
# class CalendarSyncSettingsView(TemplateView):
#     """
#     View for managing calendar synchronization settings.
#     """
#     template_name = 'meal_planner/calendar_sync_settings.html'
    
#     def get_context_data(self, **kwargs):
#         """Add calendar sync data to context."""
#         context = super().get_context_data(**kwargs)
        
#         # Check if Microsoft account is connected
#         context['microsoft_connected'] = hasattr(
#             self.request.user, 
#             'microsoft_token'
#         )
        
#         if context['microsoft_connected']:
#             token = self.request.user.microsoft_token
#             context['sync_enabled'] = token.calendar_sync_enabled
#             context['last_sync'] = token.last_sync
            
#             # Get sync statistics
#             from meal_planner.models import CalendarEvent
#             context['synced_events'] = CalendarEvent.objects.filter(
#                 user=self.request.user,
#                 sync_status='synced'
#             ).count()
            
#             context['pending_events'] = CalendarEvent.objects.filter(
#                 user=self.request.user,
#                 sync_status='pending'
#             ).count()
            
#             context['error_events'] = CalendarEvent.objects.filter(
#                 user=self.request.user,
#                 sync_status='error'
#             ).count()
        
#         return context
    
#     def post(self, request, *args, **kwargs):
#         """Handle enabling/disabling sync."""
#         if hasattr(request.user, 'microsoft_token'):
#             token = request.user.microsoft_token
#             action = request.POST.get('action')
            
#             if action == 'enable':
#                 token.calendar_sync_enabled = True
#                 token.save()
#                 messages.success(request, "Calendar sync enabled!")
                
#                 # Trigger immediate sync
#                 from meal_planner.tasks import sync_user_calendar
#                 sync_user_calendar.delay(request.user.id)
                
#             elif action == 'disable':
#                 token.calendar_sync_enabled = False
#                 token.save()
#                 messages.info(request, "Calendar sync disabled.")
            
#             elif action == 'sync_now':
#                 # Trigger manual sync
#                 from meal_planner.tasks import sync_user_calendar
#                 sync_user_calendar.delay(request.user.id)
#                 messages.info(request, "Calendar sync started. Check back in a few moments.")
        
#         return redirect('meal_planner:calendar_sync_settings')




# @login_required
# def sync_meal_plan(request, pk):
#     """
#     Sync a specific meal plan to Outlook calendar.
    
#     Args:
#         request: HTTP request
#         pk: Primary key of the meal plan
        
#     Returns:
#         JSON response with sync status
#     """
#     if request.method != 'POST':
#         return JsonResponse({'success': False, 'error': 'POST request required'})
    
#     try:
#         # Get the meal plan
#         meal_plan = get_object_or_404(MealPlan, pk=pk, owner=request.user)
        
#         # Check if user has Microsoft account connected
#         if not hasattr(request.user, 'microsoft_token'):
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Please connect your Microsoft account first',
#                 'redirect': reverse('meal_planner:calendar_sync_settings')
#             })
        
#         # Check if sync is enabled
#         if not request.user.microsoft_token.calendar_sync_enabled:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Calendar sync is disabled. Please enable it in settings.',
#                 'redirect': reverse('meal_planner:calendar_sync_settings')
#             })
        
#         # Import and trigger sync task
#         from meal_planner.tasks import sync_meal_plan_to_outlook
        
#         # For immediate feedback, we'll use a synchronous approach
#         # In production, you might want to use Celery for async processing
#         result = sync_meal_plan_to_outlook(meal_plan.id, request.user.id)
        
#         if result['success']:
#             # Log the sync
#             ActivityLog.objects.create(
#                 user=request.user,
#                 action='outlook_sync',
#                 details=f"Synced meal plan '{meal_plan.name}' to Outlook"
#             )
            
#             return JsonResponse({
#                 'success': True,
#                 'message': f"Successfully synced {result['events_created']} meals to Outlook!",
#                 'details': result
#             })
#         else:
#             return JsonResponse({
#                 'success': False,
#                 'error': result.get('error', 'Sync failed')
#             })
            
#     except Exception as e:
#         logger.error(f"Error syncing meal plan {pk}: {str(e)}")
#         return JsonResponse({
#             'success': False,
#             'error': 'An error occurred while syncing'
#         })


# @login_required
# def outlook_sync_status(request):
#     """
#     Get the current Outlook sync status for the user.
    
#     Returns:
#         JSON response with sync status information
#     """
#     try:
#         status = {
#             'connected': hasattr(request.user, 'microsoft_token'),
#             'sync_enabled': False,
#             'last_sync': None,
#             'events_count': 0
#         }
        
#         if status['connected']:
#             token = request.user.microsoft_token
#             status['sync_enabled'] = token.calendar_sync_enabled
#             status['last_sync'] = token.last_sync.isoformat() if token.last_sync else None
            
#             # Get event counts
#             from meal_planner.models import CalendarEvent
#             status['events_count'] = CalendarEvent.objects.filter(
#                 user=request.user,
#                 sync_status='synced'
#             ).count()
        
#         return JsonResponse(status)
        
#     except Exception as e:
#         logger.error(f"Error getting sync status: {str(e)}")
#         return JsonResponse({'error': 'Failed to get sync status'}, status=500)



# @login_required
# def sync_all_meal_plans(request):
#     """
#     Sync all active meal plans to Outlook calendar.
    
#     Returns:
#         JSON response with sync results
#     """
#     if request.method != 'POST':
#         return JsonResponse({'success': False, 'error': 'POST request required'})
    
#     try:
#         # Check if user has Microsoft account connected
#         if not hasattr(request.user, 'microsoft_token'):
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Please connect your Microsoft account first',
#                 'redirect': reverse('meal_planner:calendar_sync_settings')
#             })
        
#         # Check if sync is enabled
#         if not request.user.microsoft_token.calendar_sync_enabled:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Calendar sync is disabled. Please enable it in settings.',
#                 'redirect': reverse('meal_planner:calendar_sync_settings')
#             })
        
#         # Get all active meal plans for the user
#         active_meal_plans = MealPlan.objects.filter(
#             owner=request.user,
#             is_active=True,
#             end_date__gte=timezone.now().date()  # Only sync current/future plans
#         )
        
#         if not active_meal_plans.exists():
#             return JsonResponse({
#                 'success': False,
#                 'error': 'No active meal plans to sync'
#             })
        
#         # Import sync function
#         from meal_planner.tasks import sync_meal_plan_to_outlook
        
#         total_results = {
#             'plans_synced': 0,
#             'total_events_created': 0,
#             'total_events_updated': 0,
#             'errors': []
#         }
        
#         # Sync each active meal plan
#         for meal_plan in active_meal_plans:
#             try:
#                 result = sync_meal_plan_to_outlook(meal_plan.id, request.user.id)
                
#                 if result['success']:
#                     total_results['plans_synced'] += 1
#                     total_results['total_events_created'] += result.get('events_created', 0)
#                     total_results['total_events_updated'] += result.get('events_updated', 0)
#                 else:
#                     total_results['errors'].append(f"{meal_plan.name}: {result.get('error', 'Unknown error')}")
                    
#             except Exception as e:
#                 logger.error(f"Error syncing meal plan {meal_plan.id}: {str(e)}")
#                 total_results['errors'].append(f"{meal_plan.name}: {str(e)}")
        
#         # Log the sync
#         ActivityLog.objects.create(
#             user=request.user,
#             action='outlook_sync_all',
#             details=f"Synced {total_results['plans_synced']} meal plans to Outlook"
#         )
        
#         # Prepare response
#         if total_results['plans_synced'] > 0:
#             message = (
#                 f"Successfully synced {total_results['plans_synced']} meal plan(s)! "
#                 f"Created {total_results['total_events_created']} events, "
#                 f"updated {total_results['total_events_updated']} events."
#             )
            
#             if total_results['errors']:
#                 message += f" Some plans had errors: {len(total_results['errors'])}"
            
#             return JsonResponse({
#                 'success': True,
#                 'message': message,
#                 'details': total_results
#             })
#         else:
#             return JsonResponse({
#                 'success': False,
#                 'error': 'Failed to sync any meal plans',
#                 'details': total_results
#             })
            
#     except Exception as e:
#         logger.error(f"Error in sync_all_meal_plans: {str(e)}")
#         return JsonResponse({
#             'success': False,
#             'error': 'An error occurred while syncing'
#         })
    

# @login_required
# def microsoft_switch_account(request):
#     """
#     Switch Microsoft account by disconnecting current and reconnecting.
#     """
#     try:
#         # Delete existing token if it exists
#         if hasattr(request.user, 'microsoft_token'):
#             request.user.microsoft_token.delete()
#             logger.info(f"Disconnected Microsoft account for user {request.user.username}")
        
#         # Redirect to connect with forced account selection
#         return redirect('auth_hub:microsoft_login')
        
#     except Exception as e:
#         logger.error(f"Error switching Microsoft account: {str(e)}")
#         messages.error(request, "Error switching accounts. Please try again.")
#         return redirect('meal_planner:calendar_sync_settings')
    
# @login_required
# def get_connected_account(request):
#     """
#     Get the connected Microsoft account details.
#     """
#     try:
#         if hasattr(request.user, 'microsoft_token'):
#             from auth_hub.services.microsoft_auth import OutlookCalendarService
#             service = OutlookCalendarService(request.user)
            
#             import requests
#             headers = {'Authorization': f'Bearer {service.access_token}'}
#             response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
            
#             if response.status_code == 200:
#                 data = response.json()
#                 return JsonResponse({
#                     'email': data.get('mail') or data.get('userPrincipalName'),
#                     'name': data.get('displayName'),
#                     'connected': True
#                 })
        
#         return JsonResponse({'connected': False})
        
#     except Exception as e:
#         logger.error(f"Error getting connected account: {str(e)}")
#         return JsonResponse({'error': str(e)}, status=500)
    

# @login_required
# def test_endpoint(request):
#     """Simple test endpoint to check if routing works."""
#     print("=== TEST ENDPOINT CALLED ===")
#     logger.info("=== TEST ENDPOINT CALLED ===")
    
#     return JsonResponse({
#         'success': True,
#         'message': 'Test endpoint working',
#         'method': request.method,
#         'user': str(request.user)
#     })