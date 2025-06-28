"""
Recipe Hub API Views

Provides API endpoints for recipe-related operations.
"""

import logging
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from recipe_hub.models import Recipe, RecipeCategory, RecipeFavorite

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def check_recipe_limit(request):
    """
    Check if user can create more recipes based on subscription.
    
    Returns:
        JSON response with limit information
    """
    try:
        profile = request.user.userprofile
        subscription_tier = profile.subscription_tier
        current_count = Recipe.objects.filter(author=request.user).count()
        
        can_create = (
            subscription_tier.max_recipes == -1 or 
            current_count < subscription_tier.max_recipes
        )
        
        return JsonResponse({
            'can_create': can_create,
            'current_count': current_count,
            'max_recipes': subscription_tier.max_recipes,
            'tier_name': subscription_tier.name,
            'remaining': (
                -1 if subscription_tier.max_recipes == -1 
                else subscription_tier.max_recipes - current_count
            )
        })
    except Exception as e:
        logger.error(f"Error checking recipe limit for user {request.user.username}: {str(e)}")
        return JsonResponse({'error': 'Unable to check recipe limit'}, status=500)


@login_required
@require_http_methods(["GET"])
def recipe_stats(request):
    """
    Get statistics for user's recipes.
    
    Returns:
        JSON response with recipe statistics
    """
    try:
        user_recipes = Recipe.objects.filter(author=request.user)
        
        stats = {
            'total_recipes': user_recipes.count(),
            'public_recipes': user_recipes.filter(is_public=True).count(),
            'private_recipes': user_recipes.filter(is_public=False).count(),
            'total_ratings': sum(recipe.rating_count for recipe in user_recipes),
            'total_favorites': sum(recipe.favorites.count() for recipe in user_recipes),
            'average_rating': sum(
                recipe.average_rating * recipe.rating_count 
                for recipe in user_recipes if recipe.rating_count > 0
            ) / max(sum(recipe.rating_count for recipe in user_recipes), 1),
            'categories': list(
                RecipeCategory.objects.filter(
                    recipes__author=request.user
                ).distinct().values('id', 'name', 'slug')
            )
        }
        
        return JsonResponse(stats)
    except Exception as e:
        logger.error(f"Error getting recipe stats for user {request.user.username}: {str(e)}")
        return JsonResponse({'error': 'Unable to get statistics'}, status=500)


@require_http_methods(["GET"])
def recipe_search_suggestions(request):
    """
    Get recipe search suggestions based on query.
    
    Returns:
        JSON response with recipe suggestions
    """
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    try:
        # Search in recipe titles
        recipes = Recipe.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query),
            is_public=True
        ).values('id', 'title', 'slug')[:10]
        
        # Search in categories
        categories = RecipeCategory.objects.filter(
            name__icontains=query,
            is_active=True
        ).values('id', 'name', 'slug')[:5]
        
        suggestions = {
            'recipes': list(recipes),
            'categories': list(categories)
        }
        
        return JsonResponse(suggestions)
    except Exception as e:
        logger.error(f"Error getting search suggestions: {str(e)}")
        return JsonResponse({'suggestions': []}, status=500)


@login_required
@require_http_methods(["GET"])
def user_favorites_list(request):
    """
    Get list of user's favorite recipe IDs.
    
    Returns:
        JSON response with favorite recipe IDs
    """
    try:
        favorite_ids = RecipeFavorite.objects.filter(
            user=request.user
        ).values_list('recipe_id', flat=True)
        
        return JsonResponse({
            'favorite_ids': list(favorite_ids),
            'count': len(favorite_ids)
        })
    except Exception as e:
        logger.error(f"Error getting favorites for user {request.user.username}: {str(e)}")
        return JsonResponse({'error': 'Unable to get favorites'}, status=500)


@require_http_methods(["GET"])
def popular_recipes(request):
    """
    Get list of popular recipes based on ratings and favorites.
    
    Returns:
        JSON response with popular recipes
    """
    try:
        limit = min(int(request.GET.get('limit', 10)), 50)
        
        recipes = Recipe.objects.filter(
            is_public=True
        ).annotate(
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings'),
            favorite_count=Count('favorites')
        ).filter(
            rating_count__gte=2  # At least 2 ratings
        ).order_by('-avg_rating', '-favorite_count')[:limit]
        
        recipe_data = []
        for recipe in recipes:
            recipe_data.append({
                'id': recipe.id,
                'title': recipe.title,
                'slug': recipe.slug,
                'average_rating': recipe.avg_rating,
                'rating_count': recipe.rating_count,
                'favorite_count': recipe.favorite_count,
                'author': recipe.author.username,
                'total_time': recipe.total_time,
                'image_url': recipe.image.url if recipe.image else None
            })
        
        return JsonResponse({'recipes': recipe_data})
    except Exception as e:
        logger.error(f"Error getting popular recipes: {str(e)}")
        return JsonResponse({'error': 'Unable to get popular recipes'}, status=500)