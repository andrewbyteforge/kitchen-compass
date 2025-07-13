"""
ASDA Scrapers module.

Provides scraper classes for different crawling tasks.
"""

from .base_scraper import BaseScraper
from .category_mapper import CategoryMapperCrawler
from .product_list_crawler import ProductListCrawler
from .product_detail_crawler import ProductDetailCrawler

__all__ = [
    'BaseScraper',
    'CategoryMapperCrawler',
    'ProductListCrawler',
    'ProductDetailCrawler',
]