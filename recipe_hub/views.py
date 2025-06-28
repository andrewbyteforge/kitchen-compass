"""
Recipe Hub Views - Updated with CSV Import

This module contains all views for recipe management including CSV import functionality.
"""

import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Avg, Count, Prefetch, F
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView
)

from auth_hub.models import ActivityLog
from .models import (
    Recipe, RecipeCategory, RecipeRating, RecipeFavorite, RecipeComment,
    Ingredient, Instruction
)
from .forms import (
    RecipeForm, RecipeSearchForm, RecipeRatingForm, RecipeCommentForm,
    IngredientFormSet, InstructionFormSet, RecipeImportForm, RecipeCSVImportForm
)

logger = logging.getLogger(__name__)


class RecipeListView(ListView):
    """
    Display list of recipes with search and filtering.
    
    Supports filtering by category, difficulty, time, and dietary restrictions.
    """
    model = Recipe
    template_name = 'recipe_hub/recipe_list.html'
    context_object_name = 'recipes'
    paginate_by = 12
    
    def get_queryset(self):
        """Apply filters and search to recipe queryset."""
        queryset = Recipe.objects.filter(is_public=True).select_related(
            'author', 'author__profile'
        ).prefetch_related('categories', 'ratings')
        
        # Get search form
        self.search_form = RecipeSearchForm(self.request.GET)
        
        if self.search_form.is_valid():
            # Text search
            query = self.search_form.cleaned_data.get('query')
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query) |
                    Q(ingredients__name__icontains=query)
                ).distinct()
            
            # Category filter
            category = self.search_form.cleaned_data.get('category')
            if category:
                queryset = queryset.filter(categories=category)
            
            # Difficulty filter
            difficulty = self.search_form.cleaned_data.get('difficulty')
            if difficulty:
                queryset = queryset.filter(difficulty=difficulty)
            
            # Time filter
            max_time = self.search_form.cleaned_data.get('max_time')
            if max_time:
                queryset = queryset.annotate(
                    total_time=F('prep_time') + F('cook_time')
                ).filter(total_time__lte=max_time)
            
            # Dietary filters
            dietary = self.search_form.cleaned_data.get('dietary', [])
            if dietary:
                dietary = [d for d in dietary if d]
                
                diet_mapping = {
                    'vegetarian': 'vegetarian',
                    'vegan': 'vegan',
                    'gluten_free': 'gluten_free',
                    'dairy_free': 'dairy_free',
                    'nut_free': 'nut_free'
                }
                
                for diet in dietary:
                    if diet in diet_mapping:
                        queryset = queryset.filter(
                            dietary_info__contains={diet_mapping[diet]: True}
                        )
            
            # Sorting
            sort_by = self.search_form.cleaned_data.get('sort_by') or '-created_at'
            if sort_by == '-rating':
                queryset = queryset.annotate(
                    avg_rating=Avg('ratings__rating')
                ).order_by('-avg_rating', '-created_at')
            elif sort_by == 'total_time':
                queryset = queryset.annotate(
                    total_time=F('prep_time') + F('cook_time')
                ).order_by('total_time')
            else:
                queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add search form and categories to context."""
        context = super().get_context_data(**kwargs)
        context['search_form'] = self.search_form
        context['categories'] = RecipeCategory.objects.filter(is_active=True)
        context['total_recipes'] = self.get_queryset().count()
        
        # Add featured recipes for sidebar
        context['featured_recipes'] = Recipe.objects.filter(
            is_public=True, is_featured=True
        ).select_related('author')[:5]
        
        return context


class UserRecipeListView(LoginRequiredMixin, ListView):
    """Display user's own recipes."""
    model = Recipe
    template_name = 'recipe_hub/user_recipes.html'
    context_object_name = 'recipes'
    paginate_by = 12
    
    def get_queryset(self):
        """Get recipes for the current user."""
        return Recipe.objects.filter(
            author=self.request.user
        ).select_related('author').prefetch_related('categories', 'ratings')
    
    def get_context_data(self, **kwargs):
        """Add recipe statistics to context."""
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get or create user profile
        from auth_hub.models import UserProfile, SubscriptionTier
        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            default_tier = SubscriptionTier.objects.filter(tier_type='FREE').first()
            if not default_tier:
                default_tier = SubscriptionTier.objects.create(
                    name='Home Cook',
                    price=0,
                    tier_type='FREE',
                    max_recipes=10,
                    max_menus=3,
                    max_shares=0
                )
            profile = UserProfile.objects.create(
                user=user,
                subscription_tier=default_tier
            )
            logger.warning(f"Created missing UserProfile for user {user.username}")
        
        context['recipe_count'] = self.get_queryset().count()
        context['recipe_limit'] = profile.subscription_tier.max_recipes
        context['can_add_recipe'] = (
            profile.subscription_tier.max_recipes == -1 or
            context['recipe_count'] < profile.subscription_tier.max_recipes
        )
        
        # Recipe statistics
        context['total_ratings'] = RecipeRating.objects.filter(
            recipe__author=user
        ).count()
        context['total_favorites'] = RecipeFavorite.objects.filter(
            recipe__author=user
        ).count()
        
        return context


