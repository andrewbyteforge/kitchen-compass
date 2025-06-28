"""
Meal Plan Views - Core CRUD Operations

This module contains views for meal plan management including
list, detail, create, update, and delete operations.
"""

import logging
import traceback
from datetime import date, datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
import csv
import logging
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404

from ..models import MealPlan
from recipe_hub.models import IngredientCategory

logger = logging.getLogger(__name__)
from auth_hub.models import ActivityLog
from recipe_hub.models import Recipe
from ..models import MealPlan, MealSlot, MealType
from ..forms import MealPlanForm, MealPlanFilterForm
from django.http import HttpResponse
from django.template.loader import render_to_string
from collections import defaultdict
import csv
from decimal import Decimal
import logging
import traceback
from datetime import date, datetime, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Q, Count, Avg
from django.shortcuts import redirect, get_object_or_404, render  # Add get_object_or_404 and render here
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import HttpResponse  # Add this
from django.template.loader import render_to_string  # Add this
from collections import defaultdict  # Add this
import csv  # Add this
from decimal import Decimal  # Add this

from auth_hub.models import ActivityLog
from recipe_hub.models import Recipe
from ..models import MealPlan, MealSlot, MealType
from ..forms import MealPlanForm, MealPlanFilterForm
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class MealPlanListView(LoginRequiredMixin, ListView):
    """
    List view for meal plans with filtering and pagination.
    """
    model = MealPlan
    template_name = 'meal_planner/meal_plan_list.html'
    context_object_name = 'meal_plans'
    paginate_by = 20
    
    def get_queryset(self):
        """Get meal plans for current user with meal slot count."""
        queryset = MealPlan.objects.filter(
            owner=self.request.user
        ).prefetch_related(
            'meal_slots__recipe',
            'meal_slots__meal_type'
        ).annotate(
            meal_count=Count('meal_slots')
        ).order_by('-start_date')
        
        # Filter by date range if provided
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                queryset = queryset.filter(start_date__gte=start_date)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(end_date__lte=end_date)
            except ValueError:
                pass
        
        # Filter by active status
        is_active = self.request.GET.get('is_active')
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add additional context for meal plan list."""
        context = super().get_context_data(**kwargs)
        
        # Get meal types for filtering
        try:
            meal_types = MealType.objects.all().order_by('display_order')
            context['meal_types'] = meal_types
        except Exception as e:
            logger.warning(f"Error fetching meal types: {str(e)}")
            context['meal_types'] = []
        
        context['current_filters'] = {
            'start_date': self.request.GET.get('start_date', ''),
            'end_date': self.request.GET.get('end_date', ''),
            'is_active': self.request.GET.get('is_active', ''),
        }
        
        # Add active count and limit info
        context['active_count'] = MealPlan.objects.filter(
            owner=self.request.user,
            is_active=True
        ).count()
        
        # Get user profile and subscription info
        try:
            profile = self.request.user.profile
            context['meal_plan_limit'] = profile.subscription_tier.max_menus
            context['can_create_meal_plan'] = (
                context['meal_plan_limit'] == -1 or 
                context['active_count'] < context['meal_plan_limit']
            )
        except Exception as e:
            logger.warning(f"Error fetching user profile: {str(e)}")
            context['meal_plan_limit'] = -1
            context['can_create_meal_plan'] = True
        
        # Add filter form
        try:
            context['filter_form'] = MealPlanFilterForm(self.request.GET)
        except ImportError:
            context['filter_form'] = None
        
        return context


class MealPlanDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Detailed view of a meal plan with recipe selection capabilities.
    """
    model = MealPlan
    template_name = 'meal_planner/meal_plan_detail.html'
    context_object_name = 'meal_plan'
    
    def test_func(self):
        """Check if user owns this meal plan."""
        meal_plan = self.get_object()
        return meal_plan.owner == self.request.user
    
    def get_context_data(self, **kwargs):
        """Add organized meal data and enhanced recipe information to context."""
        context = super().get_context_data(**kwargs)
        meal_plan = self.object
        
        # Get all meal slots organized by date
        meal_slots = meal_plan.meal_slots.select_related(
            'recipe', 'meal_type', 'recipe__author'
        ).prefetch_related(
            'recipe__categories'
        ).order_by('date', 'meal_type__display_order')
        
        # Get user's recipes AND public recipes for the recipe selector
        try:
            user_recipes = Recipe.objects.filter(
                Q(author=self.request.user) | Q(is_public=True)
            ).select_related(
                'author'
            ).prefetch_related(
                'categories'
            ).annotate(
                annotated_avg_rating=Avg('ratings__rating'),
                annotated_rating_count=Count('ratings')
            ).order_by('-created_at')
            
            context['user_recipes'] = user_recipes
            
            logger.info(f"Found {user_recipes.count()} recipes available for user {self.request.user.username}")
            
        except Exception as e:
            logger.error(f"Error fetching recipes for meal plan detail: {str(e)}")
            context['user_recipes'] = Recipe.objects.none()
        
        # Organize meal slots by week for better template display
        weeks = []
        current_date = meal_plan.start_date
        
        while current_date <= meal_plan.end_date:
            week_start = current_date - timedelta(days=current_date.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Make sure we don't go beyond meal plan end date
            if week_end > meal_plan.end_date:
                week_end = meal_plan.end_date
            
            week_data = {
                'start_date': week_start,
                'end_date': week_end,
                'days': []
            }
            
            # Get dates for this week within meal plan range
            week_date = max(week_start, meal_plan.start_date)
            while week_date <= min(week_end, meal_plan.end_date):
                day_slots = [slot for slot in meal_slots if slot.date == week_date]
                week_data['days'].append({
                    'date': week_date,
                    'slots': day_slots,
                    'is_today': week_date == date.today()
                })
                week_date += timedelta(days=1)
            
            weeks.append(week_data)
            current_date = week_end + timedelta(days=1)
        
        context['organized_weeks'] = weeks
        context['meal_types'] = MealType.objects.all().order_by('display_order')
        
        # Recipe categories for filtering in the modal
        try:
            from recipe_hub.models import RecipeCategory
            context['recipe_categories'] = RecipeCategory.objects.filter(
                is_active=True
            ).order_by('name')
        except Exception as e:
            logger.warning(f"Error fetching recipe categories: {str(e)}")
            context['recipe_categories'] = []
        
        # Shopping list preview (ingredients from all recipes)
        ingredients = {}
        for slot in meal_slots:
            if slot.recipe:
                try:
                    # Handle the case where ingredients might not exist
                    if hasattr(slot.recipe, 'ingredients'):
                        for ingredient in slot.recipe.ingredients.all():
                            key = f"{ingredient.name}_{ingredient.unit or 'unit'}"
                            if key not in ingredients:
                                ingredients[key] = {
                                    'name': ingredient.name,
                                    'unit': ingredient.unit or '',
                                    'quantity': 0,
                                    'recipes': []
                                }
                            
                            # Calculate quantity based on servings
                            multiplier = slot.servings or 1
                            try:
                                quantity = float(ingredient.quantity) * multiplier
                                ingredients[key]['quantity'] += quantity
                            except (ValueError, TypeError):
                                # Handle non-numeric quantities
                                pass
                            
                            if slot.recipe.title not in ingredients[key]['recipes']:
                                ingredients[key]['recipes'].append(slot.recipe.title)
                except Exception as e:
                    logger.warning(f"Error processing ingredients for recipe {slot.recipe.id}: {str(e)}")
                    continue
        
        context['ingredients_preview'] = list(ingredients.values())[:10]
        context['total_ingredients'] = len(ingredients)
        
        # Meal plan statistics
        total_slots = meal_slots.count()
        filled_slots = meal_slots.filter(recipe__isnull=False).count()
        context['meal_plan_stats'] = {
            'total_slots': total_slots,
            'filled_slots': filled_slots,
            'empty_slots': total_slots - filled_slots,
            'completion_percentage': round((filled_slots / total_slots) * 100, 1) if total_slots > 0 else 0
        }
        
        return context


@method_decorator(login_required, name='dispatch')
class MealPlanCreateView(CreateView):
    """
    Create a new meal plan with automatic meal slot generation.
    """
    model = MealPlan
    form_class = MealPlanForm
    template_name = 'meal_planner/meal_plan_form.html'
    success_url = reverse_lazy('meal_planner:meal_plan_list')
    
    def dispatch(self, request, *args, **kwargs):
        """Check if user can create meal plans."""
        try:
            profile = request.user.profile
            subscription_tier = profile.subscription_tier
            
            if subscription_tier.max_menus != -1:
                active_count = MealPlan.objects.filter(
                    owner=request.user,
                    is_active=True
                ).count()
                if active_count >= subscription_tier.max_menus:
                    messages.error(
                        request,
                        f"You've reached your meal plan limit ({subscription_tier.max_menus}). "
                        f"Please deactivate an existing plan or upgrade your subscription."
                    )
                    return redirect('meal_planner:meal_plan_list')
        except Exception as e:
            logger.error(f"Error checking meal plan limits: {str(e)}")
            # Continue anyway - don't block user if there's an error
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Create meal plan and automatically generate meal slots."""
        logger.info(f"Creating meal plan for user {self.request.user.username}")
        
        try:
            # Set the owner
            form.instance.owner = self.request.user
            
            # Save the meal plan first
            with transaction.atomic():
                response = super().form_valid(form)
                meal_plan = self.object
                
                logger.info(f"Meal plan saved - ID: {meal_plan.pk}, Name: {meal_plan.name}")
                
                # Get all meal types
                meal_types = MealType.objects.all().order_by('display_order')
                
                if not meal_types.exists():
                    logger.error("No meal types found!")
                    messages.error(
                        self.request,
                        "No meal types configured. Please run: python manage.py create_meal_types"
                    )
                    return self.form_invalid(form)
                
                # Create meal slots for each day and meal type
                slots_created = 0
                current_date = meal_plan.start_date
                
                while current_date <= meal_plan.end_date:
                    for meal_type in meal_types:
                        try:
                            slot, created = MealSlot.objects.get_or_create(
                                meal_plan=meal_plan,
                                date=current_date,
                                meal_type=meal_type,
                                defaults={
                                    'servings': 1,
                                    'notes': ''
                                }
                            )
                            
                            if created:
                                slots_created += 1
                                
                        except Exception as slot_error:
                            logger.error(
                                f"Error creating meal slot for {current_date} "
                                f"- {meal_type.name}: {str(slot_error)}"
                            )
                            continue
                    
                    current_date += timedelta(days=1)
                
                logger.info(f"Total slots created: {slots_created}")
                
                # Success message
                messages.success(
                    self.request,
                    f"Meal plan '{meal_plan.name}' created successfully with "
                    f"{slots_created} meal slots ready for planning!"
                )
                
                # Log activity
                try:
                    ActivityLog.objects.create(
                        user=self.request.user,
                        action='create_meal_plan',
                        details=f"Created meal plan: {meal_plan.name} with {slots_created} slots"
                    )
                except Exception as log_error:
                    logger.warning(f"Failed to log activity: {str(log_error)}")
                
                return response
            
        except Exception as e:
            logger.error(f"Error creating meal plan for user {self.request.user.username}: {str(e)}")
            logger.error(traceback.format_exc())
            
            messages.error(
                self.request,
                f"Error creating meal plan: {str(e)}. Please try again."
            )
            return self.form_invalid(form)
    
    def get_success_url(self):
        """Redirect to the newly created meal plan's detail page."""
        return reverse_lazy('meal_planner:meal_plan_detail', kwargs={'pk': self.object.pk})


@method_decorator(login_required, name='dispatch')
class MealPlanUpdateView(UserPassesTestMixin, UpdateView):
    """
    Update an existing meal plan and adjust meal slots as needed.
    """
    model = MealPlan
    form_class = MealPlanForm
    template_name = 'meal_planner/meal_plan_form.html'
    
    def test_func(self):
        """Check if user owns this meal plan."""
        meal_plan = self.get_object()
        return meal_plan.owner == self.request.user
    
    @transaction.atomic
    def form_valid(self, form):
        """Update meal plan and adjust meal slots if date range changed."""
        # Store original date range
        old_start = self.object.start_date
        old_end = self.object.end_date
        
        logger.info(f"Updating meal plan '{self.object.name}' for user {self.request.user.username}")
        
        # Update the meal plan
        response = super().form_valid(form)
        meal_plan = self.object
        
        # Check if date range changed
        date_range_changed = (
            old_start != meal_plan.start_date or 
            old_end != meal_plan.end_date
        )
        
        if date_range_changed:
            logger.info("Date range changed, adjusting meal slots...")
            slots_removed, slots_created = self._adjust_meal_slots(
                meal_plan, old_start, old_end
            )
            
            if slots_removed > 0 or slots_created > 0:
                messages.info(
                    self.request,
                    f"Date range updated: {slots_removed} slots removed, "
                    f"{slots_created} slots added."
                )
        
        # Log activity
        try:
            ActivityLog.objects.create(
                user=self.request.user,
                action='update_meal_plan',
                details=f"Updated meal plan: {meal_plan.name}"
            )
        except Exception as log_error:
            logger.warning(f"Failed to log activity: {str(log_error)}")
        
        messages.success(
            self.request,
            f"Meal plan '{meal_plan.name}' updated successfully!"
        )
        
        return response
    
    def _adjust_meal_slots(self, meal_plan, old_start, old_end):
        """Adjust meal slots when date range changes."""
        slots_removed = 0
        slots_created = 0
        
        try:
            # Remove slots outside the new date range
            removed_slots = MealSlot.objects.filter(
                meal_plan=meal_plan
            ).exclude(
                date__gte=meal_plan.start_date,
                date__lte=meal_plan.end_date
            )
            
            slots_removed = removed_slots.count()
            if slots_removed > 0:
                logger.info(f"Removing {slots_removed} slots outside new date range")
                removed_slots.delete()
            
            # Get meal types
            meal_types = MealType.objects.all().order_by('display_order')
            if not meal_types.exists():
                logger.warning("No meal types found, creating default meal types")
                self._create_default_meal_types()
                meal_types = MealType.objects.all().order_by('display_order')
            
            # Create missing slots for new dates
            current_date = meal_plan.start_date
            while current_date <= meal_plan.end_date:
                for meal_type in meal_types:
                    try:
                        slot, created = MealSlot.objects.get_or_create(
                            meal_plan=meal_plan,
                            date=current_date,
                            meal_type=meal_type,
                            defaults={
                                'servings': 1,
                                'notes': ''
                            }
                        )
                        if created:
                            slots_created += 1
                            
                    except Exception as slot_error:
                        logger.error(
                            f"Error creating meal slot for {current_date} "
                            f"- {meal_type.name}: {str(slot_error)}"
                        )
                        continue
                
                current_date += timedelta(days=1)
            
            if slots_created > 0:
                logger.info(f"Created {slots_created} new meal slots")
            
        except Exception as e:
            logger.error(f"Error adjusting meal slots: {str(e)}")
            # Don't raise the error - the meal plan update should still succeed
        
        return slots_removed, slots_created
    
    def _create_default_meal_types(self):
        """Create default meal types if none exist."""
        from datetime import time
        
        default_meal_types = [
            {'name': 'Breakfast', 'display_order': 1, 'default_time': time(7, 0), 'icon': 'bi-sunrise'},
            {'name': 'Lunch', 'display_order': 2, 'default_time': time(12, 0), 'icon': 'bi-sun'},
            {'name': 'Dinner', 'display_order': 3, 'default_time': time(18, 0), 'icon': 'bi-moon'},
            {'name': 'Snack', 'display_order': 4, 'default_time': time(15, 0), 'icon': 'bi-cup-straw'}
        ]
        
        for meal_type_data in default_meal_types:
            try:
                MealType.objects.get_or_create(
                    name=meal_type_data['name'],
                    defaults={
                        'display_order': meal_type_data['display_order'],
                        'default_time': meal_type_data['default_time'],
                        'icon': meal_type_data['icon']
                    }
                )
                logger.info(f"Created default meal type: {meal_type_data['name']}")
                
            except Exception as e:
                logger.error(f"Error creating meal type {meal_type_data['name']}: {str(e)}")
    
    def get_success_url(self):
        """Redirect to the updated meal plan's detail page."""
        return self.object.get_absolute_url()


@method_decorator(login_required, name='dispatch')
class MealPlanDeleteView(UserPassesTestMixin, DeleteView):
    """
    Delete a meal plan.
    """
    model = MealPlan
    template_name = 'meal_planner/meal_plan_confirm_delete.html'
    success_url = reverse_lazy('meal_planner:meal_plan_list')
    
    def test_func(self):
        """Check if user owns this meal plan."""
        meal_plan = self.get_object()
        return meal_plan.owner == self.request.user
    
    def delete(self, request, *args, **kwargs):
        """Log deletion and show success message."""
        meal_plan = self.get_object()
        meal_plan_name = meal_plan.name
        
        try:
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='delete_meal_plan',
                details=f"Deleted meal plan: {meal_plan_name}"
            )
            
            response = super().delete(request, *args, **kwargs)
            
            messages.success(
                request,
                f"Meal plan '{meal_plan_name}' deleted successfully."
            )
            
            logger.info(f"Meal plan deleted: {meal_plan_name} by {request.user.username}")
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error deleting meal plan {meal_plan.pk} for user "
                f"{request.user.username}: {str(e)}"
            )
            messages.error(
                request,
                "An error occurred while deleting the meal plan."
            )
            return redirect(meal_plan.get_absolute_url())
        

