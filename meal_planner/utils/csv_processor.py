"""
CSV Processor for Recipe Imports

Handles the actual processing of CSV files and recipe creation.
"""

import csv
import io
import json
import logging
from datetime import datetime
from django.db import transaction
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from recipe_hub.models import Recipe, RecipeCategory, Ingredient, Instruction
from meal_planner.models import MealType

User = get_user_model()
logger = logging.getLogger(__name__)


class RecipeCSVProcessor:
    """
    Process CSV files and create recipes.
    
    Handles parsing, validation, and database creation.
    """
    
    def __init__(self, csv_upload, user):
        """
        Initialize processor.
        
        Args:
            csv_upload: RecipeCSVUpload instance
            user: User creating the recipes
        """
        self.csv_upload = csv_upload
        self.user = user
        self.errors = []
        self.success_count = 0
        self.failed_count = 0
        
    def process(self):
        """
        Process the entire CSV file.
        
        Returns:
            tuple: (success_count, failed_count, errors)
        """
        logger.info(f"Starting CSV processing for upload {self.csv_upload.id}")
        
        try:
            # Read file content
            self.csv_upload.file.seek(0)
            content = self.csv_upload.file.read()
            
            # Decode content
            decoded_content = self._decode_content(content)
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(decoded_content))
            
            # Process each row
            total_rows = 0
            for row_num, row in enumerate(csv_reader, start=2):
                total_rows += 1
                self._process_row(row, row_num)
            
            # Update upload record
            self.csv_upload.total_rows = total_rows
            self.csv_upload.successful_imports = self.success_count
            self.csv_upload.failed_imports = self.failed_count
            self.csv_upload.error_log = {
                'errors': self.errors,
                'processed_at': datetime.now().isoformat()
            }
            self.csv_upload.mark_completed()
            
            logger.info(
                f"CSV processing completed: {self.success_count} successful, "
                f"{self.failed_count} failed out of {total_rows} total"
            )
            
        except Exception as e:
            logger.error(f"Fatal error processing CSV: {str(e)}")
            self.csv_upload.status = 'failed'
            self.csv_upload.error_log = {
                'fatal_error': str(e),
                'processed_at': datetime.now().isoformat()
            }
            self.csv_upload.save()
            raise
        
        return self.success_count, self.failed_count, self.errors
    
    def _decode_content(self, content):
        """Try to decode content with different encodings."""
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Unable to decode CSV file")
    
    def _process_row(self, row, row_num):
        """
        Process a single CSV row.
        
        Args:
            row: Dictionary of row data
            row_num: Row number for error reporting
        """
        try:
            with transaction.atomic():
                # Clean row data
                cleaned_row = {k: v.strip() for k, v in row.items()}
                
                # Create recipe
                recipe = self._create_recipe(cleaned_row)
                
                # Add categories
                self._add_categories(recipe, cleaned_row.get('categories', ''))
                
                # Add meal types
                self._add_meal_types(recipe, cleaned_row.get('meal_types', ''))
                
                # Add ingredients
                self._add_ingredients(recipe, cleaned_row.get('ingredients', ''))
                
                # Add instructions
                self._add_instructions(recipe, cleaned_row.get('instructions', ''))
                
                self.success_count += 1
                logger.info(f"Successfully imported recipe: {recipe.title}")
                
        except Exception as e:
            self.failed_count += 1
            error_msg = f"Row {row_num}: {str(e)}"
            self.errors.append(error_msg)
            logger.error(f"Error processing row {row_num}: {str(e)}")
    
    def _create_recipe(self, row):
        """Create recipe from row data."""
        # Generate unique slug
        base_slug = slugify(row['title'])
        slug = base_slug
        counter = 1
        while Recipe.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Parse difficulty
        difficulty = row.get('difficulty', 'medium').lower()
        if difficulty not in ['easy', 'medium', 'hard']:
            difficulty = 'medium'
        
        # Parse boolean fields
        is_public = row.get('is_public', '').lower() in ['true', '1', 'yes']
        
        # Parse dietary info
        dietary_info = {}
        if row.get('dietary_info'):
            try:
                dietary_info = json.loads(row['dietary_info'])
            except json.JSONDecodeError:
                # Try comma-separated format
                tags = [tag.strip() for tag in row['dietary_info'].split(',') if tag.strip()]
                dietary_info = {'tags': tags}
        
        # Create recipe
        recipe = Recipe.objects.create(
            author=self.user,
            title=row['title'],
            slug=slug,
            description=row['description'],
            prep_time=int(row.get('prep_time', 0)),
            cook_time=int(row.get('cook_time', 0)),
            servings=int(row.get('servings', 4)),
            difficulty=difficulty,
            is_public=is_public,
            dietary_info=dietary_info
        )
        
        return recipe
    
    def _add_categories(self, recipe, categories_str):
        """Add categories to recipe."""
        if not categories_str:
            return
        
        categories = [cat.strip() for cat in categories_str.split(',') if cat.strip()]
        
        for cat_name in categories:
            category, created = RecipeCategory.objects.get_or_create(
                name=cat_name,
                defaults={'slug': slugify(cat_name)}
            )
            recipe.categories.add(category)
    
    def _add_meal_types(self, recipe, meal_types_str):
        """Add meal types to recipe."""
        if not meal_types_str:
            return
        
        meal_types = [mt.strip() for mt in meal_types_str.split(',') if mt.strip()]
        
        for mt_name in meal_types:
            try:
                meal_type = MealType.objects.get(name__iexact=mt_name)
                recipe.meal_types.add(meal_type)
            except MealType.DoesNotExist:
                logger.warning(f"Meal type not found: {mt_name}")
    
    def _add_ingredients(self, recipe, ingredients_str):
        """
        Add ingredients to recipe.
        
        Expected format: "2 cups flour, 1 tsp salt, 3 eggs"
        """
        if not ingredients_str:
            return
        
        ingredients = [ing.strip() for ing in ingredients_str.split(',') if ing.strip()]
        
        for order, ingredient_str in enumerate(ingredients, start=1):
            # Parse ingredient string
            parts = ingredient_str.split(' ', 2)
            
            if len(parts) >= 3:
                quantity = parts[0]
                unit = parts[1]
                name = parts[2]
            elif len(parts) == 2:
                quantity = parts[0]
                unit = ''
                name = parts[1]
            else:
                quantity = ''
                unit = ''
                name = ingredient_str
            
            Ingredient.objects.create(
                recipe=recipe,
                name=name,
                quantity=quantity,
                unit=unit,
                order=order
            )
    
    def _add_instructions(self, recipe, instructions_str):
        """
        Add instructions to recipe.
        
        Expected format: "Step 1|Step 2|Step 3" or numbered list
        """
        if not instructions_str:
            return
        
        # Split by pipe or numbered patterns
        if '|' in instructions_str:
            steps = [step.strip() for step in instructions_str.split('|') if step.strip()]
        else:
            # Try to split by numbered patterns (1., 2., etc.)
            import re
            steps = re.split(r'\d+\.', instructions_str)
            steps = [step.strip() for step in steps if step.strip()]
        
        for step_num, instruction in enumerate(steps, start=1):
            Instruction.objects.create(
                recipe=recipe,
                step_number=step_num,
                instruction=instruction
            )