class RecipeDetailView(DetailView):
    """Display detailed recipe view."""
    model = Recipe
    template_name = 'recipe_hub/recipe_detail.html'
    context_object_name = 'recipe'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def get_queryset(self):
        """Include related data in queryset."""
        return Recipe.objects.select_related(
            'author', 'author__profile'
        ).prefetch_related(
            'categories',
            'ingredients',
            'instructions',
            Prefetch(
                'ratings',
                queryset=RecipeRating.objects.select_related('user')
            ),
            Prefetch(
                'comments',
                queryset=RecipeComment.objects.filter(
                    is_approved=True, parent__isnull=True
                ).select_related('user').prefetch_related('replies')
            )
        )
    
    def get_context_data(self, **kwargs):
        """Add additional recipe data to context."""
        context = super().get_context_data(**kwargs)
        recipe = self.object
        user = self.request.user
        
        # User interactions
        if user.is_authenticated:
            context['user_rating'] = recipe.ratings.filter(user=user).first()
            context['is_favorited'] = recipe.favorites.filter(user=user).exists()
            context['can_edit'] = recipe.can_edit(user)
        else:
            context['user_rating'] = None
            context['is_favorited'] = False
            context['can_edit'] = False
        
        # Forms
        context['rating_form'] = RecipeRatingForm()
        context['comment_form'] = RecipeCommentForm()
        
        # Similar recipes
        context['similar_recipes'] = Recipe.objects.filter(
            categories__in=recipe.categories.all(),
            is_public=True
        ).exclude(id=recipe.id).distinct()[:4]
        
        # Log view
        if user.is_authenticated:
            ActivityLog.objects.create(
                user=user,
                action='view_recipe',
                details=f"Viewed recipe: {recipe.title}"
            )
        
        return context


