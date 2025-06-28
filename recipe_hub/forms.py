"""
Recipe Hub Forms - FINAL FIX

This module contains all forms for recipe creation, editing, and interaction.
Includes formsets for managing ingredients and instructions.
"""

import logging
from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import (
    Recipe, RecipeCategory, Ingredient, Instruction,
    RecipeRating, RecipeComment, IngredientCategory
)

logger = logging.getLogger(__name__)


# Update your RecipeForm class in recipe_hub/forms.py

class RecipeForm(forms.ModelForm):
    """Form for creating and updating recipes."""
    
    categories = forms.ModelMultipleChoiceField(
        queryset=RecipeCategory.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        required=False,
        help_text="Select all categories that apply"
    )
    
    # ADD THIS NEW FIELD
    meal_types = forms.ModelMultipleChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        required=False,
        help_text="What meals is this recipe suitable for?"
    )
    
    class Meta:
        model = Recipe
        fields = [
            'title',
            'slug',
            'description',
            'categories',
            'meal_types',  # ADD THIS
            'prep_time',
            'cook_time',
            'servings',
            'difficulty',
            'image',
            'is_public',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter recipe title',
                'required': True
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'leave-blank-for-auto-generate'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of your recipe',
                'required': True
            }),
            'prep_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Minutes',
                'required': True
            }),
            'cook_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Minutes',
                'required': True
            }),
            'servings': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 50,
                'value': 4,
                'required': True
            }),
            'difficulty': forms.Select(attrs={
                'class': 'form-select'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'checked': True
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make slug not required
        self.fields['slug'].required = False
        
        # ADD THIS - Set up meal types queryset
        try:
            from meal_planner.models import MealType
            self.fields['meal_types'].queryset = MealType.objects.all().order_by('display_order')
        except Exception:
            # If meal_planner app is not available, hide the field
            self.fields['meal_types'].widget = forms.HiddenInput()
            self.fields['meal_types'].required = False


class IngredientForm(forms.ModelForm):
    """Form for individual ingredients."""
    
    class Meta:
        model = Ingredient
        fields = ['name', 'quantity', 'unit', 'notes', 'order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingredient name'
            }),
            'quantity': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Amount'
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Unit (optional)'
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Notes (optional)'
            }),
            'order': forms.HiddenInput()
        }
    
    def clean_name(self):
        """Validate ingredient name."""
        name = self.cleaned_data.get('name')
        if name and len(name) < 2:
            raise ValidationError("Ingredient name is too short.")
        return name





class InstructionForm(forms.ModelForm):
    """Form for individual instructions."""
    
    class Meta:
        model = Instruction
        fields = ['step_number', 'instruction', 'time_minutes', 'image']
        widgets = {
            'step_number': forms.HiddenInput(),
            'instruction': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Describe this step'
            }),
            'time_minutes': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Time (optional)',
                'min': 1
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
    
    def clean_instruction(self):
        """Validate instruction text."""
        instruction = self.cleaned_data.get('instruction')
        if instruction and len(instruction) < 10:
            raise ValidationError("Instruction must be at least 10 characters long.")
        return instruction


# Formsets for managing multiple ingredients and instructions
IngredientFormSet = inlineformset_factory(
    Recipe,
    Ingredient,
    form=IngredientForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
    error_messages={
        'too_few_forms': 'At least one ingredient is required.',
    }
)

InstructionFormSet = inlineformset_factory(
    Recipe,
    Instruction,
    form=InstructionForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
    error_messages={
        'too_few_forms': 'At least one instruction is required.',
    }
)




class BaseIngredientFormSet(BaseInlineFormSet):
    """Custom formset for ingredients with validation."""
    
    def clean(self):
        """Ensure at least one valid ingredient is provided."""
        super().clean()
        if any(self.errors):
            return
        
        valid_ingredients = 0
        for form in self.forms:
            if self.can_delete and form.cleaned_data.get('DELETE'):
                continue
            if form.cleaned_data and form.cleaned_data.get('name'):
                valid_ingredients += 1
        
        if valid_ingredients < 1:
            raise forms.ValidationError('At least one ingredient is required.')


from django.forms import inlineformset_factory, BaseInlineFormSet

class BaseIngredientFormSet(BaseInlineFormSet):
    def clean(self):
        """Ensure at least one ingredient is provided."""
        super().clean()
        if any(self.errors):
            return
        
        ingredients = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                ingredients.append(form.cleaned_data)
        
        if not ingredients:
            raise forms.ValidationError('At least one ingredient is required.')




