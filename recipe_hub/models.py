"""
Recipe Hub Models

This module contains all models for recipe management including recipes,
ingredients, instructions, categories, and user interactions.
"""

import logging
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class RecipeCategory(models.Model):
    """
    Categories for organizing recipes.
    
    Attributes:
        name: Category name (e.g., 'Italian', 'Breakfast')
        slug: URL-friendly version of name
        description: Optional description of the category
        icon: Bootstrap icon class for UI display
        is_active: Whether category is available for selection
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50, 
        default='bi-tag',
        help_text="Bootstrap icon class (e.g., 'bi-egg-fried' for breakfast)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Recipe Category"
        verbose_name_plural = "Recipe Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        logger.info(f"RecipeCategory saved: {self.name} (ID: {self.pk})")


class Recipe(models.Model):
    """
    Main recipe model containing all recipe information.
    
    Attributes:
        author: User who created the recipe
        title: Recipe name
        slug: URL-friendly version of title
        description: Short description
        categories: Many-to-many relationship with categories
        meal_types: Many-to-many relationship with meal types (NEW)
        prep_time: Preparation time in minutes
        cook_time: Cooking time in minutes
        servings: Number of servings
        difficulty: Recipe difficulty level
        image: Main recipe image
        is_public: Whether recipe is visible to other users
        is_featured: Admin-selected featured recipes
        dietary_info: JSON field for dietary restrictions
    """
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipes'
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(help_text="Brief description of the recipe")
    categories = models.ManyToManyField(
        RecipeCategory,
        related_name='recipes',
        help_text="Select one or more categories"
    )
    
    # ADD THIS NEW FIELD - Meal Types relationship
    meal_types = models.ManyToManyField(
        'meal_planner.MealType',
        related_name='recipes',
        blank=True,
        help_text="What meals is this recipe suitable for? (breakfast, lunch, dinner, snack)"
    )
    
    # Time and servings
    prep_time = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Preparation time in minutes"
    )
    cook_time = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Cooking time in minutes"
    )
    servings = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        default=4
    )
    
    # Additional info
    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    image = models.ImageField(
        upload_to='recipes/',
        blank=True,
        null=True,
        help_text="Recipe image (optional)"
    )
    
    # Visibility and features
    is_public = models.BooleanField(
        default=True,
        help_text="Make recipe visible to other users"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Featured recipes appear on homepage"
    )
    
    # Dietary information (stored as JSON)
    dietary_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dietary restrictions and allergens"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # SEO and metadata
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text="SEO meta description"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['is_public', '-created_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Auto-generate slug and validate recipe limits."""
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Recipe.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Check recipe limits for user
        if not self.pk:  # New recipe
            try:
                self._check_recipe_limit()
            except ValidationError as e:
                logger.warning(f"Recipe limit exceeded for user {self.author.username}: {str(e)}")
                raise
        
        super().save(*args, **kwargs)
        logger.info(f"Recipe saved: {self.title} by {self.author.username} (ID: {self.pk})")

    def _check_recipe_limit(self):
        """Check if user has reached their recipe limit based on subscription."""
        from auth_hub.models import UserProfile
        
        # Skip limit check for admin/staff users
        if self.author.is_staff or self.author.is_superuser:
            logger.info(f"Recipe limit check skipped for admin user {self.author.username}")
            return
        
        try:
            profile = self.author.profile
            subscription_tier = profile.subscription_tier
            
            if subscription_tier.max_recipes != -1:  # -1 means unlimited
                current_count = Recipe.objects.filter(author=self.author).count()
                if current_count >= subscription_tier.max_recipes:
                    raise ValidationError(
                        f"Recipe limit reached. Your {subscription_tier.name} plan allows "
                        f"{subscription_tier.max_recipes} recipes. Please upgrade to add more."
                    )
        except UserProfile.DoesNotExist:
            logger.error(f"UserProfile not found for user {self.author.username}")
            raise ValidationError("User profile not found. Please contact support.")

    def get_absolute_url(self):
        """Get the canonical URL for this recipe."""
        return reverse('recipe_hub:recipe_detail', kwargs={'slug': self.slug})

    @property
    def total_time(self):
        """Calculate total time (prep + cook)."""
        return self.prep_time + self.cook_time

    @property
    def average_rating(self):
        """Calculate average rating from all ratings."""
        avg = self.ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg, 1) if avg else 0

    @property
    def rating_count(self):
        """Get total number of ratings."""
        return self.ratings.count()

    def is_favorited_by(self, user):
        """Check if recipe is favorited by given user."""
        if user.is_authenticated:
            return self.favorites.filter(user=user).exists()
        return False

    def can_edit(self, user):
        """Check if user can edit this recipe."""
        return user == self.author or user.is_staff

    def get_dietary_labels(self):
        """Get list of dietary labels for display."""
        labels = []
        dietary_info = self.dietary_info or {}
        
        if dietary_info.get('vegetarian'):
            labels.append('Vegetarian')
        if dietary_info.get('vegan'):
            labels.append('Vegan')
        if dietary_info.get('gluten_free'):
            labels.append('Gluten-Free')
        if dietary_info.get('dairy_free'):
            labels.append('Dairy-Free')
        if dietary_info.get('nut_free'):
            labels.append('Nut-Free')
        
        return labels

    # ADD THIS NEW METHOD
    def get_meal_type_names(self):
        """Get list of meal type names for display."""
        return [mt.name for mt in self.meal_types.all()]
    
    # ADD THIS NEW METHOD  
    def is_suitable_for_meal_type(self, meal_type_name):
        """Check if recipe is suitable for a specific meal type."""
        return self.meal_types.filter(name__iexact=meal_type_name).exists()
    



