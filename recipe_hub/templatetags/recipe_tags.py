"""
Custom template tags for recipe_hub app.

Provides utility tags for recipe display and interaction.
"""

import logging
from django import template
from django.db.models import Avg, Count, Q
from recipe_hub.models import Recipe, RecipeCategory, RecipeFavorite

logger = logging.getLogger(__name__)
register = template.Library()


@register.filter
def is_favorited_by(recipe, user):
    """
    Check if a recipe is favorited by the given user.
    
    Usage: {% if recipe|is_favorited_by:user %}
    """
    if not user.is_authenticated:
        return False
    
    try:
        return RecipeFavorite.objects.filter(recipe=recipe, user=user).exists()
    except Exception as e:
        logger.error(f"Error checking favorite status: {str(e)}")
        return False


@register.filter
def rating_stars(rating):
    """
    Convert numeric rating to star display.
    
    Usage: {{ recipe.average_rating|rating_stars }}
    """
    try:
        rating = float(rating)
        full_stars = int(rating)
        half_star = 1 if rating - full_stars >= 0.5 else 0
        empty_stars = 5 - full_stars - half_star
        
        stars = '★' * full_stars
        if half_star:
            stars += '⯨'
        stars += '☆' * empty_stars
        
        return stars
    except (ValueError, TypeError):
        return '☆' * 5


@register.filter
def time_format(minutes):
    """
    Format minutes into human-readable time.
    
    Usage: {{ recipe.total_time|time_format }}
    """
    try:
        minutes = int(minutes)
        if minutes < 60:
            return f"{minutes} min"
        
        hours = minutes // 60
        mins = minutes % 60
        
        if mins == 0:
            return f"{hours} hr" if hours == 1 else f"{hours} hrs"
        
        hr_text = "hr" if hours == 1 else "hrs"
        return f"{hours} {hr_text} {mins} min"
    except (ValueError, TypeError):
        return "N/A"


@register.filter
def difficulty_badge_class(difficulty):
    """
    Get Bootstrap class for difficulty badge.
    
    Usage: class="badge bg-{{ recipe.difficulty|difficulty_badge_class }}"
    """
    classes = {
        'easy': 'success',
        'medium': 'warning',
        'hard': 'danger'
    }
    return classes.get(difficulty, 'secondary')


@register.simple_tag
def user_recipe_count(user):
    """
    Get the number of recipes created by a user.
    
    Usage: {% user_recipe_count user as count %}
    """
    try:
        return Recipe.objects.filter(author=user).count()
    except Exception as e:
        logger.error(f"Error counting user recipes: {str(e)}")
        return 0


@register.simple_tag
def recipe_limit_percentage(user):
    """
    Calculate percentage of recipe limit used.
    
    Usage: {% recipe_limit_percentage user as percentage %}
    """
    try:
        profile = user.profile
        max_recipes = profile.subscription_tier.max_recipes
        
        if max_recipes == -1:  # Unlimited
            return 0
        
        current_count = Recipe.objects.filter(author=user).count()
        percentage = (current_count / max_recipes) * 100
        return min(int(percentage), 100)
    except Exception as e:
        logger.error(f"Error calculating recipe limit percentage: {str(e)}")
        return 0


@register.inclusion_tag('recipe_hub/includes/recipe_card.html')
def recipe_card(recipe, user=None):
    """
    Render a recipe card component.
    
    Usage: {% recipe_card recipe user=request.user %}
    """
    context = {
        'recipe': recipe,
        'user': user,
        'is_favorited': False
    }
    
    if user and user.is_authenticated:
        context['is_favorited'] = RecipeFavorite.objects.filter(
            recipe=recipe, user=user
        ).exists()
    
    return context


@register.inclusion_tag('recipe_hub/includes/category_badge.html')
def category_badge(category, show_count=False):
    """
    Render a category badge.
    
    Usage: {% category_badge category show_count=True %}
    """
    context = {
        'category': category,
        'show_count': show_count
    }
    
    if show_count:
        context['recipe_count'] = category.recipes.filter(is_public=True).count()
    
    return context


@register.simple_tag
def popular_categories(limit=5):
    """
    Get most popular categories by recipe count.
    
    Usage: {% popular_categories 5 as categories %}
    """
    try:
        return RecipeCategory.objects.filter(
            is_active=True
        ).annotate(
            recipe_count=Count('recipes', filter=Q(recipes__is_public=True))
        ).order_by('-recipe_count')[:limit]
    except Exception as e:
        logger.error(f"Error getting popular categories: {str(e)}")
        return RecipeCategory.objects.none()


@register.simple_tag
def recent_recipes(limit=5, exclude=None):
    """
    Get most recent public recipes.
    
    Usage: {% recent_recipes 5 exclude=recipe as recipes %}
    """
    try:
        queryset = Recipe.objects.filter(is_public=True)
        
        if exclude:
            queryset = queryset.exclude(pk=exclude.pk)
        
        return queryset.select_related(
            'author'
        ).prefetch_related('categories')[:limit]
    except Exception as e:
        logger.error(f"Error getting recent recipes: {str(e)}")
        return Recipe.objects.none()


@register.simple_tag
def top_rated_recipes(limit=5):
    """
    Get highest rated recipes.
    
    Usage: {% top_rated_recipes 5 as recipes %}
    """
    try:
        return Recipe.objects.filter(
            is_public=True
        ).annotate(
            avg_rating=Avg('ratings__rating'),
            rating_count=Count('ratings')
        ).filter(
            rating_count__gte=2  # At least 2 ratings
        ).order_by('-avg_rating')[:limit]
    except Exception as e:
        logger.error(f"Error getting top rated recipes: {str(e)}")
        return Recipe.objects.none()


@register.filter
def truncate_words(value, length=20):
    """
    Truncate text to specified word count.
    
    Usage: {{ recipe.description|truncate_words:15 }}
    """
    try:
        words = value.split()
        if len(words) > length:
            return ' '.join(words[:length]) + '...'
        return value
    except (AttributeError, TypeError):
        return value


@register.simple_tag(takes_context=True)
def query_string(context, **kwargs):
    """
    Build query string maintaining existing parameters.
    
    Usage: href="?{% query_string page=2 %}"
    """
    request = context.get('request')
    if not request:
        return ''
    
    params = request.GET.copy()
    
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    
    return params.urlencode()