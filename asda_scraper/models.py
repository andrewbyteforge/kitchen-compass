"""
ASDA Scraper Models

This module contains models for storing scraped ASDA product data,
categories, crawl session information, and enhanced link mapping capabilities.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    Model for tracking individual crawl sessions with enhanced link mapping support.
    
    Attributes:
        user: User who started the crawl
        session_id: Unique identifier for this crawl session
        start_url: Starting URL for the crawl
        status: Current status of the crawl
        max_depth: Maximum crawling depth
        delay_seconds: Delay between requests in seconds
        user_agent: User agent string for requests
        start_time: When the crawl started
        end_time: When the crawl finished
        categories_crawled: Number of categories processed
        products_found: Number of products discovered
        products_updated: Number of existing products updated
        urls_discovered: Total number of URLs discovered
        urls_crawled: Number of URLs successfully crawled
        errors_count: Number of errors encountered
        error_log: Any errors encountered during crawling
        crawl_settings: JSON field for crawl configuration
        notes: Additional notes about this crawl session
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('PAUSED', 'Paused'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='crawl_sessions'
    )
    session_id = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        help_text="Unique identifier for this crawl session"
    )
    start_url = models.URLField(
        default="https://groceries.asda.com/",
        help_text="Starting URL for the crawl"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    max_depth = models.PositiveIntegerField(
        default=3,
        help_text="Maximum crawling depth"
    )
    delay_seconds = models.FloatField(
        default=2.0,
        help_text="Delay between requests in seconds"
    )
    user_agent = models.TextField(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        help_text="User agent string for requests"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    categories_crawled = models.IntegerField(default=0)
    products_found = models.IntegerField(default=0)
    products_updated = models.IntegerField(default=0)
    urls_discovered = models.PositiveIntegerField(
        default=0,
        help_text="Total number of URLs discovered"
    )
    urls_crawled = models.PositiveIntegerField(
        default=0,
        help_text="Number of URLs successfully crawled"
    )
    errors_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of errors encountered"
    )
    error_log = models.TextField(
        blank=True,
        help_text="Any errors encountered during crawling"
    )
    crawl_settings = models.JSONField(
        default=dict,
        help_text="Configuration used for this crawl session"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this crawl session"
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
        return f"Crawl {self.session_id or self.pk} - {self.status}{duration}"
    
    def save(self, *args, **kwargs):
        """Save with automatic session ID generation."""
        if not self.session_id:
            # Generate session ID based on timestamp
            self.session_id = f"asda_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Saving crawl session: {self.session_id}")
        super().save(*args, **kwargs)
    
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
    
    def get_progress_percentage(self):
        """Calculate crawling progress as percentage."""
        if self.urls_discovered == 0:
            return 0
        return min(100, (self.urls_crawled / self.urls_discovered) * 100)
    
    def mark_completed(self):
        """Mark the crawl session as completed."""
        self.status = 'COMPLETED'
        self.end_time = timezone.now()
        self.save(update_fields=['status', 'end_time'])
        logger.info(
            f"Crawl session {self.session_id} completed. "
            f"Products found: {self.products_found}, "
            f"Products updated: {self.products_updated}, "
            f"URLs crawled: {self.urls_crawled}, "
            f"Rate: {self.get_products_per_minute()} products/min"
        )
    
    def mark_failed(self, error_message):
        """Mark the crawl session as failed with error message."""
        self.status = 'FAILED'
        self.end_time = timezone.now()
        if error_message:
            self.error_log = f"{self.error_log}\n{error_message}" if self.error_log else error_message
        self.save(update_fields=['status', 'end_time', 'error_log'])
        logger.error(f"Crawl session {self.session_id} failed: {error_message}")
    
    # Enhanced methods for link mapping
    def get_discovered_urls_count(self):
        """Get count of discovered URLs in this session."""
        return self.discovered_urls.count()

    def get_crawled_urls_count(self):
        """Get count of successfully crawled URLs."""
        return self.discovered_urls.filter(status='completed').count()

    def get_pending_urls_count(self):
        """Get count of URLs waiting to be crawled."""
        return self.discovered_urls.filter(
            status__in=['discovered', 'queued']
        ).count()

    def get_failed_urls_count(self):
        """Get count of URLs that failed to crawl."""
        return self.discovered_urls.filter(status='failed').count()

    def get_next_urls_to_crawl(self, limit=10):
        """Get the next URLs that should be crawled."""
        return self.crawl_queue.filter(
            scheduled_time__lte=timezone.now()
        ).select_related('url_map').order_by('-priority', 'scheduled_time')[:limit]

    def add_url_to_queue(self, url, parent_url=None, priority=None):
        """Add a new URL to the crawling queue."""
        # Import here to avoid circular imports
        from .models import UrlMap, CrawlQueue
        
        # Create or get URL map entry
        url_hash = UrlMap.generate_url_hash(url)
        url_map, created = UrlMap.objects.get_or_create(
            crawl_session=self,
            url_hash=url_hash,
            defaults={
                'url': url,
                'normalized_url': UrlMap.normalize_url(url),
                'parent_url': parent_url,
                'depth': (parent_url.depth + 1) if parent_url else 0,
            }
        )
        
        if created:
            # Add to crawl queue
            if priority is None:
                priority = url_map.priority
            
            CrawlQueue.objects.get_or_create(
                crawl_session=self,
                url_map=url_map,
                defaults={
                    'priority': priority,
                    'scheduled_time': timezone.now()
                }
            )
            
            logger.info(f"Added URL to queue: {url}")
            return url_map, True
        else:
            logger.debug(f"URL already discovered: {url}")
            return url_map, False

    def update_statistics(self):
        """Update crawl session statistics."""
        urls_discovered = self.get_discovered_urls_count()
        urls_crawled = self.get_crawled_urls_count()
        products_found = sum(
            url.products_found for url in 
            self.discovered_urls.filter(products_found__gt=0)
        )
        
        self.urls_discovered = urls_discovered
        self.urls_crawled = urls_crawled
        self.products_found = products_found
        
        self.save(update_fields=['urls_discovered', 'urls_crawled', 'products_found'])


class UrlMap(models.Model):
    """
    Tracks all discovered URLs and their relationships during crawling.
    
    This model creates a comprehensive map of all URLs discovered during
    the crawling process, including their parent-child relationships,
    crawling status, and extracted metadata.
    """
    
    STATUS_CHOICES = [
        ('discovered', 'Discovered'),
        ('queued', 'Queued for Processing'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('duplicate', 'Duplicate'),
        ('blocked', 'Blocked/Forbidden'),
    ]
    
    URL_TYPE_CHOICES = [
        ('unknown', 'Unknown'),
        ('homepage', 'Homepage'),
        ('category_main', 'Main Category Page'),
        ('category_sub', 'Sub-Category Page'),
        ('product_list', 'Product Listing Page'),
        ('product_detail', 'Product Detail Page'),
        ('search_results', 'Search Results'),
        ('pagination', 'Pagination Page'),
        ('filter_results', 'Filtered Results'),
        ('other', 'Other Page'),
    ]
    
    crawl_session = models.ForeignKey(
        CrawlSession,
        on_delete=models.CASCADE,
        related_name='discovered_urls',
        help_text="The crawl session that discovered this URL"
    )
    url = models.URLField(
        max_length=2000,
        help_text="The complete URL"
    )
    url_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA256 hash of the URL for fast duplicate detection"
    )
    normalized_url = models.URLField(
        max_length=2000,
        help_text="Normalized version of URL for deduplication"
    )
    parent_url = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_urls',
        help_text="The URL that discovered this URL"
    )
    depth = models.PositiveIntegerField(
        default=0,
        help_text="Crawling depth (0 = starting URL)"
    )
    url_type = models.CharField(
        max_length=20,
        choices=URL_TYPE_CHOICES,
        default='unknown',
        help_text="Type of content this URL contains"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='discovered',
        db_index=True,
        help_text="Current processing status"
    )
    priority = models.IntegerField(
        default=0,
        help_text="Crawling priority (higher = more important)"
    )
    discovered_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this URL was first discovered"
    )
    last_crawled = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this URL was last crawled"
    )
    next_crawl = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this URL should be crawled next"
    )
    crawl_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times this URL has been crawled"
    )
    response_code = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Last HTTP response code"
    )
    response_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Response time in seconds"
    )
    content_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Content length in bytes"
    )
    content_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Content type from response headers"
    )
    page_title = models.CharField(
        max_length=500,
        blank=True,
        help_text="Page title if available"
    )
    meta_description = models.TextField(
        blank=True,
        help_text="Meta description if available"
    )
    links_found = models.PositiveIntegerField(
        default=0,
        help_text="Number of links discovered on this page"
    )
    products_found = models.PositiveIntegerField(
        default=0,
        help_text="Number of products found on this page"
    )
    categories_found = models.PositiveIntegerField(
        default=0,
        help_text="Number of categories found on this page"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if crawling failed"
    )
    robots_txt_allowed = models.BooleanField(
        default=True,
        help_text="Whether robots.txt allows crawling this URL"
    )
    last_modified = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last-Modified header from response"
    )
    etag = models.CharField(
        max_length=100,
        blank=True,
        help_text="ETag header from response"
    )
    
    class Meta:
        db_table = 'asda_scraper_url_map'
        verbose_name = 'URL Map'
        verbose_name_plural = 'URL Maps'
        unique_together = ['crawl_session', 'url_hash']
        indexes = [
            models.Index(fields=['crawl_session', 'status']),
            models.Index(fields=['crawl_session', 'url_type']),
            models.Index(fields=['priority', 'discovered_at']),
            models.Index(fields=['last_crawled']),
            models.Index(fields=['next_crawl']),
            models.Index(fields=['depth']),
        ]
        ordering = ['-priority', 'discovered_at']
    
    def __str__(self):
        return f"[{self.get_url_type_display()}] {self.url[:80]}..."
    
    @classmethod
    def normalize_url(cls, url):
        """
        Normalize URL for deduplication.
        
        Removes unnecessary parameters, fragments, and standardizes format.
        """
        try:
            parsed = urlparse(url.lower().strip())
            
            # Remove fragment
            parsed = parsed._replace(fragment='')
            
            # Sort query parameters and remove tracking parameters
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=False)
                
                # Remove common tracking parameters
                tracking_params = {
                    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term',
                    'utm_content', 'gclid', 'fbclid', '_ga', 'sessionid'
                }
                
                filtered_params = {
                    k: v for k, v in params.items() 
                    if k.lower() not in tracking_params
                }
                
                # Sort parameters for consistency
                if filtered_params:
                    sorted_params = sorted(filtered_params.items())
                    query = urlencode(sorted_params, doseq=True)
                    parsed = parsed._replace(query=query)
                else:
                    parsed = parsed._replace(query='')
            
            # Remove trailing slash from path unless it's the root
            if parsed.path != '/' and parsed.path.endswith('/'):
                parsed = parsed._replace(path=parsed.path.rstrip('/'))
            
            return urlunparse(parsed)
            
        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return url.lower().strip()
    
    @classmethod
    def generate_url_hash(cls, url):
        """Generate SHA256 hash for a URL."""
        normalized = cls.normalize_url(url)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    @classmethod
    def classify_url_type(cls, url):
        """
        Automatically classify URL type based on URL pattern.
        
        Args:
            url: The URL to classify
            
        Returns:
            URL type classification
        """
        url_lower = url.lower()
        
        if url_lower == 'https://groceries.asda.com/':
            return 'homepage'
        elif '/dept/' in url_lower:
            # Check if it's a main department or sub-category
            path_parts = urlparse(url_lower).path.split('/')
            if path_parts.count('dept') == 1:
                return 'category_main'
            else:
                return 'category_sub'
        elif '/product/' in url_lower:
            return 'product_detail'
        elif '/search' in url_lower or 'q=' in url_lower:
            return 'search_results'
        elif 'page=' in url_lower or 'offset=' in url_lower:
            return 'pagination'
        elif any(filter_param in url_lower for filter_param in ['filter', 'sort', 'brand']):
            return 'filter_results'
        elif '/shelf/' in url_lower or '/category/' in url_lower:
            return 'product_list'
        else:
            return 'unknown'
    
    @classmethod
    def calculate_priority(cls, url, url_type, depth):
        """
        Calculate crawling priority for a URL.
        
        Args:
            url: The URL to prioritize
            url_type: Type of the URL
            depth: Crawling depth
            
        Returns:
            Priority score (higher = more important)
        """
        base_priority = {
            'homepage': 100,
            'category_main': 90,
            'category_sub': 80,
            'product_list': 70,
            'product_detail': 60,
            'pagination': 50,
            'filter_results': 40,
            'search_results': 30,
            'unknown': 20,
            'other': 10,
        }.get(url_type, 10)
        
        # Reduce priority based on depth
        depth_penalty = depth * 5
        
        # Boost priority for certain keywords
        url_lower = url.lower()
        if any(keyword in url_lower for keyword in ['fresh', 'meat', 'dairy', 'bakery']):
            base_priority += 10
        
        return max(0, base_priority - depth_penalty)
    
    def save(self, *args, **kwargs):
        """Save with automatic hash and normalization."""
        if not self.url_hash:
            self.url_hash = self.generate_url_hash(self.url)
        
        if not self.normalized_url:
            self.normalized_url = self.normalize_url(self.url)
        
        if self.url_type == 'unknown':
            self.url_type = self.classify_url_type(self.url)
        
        if self.priority == 0:
            self.priority = self.calculate_priority(self.url, self.url_type, self.depth)
        
        logger.debug(f"Saving URL map: {self.url} (Type: {self.url_type}, Priority: {self.priority})")
        super().save(*args, **kwargs)
    
    def mark_as_crawled(self, response_code=200, response_time=None, content_length=None, 
                       content_type="", error_message="", links_found=0, products_found=0, 
                       categories_found=0, page_title="", meta_description=""):
        """
        Mark this URL as crawled with comprehensive results.
        """
        self.status = 'completed' if response_code == 200 else 'failed'
        self.last_crawled = timezone.now()
        self.crawl_count += 1
        self.response_code = response_code
        self.response_time = response_time
        self.content_length = content_length
        self.content_type = content_type
        self.error_message = error_message
        self.links_found = links_found
        self.products_found = products_found
        self.categories_found = categories_found
        self.page_title = page_title
        self.meta_description = meta_description
        
        # Set next crawl time based on URL type and success
        if response_code == 200:
            if self.url_type in ['product_list', 'category_main', 'category_sub']:
                # Recrawl important pages more frequently
                self.next_crawl = timezone.now() + timedelta(hours=24)
            elif self.url_type == 'product_detail':
                # Product pages less frequently
                self.next_crawl = timezone.now() + timedelta(days=3)
            else:
                # Other pages weekly
                self.next_crawl = timezone.now() + timedelta(days=7)
        
        self.save(update_fields=[
            'status', 'last_crawled', 'crawl_count', 'response_code', 
            'response_time', 'content_length', 'content_type', 'error_message',
            'links_found', 'products_found', 'categories_found', 'page_title',
            'meta_description', 'next_crawl'
        ])
        
        logger.info(f"URL crawled: {self.url} (Status: {response_code}, Links: {links_found}, Products: {products_found})")
    
    def is_stale(self, hours=24):
        """Check if this URL needs to be re-crawled."""
        if not self.last_crawled:
            return True
        if self.next_crawl and timezone.now() >= self.next_crawl:
            return True
        return timezone.now() - self.last_crawled > timedelta(hours=hours)
    
    def should_crawl(self):
        """Determine if this URL should be crawled now."""
        if self.status in ['discovered', 'queued']:
            return True
        if self.status == 'failed' and self.crawl_count < 3:
            return True
        if self.status == 'completed' and self.is_stale():
            return True
        return False
    
    def get_crawl_delay(self):
        """Get appropriate delay before crawling this URL."""
        base_delay = 1.0  # Base delay in seconds
        
        # Increase delay for failed URLs
        if self.status == 'failed':
            base_delay *= (2 ** min(self.crawl_count, 5))
        
        # Different delays for different URL types
        type_delays = {
            'product_detail': 0.5,
            'product_list': 1.0,
            'category_main': 1.5,
            'category_sub': 1.0,
            'pagination': 0.8,
        }
        
        return base_delay * type_delays.get(self.url_type, 1.0)


class LinkRelationship(models.Model):
    """
    Tracks specific link relationships between pages.
    
    This model stores information about how URLs link to each other,
    including the anchor text, link position, and context.
    """
    
    LINK_TYPE_CHOICES = [
        ('navigation', 'Navigation Link'),
        ('category', 'Category Link'),
        ('product', 'Product Link'),
        ('pagination', 'Pagination Link'),
        ('breadcrumb', 'Breadcrumb Link'),
        ('related', 'Related Link'),
        ('other', 'Other Link'),
    ]
    
    from_url = models.ForeignKey(
        UrlMap,
        on_delete=models.CASCADE,
        related_name='outbound_links',
        help_text="The page containing the link"
    )
    to_url = models.ForeignKey(
        UrlMap,
        on_delete=models.CASCADE,
        related_name='inbound_links',
        help_text="The page the link points to"
    )
    anchor_text = models.CharField(
        max_length=500,
        blank=True,
        help_text="The anchor text of the link"
    )
    link_type = models.CharField(
        max_length=20,
        choices=LINK_TYPE_CHOICES,
        default='other',
        help_text="Type of link relationship"
    )
    css_selector = models.CharField(
        max_length=200,
        blank=True,
        help_text="CSS selector where the link was found"
    )
    position_on_page = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Position of link on the page (1st, 2nd, etc.)"
    )
    first_seen = models.DateTimeField(
        auto_now_add=True,
        help_text="When this link relationship was first discovered"
    )
    last_seen = models.DateTimeField(
        auto_now=True,
        help_text="When this link was last seen on the page"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this link is still present on the page"
    )
    
    class Meta:
        db_table = 'asda_scraper_link_relationship'
        verbose_name = 'Link Relationship'
        verbose_name_plural = 'Link Relationships'
        unique_together = ['from_url', 'to_url', 'position_on_page']
        indexes = [
            models.Index(fields=['from_url', 'link_type']),
            models.Index(fields=['to_url', 'link_type']),
            models.Index(fields=['first_seen']),
        ]
    
    def __str__(self):
        return f"{self.from_url.url[:50]}... → {self.to_url.url[:50]}... ({self.anchor_text[:30]}...)"


class CrawlQueue(models.Model):
    """
    Queue system for managing URLs to be crawled.
    
    This model implements a priority queue for URLs that need to be crawled,
    with support for different crawling strategies and throttling.
    """
    
    crawl_session = models.ForeignKey(
        CrawlSession,
        on_delete=models.CASCADE,
        related_name='crawl_queue',
        help_text="The crawl session this queue item belongs to"
    )
    url_map = models.ForeignKey(
        UrlMap,
        on_delete=models.CASCADE,
        related_name='queue_entries',
        help_text="The URL to be crawled"
    )
    priority = models.IntegerField(
        default=0,
        help_text="Crawling priority (higher = sooner)"
    )
    scheduled_time = models.DateTimeField(
        help_text="When this URL should be crawled"
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of crawl attempts"
    )
    last_attempt = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last crawl attempt was made"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this queue entry was created"
    )
    
    class Meta:
        db_table = 'asda_scraper_crawl_queue'
        verbose_name = 'Crawl Queue Entry'
        verbose_name_plural = 'Crawl Queue Entries'
        unique_together = ['crawl_session', 'url_map']
        indexes = [
            models.Index(fields=['crawl_session', 'priority', 'scheduled_time']),
            models.Index(fields=['scheduled_time']),
        ]
        ordering = ['-priority', 'scheduled_time']
    
    def __str__(self):
        return f"Queue: {self.url_map.url[:80]}... (Priority: {self.priority})"
    
    def is_ready_to_crawl(self):
        """Check if this URL is ready to be crawled."""
        return timezone.now() >= self.scheduled_time
    
    def mark_attempt(self):
        """Mark a crawl attempt."""
        self.attempts += 1
        self.last_attempt = timezone.now()
        self.save(update_fields=['attempts', 'last_attempt'])
    
    def reschedule(self, delay_minutes=5):
        """Reschedule this URL for later crawling."""
        self.scheduled_time = timezone.now() + timedelta(minutes=delay_minutes)
        self.save(update_fields=['scheduled_time'])