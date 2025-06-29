"""
ASDA Scraper Models

This module contains models for storing scraped ASDA product data,
categories, and crawl session information.
"""

import logging
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

logger = logging.getLogger(__name__)


class AsdaCategory(models.Model):
    """
    Model for ASDA product categories discovered during scraping.
    
    Attributes:
        name: Display name of the category (e.g., 'Fruit, Veg & Flowers')
        url_code: The numeric code used in ASDA URLs for this category
        parent_category: Optional parent category for hierarchical structure
        is_active: Whether this category should be crawled
        last_crawled: When this category was last scraped
        product_count: Number of products found in this category
    """
    name = models.CharField(
        max_length=255,
        help_text="Display name of the category"
    )
    url_code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Numeric code used in ASDA URLs"
    )
    parent_category = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text="Parent category if this is a subcategory"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category should be included in scraping"
    )
    last_crawled = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this category was scraped"
    )
    product_count = models.IntegerField(
        default=0,
        help_text="Number of products found in this category"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "ASDA Category"
        verbose_name_plural = "ASDA Categories"
        ordering = ['name']
    
    def __str__(self):
        """String representation of the category."""
        if self.parent_category:
            return f"{self.parent_category.name} > {self.name}"
        return self.name
    
    def get_full_path(self):
        """Get the full category path from root to this category."""
        path = [self.name]
        parent = self.parent_category
        while parent:
            path.append(parent.name)
            parent = parent.parent_category
        return ' > '.join(reversed(path))
    
    def save(self, *args, **kwargs):
        """Override save to log category changes."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            logger.info(f"New ASDA category created: {self.name} (URL code: {self.url_code})")
        else:
            logger.info(f"ASDA category updated: {self.name}")


class AsdaProduct(models.Model):
    """
    Model for storing individual ASDA product information.
    
    Enhanced with additional fields for comprehensive product data including
    ratings, sale prices, and detailed pricing information.
    
    Attributes:
        name: Product name
        price: Current price in pounds
        was_price: Original price if item is on sale
        unit: Unit of measurement (e.g., 'each', 'kg', '100g')
        price_per_unit: Price per unit string (e.g., '£6.83/kg')
        description: Product description
        image_url: URL to product image
        product_url: Direct URL to product page
        asda_id: ASDA's internal product ID
        category: Category this product belongs to
        in_stock: Whether product is currently in stock
        special_offer: Any special offer text
        rating: Product rating out of 5
        review_count: Number of reviews (e.g., '50+')
        nutritional_info: JSON field for nutritional information
    """
    name = models.CharField(
        max_length=500,
        help_text="Product name as shown on ASDA website"
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Current price in pounds"
    )
    was_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Original price if item is on sale"
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Unit of measurement (e.g., 'each', 'kg', '100g')"
    )
    price_per_unit = models.CharField(
        max_length=100,
        blank=True,
        help_text="Price per unit string (e.g., '£6.83/kg')"
    )
    description = models.TextField(
        blank=True,
        help_text="Product description"
    )
    image_url = models.URLField(
        blank=True,
        help_text="URL to product image"
    )
    product_url = models.URLField(
        unique=True,
        help_text="Direct URL to product page on ASDA"
    )
    asda_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ASDA's internal product ID"
    )
    category = models.ForeignKey(
        AsdaCategory,
        on_delete=models.CASCADE,
        related_name='products',
        help_text="Category this product belongs to"
    )
    in_stock = models.BooleanField(
        default=True,
        help_text="Whether product is currently available"
    )
    special_offer = models.CharField(
        max_length=200,
        blank=True,
        help_text="Any special offer or promotion text (e.g., 'Rollback')"
    )
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Product rating out of 5 stars"
    )
    review_count = models.CharField(
        max_length=20,
        blank=True,
        help_text="Number of reviews (e.g., '50+', '127')"
    )
    nutritional_info = models.JSONField(
        default=dict,
        blank=True,
        help_text="Nutritional information if available"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "ASDA Product"
        verbose_name_plural = "ASDA Products"
        ordering = ['name']
        indexes = [
            models.Index(fields=['asda_id']),
            models.Index(fields=['category', 'name']),
            models.Index(fields=['price']),
            models.Index(fields=['rating']),
            models.Index(fields=['was_price']),
            models.Index(fields=['special_offer']),
        ]
    
    def __str__(self):
        """String representation of the product."""
        if self.was_price and self.was_price > self.price:
            return f"{self.name} - £{self.price} (was £{self.was_price})"
        return f"{self.name} - £{self.price}"
    
    def get_price_per_unit(self):
        """Calculate price per standard unit if possible."""
        if self.unit and 'kg' in self.unit.lower():
            return self.price
        elif self.unit and 'g' in self.unit.lower():
            # Convert to price per kg
            try:
                grams = float(''.join(filter(str.isdigit, self.unit)))
                return (self.price / grams) * 1000
            except (ValueError, ZeroDivisionError):
                return None
        return None
    
    def get_savings(self):
        """Calculate savings if item is on sale."""
        if self.was_price and self.was_price > self.price:
            return self.was_price - self.price
        return None
    
    def get_savings_percentage(self):
        """Calculate savings percentage if item is on sale."""
        savings = self.get_savings()
        if savings and self.was_price:
            return round((savings / self.was_price) * 100, 1)
        return None
    
    def is_on_sale(self):
        """Check if product is currently on sale."""
        return bool(self.was_price and self.was_price > self.price)
    
    def get_rating_display(self):
        """Get formatted rating display."""
        if self.rating:
            stars = "★" * int(self.rating) + "☆" * (5 - int(self.rating))
            review_text = f" ({self.review_count} reviews)" if self.review_count else ""
            return f"{self.rating}/5 {stars}{review_text}"
        return "No rating"
    
    def save(self, *args, **kwargs):
        """Override save to log product changes and update category count."""
        is_new = self.pk is None
        
        # Log price changes for existing products
        if not is_new:
            try:
                old_product = AsdaProduct.objects.get(pk=self.pk)
                if old_product.price != self.price:
                    logger.info(
                        f"Price change for {self.name}: £{old_product.price} → £{self.price}"
                    )
            except AsdaProduct.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        if is_new:
            # Update category product count
            self.category.product_count = self.category.products.count()
            self.category.save(update_fields=['product_count'])
            logger.info(f"New ASDA product added: {self.name} - £{self.price}")
        else:
            logger.info(f"ASDA product updated: {self.name}")


class CrawlSession(models.Model):
    """
    Model for tracking individual crawl sessions.
    
    Attributes:
        user: User who started the crawl
        status: Current status of the crawl
        start_time: When the crawl started
        end_time: When the crawl finished
        categories_crawled: Number of categories processed
        products_found: Number of products discovered
        products_updated: Number of existing products updated
        error_log: Any errors encountered during crawling
        crawl_settings: JSON field for crawl configuration
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='crawl_sessions'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    categories_crawled = models.IntegerField(default=0)
    products_found = models.IntegerField(default=0)
    products_updated = models.IntegerField(default=0)
    error_log = models.TextField(
        blank=True,
        help_text="Any errors encountered during crawling"
    )
    crawl_settings = models.JSONField(
        default=dict,
        help_text="Configuration used for this crawl session"
    )
    
    class Meta:
        verbose_name = "Crawl Session"
        verbose_name_plural = "Crawl Sessions"
        ordering = ['-start_time']
    
    def __str__(self):
        """String representation of the crawl session."""
        duration = ""
        if self.end_time:
            duration = f" ({(self.end_time - self.start_time).seconds}s)"
        return f"Crawl {self.pk} - {self.status}{duration}"
    
    def get_duration(self):
        """Get the duration of the crawl session."""
        if self.end_time:
            return self.end_time - self.start_time
        elif self.status == 'RUNNING':
            return timezone.now() - self.start_time
        return None
    
    def get_products_per_minute(self):
        """Calculate products processed per minute."""
        duration = self.get_duration()
        if duration and duration.total_seconds() > 0:
            total_products = self.products_found + self.products_updated
            minutes = duration.total_seconds() / 60
            return round(total_products / minutes, 2)
        return 0
    
    def mark_completed(self):
        """Mark the crawl session as completed."""
        self.status = 'COMPLETED'
        self.end_time = timezone.now()
        self.save(update_fields=['status', 'end_time'])
        logger.info(
            f"Crawl session {self.pk} completed. "
            f"Products found: {self.products_found}, "
            f"Products updated: {self.products_updated}, "
            f"Rate: {self.get_products_per_minute()} products/min"
        )
    
    def mark_failed(self, error_message):
        """Mark the crawl session as failed with error message."""
        self.status = 'FAILED'
        self.end_time = timezone.now()
        self.error_log = error_message
        self.save(update_fields=['status', 'end_time', 'error_log'])
        logger.error(f"Crawl session {self.pk} failed: {error_message}")