class RecipeCreateView(LoginRequiredMixin, CreateView):
    model = Recipe
    form_class = RecipeForm
    template_name = 'recipe_hub/recipe_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['ingredient_formset'] = IngredientFormSet(self.request.POST, prefix='ingredients')
            context['instruction_formset'] = InstructionFormSet(self.request.POST, prefix='instructions')
        else:
            context['ingredient_formset'] = IngredientFormSet(prefix='ingredients')
            context['instruction_formset'] = InstructionFormSet(prefix='instructions')
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        ingredient_formset = context['ingredient_formset']
        instruction_formset = context['instruction_formset']
        
        if ingredient_formset.is_valid() and instruction_formset.is_valid():
            self.object = form.save(commit=False)
            self.object.author = self.request.user
            self.object.save()
            form.save_m2m()  # Save many-to-many fields (categories)
            
            # Save ingredients
            ingredient_formset.instance = self.object
            ingredient_formset.save()
            
            # Save instructions
            instruction_formset.instance = self.object
            instruction_formset.save()
            
            messages.success(self.request, 'Recipe created successfully!')
            return redirect(self.object.get_absolute_url())
        else:
            return self.form_invalid(form)
    
    def dispatch(self, request, *args, **kwargs):
        """Check if user can create recipes based on subscription."""
        if request.user.is_authenticated:
            # Ensure user has a profile
            from auth_hub.models import UserProfile, SubscriptionTier
            
            try:
                profile = request.user.profile
            except UserProfile.DoesNotExist:
                # Create profile if it doesn't exist
                free_tier = SubscriptionTier.get_free_tier()
                profile = UserProfile.objects.create(
                    user=request.user,
                    subscription_tier=free_tier
                )
                logger.info(f"Created profile for user {request.user.username}")
            
            # Ensure profile has a subscription tier
            if not profile.subscription_tier:
                profile.subscription_tier = SubscriptionTier.get_free_tier()
                profile.save()
            
            # Now check the limits
            if profile.subscription_tier.max_recipes != -1:
                recipe_count = Recipe.objects.filter(author=request.user).count()
                if recipe_count >= profile.subscription_tier.max_recipes:
                    messages.warning(
                        request,
                        f"You've reached your recipe limit ({profile.subscription_tier.max_recipes}). "
                        f"Please upgrade your subscription to create more recipes."
                    )
                    return redirect('recipe_hub:recipe_list')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        """Add formsets to context."""
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['ingredient_formset'] = IngredientFormSet(
                self.request.POST, prefix='ingredients'
            )
            context['instruction_formset'] = InstructionFormSet(
                self.request.POST, self.request.FILES, prefix='instructions'
            )
        else:
            context['ingredient_formset'] = IngredientFormSet(prefix='ingredients')
            context['instruction_formset'] = InstructionFormSet(prefix='instructions')
        
        return context

    @transaction.atomic
    def form_valid(self, form):
        """Save recipe with related ingredients and instructions."""
        context = self.get_context_data()
        ingredient_formset = context['ingredient_formset']
        instruction_formset = context['instruction_formset']
        
        # Set author BEFORE any operations
        form.instance.author = self.request.user
        
        # Validate formsets
        if not ingredient_formset.is_valid():
            logger.warning(
                f"Invalid ingredient formset for user {self.request.user.username}: "
                f"{ingredient_formset.errors}"
            )
            return self.form_invalid(form)
        
        if not instruction_formset.is_valid():
            logger.warning(
                f"Invalid instruction formset for user {self.request.user.username}: "
                f"{instruction_formset.errors}"
            )
            return self.form_invalid(form)
        
        try:
            # Save the main recipe first
            self.object = form.save()
            
            # Save formsets
            ingredient_formset.instance = self.object
            instruction_formset.instance = self.object
            
            ingredient_formset.save()
            instruction_formset.save()
            
            # Log activity
            ActivityLog.objects.create(
                user=self.request.user,
                action='create_recipe',
                details=f"Created recipe: {self.object.title}"
            )
            
            messages.success(
                self.request,
                f"Recipe '{self.object.title}' created successfully!"
            )
            
            logger.info(
                f"Recipe created: {self.object.title} by {self.request.user.username} "
                f"(ID: {self.object.pk})"
            )
            
            return redirect('recipe_hub:recipe_detail', slug=self.object.slug)
            
        except Exception as e:
            logger.error(
                f"Error creating recipe for user {self.request.user.username}: {str(e)}"
            )
            messages.error(
                self.request,
                "An error occurred while creating the recipe. Please try again."
            )
            return self.form_invalid(form)


@method_decorator(login_required, name='dispatch')
class RecipeUpdateView(UserPassesTestMixin, UpdateView):
    """Update existing recipe."""
    model = Recipe
    form_class = RecipeForm
    template_name = 'recipe_hub/recipe_form.html'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        """Check if user can edit this recipe."""
        recipe = self.get_object()
        return recipe.can_edit(self.request.user)
    
    def get_context_data(self, **kwargs):
        """Add formsets to context."""
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['ingredient_formset'] = IngredientFormSet(
                self.request.POST, instance=self.object, prefix='ingredients'
            )
            context['instruction_formset'] = InstructionFormSet(
                self.request.POST, self.request.FILES,
                instance=self.object, prefix='instructions'
            )
        else:
            context['ingredient_formset'] = IngredientFormSet(
                instance=self.object, prefix='ingredients'
            )
            context['instruction_formset'] = InstructionFormSet(
                instance=self.object, prefix='instructions'
            )
        
        context['is_update'] = True
        return context

    @transaction.atomic
    def form_valid(self, form):
        """Update recipe with related ingredients and instructions."""
        context = self.get_context_data()
        ingredient_formset = context['ingredient_formset']
        instruction_formset = context['instruction_formset']
        
        # Validate formsets
        if not ingredient_formset.is_valid():
            logger.warning(
                f"Invalid ingredient formset for user {self.request.user.username}: "
                f"{ingredient_formset.errors}"
            )
            return self.form_invalid(form)
        
        if not instruction_formset.is_valid():
            logger.warning(
                f"Invalid instruction formset for user {self.request.user.username}: "
                f"{instruction_formset.errors}"
            )
            return self.form_invalid(form)
        
        try:
            # Save the main recipe
            self.object = form.save()
            
            # Save formsets
            ingredient_formset.save()
            instruction_formset.save()
            
            # Log activity
            ActivityLog.objects.create(
                user=self.request.user,
                action='update_recipe',
                details=f"Updated recipe: {self.object.title}"
            )
            
            messages.success(
                self.request,
                f"Recipe '{self.object.title}' updated successfully!"
            )
            
            logger.info(
                f"Recipe updated: {self.object.title} by {self.request.user.username}"
            )
            
            return redirect('recipe_hub:recipe_detail', slug=self.object.slug)
            
        except Exception as e:
            logger.error(
                f"Error updating recipe for user {self.request.user.username}: {str(e)}"
            )
            messages.error(
                self.request,
                "An error occurred while updating the recipe. Please try again."
            )
            return self.form_invalid(form)


