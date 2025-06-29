"""
Asda product and category models for storing scraped grocery data.

This module contains Django models for organizing and storing:
- Asda product categories with hierarchical structure
- Product information including prices and availability
- Historical price tracking

File: auth_hub/models.py (add to existing models)
"""

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class AsdaCategory(models.Model):
    """
    Represents a product category from Asda groceries.
    
    Supports hierarchical categories with parent-child relationships
    for organizing products in a tree structure.
    """
    
    name = models.CharField(
        max_length=200,
        help_text="Category name as displayed on Asda website"
    )
    
    slug = models.SlugField(
        max_length=250,
        unique=True,
        blank=True,
        help_text="URL-friendly version of category name"
    )
    
    url = models.URLField(
        blank=True,
        null=True,
        help_text="Direct URL to category page on Asda website"
    )
    
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='subcategories',
        help_text="Parent category for hierarchical organization"
    )
    
    level = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Hierarchy level (1=main category, 2=subcategory, etc.)"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Category description or notes"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is currently being tracked"
    )
    
    product_count = models.PositiveIntegerField(
        default=0,
        help_text="Cached count of products in this category"
    )
    
    last_scraped = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time this category was scraped for products"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when category was first created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when category was last updated"
    )
    
    class Meta:
        """Meta configuration for AsdaCategory model."""
        
        verbose_name = "Asda Category"
        verbose_name_plural = "Asda Categories"
        ordering = ['level', 'name']
        indexes = [
            models.Index(fields=['parent', 'level']),
            models.Index(fields=['is_active', 'last_scraped']),
            models.Index(fields=['slug']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(level__gte=1),
                name='category_level_positive'
            )
        ]
    
    def __str__(self) -> str:
        """String representation of category."""
        if self.parent:
            return f"{self.parent.name} > {self.name}"
        return self.name
    
    def save(self, *args, **kwargs):
        """
        Custom save method to generate slug and update product count.
        
        Automatically creates URL-friendly slug from category name
        and maintains product count cache.
        """
        try:
            if not self.slug:
                from django.utils.text import slugify
                base_slug = slugify(self.name)
                slug = base_slug
                counter = 1
                
                while AsdaCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                self.slug = slug
            
            super().save(*args, **kwargs)
            
            # Update product count after saving
            self.update_product_count()
            
            logger.info(f"Saved Asda category: {self.name} (Level {self.level})")
            
        except Exception as e:
            logger.error(f"Error saving AsdaCategory {self.name}: {str(e)}")
            raise
    
    def update_product_count(self):
        """Update the cached product count for this category."""
        try:
            count = self.products.filter(is_available=True).count()
            if count != self.product_count:
                AsdaCategory.objects.filter(pk=self.pk).update(product_count=count)
                logger.debug(f"Updated product count for {self.name}: {count}")
        except Exception as e:
            logger.error(f"Error updating product count for {self.name}: {str(e)}")
    
    def get_all_products(self):
        """
        Get all products in this category and its subcategories.
        
        Returns:
            QuerySet: All products in category hierarchy
        """
        try:
            # Get all descendant categories
            descendant_ids = [self.pk]
            
            def get_descendants(category_id):
                children = AsdaCategory.objects.filter(parent_id=category_id).values_list('id', flat=True)
                for child_id in children:
                    descendant_ids.append(child_id)
                    get_descendants(child_id)
            
            get_descendants(self.pk)
            
            return AsdaProduct.objects.filter(
                category_id__in=descendant_ids,
                is_available=True
            )
            
        except Exception as e:
            logger.error(f"Error getting products for category {self.name}: {str(e)}")
            return AsdaProduct.objects.none()
    
    def get_breadcrumb(self):
        """
        Get breadcrumb path for this category.
        
        Returns:
            List[AsdaCategory]: Path from root to this category
        """
        breadcrumb = []
        current = self
        
        while current:
            breadcrumb.insert(0, current)
            current = current.parent
        
        return breadcrumb