@login_required
def generate_shopping_list(request, pk):
    """
    Generate and display shopping list for a meal plan.
    
    Args:
        request: HTTP request
        pk: Primary key of the meal plan
        
    Returns:
        Rendered shopping list template with categorized ingredients
    """
    # Get meal plan and verify ownership
    meal_plan = get_object_or_404(MealPlan, pk=pk, owner=request.user)
    
    logger.info(f"Generating shopping list for meal plan {pk} by user {request.user.username}")
    
    # Get all active categories
    categories = IngredientCategory.objects.filter(is_active=True).order_by('display_order')
    
    # Initialize category buckets
    categorized_ingredients = defaultdict(list)
    uncategorized_ingredients = []
    
    # Aggregate ingredients
    ingredients = defaultdict(lambda: {
        'quantity': 0,
        'unit': '',
        'recipes': [],
        'category': None
    })
    
    # Get all meal slots with recipes
    meal_slots = meal_plan.meal_slots.filter(
        recipe__isnull=False
    ).select_related('recipe').prefetch_related(
        'recipe__ingredients__category'
    )
    
    for slot in meal_slots:
        if hasattr(slot.recipe, 'ingredients'):
            for ingredient in slot.recipe.ingredients.all():
                key = f"{ingredient.name}_{ingredient.unit or 'unit'}"
                
                # Store ingredient details
                ingredients[key]['name'] = ingredient.name
                ingredients[key]['unit'] = ingredient.unit or ''
                ingredients[key]['category'] = ingredient.category
                
                # Calculate quantity based on servings
                try:
                    quantity = float(ingredient.quantity or 0) * (slot.servings or 1)
                    ingredients[key]['quantity'] += quantity
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid quantity for ingredient {ingredient.name} "
                        f"in recipe {slot.recipe.title}"
                    )
                
                # Track which recipes use this ingredient
                recipe_info = f"{slot.recipe.title} ({slot.date.strftime('%b %d')})"
                if recipe_info not in ingredients[key]['recipes']:
                    ingredients[key]['recipes'].append(recipe_info)
    
    # Sort ingredients into categories
    for key, data in ingredients.items():
        item = {
            'name': data['name'],
            'quantity': data['quantity'],
            'unit': data['unit'],
            'recipes': data['recipes']
        }
        
        # Check if ingredient has a category
        if data['category']:
            categorized_ingredients[data['category'].name].append(item)
        else:
            # Try to auto-categorize based on keywords
            categorized = False
            ingredient_name_lower = data['name'].lower()
            
            for category in categories:
                keywords = category.get_keywords_list()
                if any(keyword in ingredient_name_lower for keyword in keywords):
                    categorized_ingredients[category.name].append(item)
                    categorized = True
                    break
            
            if not categorized:
                uncategorized_ingredients.append(item)
    
    # Sort items within each category
    for category_name in categorized_ingredients:
        categorized_ingredients[category_name].sort(key=lambda x: x['name'].lower())
    
    uncategorized_ingredients.sort(key=lambda x: x['name'].lower())
    
    # Add uncategorized items to "Other" category if it exists
    if uncategorized_ingredients:
        if 'Other' in [cat.name for cat in categories]:
            categorized_ingredients['Other'].extend(uncategorized_ingredients)
        else:
            categorized_ingredients['Uncategorized'] = uncategorized_ingredients
    
    # Convert to list format for template
    shopping_list_by_category = []
    for category in categories:
        if category.name in categorized_ingredients:
            shopping_list_by_category.append({
                'category': category,
                'items': categorized_ingredients[category.name]
            })
    
    # Add any remaining categories not in the database
    for category_name, items in categorized_ingredients.items():
        if not any(cat['category'].name == category_name for cat in shopping_list_by_category if 'category' in cat and hasattr(cat['category'], 'name')):
            shopping_list_by_category.append({
                'category': {'name': category_name},
                'items': items
            })
    
    # Calculate totals
    total_items = sum(len(cat['items']) for cat in shopping_list_by_category)
    
    context = {
        'meal_plan': meal_plan,
        'shopping_list_by_category': shopping_list_by_category,
        'total_items': total_items,
        'meal_count': meal_slots.count()
    }
    
    logger.info(f"Generated shopping list with {total_items} items in {len(shopping_list_by_category)} categories")
    
    return render(request, 'meal_planner/shopping_list.html', context)