@method_decorator(login_required, name='dispatch')
class RecipeDeleteView(UserPassesTestMixin, DeleteView):
    """Delete recipe."""
    model = Recipe
    template_name = 'recipe_hub/recipe_confirm_delete.html'
    success_url = reverse_lazy('recipe_hub:user_recipes')
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        """Check if user can delete this recipe."""
        recipe = self.get_object()
        return recipe.can_edit(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        """Log deletion and show success message."""
        recipe = self.get_object()
        recipe_title = recipe.title
        
        try:
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='delete_recipe',
                details=f"Deleted recipe: {recipe_title}"
            )
            
            response = super().delete(request, *args, **kwargs)
            
            messages.success(
                request,
                f"Recipe '{recipe_title}' deleted successfully."
            )
            
            logger.info(
                f"Recipe deleted: {recipe_title} by {request.user.username}"
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error deleting recipe {recipe.pk} for user "
                f"{request.user.username}: {str(e)}"
            )
            messages.error(
                request,
                "An error occurred while deleting the recipe."
            )
            return redirect(recipe.get_absolute_url())


class FavoriteRecipesView(LoginRequiredMixin, ListView):
    """Display user's favorite recipes."""
    model = Recipe
    template_name = 'recipe_hub/favorite_recipes.html'
    context_object_name = 'recipes'
    paginate_by = 12
    
    def get_queryset(self):
        """Get favorited recipes for current user."""
        return Recipe.objects.filter(
            favorites__user=self.request.user,
            is_public=True
        ).select_related('author').prefetch_related('categories', 'ratings')
    
    def get_context_data(self, **kwargs):
        """Add total favorites count."""
        context = super().get_context_data(**kwargs)
        context['total_favorites'] = self.get_queryset().count()
        return context


class CategoryRecipesView(ListView):
    """Display recipes from a specific category."""
    model = Recipe
    template_name = 'recipe_hub/category_recipes.html'
    context_object_name = 'recipes'
    paginate_by = 12
    
    def get_queryset(self):
        """Get recipes for the specified category."""
        self.category = get_object_or_404(
            RecipeCategory,
            slug=self.kwargs['slug'],
            is_active=True
        )
        return Recipe.objects.filter(
            categories=self.category,
            is_public=True
        ).select_related('author').prefetch_related('categories', 'ratings')
    
    def get_context_data(self, **kwargs):
        """Add category to context."""
        context = super().get_context_data(**kwargs)
        context['category'] = self.category
        context['total_recipes'] = self.get_queryset().count()
        return context


@login_required
def import_recipe_csv(request):
    """
    Import recipes from CSV file.
    
    Handles CSV file upload, validation, and batch recipe creation.
    """
    if request.method == 'POST':
        form = RecipeCSVImportForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Check user's recipe limit
                from auth_hub.models import UserProfile, SubscriptionTier
                
                try:
                    profile = request.user.profile
                except UserProfile.DoesNotExist:
                    default_tier = SubscriptionTier.objects.filter(tier_type='FREE').first()
                    if not default_tier:
                        default_tier = SubscriptionTier.objects.create(
                            name='Home Cook',
                            price=0,
                            tier_type='FREE',
                            max_recipes=10,
                            max_menus=3,
                            max_shares=0
                        )
                    profile = UserProfile.objects.create(
                        user=request.user,
                        subscription_tier=default_tier
                    )
                    logger.warning(f"Created missing UserProfile for user {request.user.username}")
                
                # Get CSV data
                csv_data = form.get_csv_data()
                if not csv_data:
                    messages.error(request, "No valid data found in CSV file.")
                    return render(request, 'recipe_hub/recipe_csv_import.html', {'form': form})
                
                # Check recipe limits
                current_count = Recipe.objects.filter(author=request.user).count()
                max_recipes = profile.subscription_tier.max_recipes
                
                if max_recipes != -1:  # Not unlimited
                    available_slots = max_recipes - current_count
                    if len(csv_data) > available_slots:
                        messages.error(
                            request,
                            f"CSV contains {len(csv_data)} recipes, but you can only add "
                            f"{available_slots} more recipes with your current plan. "
                            f"Please upgrade your subscription or reduce the CSV size."
                        )
                        return render(request, 'recipe_hub/recipe_csv_import.html', {'form': form})
                
                # Process import
                import_results = _process_csv_import(
                    csv_data, 
                    request.user, 
                    form.cleaned_data
                )
                
                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    action='import_recipes_csv',
                    details=f"Imported {import_results['created']} recipes from CSV"
                )
                
                # Show results
                if import_results['created'] > 0:
                    messages.success(
                        request,
                        f"Successfully imported {import_results['created']} recipes!"
                    )
                
                if import_results['skipped'] > 0:
                    messages.info(
                        request,
                        f"Skipped {import_results['skipped']} duplicate recipes."
                    )
                
                if import_results['errors']:
                    messages.warning(
                        request,
                        f"Encountered {len(import_results['errors'])} errors during import. "
                        f"Check the logs for details."
                    )
                
                logger.info(
                    f"CSV import completed for {request.user.username}: "
                    f"{import_results['created']} created, {import_results['skipped']} skipped, "
                    f"{len(import_results['errors'])} errors"
                )
                
                return redirect('recipe_hub:user_recipes')
                
            except Exception as e:
                logger.error(f"CSV import error for user {request.user.username}: {str(e)}")
                messages.error(
                    request,
                    f"An error occurred during import: {str(e)}"
                )
    else:
        form = RecipeCSVImportForm()
    
    return render(request, 'recipe_hub/recipe_csv_import.html', {
        'form': form
    })


def _process_csv_import(csv_data, user, options):
    """
    Process CSV data and create recipes.
    
    Args:
        csv_data (list): Parsed CSV data
        user: User creating the recipes
        options (dict): Import options from form
        
    Returns:
        dict: Import results with counts and errors
    """
    results = {
        'created': 0,
        'skipped': 0,
        'errors': []
    }
    
    skip_duplicates = options.get('skip_duplicates', True)
    make_public = options.get('make_public', True)
    default_category = options.get('default_category')
    
    for row_data in csv_data:
        try:
            # Check for duplicates
            if skip_duplicates:
                existing = Recipe.objects.filter(
                    title__iexact=row_data['title'],
                    author=user
                ).exists()
                
                if existing:
                    logger.info(f"Skipping duplicate recipe: {row_data['title']}")
                    results['skipped'] += 1
                    continue
            
            # Create recipe
            with transaction.atomic():
                recipe = Recipe.objects.create(
                    author=user,
                    title=row_data['title'],
                    description=row_data['description'],
                    prep_time=row_data['prep_time'],
                    cook_time=row_data['cook_time'],
                    servings=row_data['servings'],
                    difficulty=row_data['difficulty'],
                    is_public=make_public,
                    dietary_info=row_data['dietary_info']
                )
                
                # Add categories
                categories_to_add = []
                
                # Add specified categories
                for cat_name in row_data['categories']:
                    try:
                        category = RecipeCategory.objects.get(
                            name__iexact=cat_name,
                            is_active=True
                        )
                        categories_to_add.append(category)
                    except RecipeCategory.DoesNotExist:
                        logger.warning(f"Category not found: {cat_name}")
                
                # Add default category if no categories and default is specified
                if not categories_to_add and default_category:
                    categories_to_add.append(default_category)
                
                if categories_to_add:
                    recipe.categories.set(categories_to_add)
                
                # Create ingredients
                for i, ingredient_data in enumerate(row_data['ingredients']):
                    Ingredient.objects.create(
                        recipe=recipe,
                        name=ingredient_data['name'],
                        quantity=ingredient_data['quantity'],
                        unit=ingredient_data['unit'],
                        notes=ingredient_data['notes'],
                        order=i + 1
                    )
                
                # Create instructions
                for instruction_data in row_data['instructions']:
                    Instruction.objects.create(
                        recipe=recipe,
                        step_number=instruction_data['step_number'],
                        instruction=instruction_data['instruction'],
                        time_minutes=instruction_data['time_minutes']
                    )
                
                logger.info(f"Created recipe from CSV: {recipe.title} (ID: {recipe.pk})")
                results['created'] += 1
                
        except Exception as e:
            error_msg = f"Error creating recipe '{row_data.get('title', 'Unknown')}': {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
    
    return results


