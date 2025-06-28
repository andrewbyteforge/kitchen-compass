"""
Recipe Hub Admin Configuration

Provides comprehensive admin interface for managing recipes, categories,
and user interactions.
"""

from django.contrib import admin
from django.db.models import Avg, Count
from django.utils.html import format_html
from .models import (
    RecipeCategory, Recipe, Ingredient, Instruction,
    RecipeRating, RecipeFavorite, RecipeComment
)
from .models import Recipe, RecipeCategory, Ingredient, Instruction, RecipeRating, RecipeFavorite, RecipeComment, IngredientCategory

@admin.register(RecipeCategory)
class RecipeCategoryAdmin(admin.ModelAdmin):
    """Admin interface for recipe categories."""
    
    list_display = ['name', 'slug', 'icon_preview', 'recipe_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'description')
        }),
        ('Display', {
            'fields': ('icon', 'is_active')
        }),
    )
    
    def icon_preview(self, obj):
        """Show icon preview."""
        return format_html(
            '<i class="bi {}"></i> {}',
            obj.icon, obj.icon
        )
    icon_preview.short_description = 'Icon'
    
    def recipe_count(self, obj):
        """Count recipes in this category."""
        return obj.recipes.filter(is_public=True).count()
    recipe_count.short_description = 'Recipes'


class IngredientInline(admin.TabularInline):
    """Inline admin for recipe ingredients."""
    model = Ingredient
    extra = 1
    fields = ['order', 'quantity', 'unit', 'name', 'notes']
    ordering = ['order']


class InstructionInline(admin.TabularInline):
    """Inline admin for recipe instructions."""
    model = Instruction
    extra = 1
    fields = ['step_number', 'instruction', 'time_minutes']
    ordering = ['step_number']


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Admin interface for recipes."""
    
    list_display = [
        'title', 'author_link', 'category_list', 'difficulty',
        'total_time', 'avg_rating', 'rating_count', 'is_public',
        'is_featured', 'created_at'
    ]
    list_filter = [
        'difficulty', 'is_public', 'is_featured', 'categories',
        'created_at', 'updated_at'
    ]
    search_fields = ['title', 'description', 'author__username', 'author__email']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ['author']
    filter_horizontal = ['categories']
    date_hierarchy = 'created_at'
    
    inlines = [IngredientInline, InstructionInline]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author', 'description', 'categories')
        }),
        ('Time & Servings', {
            'fields': ('prep_time', 'cook_time', 'servings', 'difficulty')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Visibility', {
            'fields': ('is_public', 'is_featured')
        }),
        ('Dietary Information', {
            'fields': ('dietary_info',),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_description',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['make_featured', 'remove_featured', 'make_public', 'make_private']
    
    def author_link(self, obj):
        """Link to author's profile."""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.author.pk, obj.author.username
        )
    author_link.short_description = 'Author'
    
    def category_list(self, obj):
        """Display categories as comma-separated list."""
        return ', '.join([cat.name for cat in obj.categories.all()])
    category_list.short_description = 'Categories'
    
    def total_time(self, obj):
        """Display total cooking time."""
        return f"{obj.total_time} min"
    total_time.short_description = 'Total Time'
    
    def avg_rating(self, obj):
        """Display average rating."""
        avg = obj.ratings.aggregate(avg=Avg('rating'))['avg']
        if avg:
            return format_html(
                '<span style="color: #f39c12;">★</span> {:.1f}',
                avg
            )
        return '-'
    avg_rating.short_description = 'Rating'
    
    def rating_count(self, obj):
        """Display rating count."""
        return obj.ratings.count()
    rating_count.short_description = 'Reviews'
    
    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return super().get_queryset(request).prefetch_related(
            'categories', 'ratings'
        ).select_related('author')
    
    def make_featured(self, request, queryset):
        """Mark recipes as featured."""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} recipes marked as featured.')
    make_featured.short_description = 'Mark as featured'
    
    def remove_featured(self, request, queryset):
        """Remove featured status."""
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} recipes removed from featured.')
    remove_featured.short_description = 'Remove from featured'
    
    def make_public(self, request, queryset):
        """Make recipes public."""
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} recipes made public.')
    make_public.short_description = 'Make public'
    
    def make_private(self, request, queryset):
        """Make recipes private."""
        updated = queryset.update(is_public=False)
        self.message_user(request, f'{updated} recipes made private.')
    make_private.short_description = 'Make private'


