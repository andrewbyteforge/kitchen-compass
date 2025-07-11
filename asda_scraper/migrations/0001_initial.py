# Generated by Django 4.2.23 on 2025-06-29 11:54

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AsdaCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Display name of the category", max_length=255
                    ),
                ),
                (
                    "url_code",
                    models.CharField(
                        help_text="Numeric code used in ASDA URLs",
                        max_length=50,
                        unique=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this category should be included in scraping",
                    ),
                ),
                (
                    "last_crawled",
                    models.DateTimeField(
                        blank=True,
                        help_text="Last time this category was scraped",
                        null=True,
                    ),
                ),
                (
                    "product_count",
                    models.IntegerField(
                        default=0, help_text="Number of products found in this category"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent_category",
                    models.ForeignKey(
                        blank=True,
                        help_text="Parent category if this is a subcategory",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subcategories",
                        to="asda_scraper.asdacategory",
                    ),
                ),
            ],
            options={
                "verbose_name": "ASDA Category",
                "verbose_name_plural": "ASDA Categories",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CrawlSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "session_id",
                    models.CharField(
                        blank=True,
                        help_text="Unique identifier for this crawl session",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "start_url",
                    models.URLField(
                        default="https://groceries.asda.com/",
                        help_text="Starting URL for the crawl",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("RUNNING", "Running"),
                            ("COMPLETED", "Completed"),
                            ("FAILED", "Failed"),
                            ("CANCELLED", "Cancelled"),
                            ("PAUSED", "Paused"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "max_depth",
                    models.PositiveIntegerField(
                        default=3, help_text="Maximum crawling depth"
                    ),
                ),
                (
                    "delay_seconds",
                    models.FloatField(
                        default=2.0, help_text="Delay between requests in seconds"
                    ),
                ),
                (
                    "user_agent",
                    models.TextField(
                        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        help_text="User agent string for requests",
                    ),
                ),
                ("start_time", models.DateTimeField(auto_now_add=True)),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                ("categories_crawled", models.IntegerField(default=0)),
                ("products_found", models.IntegerField(default=0)),
                ("products_updated", models.IntegerField(default=0)),
                (
                    "urls_discovered",
                    models.PositiveIntegerField(
                        default=0, help_text="Total number of URLs discovered"
                    ),
                ),
                (
                    "urls_crawled",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of URLs successfully crawled"
                    ),
                ),
                (
                    "errors_count",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of errors encountered"
                    ),
                ),
                (
                    "error_log",
                    models.TextField(
                        blank=True, help_text="Any errors encountered during crawling"
                    ),
                ),
                (
                    "crawl_settings",
                    models.JSONField(
                        default=dict,
                        help_text="Configuration used for this crawl session",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        help_text="Additional notes about this crawl session",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crawl_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Crawl Session",
                "verbose_name_plural": "Crawl Sessions",
                "ordering": ["-start_time"],
            },
        ),
        migrations.CreateModel(
            name="UrlMap",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("url", models.URLField(help_text="The complete URL", max_length=2000)),
                (
                    "url_hash",
                    models.CharField(
                        db_index=True,
                        help_text="SHA256 hash of the URL for fast duplicate detection",
                        max_length=64,
                    ),
                ),
                (
                    "normalized_url",
                    models.URLField(
                        help_text="Normalized version of URL for deduplication",
                        max_length=2000,
                    ),
                ),
                (
                    "depth",
                    models.PositiveIntegerField(
                        default=0, help_text="Crawling depth (0 = starting URL)"
                    ),
                ),
                (
                    "url_type",
                    models.CharField(
                        choices=[
                            ("unknown", "Unknown"),
                            ("homepage", "Homepage"),
                            ("category_main", "Main Category Page"),
                            ("category_sub", "Sub-Category Page"),
                            ("product_list", "Product Listing Page"),
                            ("product_detail", "Product Detail Page"),
                            ("search_results", "Search Results"),
                            ("pagination", "Pagination Page"),
                            ("filter_results", "Filtered Results"),
                            ("other", "Other Page"),
                        ],
                        default="unknown",
                        help_text="Type of content this URL contains",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("discovered", "Discovered"),
                            ("queued", "Queued for Processing"),
                            ("in_progress", "In Progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                            ("duplicate", "Duplicate"),
                            ("blocked", "Blocked/Forbidden"),
                        ],
                        db_index=True,
                        default="discovered",
                        help_text="Current processing status",
                        max_length=20,
                    ),
                ),
                (
                    "priority",
                    models.IntegerField(
                        default=0,
                        help_text="Crawling priority (higher = more important)",
                    ),
                ),
                (
                    "discovered_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this URL was first discovered",
                    ),
                ),
                (
                    "last_crawled",
                    models.DateTimeField(
                        blank=True,
                        help_text="When this URL was last crawled",
                        null=True,
                    ),
                ),
                (
                    "next_crawl",
                    models.DateTimeField(
                        blank=True,
                        help_text="When this URL should be crawled next",
                        null=True,
                    ),
                ),
                (
                    "crawl_count",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of times this URL has been crawled"
                    ),
                ),
                (
                    "response_code",
                    models.PositiveIntegerField(
                        blank=True, help_text="Last HTTP response code", null=True
                    ),
                ),
                (
                    "response_time",
                    models.FloatField(
                        blank=True, help_text="Response time in seconds", null=True
                    ),
                ),
                (
                    "content_length",
                    models.PositiveIntegerField(
                        blank=True, help_text="Content length in bytes", null=True
                    ),
                ),
                (
                    "content_type",
                    models.CharField(
                        blank=True,
                        help_text="Content type from response headers",
                        max_length=100,
                    ),
                ),
                (
                    "page_title",
                    models.CharField(
                        blank=True, help_text="Page title if available", max_length=500
                    ),
                ),
                (
                    "meta_description",
                    models.TextField(
                        blank=True, help_text="Meta description if available"
                    ),
                ),
                (
                    "links_found",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of links discovered on this page"
                    ),
                ),
                (
                    "products_found",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of products found on this page"
                    ),
                ),
                (
                    "categories_found",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of categories found on this page"
                    ),
                ),
                (
                    "error_message",
                    models.TextField(
                        blank=True, help_text="Error message if crawling failed"
                    ),
                ),
                (
                    "robots_txt_allowed",
                    models.BooleanField(
                        default=True,
                        help_text="Whether robots.txt allows crawling this URL",
                    ),
                ),
                (
                    "last_modified",
                    models.DateTimeField(
                        blank=True,
                        help_text="Last-Modified header from response",
                        null=True,
                    ),
                ),
                (
                    "etag",
                    models.CharField(
                        blank=True,
                        help_text="ETag header from response",
                        max_length=100,
                    ),
                ),
                (
                    "crawl_session",
                    models.ForeignKey(
                        help_text="The crawl session that discovered this URL",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discovered_urls",
                        to="asda_scraper.crawlsession",
                    ),
                ),
                (
                    "parent_url",
                    models.ForeignKey(
                        blank=True,
                        help_text="The URL that discovered this URL",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="child_urls",
                        to="asda_scraper.urlmap",
                    ),
                ),
            ],
            options={
                "verbose_name": "URL Map",
                "verbose_name_plural": "URL Maps",
                "db_table": "asda_scraper_url_map",
                "ordering": ["-priority", "discovered_at"],
            },
        ),
        migrations.CreateModel(
            name="LinkRelationship",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "anchor_text",
                    models.CharField(
                        blank=True,
                        help_text="The anchor text of the link",
                        max_length=500,
                    ),
                ),
                (
                    "link_type",
                    models.CharField(
                        choices=[
                            ("navigation", "Navigation Link"),
                            ("category", "Category Link"),
                            ("product", "Product Link"),
                            ("pagination", "Pagination Link"),
                            ("breadcrumb", "Breadcrumb Link"),
                            ("related", "Related Link"),
                            ("other", "Other Link"),
                        ],
                        default="other",
                        help_text="Type of link relationship",
                        max_length=20,
                    ),
                ),
                (
                    "css_selector",
                    models.CharField(
                        blank=True,
                        help_text="CSS selector where the link was found",
                        max_length=200,
                    ),
                ),
                (
                    "position_on_page",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Position of link on the page (1st, 2nd, etc.)",
                        null=True,
                    ),
                ),
                (
                    "first_seen",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="When this link relationship was first discovered",
                    ),
                ),
                (
                    "last_seen",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="When this link was last seen on the page",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this link is still present on the page",
                    ),
                ),
                (
                    "from_url",
                    models.ForeignKey(
                        help_text="The page containing the link",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outbound_links",
                        to="asda_scraper.urlmap",
                    ),
                ),
                (
                    "to_url",
                    models.ForeignKey(
                        help_text="The page the link points to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inbound_links",
                        to="asda_scraper.urlmap",
                    ),
                ),
            ],
            options={
                "verbose_name": "Link Relationship",
                "verbose_name_plural": "Link Relationships",
                "db_table": "asda_scraper_link_relationship",
            },
        ),
        migrations.CreateModel(
            name="CrawlQueue",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "priority",
                    models.IntegerField(
                        default=0, help_text="Crawling priority (higher = sooner)"
                    ),
                ),
                (
                    "scheduled_time",
                    models.DateTimeField(help_text="When this URL should be crawled"),
                ),
                (
                    "attempts",
                    models.PositiveIntegerField(
                        default=0, help_text="Number of crawl attempts"
                    ),
                ),
                (
                    "last_attempt",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the last crawl attempt was made",
                        null=True,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, help_text="When this queue entry was created"
                    ),
                ),
                (
                    "crawl_session",
                    models.ForeignKey(
                        help_text="The crawl session this queue item belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crawl_queue",
                        to="asda_scraper.crawlsession",
                    ),
                ),
                (
                    "url_map",
                    models.ForeignKey(
                        help_text="The URL to be crawled",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="queue_entries",
                        to="asda_scraper.urlmap",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crawl Queue Entry",
                "verbose_name_plural": "Crawl Queue Entries",
                "db_table": "asda_scraper_crawl_queue",
                "ordering": ["-priority", "scheduled_time"],
            },
        ),
        migrations.CreateModel(
            name="AsdaProduct",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Product name as shown on ASDA website",
                        max_length=500,
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Current price in pounds",
                        max_digits=8,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "was_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Original price if item is on sale",
                        max_digits=8,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "unit",
                    models.CharField(
                        blank=True,
                        help_text="Unit of measurement (e.g., 'each', 'kg', '100g')",
                        max_length=50,
                    ),
                ),
                (
                    "price_per_unit",
                    models.CharField(
                        blank=True,
                        help_text="Price per unit string (e.g., '£6.83/kg')",
                        max_length=100,
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, help_text="Product description"),
                ),
                (
                    "image_url",
                    models.URLField(blank=True, help_text="URL to product image"),
                ),
                (
                    "product_url",
                    models.URLField(
                        help_text="Direct URL to product page on ASDA", unique=True
                    ),
                ),
                (
                    "asda_id",
                    models.CharField(
                        help_text="ASDA's internal product ID",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "in_stock",
                    models.BooleanField(
                        default=True, help_text="Whether product is currently available"
                    ),
                ),
                (
                    "special_offer",
                    models.CharField(
                        blank=True,
                        help_text="Any special offer or promotion text (e.g., 'Rollback')",
                        max_length=200,
                    ),
                ),
                (
                    "rating",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Product rating out of 5 stars",
                        max_digits=3,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(5),
                        ],
                    ),
                ),
                (
                    "review_count",
                    models.CharField(
                        blank=True,
                        help_text="Number of reviews (e.g., '50+', '127')",
                        max_length=20,
                    ),
                ),
                (
                    "nutritional_info",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Nutritional information if available",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        help_text="Category this product belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="products",
                        to="asda_scraper.asdacategory",
                    ),
                ),
            ],
            options={
                "verbose_name": "ASDA Product",
                "verbose_name_plural": "ASDA Products",
                "ordering": ["name"],
            },
        ),
        migrations.AddIndex(
            model_name="urlmap",
            index=models.Index(
                fields=["crawl_session", "status"],
                name="asda_scrape_crawl_s_43921c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="urlmap",
            index=models.Index(
                fields=["crawl_session", "url_type"],
                name="asda_scrape_crawl_s_5decd7_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="urlmap",
            index=models.Index(
                fields=["priority", "discovered_at"],
                name="asda_scrape_priorit_95a898_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="urlmap",
            index=models.Index(
                fields=["last_crawled"], name="asda_scrape_last_cr_ec34db_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="urlmap",
            index=models.Index(
                fields=["next_crawl"], name="asda_scrape_next_cr_4cb8e3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="urlmap",
            index=models.Index(fields=["depth"], name="asda_scrape_depth_ae65cc_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="urlmap",
            unique_together={("crawl_session", "url_hash")},
        ),
        migrations.AddIndex(
            model_name="linkrelationship",
            index=models.Index(
                fields=["from_url", "link_type"], name="asda_scrape_from_ur_6748b9_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="linkrelationship",
            index=models.Index(
                fields=["to_url", "link_type"], name="asda_scrape_to_url__7a91cb_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="linkrelationship",
            index=models.Index(
                fields=["first_seen"], name="asda_scrape_first_s_58d175_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="linkrelationship",
            unique_together={("from_url", "to_url", "position_on_page")},
        ),
        migrations.AddIndex(
            model_name="crawlqueue",
            index=models.Index(
                fields=["crawl_session", "priority", "scheduled_time"],
                name="asda_scrape_crawl_s_f40e6a_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="crawlqueue",
            index=models.Index(
                fields=["scheduled_time"], name="asda_scrape_schedul_bda37e_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="crawlqueue",
            unique_together={("crawl_session", "url_map")},
        ),
        migrations.AddIndex(
            model_name="asdaproduct",
            index=models.Index(
                fields=["asda_id"], name="asda_scrape_asda_id_180bb3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="asdaproduct",
            index=models.Index(
                fields=["category", "name"], name="asda_scrape_categor_1b012c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="asdaproduct",
            index=models.Index(fields=["price"], name="asda_scrape_price_6b466c_idx"),
        ),
        migrations.AddIndex(
            model_name="asdaproduct",
            index=models.Index(fields=["rating"], name="asda_scrape_rating_b86616_idx"),
        ),
        migrations.AddIndex(
            model_name="asdaproduct",
            index=models.Index(
                fields=["was_price"], name="asda_scrape_was_pri_5cbf10_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="asdaproduct",
            index=models.Index(
                fields=["special_offer"], name="asda_scrape_special_2a3f79_idx"
            ),
        ),
    ]
