"""
Configuration settings for nutritional information extraction.

Save this as: asda_scraper/nutrition_config.py
"""

# Nutritional Information Extraction Settings
NUTRITION_EXTRACTION_CONFIG = {
    # Timing and retry settings
    'max_retries': 3,
    'page_load_timeout': 15,
    'extraction_delay': 2.0,
    'retry_delay': 3.0,
    
    # Rate limiting to be respectful to ASDA servers
    'default_delay_between_products': 3.0,
    'min_delay': 1.0,
    'max_delay': 10.0,
    
    # Batch processing settings
    'default_batch_size': 50,
    'max_batch_size': 200,
    
    # Error handling
    'max_consecutive_errors': 5,
    'skip_on_error': True,
    'continue_on_timeout': True,
}

# CSS Selectors for nutritional information
NUTRITION_SELECTORS = {
    # Primary selectors for finding nutritional sections
    'section_headers': [
        'h2:contains("Nutritional Values")',
        'h3:contains("Nutritional Values")',
        'h2:contains("Nutrition")',
        'h3:contains("Nutrition")',
        '[class*="nutrition"]',
        '[id*="nutrition"]'
    ],
    
    # Table selectors for nutritional data
    'nutrition_tables': [
        'table[class*="nutrition"]',
        'table[id*="nutrition"]',
        'div[class*="nutrition"] table',
        'section[class*="nutrition"] table'
    ],
    
    # Row selectors within nutritional tables
    'nutrition_rows': [
        'tr',
        'div[class*="nutrition-row"]',
        'li[class*="nutrition"]'
    ],
    
    # Cell selectors for nutrient names and values
    'nutrient_cells': [
        'td', 'th', 'span', 'div'
    ]
}

# Standard nutritional field mappings
NUTRITION_FIELD_MAPPINGS = {
    # Energy values
    'energy kj': 'Energy (kJ)',
    'energy kcal': 'Energy (kcal)',
    'energy kilojoules': 'Energy (kJ)',
    'energy kilocalories': 'Energy (kcal)',
    'calories': 'Energy (kcal)',
    
    # Macronutrients
    'fat': 'Fat',
    'total fat': 'Fat',
    'of which saturates': 'Saturates',
    'saturated fat': 'Saturates',
    'saturates': 'Saturates',
    
    'carbohydrate': 'Carbohydrate',
    'carbohydrates': 'Carbohydrate',
    'total carbohydrate': 'Carbohydrate',
    'of which sugars': 'Sugars',
    'total sugars': 'Sugars',
    'sugars': 'Sugars',
    
    'fibre': 'Fibre',
    'fiber': 'Fibre',
    'dietary fibre': 'Fibre',
    'dietary fiber': 'Fibre',
    
    'protein': 'Protein',
    'total protein': 'Protein',
    
    'salt': 'Salt',
    'sodium': 'Sodium',
    
    # Vitamins and minerals (if available)
    'vitamin c': 'Vitamin C',
    'vitamin d': 'Vitamin D',
    'vitamin e': 'Vitamin E',
    'vitamin a': 'Vitamin A',
    'calcium': 'Calcium',
    'iron': 'Iron',
    'potassium': 'Potassium',
    'magnesium': 'Magnesium',
    'zinc': 'Zinc'
}

# Regex patterns for extracting nutritional values
NUTRITION_VALUE_PATTERNS = [
    # Standard patterns with units
    r'(\d+\.?\d*)\s*g\b',           # e.g., "1.9g", "28g"
    r'(\d+\.?\d*)\s*mg\b',          # e.g., "150mg"
    r'(\d+\.?\d*)\s*kj\b',          # e.g., "559kJ"
    r'(\d+\.?\d*)\s*kcal\b',        # e.g., "132kcal"
    r'(\d+\.?\d*)\s*μg\b',          # e.g., "50μg"
    r'(\d+\.?\d*)\s*mcg\b',         # e.g., "50mcg"
    
    # Less than/greater than patterns
    r'<\s*(\d+\.?\d*)\s*g\b',       # e.g., "<0.5g"
    r'>\s*(\d+\.?\d*)\s*g\b',       # e.g., ">1.0g"
    r'≤\s*(\d+\.?\d*)\s*g\b',       # e.g., "≤0.5g"
    r'≥\s*(\d+\.?\d*)\s*g\b',       # e.g., "≥1.0g"
    
    # Just numbers (assume grams if no unit)
    r'^(\d+\.?\d*)$',               # e.g., "28", "1.9"
    r'(\d+\.?\d*)\s*(?:each|per)',  # e.g., "132 per 100g"
]

# Units to preserve in nutritional values
PRESERVE_UNITS = ['g', 'mg', 'μg', 'mcg', 'kJ', 'kcal', 'ml', 'l']

# Common words to exclude from nutritional data
EXCLUSION_KEYWORDS = [
    'typical values',
    'per 100g',
    'per serving',
    'overbaked',
    'preparation',
    'instructions',
    'contains',
    'allergens',
    'ingredients',
    'storage',
    'best before',
    'use by'
]

# Validation rules for nutritional data
NUTRITION_VALIDATION = {
    # Reasonable ranges for common nutrients (per 100g)
    'energy_kj_range': (0, 4000),      # kJ per 100g
    'energy_kcal_range': (0, 1000),    # kcal per 100g
    'fat_range': (0, 100),             # grams per 100g
    'protein_range': (0, 100),         # grams per 100g
    'carbohydrate_range': (0, 100),    # grams per 100g
    'salt_range': (0, 50),             # grams per 100g
    'fibre_range': (0, 50),            # grams per 100g
    
    # Minimum required fields for valid nutritional data
    'required_fields': ['Energy (kJ)', 'Energy (kcal)'],
    
    # Fields that should be numeric
    'numeric_fields': [
        'Energy (kJ)', 'Energy (kcal)', 'Fat', 'Saturates',
        'Carbohydrate', 'Sugars', 'Fibre', 'Protein', 'Salt'
    ]
}

# Logging configuration for nutritional extraction
NUTRITION_LOGGING = {
    'log_successful_extractions': True,
    'log_failed_extractions': True,
    'log_validation_failures': True,
    'log_extraction_details': False,  # Set to True for detailed debugging
    'log_regex_matches': False,       # Set to True for regex debugging
}

# Export settings for nutritional data
NUTRITION_EXPORT_CONFIG = {
    'export_formats': ['json', 'csv', 'xlsx'],
    'include_metadata': True,
    'include_extraction_timestamp': True,
    'group_by_category': True,
    
    # CSV export settings
    'csv_delimiter': ',',
    'csv_include_headers': True,
    
    # JSON export settings
    'json_indent': 2,
    'json_ensure_ascii': False,
    
    # Excel export settings
    'xlsx_sheet_name': 'Nutritional Data',
    'xlsx_include_charts': False
}