class IngredientCategory(models.Model):
    """
    Category for organizing ingredients in shopping lists.
    
    This model allows dynamic categorization of ingredients for better
    organization in shopping lists and grocery shopping.
    
    Attributes:
        name: Category name (e.g., 'Produce', 'Dairy', 'Meat & Seafood')
        slug: URL-friendly version of the name
        display_order: Order in which categories appear in shopping lists
        keywords: Keywords to auto-categorize ingredients
        is_active: Whether this category is currently in use
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Category name for ingredients"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly version of the name"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order in which to display this category"
    )
    keywords = models.TextField(
        blank=True,
        help_text="Comma-separated keywords for auto-categorization (e.g., 'chicken,beef,pork' for Meat category)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Ingredient Category"
        verbose_name_plural = "Ingredient Categories"
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return self.name
    
    def get_keywords_list(self):
        """Return keywords as a list."""
        if self.keywords:
            return [k.strip().lower() for k in self.keywords.split(',') if k.strip()]
        return []
    
    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Ingredient(models.Model):
    """
    Ingredient for a recipe with enhanced categorization.
    
    Attributes:
        recipe: The recipe this ingredient belongs to
        name: Name of the ingredient
        quantity: Amount needed
        unit: Unit of measurement
        order: Display order in the recipe
        category: Category for shopping list organization
        notes: Optional notes about the ingredient
    """
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='ingredients'
    )
    name = models.CharField(max_length=200)
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., cups, tbsp, oz"
    )
    order = models.IntegerField(default=0)
    category = models.ForeignKey(
        IngredientCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ingredients',
        help_text="Category for shopping list organization"
    )
    notes = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional notes (e.g., 'finely chopped', 'room temperature')"
    )
    
    class Meta:
        ordering = ['order', 'name']
    
    def __str__(self):
        if self.quantity and self.unit:
            return f"{self.quantity} {self.unit} {self.name}"
        elif self.quantity:
            return f"{self.quantity} {self.name}"
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-categorize ingredient if category not set."""
        if not self.category_id:
            self.auto_categorize()
        super().save(*args, **kwargs)
    
    def auto_categorize(self):
        """
        Automatically assign category based on ingredient name and category keywords.
        
        This method uses keyword matching to automatically categorize ingredients
        based on predefined keywords in each category.
        """
        try:
            ingredient_lower = self.name.lower()
            
            # Try to find a matching category based on keywords
            categories = IngredientCategory.objects.filter(is_active=True)
            
            for category in categories:
                keywords = category.get_keywords_list()
                if any(keyword in ingredient_lower for keyword in keywords):
                    self.category = category
                    logger.info(f"Auto-categorized '{self.name}' as '{category.name}'")
                    return
            
            # If no match found, try to find or create 'Other' category
            other_category, created = IngredientCategory.objects.get_or_create(
                slug='other',
                defaults={
                    'name': 'Other',
                    'display_order': 999,
                    'is_active': True
                }
            )
            self.category = other_category
            
            if created:
                logger.info("Created 'Other' category for uncategorized ingredients")
                
        except Exception as e:
            logger.error(f"Error auto-categorizing ingredient '{self.name}': {str(e)}")
            # Don't fail the save operation
            pass








