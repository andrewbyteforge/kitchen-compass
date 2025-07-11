"""
Data models for ASDA scraper.

File: asda_scraper/scrapers/models.py
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ScrapingResult:
    """
    Data class to encapsulate scraping results.
    """
    products_found: int = 0
    products_saved: int = 0
    categories_processed: int = 0
    errors: List[str] = field(default_factory=list)
    duration: Optional[float] = None
    
    def add_error(self, error: str) -> None:
        """
        Add an error to the results.
        
        Args:
            error: Error message to add
        """
        self.errors.append(error)
    
    def success_rate(self) -> float:
        """
        Calculate success rate of products saved vs found.
        
        Returns:
            float: Success rate as percentage
        """
        if self.products_found == 0:
            return 0.0
        return (self.products_saved / self.products_found) * 100


@dataclass
class ProductData:
    """
    Data class for product information.
    """
    name: str
    price: float
    was_price: Optional[float] = None
    unit: str = 'each'
    description: str = ''
    image_url: str = ''
    product_url: str = ''
    asda_id: str = ''
    in_stock: bool = True
    special_offer: str = ''
    rating: Optional[float] = None
    review_count: str = ''
    price_per_unit: str = ''
    nutritional_info: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert product data to dictionary.
        
        Returns:
            Dict[str, Any]: Product data as dictionary
        """
        return {
            'name': self.name,
            'price': self.price,
            'was_price': self.was_price,
            'unit': self.unit,
            'description': self.description,
            'image_url': self.image_url,
            'product_url': self.product_url,
            'asda_id': self.asda_id,
            'in_stock': self.in_stock,
            'special_offer': self.special_offer,
            'rating': self.rating,
            'review_count': self.review_count,
            'price_per_unit': self.price_per_unit,
            'nutritional_info': self.nutritional_info,
        }
    
    def validate(self) -> bool:
        """
        Validate required product data.
        
        Returns:
            bool: True if valid, False otherwise
        """
        return bool(self.name and self.price is not None and self.price >= 0)