class AsdaProduct(models.Model):
    """
    Represents a product from Asda groceries with pricing information.
    
    Stores product details, current pricing, and tracks availability
    for use in menu planning and cost calculations.
    """
    
    name = models.CharField(
        max_length=300,
        help_text="Product name as displayed on Asda website"
    )
    
    slug = models.SlugField(
        max_length=350,
        unique=True,
        blank=True,
        help_text="URL-friendly version of product name"
    )
    
    category = models.ForeignKey(
        AsdaCategory,
        on_delete=models.CASCADE,
        related_name='products',
        help_text="Category this product belongs to"
    )
    
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Current price in GBP"
    )
    
    price_text = models.CharField(
        max_length=50,
        blank=True,
        help_text="Raw price text as scraped from website"
    )
    
    price_per_unit = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price per unit (kg, litre, etc.)"
    )
    
    unit_type = models.CharField(
        max_length=20,
        blank=True,
        help_text="Unit type (kg, g, ml, l, each, etc.)"
    )
    
    description = models.TextField(
        blank=True,
        help_text="Product description or details"
    )
    
    brand = models.CharField(
        max_length=100,
        blank=True,
        help_text="Product brand name"
    )
    
    url = models.URLField(
        blank=True,
        null=True,
        help_text="Direct URL to product page on Asda website"
    )
    
    image_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to product image"
    )
    
    barcode = models.CharField(
        max_length=20,
        blank=True,
        help_text="Product barcode/EAN if available"
    )
    
    is_available = models.BooleanField(
        default=True,
        help_text="Whether product is currently available"
    )
    
    is_on_offer = models.BooleanField(
        default=False,
        help_text="Whether product is currently on special offer"
    )
    
    original_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Original price before any discounts"
    )
    
    offer_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Special offer description"
    )
    
    nutritional_info = models.JSONField(
        blank=True,
        null=True,
        help_text="Nutritional information as JSON"
    )
    
    allergens = models.CharField(
        max_length=500,
        blank=True,
        help_text="Allergen information"
    )
    
    ingredients = models.TextField(
        blank=True,
        help_text="Product ingredients list"
    )
    
    last_scraped = models.DateTimeField(
        auto_now=True,
        help_text="Last time product data was updated"
    )
    
    first_seen = models.DateTimeField(
        auto_now_add=True,
        help_text="When product was first discovered"
    )
    
    times_scraped = models.PositiveIntegerField(
        default=1,
        help_text="Number of times this product has been scraped"
    )
    
    class Meta:
        """Meta configuration for AsdaProduct model."""
        
        verbose_name = "Asda Product"
        verbose_name_plural = "Asda Products"
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category', 'is_available']),
            models.Index(fields=['price', 'is_available']),
            models.Index(fields=['brand', 'category']),
            models.Index(fields=['slug']),
            models.Index(fields=['last_scraped']),
            models.Index(fields=['is_on_offer', 'is_available']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gte=0) | models.Q(price__isnull=True),
                name='product_price_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(times_scraped__gte=1),
                name='product_times_scraped_positive'
            )
        ]
    
    def __str__(self) -> str:
        """String representation of product."""
        price_str = f"£{self.price}" if self.price else "No price"
        return f"{self.name} - {price_str}"
    
    def save(self, *args, **kwargs):
        """
        Custom save method to generate slug and update related data.
        
        Automatically creates URL-friendly slug and updates category
        product counts when product availability changes.
        """
        try:
            # Generate slug if not provided
            if not self.slug:
                from django.utils.text import slugify
                base_slug = slugify(self.name)
                slug = base_slug
                counter = 1
                
                while AsdaProduct.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                
                self.slug = slug
            
            # Check if this is an update and availability changed
            old_availability = None
            if self.pk:
                try:
                    old_instance = AsdaProduct.objects.get(pk=self.pk)
                    old_availability = old_instance.is_available
                    
                    # Increment scrape count if this is an update
                    if not kwargs.get('force_insert', False):
                        self.times_scraped = old_instance.times_scraped + 1
                        
                except AsdaProduct.DoesNotExist:
                    pass
            
            super().save(*args, **kwargs)
            
            # Update category product count if availability changed
            if old_availability is not None and old_availability != self.is_available:
                self.category.update_product_count()
            
            logger.info(f"Saved Asda product: {self.name} (£{self.price or 'N/A'})")
            
        except Exception as e:
            logger.error(f"Error saving AsdaProduct {self.name}: {str(e)}")
            raise
    
    def get_price_display(self) -> str:
        """
        Get formatted price for display.
        
        Returns:
            str: Formatted price string
        """
        if self.price:
            return f"£{self.price:.2f}"
        elif self.price_text:
            return self.price_text
        else:
            return "Price not available"
    
    def get_savings_display(self) -> str:
        """
        Get savings amount if product is on offer.
        
        Returns:
            str: Formatted savings string or empty string
        """
        if self.is_on_offer and self.original_price and self.price:
            savings = self.original_price - self.price
            if savings > 0:
                return f"Save £{savings:.2f}"
        return ""
    
    def is_price_current(self, hours: int = 24) -> bool:
        """
        Check if price data is current within specified hours.
        
        Args:
            hours: Maximum age in hours for price to be considered current
            
        Returns:
            bool: True if price is current, False otherwise
        """
        if not self.last_scraped:
            return False
        
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.last_scraped >= cutoff
    
    def get_nutrition_value(self, nutrient: str) -> str:
        """
        Get specific nutritional value from stored data.
        
        Args:
            nutrient: Name of nutrient to retrieve
            
        Returns:
            str: Nutrient value or empty string if not found
        """
        if self.nutritional_info and isinstance(self.nutritional_info, dict):
            return str(self.nutritional_info.get(nutrient, ''))
        return ''