@login_required
def import_recipe(request):
    """Legacy import recipe view for URL/text import."""
    if request.method == 'POST':
        form = RecipeImportForm(request.POST)
        if form.is_valid():
            messages.info(
                request,
                "Recipe URL/text import feature is coming soon! "
                "For now, please use CSV import or create recipes manually."
            )
            return redirect('recipe_hub:recipe_create')
    else:
        form = RecipeImportForm()
    
    return render(request, 'recipe_hub/recipe_import.html', {
        'form': form
    })


@login_required
def toggle_favorite(request, pk):
    """Toggle favorite status for a recipe."""
    if request.method != 'POST':
        return HttpResponseForbidden()
    
    recipe = get_object_or_404(Recipe, pk=pk, is_public=True)
    favorite, created = RecipeFavorite.objects.get_or_create(
        user=request.user,
        recipe=recipe
    )
    
    if not created:
        favorite.delete()
        is_favorited = False
        message = "Recipe removed from favorites."
        logger.info(
            f"Recipe unfavorited: {recipe.title} by {request.user.username}"
        )
    else:
        is_favorited = True
        message = "Recipe added to favorites!"
        logger.info(
            f"Recipe favorited: {recipe.title} by {request.user.username}"
        )
    
    # Log activity
    ActivityLog.objects.create(
        user=request.user,
        action='toggle_favorite',
        details=f"{'Added' if is_favorited else 'Removed'} favorite: {recipe.title}"
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'is_favorited': is_favorited,
            'message': message,
            'favorite_count': recipe.favorites.count()
        })
    
    messages.success(request, message)
    return redirect(recipe.get_absolute_url())


@login_required
def rate_recipe(request, pk):
    """Rate a recipe."""
    if request.method != 'POST':
        return HttpResponseForbidden()
    
    recipe = get_object_or_404(Recipe, pk=pk, is_public=True)
    form = RecipeRatingForm(request.POST)
    
    if form.is_valid():
        try:
            rating, created = RecipeRating.objects.update_or_create(
                user=request.user,
                recipe=recipe,
                defaults={
                    'rating': form.cleaned_data['rating'],
                    'review': form.cleaned_data.get('review', '')
                }
            )
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='rate_recipe',
                details=f"Rated recipe: {recipe.title} ({rating.rating}/5)"
            )
            
            message = "Thank you for rating this recipe!"
            logger.info(
                f"Recipe rated: {recipe.title} by {request.user.username} "
                f"({rating.rating}/5)"
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'average_rating': recipe.average_rating,
                    'rating_count': recipe.rating_count
                })
            
            messages.success(request, message)
            
        except Exception as e:
            logger.error(
                f"Error rating recipe {recipe.pk} for user "
                f"{request.user.username}: {str(e)}"
            )
            messages.error(request, "An error occurred while rating the recipe.")
    else:
        messages.error(request, "Please provide a valid rating.")
    
    return redirect(recipe.get_absolute_url())


@login_required
def add_comment(request, pk):
    """Add comment to a recipe."""
    if request.method != 'POST':
        return HttpResponseForbidden()
    
    recipe = get_object_or_404(Recipe, pk=pk, is_public=True)
    form = RecipeCommentForm(request.POST)
    
    if form.is_valid():
        try:
            comment = form.save(commit=False)
            comment.recipe = recipe
            comment.user = request.user
            
            # Handle reply to comment
            parent_id = request.POST.get('parent_id')
            if parent_id:
                parent_comment = get_object_or_404(RecipeComment, pk=parent_id)
                comment.parent = parent_comment
            
            comment.save()
            
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='add_comment',
                details=f"Commented on recipe: {recipe.title}"
            )
            
            messages.success(request, "Comment added successfully!")
            logger.info(
                f"Comment added to recipe {recipe.title} by {request.user.username}"
            )
            
        except Exception as e:
            logger.error(
                f"Error adding comment to recipe {recipe.pk} for user "
                f"{request.user.username}: {str(e)}"
            )
            messages.error(request, "An error occurred while adding your comment.")
    else:
        messages.error(request, "Please provide a valid comment.")
    
    return redirect(recipe.get_absolute_url())