class Instruction(models.Model):
    """
    Step-by-step instructions for recipes.
    
    Attributes:
        recipe: Parent recipe
        step_number: Order of the step
        instruction: The instruction text
        time_minutes: Optional time for this step
        image: Optional image for this step
    """
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='instructions'
    )
    step_number = models.PositiveIntegerField()
    instruction = models.TextField()
    time_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Time needed for this step (optional)"
    )
    image = models.ImageField(
        upload_to='recipes/steps/',
        blank=True,
        null=True,
        help_text="Optional image for this step"
    )
    
    class Meta:
        ordering = ['step_number']
        unique_together = ['recipe', 'step_number']

    def __str__(self):
        return f"Step {self.step_number}: {self.instruction[:50]}..."

    def save(self, *args, **kwargs):
        """Auto-increment step number if not provided."""
        if not self.step_number:
            max_step = self.recipe.instructions.aggregate(
                models.Max('step_number')
            )['step_number__max'] or 0
            self.step_number = max_step + 1
        super().save(*args, **kwargs)


class RecipeRating(models.Model):
    """
    User ratings for recipes.
    
    Attributes:
        recipe: Recipe being rated
        user: User who rated
        rating: Score from 1-5
        review: Optional text review
    """
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipe_ratings'
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['recipe', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} rated {self.recipe.title}: {self.rating}/5"

    def save(self, *args, **kwargs):
        """Log rating activity."""
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        if is_new:
            logger.info(
                f"New rating: {self.user.username} rated {self.recipe.title} "
                f"{self.rating}/5 (Recipe ID: {self.recipe.pk})"
            )


class RecipeFavorite(models.Model):
    """
    Track user's favorite recipes.
    
    Attributes:
        recipe: Favorited recipe
        user: User who favorited
        created_at: When favorited
    """
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorite_recipes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['recipe', 'user']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} favorited {self.recipe.title}"

    def save(self, *args, **kwargs):
        """Log favorite activity."""
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        if is_new:
            logger.info(
                f"Recipe favorited: {self.recipe.title} by {self.user.username} "
                f"(Recipe ID: {self.recipe.pk})"
            )


class RecipeComment(models.Model):
    """
    Comments on recipes for community interaction.
    
    Attributes:
        recipe: Recipe being commented on
        user: User who commented
        parent: Parent comment for replies
        comment: The comment text
        is_approved: Moderation status
    """
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipe_comments'
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    comment = models.TextField()
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.recipe.title}"

    def save(self, *args, **kwargs):
        """Log comment activity."""
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        if is_new:
            logger.info(
                f"New comment on {self.recipe.title} by {self.user.username} "
                f"(Recipe ID: {self.recipe.pk})"
            )