class AsdaPriceHistory(models.Model):
    """
    Tracks historical price changes for Asda products.
    
    Maintains a record of price changes over time to enable
    price trend analysis and deal identification.
    """
    
    product = models.ForeignKey(
        AsdaProduct,
        on_delete=models.CASCADE,
        related_name='price_history',
        help_text="Product this price record belongs to"
    )
    
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Price at this point in time"
    )
    
    price_text = models.CharField(
        max_length=50,
        blank=True,
        help_text="Raw price text as scraped"
    )
    
    is_on_offer = models.BooleanField(
        default=False,
        help_text="Whether this was an offer price"
    )
    
    offer_text = models.CharField(
        max_length=200,
        blank=True,
        help_text="Offer description if applicable"
    )
    
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this price was recorded"
    )
    
    class Meta:
        """Meta configuration for AsdaPriceHistory model."""
        
        verbose_name = "Asda Price History"
        verbose_name_plural = "Asda Price Histories"
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['product', '-recorded_at']),
            models.Index(fields=['price', 'recorded_at']),
            models.Index(fields=['is_on_offer', 'recorded_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(price__gt=0),
                name='history_price_positive'
            )
        ]
    
    def __str__(self) -> str:
        """String representation of price history entry."""
        return f"{self.product.name} - £{self.price} on {self.recorded_at.date()}"
    
    @classmethod
    def record_price_change(cls, product: AsdaProduct) -> 'AsdaPriceHistory':
        """
        Record a price change for a product.
        
        Args:
            product: AsdaProduct instance to record price for
            
        Returns:
            AsdaPriceHistory: Created price history record
        """
        try:
            if not product.price:
                raise ValueError("Product must have a price to record")
            
            # Check if price has actually changed
            latest_history = cls.objects.filter(product=product).first()
            if latest_history and latest_history.price == product.price:
                logger.debug(f"No price change for {product.name}, skipping history record")
                return latest_history
            
            history = cls.objects.create(
                product=product,
                price=product.price,
                price_text=product.price_text,
                is_on_offer=product.is_on_offer,
                offer_text=product.offer_text
            )
            
            logger.info(f"Recorded price history for {product.name}: £{product.price}")
            return history
            
        except Exception as e:
            logger.error(f"Error recording price history for {product.name}: {str(e)}")
            raise


# Add these fields to your existing User model or create a profile model
class UserAsdaPreferences(models.Model):
    """
    User preferences for Asda product filtering and notifications.
    
    Stores user-specific settings for product searches,
    price alerts, and shopping preferences.
    """
    
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='asda_preferences',
        help_text="User these preferences belong to"
    )
    
    preferred_categories = models.ManyToManyField(
        AsdaCategory,
        blank=True,
        help_text="Categories user is most interested in"
    )
    
    price_alert_threshold = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text="Maximum price for automatic price alerts"
    )
    
    enable_price_alerts = models.BooleanField(
        default=True,
        help_text="Whether to send price drop notifications"
    )
    
    preferred_brands = models.TextField(
        blank=True,
        help_text="Comma-separated list of preferred brands"
    )
    
    dietary_restrictions = models.CharField(
        max_length=500,
        blank=True,
        help_text="Dietary restrictions or allergen avoidance"
    )
    
    max_budget_per_item = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Maximum budget per item for recommendations"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When preferences were created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When preferences were last updated"
    )
    
    class Meta:
        """Meta configuration for UserAsdaPreferences model."""
        
        verbose_name = "User Asda Preferences"
        verbose_name_plural = "User Asda Preferences"
    
    def __str__(self) -> str:
        """String representation of user preferences."""
        return f"Asda preferences for {self.user.username}"
    
    def get_preferred_brand_list(self) -> list:
        """
        Get list of preferred brands.
        
        Returns:
            List[str]: List of brand names
        """
        if self.preferred_brands:
            return [brand.strip() for brand in self.preferred_brands.split(',') if brand.strip()]
        return []