@login_required
def download_shopping_list(request, pk):
    """
    Download shopping list as CSV file.
    
    Provides the shopping list in a downloadable CSV format that can be
    printed or imported into other applications.
    
    Args:
        request: HttpRequest object
        pk: Primary key of the meal plan
        
    Returns:
        HttpResponse with CSV file download
        
    Raises:
        Http404: If meal plan not found or user doesn't own it
    """
    try:
        # Get meal plan and verify ownership
        meal_plan = get_object_or_404(MealPlan, pk=pk, owner=request.user)
        
        logger.info(f"Downloading shopping list for meal plan {pk} by user {request.user.username}")
        
        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="shopping_list_{meal_plan.name}_{date.today()}.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow(['Shopping List for: ' + meal_plan.name])
        writer.writerow([f"Date Range: {meal_plan.start_date.strftime('%b %d')} - {meal_plan.end_date.strftime('%b %d, %Y')}"])
        writer.writerow([])  # Empty row
        writer.writerow(['Category', 'Item', 'Quantity', 'Unit', 'Needed For'])
        
        # Get all meal slots with recipes
        meal_slots = meal_plan.meal_slots.filter(
            recipe__isnull=False
        ).select_related(
            'recipe'
        ).prefetch_related(
            'recipe__ingredients'
        )
        
        # Aggregate ingredients (similar logic as generate_shopping_list)
        ingredients_dict = defaultdict(lambda: {
            'quantity': Decimal('0'),
            'unit': '',
            'category': 'Other',
            'recipes': set()
        })
        
        for slot in meal_slots:
            try:
                recipe = slot.recipe
                if hasattr(recipe, 'ingredients'):
                    for ingredient in recipe.ingredients.all():
                        try:
                            key = f"{ingredient.name.lower()}_{ingredient.unit or 'unit'}"
                            
                            try:
                                quantity = Decimal(str(ingredient.quantity or 0))
                            except (ValueError, TypeError, InvalidOperation):
                                quantity = Decimal('0')
                                
                            adjusted_quantity = quantity * Decimal(str(slot.servings))
                            
                            ingredients_dict[key]['quantity'] += adjusted_quantity
                            ingredients_dict[key]['unit'] = ingredient.unit or ''
                            ingredients_dict[key]['name'] = ingredient.name
                            ingredients_dict[key]['recipes'].add(recipe.title)
                            
                            # Same categorization logic
                            ingredient_lower = ingredient.name.lower()
                            if any(item in ingredient_lower for item in ['chicken', 'beef', 'pork', 'fish', 'salmon', 'shrimp', 'turkey', 'bacon']):
                                ingredients_dict[key]['category'] = 'Meat & Seafood'
                            elif any(item in ingredient_lower for item in ['milk', 'cheese', 'yogurt', 'cream', 'butter']):
                                ingredients_dict[key]['category'] = 'Dairy'
                            elif any(item in ingredient_lower for item in ['lettuce', 'tomato', 'onion', 'pepper', 'carrot', 'celery', 'garlic', 'potato', 'broccoli']):
                                ingredients_dict[key]['category'] = 'Produce'
                            elif any(item in ingredient_lower for item in ['bread', 'roll', 'bun', 'bagel', 'muffin']):
                                ingredients_dict[key]['category'] = 'Bakery'
                            elif any(item in ingredient_lower for item in ['flour', 'sugar', 'salt', 'pepper', 'oil', 'vinegar', 'rice', 'pasta']):
                                ingredients_dict[key]['category'] = 'Pantry'
                            
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error processing ingredient for CSV: {str(e)}")
                            continue
                            
            except Exception as e:
                logger.error(f"Error processing slot for CSV: {str(e)}")
                continue
        
        # Organize by category and write to CSV
        organized = defaultdict(list)
        for key, data in ingredients_dict.items():
            organized[data['category']].append(data)
        
        # Write ingredients by category
        for category in sorted(organized.keys()):
            for ingredient in sorted(organized[category], key=lambda x: x['name'].lower()):
                writer.writerow([
                    category,
                    ingredient['name'],
                    f"{ingredient['quantity']:.2f}".rstrip('0').rstrip('.'),
                    ingredient['unit'],
                    ', '.join(sorted(ingredient['recipes']))
                ])
        
        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            action='download_shopping_list',
            details=f"Downloaded shopping list for '{meal_plan.name}'"
        )
        
        logger.info(f"Successfully downloaded shopping list for user {request.user.username}")
        
        return response
        
    except Exception as e:
        logger.error(
            f"Error downloading shopping list for meal plan {pk} by user {request.user.username}: {str(e)}"
        )
        messages.error(request, "An error occurred while downloading the shopping list.")
        return redirect('meal_planner:meal_plan_detail', pk=pk)