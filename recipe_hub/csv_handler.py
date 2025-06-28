"""
CSV Handler for Recipe Import

Handles parsing and validation of CSV files for recipe import functionality.
"""

import csv
import logging
from typing import Dict, List, Tuple, Optional
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Recipe, Ingredient, Instruction, RecipeCategory

logger = logging.getLogger(__name__)


class RecipeCSVHandler:
    """
    Handles CSV import for recipes.
    
    Expected CSV format:
    title, description, prep_time, cook_time, servings, difficulty, categories,
    ingredient_1_name, ingredient_1_quantity, ingredient_1_unit, ingredient_1_notes,
    ingredient_2_name, ingredient_2_quantity, ingredient_2_unit, ingredient_2_notes,
    ...(up to 20 ingredients)
    instruction_1, instruction_2, instruction_3, ...(up to 15 instructions)
    """
    
    REQUIRED_HEADERS = [
        'title', 'description', 'prep_time', 'cook_time', 
        'servings', 'difficulty', 'categories'
    ]
    
    MAX_INGREDIENTS = 20
    MAX_INSTRUCTIONS = 15
    
    def __init__(self, user):
        """
        Initialize CSV handler with user context.
        
        Args:
            user: The user importing the recipes
        """
        self.user = user
        self.errors = []
        self.warnings = []
        self.imported_count = 0
        self._processed_titles = set()
        
    def validate_headers(self, headers: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate CSV headers match expected format.
        
        Args:
            headers: List of CSV header strings
            
        Returns:
            Tuple of (is_valid, missing_headers)
        """
        missing_headers = []
        for required in self.REQUIRED_HEADERS:
            if required not in headers:
                missing_headers.append(required)
        
        is_valid = len(missing_headers) == 0
        return is_valid, missing_headers
    
    def parse_csv_file(self, csv_file) -> List[Dict]:
        """
        Parse CSV file and return list of recipe dictionaries.
        
        Args:
            csv_file: File object containing CSV data
            
        Returns:
            List of dictionaries containing recipe data
        """
        recipes = []
        
        try:
            # Decode file if needed
            if hasattr(csv_file, 'read'):
                content = csv_file.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8-sig')  # Handle BOM
                csv_file = content.splitlines()
            
            reader = csv.DictReader(csv_file)
            
            # Validate headers
            headers = reader.fieldnames or []
            is_valid, missing = self.validate_headers(headers)
            
            if not is_valid:
                raise ValidationError(
                    f"Missing required headers: {', '.join(missing)}"
                )
            
            for row_num, row in enumerate(reader, start=2):
                try:
                    recipe_data = self._parse_recipe_row(row, row_num)
                    if recipe_data:
                        recipes.append(recipe_data)
                except Exception as e:
                    self.errors.append(
                        f"Row {row_num}: {str(e)}"
                    )
                    logger.error(
                        f"Error parsing row {row_num} for user {self.user.username}: {str(e)}"
                    )
                    
        except Exception as e:
            self.errors.append(f"CSV parsing error: {str(e)}")
            logger.error(
                f"CSV parsing error for user {self.user.username}: {str(e)}"
            )
            
        return recipes
    
    def _parse_recipe_row(self, row: Dict, row_num: int) -> Optional[Dict]:
        """
        Parse a single row of recipe data.
        
        Args:
            row: Dictionary of row data
            row_num: Row number for error reporting
            
        Returns:
            Dictionary of parsed recipe data or None if invalid
        """
        # Clean and validate basic fields
        title = row.get('title', '').strip()
        if not title:
            raise ValidationError("Recipe title is required")
        
        if len(title) < 3:
            raise ValidationError("Recipe title must be at least 3 characters")
        
        # Check for duplicate titles within this import
        if title in self._processed_titles:
            raise ValidationError(f"Duplicate recipe title: {title}")
        self._processed_titles.add(title)
        
        recipe_data = {
            'title': title,
            'description': row.get('description', '').strip() or f"Delicious {title} recipe",  # Default description
            'prep_time': self._parse_time(row.get('prep_time', ''), 'prep_time'),
            'cook_time': self._parse_time(row.get('cook_time', ''), 'cook_time'),
            'servings': self._parse_servings(row.get('servings', '')),
            'difficulty': self._parse_difficulty(row.get('difficulty', '')),
            'categories': self._parse_categories(row.get('categories', '')),
            'ingredients': self._parse_ingredients(row),
            'instructions': self._parse_instructions(row),
        }
        
        return recipe_data



    def _parse_time(self, value: str, field_name: str) -> int:
        """Parse time value in minutes."""
        try:
            time_val = int(value.strip())
            if time_val < 1:
                raise ValueError
            return time_val
        except (ValueError, AttributeError):
            raise ValidationError(
                f"{field_name} must be a positive number of minutes"
            )
    
    def _parse_servings(self, value: str) -> int:
        """Parse servings value."""
        try:
            servings = int(value.strip())
            if servings < 1 or servings > 50:
                raise ValueError
            return servings
        except (ValueError, AttributeError):
            raise ValidationError("Servings must be between 1 and 50")
    
    def _parse_difficulty(self, value: str) -> str:
        """Parse and validate difficulty level."""
        difficulty = value.strip().lower()
        valid_difficulties = ['easy', 'medium', 'hard']
        
        if difficulty not in valid_difficulties:
            self.warnings.append(
                f"Invalid difficulty '{value}', defaulting to 'medium'"
            )
            return 'medium'
        
        return difficulty
    
    def _parse_categories(self, value: str) -> List[str]:
        """Parse comma-separated categories."""
        if not value:
            return []
        
        categories = [cat.strip() for cat in value.split(',') if cat.strip()]
        return categories[:5]  # Limit to 5 categories
    
    def _parse_ingredients(self, row: Dict) -> List[Dict]:
        """Parse ingredient columns from row."""
        ingredients = []
        
        for i in range(1, self.MAX_INGREDIENTS + 1):
            name = row.get(f'ingredient_{i}_name', '').strip()
            if not name:
                continue
                
            ingredient = {
                'name': name,
                'quantity': row.get(f'ingredient_{i}_quantity', '').strip() or '1',
                'unit': row.get(f'ingredient_{i}_unit', '').strip(),
                'notes': row.get(f'ingredient_{i}_notes', '').strip(),
                'order': i
            }
            ingredients.append(ingredient)
        
        if not ingredients:
            raise ValidationError("At least one ingredient is required")
        
        return ingredients
    
    def _parse_instructions(self, row: Dict) -> List[str]:
        """Parse instruction columns from row."""
        instructions = []
        
        for i in range(1, self.MAX_INSTRUCTIONS + 1):
            instruction = row.get(f'instruction_{i}', '').strip()
            if instruction:
                instructions.append(instruction)
        
        if not instructions:
            raise ValidationError("At least one instruction is required")
        
        return instructions
    
    @transaction.atomic
    def import_recipes(self, recipes_data: List[Dict]) -> Tuple[int, List[str]]:
        """
        Import recipes from parsed data.
        
        Args:
            recipes_data: List of recipe dictionaries
            
        Returns:
            Tuple of (imported_count, error_messages)
        """
        imported_count = 0
        
        for idx, recipe_data in enumerate(recipes_data):
            try:
                recipe = self._create_recipe(recipe_data)
                imported_count += 1
                
                logger.info(
                    f"Imported recipe '{recipe.title}' for user {self.user.username}"
                )
                
            except Exception as e:
                self.errors.append(
                    f"Recipe '{recipe_data.get('title', 'Unknown')}': {str(e)}"
                )
                logger.error(
                    f"Error importing recipe for user {self.user.username}: {str(e)}"
                )
        
        self.imported_count = imported_count
        return imported_count, self.errors
    
    def _create_recipe(self, recipe_data: Dict) -> Recipe:
        """
        Create a recipe from parsed data.
        
        Args:
            recipe_data: Dictionary of recipe data
            
        Returns:
            Created Recipe instance
        """
        # Create base recipe
        recipe = Recipe.objects.create(
            author=self.user,
            title=recipe_data['title'],
            description=recipe_data['description'],
            prep_time=recipe_data['prep_time'],
            cook_time=recipe_data['cook_time'],
            servings=recipe_data['servings'],
            difficulty=recipe_data['difficulty'],
            is_public=False  # Default to private for imported recipes
        )
        
        # Add categories
        for category_name in recipe_data['categories']:
            try:
                category = RecipeCategory.objects.get(
                    name__iexact=category_name,
                    is_active=True
                )
                recipe.categories.add(category)
            except RecipeCategory.DoesNotExist:
                self.warnings.append(
                    f"Category '{category_name}' not found for recipe '{recipe.title}'"
                )
        
        # Create ingredients
        for ing_data in recipe_data['ingredients']:
            Ingredient.objects.create(
                recipe=recipe,
                name=ing_data['name'],
                quantity=ing_data['quantity'],
                unit=ing_data['unit'],
                notes=ing_data['notes'],
                order=ing_data['order']
            )
        
        # Create instructions
        for idx, instruction_text in enumerate(recipe_data['instructions'], 1):
            Instruction.objects.create(
                recipe=recipe,
                step_number=idx,
                instruction=instruction_text
            )
        
        return recipe
    
    def generate_sample_csv(self) -> str:
        """
        Generate a sample CSV template.
        
        Returns:
            CSV string with headers and sample data
        """
        headers = self.REQUIRED_HEADERS.copy()
        
        # Add ingredient headers
        for i in range(1, 6):  # Show 5 ingredient columns as example
            headers.extend([
                f'ingredient_{i}_name',
                f'ingredient_{i}_quantity',
                f'ingredient_{i}_unit',
                f'ingredient_{i}_notes'
            ])
        
        # Add instruction headers
        for i in range(1, 6):  # Show 5 instruction columns as example
            headers.append(f'instruction_{i}')
        
        # Create sample row
        sample_data = {
            'title': 'Classic Spaghetti Carbonara',
            'description': 'Traditional Italian pasta dish with eggs, cheese, and pancetta',
            'prep_time': '15',
            'cook_time': '20',
            'servings': '4',
            'difficulty': 'medium',
            'categories': 'Italian, Dinner',
            'ingredient_1_name': 'Spaghetti',
            'ingredient_1_quantity': '400',
            'ingredient_1_unit': 'grams',
            'ingredient_1_notes': '',
            'ingredient_2_name': 'Pancetta',
            'ingredient_2_quantity': '200',
            'ingredient_2_unit': 'grams',
            'ingredient_2_notes': 'diced',
            'ingredient_3_name': 'Eggs',
            'ingredient_3_quantity': '4',
            'ingredient_3_unit': '',
            'ingredient_3_notes': 'large, room temperature',
            'ingredient_4_name': 'Parmesan cheese',
            'ingredient_4_quantity': '100',
            'ingredient_4_unit': 'grams',
            'ingredient_4_notes': 'freshly grated',
            'ingredient_5_name': 'Black pepper',
            'ingredient_5_quantity': '2',
            'ingredient_5_unit': 'teaspoons',
            'ingredient_5_notes': 'freshly ground',
            'instruction_1': 'Bring a large pot of salted water to boil and cook spaghetti according to package directions',
            'instruction_2': 'While pasta cooks, fry pancetta in a large pan until crispy',
            'instruction_3': 'In a bowl, whisk together eggs, grated Parmesan, and black pepper',
            'instruction_4': 'Drain pasta, reserving 1 cup of pasta water',
            'instruction_5': 'Add hot pasta to pancetta, remove from heat, and quickly stir in egg mixture, adding pasta water as needed'
        }
        
        # Fill remaining columns with empty strings
        for i in range(6, self.MAX_INGREDIENTS + 1):
            sample_data[f'ingredient_{i}_name'] = ''
            sample_data[f'ingredient_{i}_quantity'] = ''
            sample_data[f'ingredient_{i}_unit'] = ''
            sample_data[f'ingredient_{i}_notes'] = ''
        
        for i in range(6, self.MAX_INSTRUCTIONS + 1):
            sample_data[f'instruction_{i}'] = ''
        
        # Generate CSV string
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerow(sample_data)
        
        return output.getvalue()