class BaseInstructionFormSet(BaseInlineFormSet):
    """Custom formset for instructions with validation."""
    
    def clean(self):
        """Ensure at least one valid instruction is provided."""
        super().clean()
        if any(self.errors):
            return
        
        valid_instructions = 0
        for form in self.forms:
            if self.can_delete and form.cleaned_data.get('DELETE'):
                continue
            if form.cleaned_data and form.cleaned_data.get('instruction'):
                valid_instructions += 1
        
        if valid_instructions < 1:
            raise forms.ValidationError('At least one instruction is required.')


# Create the formsets
IngredientFormSet = inlineformset_factory(
    Recipe,
    Ingredient,
    formset=BaseIngredientFormSet,
    fields=['name', 'quantity', 'unit', 'notes'],
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
    widgets={
        'name': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., flour',
            'required': True
        }),
        'quantity': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2',
            'required': True
        }),
        'unit': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., cups'
        }),
        'notes': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'optional notes'
        }),
    }
)

InstructionFormSet = inlineformset_factory(
    Recipe,
    Instruction,
    formset=BaseInstructionFormSet,
    fields=['instruction', 'time_minutes'],
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
    widgets={
        'instruction': forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Describe this step',
            'required': True
        }),
        'time_minutes': forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Time (optional)',
            'min': 0
        }),
    }
)


class RecipeSearchForm(forms.Form):
    """Form for searching and filtering recipes."""
    
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search recipes...'
        })
    )
    
    category = forms.ModelChoiceField(
        required=False,
        queryset=RecipeCategory.objects.filter(is_active=True),
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    difficulty = forms.ChoiceField(
        required=False,
        choices=[('', 'Any Difficulty')] + Recipe.DIFFICULTY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    max_time = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max time (minutes)',
            'min': 1
        })
    )
    
    dietary = forms.MultipleChoiceField(
        required=False,
        choices=[
            ('vegetarian', 'Vegetarian'),
            ('vegan', 'Vegan'),
            ('gluten_free', 'Gluten-Free'),
            ('dairy_free', 'Dairy-Free'),
            ('nut_free', 'Nut-Free'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        })
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('-rating', 'Highest Rated'),
            ('title', 'Alphabetical'),
            ('total_time', 'Quickest First'),
        ],
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean_max_time(self):
        """Validate maximum time filter."""
        max_time = self.cleaned_data.get('max_time')
        if max_time and max_time < 1:
            raise ValidationError("Time must be at least 1 minute.")
        if max_time and max_time > 1440:
            raise ValidationError("Time cannot exceed 24 hours.")
        return max_time








class RecipeRatingForm(forms.ModelForm):
    """Form for rating recipes."""
    
    class Meta:
        model = RecipeRating
        fields = ['rating', 'review']
        widgets = {
            'rating': forms.RadioSelect(
                choices=[(i, i) for i in range(1, 6)],
                attrs={'class': 'form-check-input'}
            ),
            'review': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Share your thoughts about this recipe (optional)'
            })
        }
    
    def clean_review(self):
        """Validate review text."""
        review = self.cleaned_data.get('review')
        if review and len(review) < 10:
            raise ValidationError("Review must be at least 10 characters long.")
        return review






class RecipeCommentForm(forms.ModelForm):
    """Form for commenting on recipes."""
    
    class Meta:
        model = RecipeComment
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Add a comment...'
            })
        }
    
    def clean_comment(self):
        """Validate comment text."""
        comment = self.cleaned_data.get('comment')
        if not comment:
            raise ValidationError("Comment cannot be empty.")
        if len(comment) < 5:
            raise ValidationError("Comment must be at least 5 characters long.")
        if len(comment) > 1000:
            raise ValidationError("Comment cannot exceed 1000 characters.")
        return comment