@admin.register(RecipeRating)
class RecipeRatingAdmin(admin.ModelAdmin):
    """Admin interface for recipe ratings."""
    
    list_display = ['recipe_link', 'user_link', 'rating_stars', 'has_review', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['recipe__title', 'user__username', 'review']
    raw_id_fields = ['recipe', 'user']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('recipe', 'user', 'rating')
        }),
        ('Review', {
            'fields': ('review',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def recipe_link(self, obj):
        """Link to recipe."""
        return format_html(
            '<a href="/admin/recipe_hub/recipe/{}/change/">{}</a>',
            obj.recipe.pk, obj.recipe.title[:50]
        )
    recipe_link.short_description = 'Recipe'
    
    def user_link(self, obj):
        """Link to user."""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.username
        )
    user_link.short_description = 'User'
    
    def rating_stars(self, obj):
        """Display rating as stars."""
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html(
            '<span style="color: #f39c12;">{}</span>',
            stars
        )
    rating_stars.short_description = 'Rating'
    
    def has_review(self, obj):
        """Check if rating includes a review."""
        return bool(obj.review)
    has_review.boolean = True
    has_review.short_description = 'Has Review'


@admin.register(RecipeFavorite)
class RecipeFavoriteAdmin(admin.ModelAdmin):
    """Admin interface for recipe favorites."""
    
    list_display = ['recipe_link', 'user_link', 'created_at']
    list_filter = ['created_at']
    search_fields = ['recipe__title', 'user__username']
    raw_id_fields = ['recipe', 'user']
    date_hierarchy = 'created_at'
    
    def recipe_link(self, obj):
        """Link to recipe."""
        return format_html(
            '<a href="/admin/recipe_hub/recipe/{}/change/">{}</a>',
            obj.recipe.pk, obj.recipe.title[:50]
        )
    recipe_link.short_description = 'Recipe'
    
    def user_link(self, obj):
        """Link to user."""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.username
        )
    user_link.short_description = 'User'


@admin.register(RecipeComment)
class RecipeCommentAdmin(admin.ModelAdmin):
    """Admin interface for recipe comments."""
    
    list_display = [
        'recipe_link', 'user_link', 'comment_preview',
        'is_reply', 'is_approved', 'created_at'
    ]
    list_filter = ['is_approved', 'created_at']
    search_fields = ['recipe__title', 'user__username', 'comment']
    raw_id_fields = ['recipe', 'user', 'parent']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('recipe', 'user', 'parent')
        }),
        ('Content', {
            'fields': ('comment', 'is_approved')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    actions = ['approve_comments', 'disapprove_comments']
    
    def recipe_link(self, obj):
        """Link to recipe."""
        return format_html(
            '<a href="/admin/recipe_hub/recipe/{}/change/">{}</a>',
            obj.recipe.pk, obj.recipe.title[:30]
        )
    recipe_link.short_description = 'Recipe'
    
    def user_link(self, obj):
        """Link to user."""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.username
        )
    user_link.short_description = 'User'
    
    def comment_preview(self, obj):
        """Preview of comment text."""
        return obj.comment[:100] + '...' if len(obj.comment) > 100 else obj.comment
    comment_preview.short_description = 'Comment'
    
    def is_reply(self, obj):
        """Check if comment is a reply."""
        return obj.parent is not None
    is_reply.boolean = True
    is_reply.short_description = 'Is Reply'
    
    def approve_comments(self, request, queryset):
        """Approve selected comments."""
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} comments approved.')
    approve_comments.short_description = 'Approve selected comments'
    
    def disapprove_comments(self, request, queryset):
        """Disapprove selected comments."""
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} comments disapproved.')
    disapprove_comments.short_description = 'Disapprove selected comments'



@admin.register(IngredientCategory)
class IngredientCategoryAdmin(admin.ModelAdmin):
    """Admin interface for ingredient categories."""
    
    list_display = ['name', 'display_order', 'keyword_count', 'ingredient_count', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'keywords']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['display_order', 'name']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'slug', 'display_order', 'is_active')
        }),
        ('Auto-Categorization', {
            'fields': ('keywords',),
            'description': 'Enter comma-separated keywords to automatically categorize ingredients'
        }),
    )
    
    def keyword_count(self, obj):
        """Count number of keywords."""
        return len(obj.get_keywords_list())
    keyword_count.short_description = 'Keywords'
    
    def ingredient_count(self, obj):
        """Count ingredients in this category."""
        return obj.ingredients.count()
    ingredient_count.short_description = 'Ingredients'
    
    ingredient_count.admin_order_field = 'ingredients__count'
    
    def get_queryset(self, request):
        """Optimize queryset with ingredient counts."""
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(Count('ingredients'))
        return queryset


# Admin site customization
admin.site.site_header = 'KitchenCompass Admin'
admin.site.site_title = 'KitchenCompass Admin'
admin.site.index_title = 'Recipe Management'