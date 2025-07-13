"""
Models for ASDA product scraping.

Stores product information, prices, nutrition data, and crawl metadata.
"""

import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class Category(models.Model):
    """
    Represents ASDA product categories and subcategories.

    Stores the hierarchical category structure from ASDA's website.
    """

    name = models.CharField(max_length=255, db_index=True)
    url = models.URLField(unique=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    level = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Category model."""
        verbose_name_plural = "Categories"
        ordering = ['level', 'name']
        indexes = [
            models.Index(fields=['level', 'is_active']),
        ]

    def __str__(self):
        """String representation of category."""
        return f"{self.name} (Level {self.level})"


class Product(models.Model):
    """
    Represents an ASDA product with price and basic information.

    Stores core product data scraped from product listings.
    """

    # Basic Information
    asda_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=500)
    brand = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    # URLs
    url = models.URLField(unique=True)
    image_url = models.URLField(blank=True, null=True)

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    price_per_unit = models.CharField(max_length=100, blank=True, null=True)
    on_offer = models.BooleanField(default=False)
    offer_text = models.CharField(max_length=255, blank=True, null=True)

    # Categories
    categories = models.ManyToManyField(Category, related_name='products')

    # Status
    is_available = models.BooleanField(default=True)
    last_scraped = models.DateTimeField(null=True, blank=True)
    nutrition_scraped = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Product model."""
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['asda_id', 'is_available']),
            models.Index(fields=['nutrition_scraped', 'is_available']),
        ]

    def __str__(self):
        """String representation of product."""
        return f"{self.name} - £{self.price}"


class NutritionInfo(models.Model):
    """
    Stores detailed nutrition information for products.

    Linked to Product model, stores data from product detail pages.
    """

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='nutrition'
    )

    # Per 100g/100ml values
    energy_kj = models.IntegerField(null=True, blank=True)
    energy_kcal = models.IntegerField(null=True, blank=True)
    fat = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    saturated_fat = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    carbohydrates = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    sugars = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    fibre = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    protein = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    salt = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Additional nutrition data as JSON
    other_nutrients = models.JSONField(default=dict, blank=True)

    # Serving information
    serving_size = models.CharField(max_length=100, blank=True, null=True)
    servings_per_pack = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True
    )

    # Raw nutrition text (for debugging)
    raw_nutrition_text = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for NutritionInfo model."""
        verbose_name_plural = "Nutrition Information"

    def __str__(self):
        """String representation of nutrition info."""
        return f"Nutrition for {self.product.name}"


class CrawlSession(models.Model):
    """
    Tracks crawler sessions for monitoring and debugging.

    Records statistics and status of each crawl operation.
    """

    CRAWLER_CHOICES = [
        ('CATEGORY', 'Category Mapper'),
        ('PRODUCT_LIST', 'Product List Crawler'),
        ('PRODUCT_DETAIL', 'Product Detail Crawler'),
    ]

    STATUS_CHOICES = [
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('STOPPED', 'Stopped'),
    ]

    # Session Information
    crawler_type = models.CharField(max_length=20, choices=CRAWLER_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='RUNNING'
    )

    # Statistics
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    failed_items = models.IntegerField(default=0)

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_log = models.TextField(blank=True, null=True)

    class Meta:
        """Meta options for CrawlSession model."""
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['crawler_type', 'status']),
        ]

    def __str__(self):
        """String representation of crawl session."""
        return (
            f"{self.get_crawler_type_display()} - "
            f"{self.started_at.strftime('%Y-%m-%d %H:%M')}"
        )

    @property
    def duration(self):
        """Calculate session duration."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return timezone.now() - self.started_at

    @property
    def success_rate(self):
        """Calculate success rate percentage."""
        if self.processed_items == 0:
            return 0
        return (
            (self.processed_items - self.failed_items) /
            self.processed_items
        ) * 100


class CrawledURL(models.Model):
    """
    Tracks URLs that have been crawled to prevent duplicates.

    Helps manage crawl state and avoid re-crawling same URLs.
    """

    url = models.URLField(unique=True, db_index=True)
    url_hash = models.CharField(max_length=64, unique=True, db_index=True)
    crawler_type = models.CharField(
        max_length=20,
        choices=CrawlSession.CRAWLER_CHOICES
    )
    last_crawled = models.DateTimeField(auto_now=True)
    times_crawled = models.IntegerField(default=1)

    class Meta:
        """Meta options for CrawledURL model."""
        indexes = [
            models.Index(fields=['crawler_type', 'last_crawled']),
        ]

    def __str__(self):
        """String representation of crawled URL."""
        return f"{self.url} (crawled {self.times_crawled} times)"


class CrawlQueue(models.Model):
    """
    Queue system for managing URLs to be crawled.

    Supports different queue types and priority-based processing.
    """

    QUEUE_TYPE_CHOICES = [
        ('CATEGORY', 'Category URL'),
        ('PRODUCT_LIST', 'Product List URL'),
        ('PRODUCT_DETAIL', 'Product Detail URL'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    # URL Information
    url = models.URLField(db_index=True)
    url_hash = models.CharField(max_length=64, db_index=True)
    queue_type = models.CharField(
        max_length=20,
        choices=QUEUE_TYPE_CHOICES,
        db_index=True
    )

    # Processing Information
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    priority = models.IntegerField(default=0, db_index=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)

    # Related Data
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='queue_items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='queue_items'
    )

    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Meta options for CrawlQueue model."""
        ordering = ['-priority', 'created_at']
        indexes = [
            models.Index(fields=['queue_type', 'status', '-priority']),
            models.Index(fields=['url_hash', 'queue_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['url_hash', 'queue_type'],
                name='unique_url_per_queue_type'
            )
        ]

    def __str__(self):
        """String representation of queue item."""
        return f"{self.get_queue_type_display()} - {self.url[:50]}"

    def save(self, *args, **kwargs):
        """Override save to generate URL hash."""
        if not self.url_hash:
            import hashlib
            self.url_hash = hashlib.sha256(
                self.url.encode('utf-8')
            ).hexdigest()
        super().save(*args, **kwargs)