class RecipeCSVImportForm(forms.Form):
    """
    Form for importing recipes from CSV files.
    
    Supports batch recipe import with validation and error reporting.
    """
    
    csv_file = forms.FileField(
        label="CSV File",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv',
            'help_text': 'Upload a CSV file with recipe data'
        }),
        help_text="Upload a CSV file with recipe data. Maximum file size: 5MB"
    )
    
    # Options for import behavior
    skip_duplicates = forms.BooleanField(
        required=False,
        initial=True,
        label="Skip duplicate recipes",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Skip recipes with titles that already exist"
    )
    
    make_public = forms.BooleanField(
        required=False,
        initial=True,
        label="Make imported recipes public",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Make all imported recipes visible to other users"
    )
    
    default_category = forms.ModelChoiceField(
        required=False,
        queryset=RecipeCategory.objects.filter(is_active=True),
        empty_label="No default category",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Assign this category to recipes without specified categories"
    )
    
    def clean_csv_file(self):
        """Validate CSV file."""
        csv_file = self.cleaned_data.get('csv_file')
        
        if not csv_file:
            raise ValidationError("Please select a CSV file.")
        
        # Check file size (5MB limit)
        if csv_file.size > 5 * 1024 * 1024:
            raise ValidationError("File size cannot exceed 5MB.")
        
        # Check file extension
        if not csv_file.name.lower().endswith('.csv'):
            raise ValidationError("Please upload a CSV file.")
        
        # Validate CSV content
        try:
            # Read first few lines to validate format
            csv_file.seek(0)
            file_content = csv_file.read().decode('utf-8')
            csv_file.seek(0)  # Reset for later use
            
            # Check if file has content
            if not file_content.strip():
                raise ValidationError("CSV file is empty.")
            
            # Parse CSV to check format
            csv_reader = csv.DictReader(io.StringIO(file_content))
            headers = csv_reader.fieldnames
            
            if not headers:
                raise ValidationError("CSV file has no headers.")
            
            # Required fields
            required_fields = ['title', 'description', 'prep_time', 'cook_time', 'servings']
            missing_fields = [field for field in required_fields if field not in headers]
            
            if missing_fields:
                raise ValidationError(
                    f"CSV file is missing required columns: {', '.join(missing_fields)}. "
                    f"Required columns: {', '.join(required_fields)}"
                )
            
            # Check for at least one row of data
            try:
                first_row = next(csv_reader)
                if not any(first_row.values()):
                    raise ValidationError("CSV file has no data rows.")
            except StopIteration:
                raise ValidationError("CSV file has no data rows.")
            
            logger.info(f"CSV file validated: {csv_file.name} with headers: {headers}")
            
        except UnicodeDecodeError:
            raise ValidationError("Unable to read CSV file. Please ensure it's properly encoded.")
        except Exception as e:
            logger.error(f"CSV validation error: {str(e)}")
            raise ValidationError(f"Invalid CSV file format: {str(e)}")
        
        return csv_file
    
    def get_csv_data(self):
        """
        Parse and return CSV data as a list of dictionaries.
        
        Returns:
            list: Parsed CSV data with validation
        """
        csv_file = self.cleaned_data.get('csv_file')
        if not csv_file:
            return []
        
        try:
            csv_file.seek(0)
            file_content = csv_file.read().decode('utf-8')
            csv_reader = csv.DictReader(io.StringIO(file_content))
            
            parsed_data = []
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (after header)
                # Skip empty rows
                if not any(row.values()):
                    continue
                
                # Clean and validate row data
                try:
                    clean_row = self._clean_csv_row(row, row_num)
                    if clean_row:
                        parsed_data.append(clean_row)
                except ValidationError as e:
                    logger.warning(f"Skipping row {row_num}: {str(e)}")
                    continue
            
            logger.info(f"Parsed {len(parsed_data)} valid rows from CSV")
            return parsed_data
            
        except Exception as e:
            logger.error(f"Error parsing CSV data: {str(e)}")
            return []
    
    def _clean_csv_row(self, row, row_num):
        """
        Clean and validate a single CSV row.
        
        Args:
            row (dict): Raw CSV row data
            row_num (int): Row number for error reporting
            
        Returns:
            dict: Cleaned row data
            
        Raises:
            ValidationError: If row data is invalid
        """
        clean_row = {}
        
        # Required fields validation
        title = row.get('title', '').strip()
        if not title:
            raise ValidationError(f"Row {row_num}: Title is required")
        if len(title) < 3:
            raise ValidationError(f"Row {row_num}: Title must be at least 3 characters")
        clean_row['title'] = title
        
        description = row.get('description', '').strip()
        if not description:
            raise ValidationError(f"Row {row_num}: Description is required")
        clean_row['description'] = description
        
        # Numeric fields
        for field in ['prep_time', 'cook_time', 'servings']:
            try:
                value = int(row.get(field, 0))
                if value <= 0:
                    raise ValueError("Must be positive")
                clean_row[field] = value
            except (ValueError, TypeError):
                raise ValidationError(f"Row {row_num}: {field} must be a positive number")
        
        # Optional fields
        clean_row['difficulty'] = row.get('difficulty', 'medium').lower()
        if clean_row['difficulty'] not in ['easy', 'medium', 'hard']:
            clean_row['difficulty'] = 'medium'
        
        # Categories (comma-separated)
        categories_str = row.get('categories', '').strip()
        clean_row['categories'] = [cat.strip() for cat in categories_str.split(',') if cat.strip()]
        
        # Ingredients (semicolon-separated, format: "quantity unit name")
        ingredients_str = row.get('ingredients', '').strip()
        clean_row['ingredients'] = []
        if ingredients_str:
            for ingredient in ingredients_str.split(';'):
                ingredient = ingredient.strip()
                if ingredient:
                    # Parse ingredient format: "2 cups flour" or "1 large onion, diced"
                    parts = ingredient.split(' ', 2)
                    if len(parts) >= 2:
                        clean_row['ingredients'].append({
                            'quantity': parts[0],
                            'unit': parts[1] if len(parts) > 2 and not parts[1].isalpha() else '',
                            'name': ' '.join(parts[1:]) if len(parts) == 2 else ' '.join(parts[2:]),
                            'notes': ''
                        })
        
        # Instructions (numbered or semicolon-separated)
        instructions_str = row.get('instructions', '').strip()
        clean_row['instructions'] = []
        if instructions_str:
            for i, instruction in enumerate(instructions_str.split(';')):
                instruction = instruction.strip()
                if instruction:
                    clean_row['instructions'].append({
                        'step_number': i + 1,
                        'instruction': instruction,
                        'time_minutes': None
                    })
        
        # Dietary info
        clean_row['dietary_info'] = {}
        for diet_field in ['vegetarian', 'vegan', 'gluten_free', 'dairy_free', 'nut_free']:
            value = row.get(diet_field, '').lower()
            clean_row['dietary_info'][diet_field] = value in ['true', '1', 'yes', 'y']
        
        return clean_row


class RecipeImportForm(forms.Form):
    """Legacy form for recipe import - keeping for backward compatibility."""
    
    import_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://example.com/recipe'
        }),
        help_text="Paste a recipe URL to import (experimental feature)"
    )
    
    import_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Or paste recipe text here...'
        }),
        help_text="Paste recipe text to parse and import"
    )
    
    def clean(self):
        """Ensure at least one import method is provided."""
        cleaned_data = super().clean()
        import_url = cleaned_data.get('import_url')
        import_text = cleaned_data.get('import_text')
        
        if not import_url and not import_text:
            raise ValidationError(
                "Please provide either a URL or recipe text to import."
            )
        
        if import_url and import_text:
            raise ValidationError(
                "Please provide either a URL or recipe text, not both."
            )
        
        return cleaned_data








# Add this import at the top
from django.core.validators import FileExtensionValidator

# Add this form class at the end of the file
class RecipeCSVUploadForm(forms.Form):
    """
    Form for uploading recipes via CSV file.
    
    Validates file type and size for CSV uploads.
    """
    
    csv_file = forms.FileField(
        label="Select CSV File",
        help_text="Upload a CSV file containing recipes. Max size: 5MB",
        validators=[FileExtensionValidator(allowed_extensions=['csv'])],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    
    import_as_public = forms.BooleanField(
        required=False,
        initial=False,
        label="Make imported recipes public",
        help_text="Check this to make all imported recipes visible to other users",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    skip_errors = forms.BooleanField(
        required=False,
        initial=True,
        label="Skip recipes with errors",
        help_text="Continue importing valid recipes even if some have errors",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def clean_csv_file(self):
        """Validate the uploaded CSV file."""
        csv_file = self.cleaned_data.get('csv_file')
        
        if csv_file:
            # Check file size (5MB limit)
            if csv_file.size > 5 * 1024 * 1024:
                raise forms.ValidationError(
                    "CSV file size cannot exceed 5MB. Please split large files."
                )
            
            # Check if file is readable
            try:
                # Read first few bytes to ensure it's readable
                csv_file.seek(0)
                sample = csv_file.read(1024)
                csv_file.seek(0)  # Reset file pointer
                
                # Basic CSV validation - check for common delimiters
                if isinstance(sample, bytes):
                    sample = sample.decode('utf-8-sig', errors='ignore')
                
                if not any(delimiter in sample for delimiter in [',', ';', '\t']):
                    raise forms.ValidationError(
                        "File doesn't appear to be a valid CSV file."
                    )
                    
            except Exception as e:
                logger.error(f"CSV file validation error: {str(e)}")
                raise forms.ValidationError(
                    "Unable to read the CSV file. Please ensure it's a valid CSV."
                )
        
        return csv_file
    

class UserIngredientCategoryForm(forms.ModelForm):
    """Form for users to create custom categories."""
    
    class Meta:
        model = IngredientCategory
        fields = ['name', 'keywords']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Category name (e.g., Organic, Gluten-Free)'
            }),
            'keywords': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter keywords separated by commas (e.g., organic, fresh, natural)'
            })
        }