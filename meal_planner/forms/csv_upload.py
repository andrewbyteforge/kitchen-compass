"""
CSV Upload Forms for Meal Planner

Handles CSV file uploads and validation.
"""

import csv
import io
import logging
from django import forms
from django.core.exceptions import ValidationError
from meal_planner.models import RecipeCSVUpload

logger = logging.getLogger(__name__)


class RecipeCSVUploadForm(forms.ModelForm):
    """
    Form for uploading recipe CSV files.
    
    Validates CSV format and provides preview functionality.
    """
    
    # Define expected CSV columns
    REQUIRED_COLUMNS = [
        'title',
        'description',
        'prep_time',
        'cook_time',
        'servings',
        'difficulty',
    ]
    
    OPTIONAL_COLUMNS = [
        'categories',  # Comma-separated
        'meal_types',  # Comma-separated (breakfast, lunch, dinner, snack)
        'ingredients',  # Special format: "quantity unit name, quantity unit name"
        'instructions',  # Numbered steps separated by |
        'image_url',
        'is_public',
        'dietary_info',  # JSON or comma-separated tags
    ]
    
    class Meta:
        model = RecipeCSVUpload
        fields = ['file', 'notes']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv',
                'id': 'csvFileInput'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional notes about this upload...'
            })
        }
    
    def clean_file(self):
        """
        Validate CSV file format and content.
        """
        file = self.cleaned_data.get('file')
        
        if not file:
            raise ValidationError("Please select a CSV file.")
        
        # Check file size (max 10MB)
        if file.size > 10 * 1024 * 1024:
            raise ValidationError("File size cannot exceed 10MB.")
        
        # Read and validate CSV content
        try:
            # Read file content
            file.seek(0)
            content = file.read()
            
            # Try to decode with different encodings
            decoded_content = None
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                try:
                    decoded_content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if not decoded_content:
                raise ValidationError("Unable to decode CSV file. Please ensure it's properly encoded.")
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(decoded_content))
            
            # Check headers
            if not csv_reader.fieldnames:
                raise ValidationError("CSV file appears to be empty.")
            
            headers = [h.strip().lower() for h in csv_reader.fieldnames]
            
            # Check for required columns
            missing_columns = []
            for col in self.REQUIRED_COLUMNS:
                if col.lower() not in headers:
                    missing_columns.append(col)
            
            if missing_columns:
                raise ValidationError(
                    f"Missing required columns: {', '.join(missing_columns)}"
                )
            
            # Validate first few rows
            row_count = 0
            sample_errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                row_count += 1
                
                # Basic validation for first 5 rows
                if row_count <= 5:
                    errors = self._validate_row(row, row_num)
                    if errors:
                        sample_errors.extend(errors)
                
                # Don't process entire file during validation
                if row_count >= 100:
                    break
            
            if sample_errors:
                error_msg = "Sample validation errors found:\n"
                error_msg += "\n".join(sample_errors[:5])  # Show first 5 errors
                if len(sample_errors) > 5:
                    error_msg += f"\n... and {len(sample_errors) - 5} more errors"
                raise ValidationError(error_msg)
            
            # Reset file pointer
            file.seek(0)
            
            # Store row count for later use
            self.total_rows = row_count
            
        except csv.Error as e:
            raise ValidationError(f"Invalid CSV format: {str(e)}")
        except Exception as e:
            logger.error(f"Error validating CSV: {str(e)}")
            raise ValidationError(f"Error processing CSV file: {str(e)}")
        
        return file
    
    def _validate_row(self, row, row_num):
        """
        Validate a single CSV row.
        
        Returns list of error messages.
        """
        errors = []
        
        # Check required fields
        for field in self.REQUIRED_COLUMNS:
            if not row.get(field, '').strip():
                errors.append(f"Row {row_num}: Missing required field '{field}'")
        
        # Validate numeric fields
        try:
            prep_time = int(row.get('prep_time', '0'))
            if prep_time < 0:
                errors.append(f"Row {row_num}: Prep time must be positive")
        except ValueError:
            errors.append(f"Row {row_num}: Invalid prep time (must be a number)")
        
        try:
            cook_time = int(row.get('cook_time', '0'))
            if cook_time < 0:
                errors.append(f"Row {row_num}: Cook time must be positive")
        except ValueError:
            errors.append(f"Row {row_num}: Invalid cook time (must be a number)")
        
        try:
            servings = int(row.get('servings', '1'))
            if servings < 1 or servings > 50:
                errors.append(f"Row {row_num}: Servings must be between 1 and 50")
        except ValueError:
            errors.append(f"Row {row_num}: Invalid servings (must be a number)")
        
        # Validate difficulty
        difficulty = row.get('difficulty', '').lower()
        if difficulty and difficulty not in ['easy', 'medium', 'hard']:
            errors.append(f"Row {row_num}: Invalid difficulty (must be easy, medium, or hard)")
        
        return errors


class CSVPreviewForm(forms.Form):
    """
    Form for previewing and confirming CSV import.
    """
    
    upload_id = forms.IntegerField(widget=forms.HiddenInput())
    confirm = forms.BooleanField(
        required=True,
        label="I have reviewed the preview and want to import these recipes",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )