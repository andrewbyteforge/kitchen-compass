"""
CSV Upload Views for Admin Users

Handles CSV upload, preview, and processing for recipe imports.
"""

import csv
import io
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView

from meal_planner.forms.csv_upload import RecipeCSVUploadForm, CSVPreviewForm
from meal_planner.models import RecipeCSVUpload
from meal_planner.utils.csv_processor import RecipeCSVProcessor

logger = logging.getLogger(__name__)


def is_admin_user(user):
    """Check if user is admin or staff."""
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_admin_user), name='dispatch')
class CSVUploadView(View):
    """
    Handle CSV file uploads for recipes.
    
    Admin-only view for uploading recipe CSV files.
    """
    
    template_name = 'meal_planner/admin/csv_upload.html'
    
    def get(self, request):
        """Display upload form."""
        form = RecipeCSVUploadForm()
        
        # Get recent uploads
        recent_uploads = RecipeCSVUpload.objects.filter(
            uploaded_by=request.user
        ).order_by('-uploaded_at')[:5]
        
        context = {
            'form': form,
            'recent_uploads': recent_uploads,
            'sample_csv_url': reverse('meal_planner:csv_sample')
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Handle file upload."""
        form = RecipeCSVUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Save upload record
                csv_upload = form.save(commit=False)
                csv_upload.uploaded_by = request.user
                csv_upload.save()
                
                # Store row count from validation
                if hasattr(form, 'total_rows'):
                    csv_upload.total_rows = form.total_rows
                    csv_upload.save()
                
                logger.info(f"CSV file uploaded by {request.user.username}: {csv_upload.filename}")
                
                # Redirect to preview
                return redirect('meal_planner:csv_preview', upload_id=csv_upload.id)
                
            except Exception as e:
                logger.error(f"Error saving CSV upload: {str(e)}")
                messages.error(request, f"Error saving upload: {str(e)}")
                return redirect('meal_planner:csv_upload')
        
        # Form is invalid
        recent_uploads = RecipeCSVUpload.objects.filter(
            uploaded_by=request.user
        ).order_by('-uploaded_at')[:5]
        
        context = {
            'form': form,
            'recent_uploads': recent_uploads,
            'sample_csv_url': reverse('meal_planner:csv_sample')
        }
        
        return render(request, self.template_name, context)


@login_required
@user_passes_test(is_admin_user)
def csv_preview_view(request, upload_id):
    """
    Preview CSV content before processing.
    
    Shows a sample of recipes that will be imported.
    """
    csv_upload = get_object_or_404(RecipeCSVUpload, id=upload_id, uploaded_by=request.user)
    
    if csv_upload.status != 'pending':
        messages.warning(request, "This CSV has already been processed.")
        return redirect('meal_planner:csv_history')
    
    # Read and parse CSV for preview
    preview_data = []
    errors = []
    
    try:
        csv_upload.file.seek(0)
        content = csv_upload.file.read()
        
        # Decode content
        decoded_content = None
        for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            try:
                decoded_content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if decoded_content:
            csv_reader = csv.DictReader(io.StringIO(decoded_content))
            
            # Get first 10 rows for preview
            for i, row in enumerate(csv_reader):
                if i >= 10:
                    break
                preview_data.append(row)
    
    except Exception as e:
        logger.error(f"Error reading CSV for preview: {str(e)}")
        errors.append(f"Error reading file: {str(e)}")
    
    if request.method == 'POST':
        form = CSVPreviewForm(request.POST)
        if form.is_valid() and form.cleaned_data['confirm']:
            # Process the CSV
            return redirect('meal_planner:csv_process', upload_id=csv_upload.id)
    else:
        form = CSVPreviewForm(initial={'upload_id': csv_upload.id})
    
    context = {
        'csv_upload': csv_upload,
        'preview_data': preview_data,
        'errors': errors,
        'form': form,
        'column_count': len(preview_data[0]) if preview_data else 0
    }
    
    return render(request, 'meal_planner/admin/csv_preview.html', context)


@login_required
@user_passes_test(is_admin_user)
def csv_process_view(request, upload_id):
    """
    Process the CSV file and create recipes.
    
    This is the actual import process.
    """
    csv_upload = get_object_or_404(RecipeCSVUpload, id=upload_id, uploaded_by=request.user)
    
    if csv_upload.status != 'pending':
        messages.warning(request, "This CSV has already been processed.")
        return redirect('meal_planner:csv_history')
    
    try:
        # Update status
        csv_upload.status = 'processing'
        csv_upload.save()
        
        # Process the CSV
        processor = RecipeCSVProcessor(csv_upload, request.user)
        success_count, failed_count, errors = processor.process()
        
        # Show results
        if success_count > 0:
            messages.success(
                request, 
                f"Successfully imported {success_count} recipes!"
            )
        
        if failed_count > 0:
            messages.warning(
                request,
                f"{failed_count} recipes failed to import. Check the error log for details."
            )
        
        return redirect('meal_planner:csv_result', upload_id=csv_upload.id)
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        messages.error(request, f"Error processing CSV: {str(e)}")
        
        # Update status
        csv_upload.status = 'failed'
        csv_upload.save()
        
        return redirect('meal_planner:csv_history')


@login_required
@user_passes_test(is_admin_user)
def csv_result_view(request, upload_id):
    """
    Show results of CSV processing.
    
    Displays success/failure counts and error details.
    """
    csv_upload = get_object_or_404(RecipeCSVUpload, id=upload_id, uploaded_by=request.user)
    
    # Parse error log
    errors = []
    if csv_upload.error_log:
        errors = csv_upload.error_log.get('errors', [])
    
    context = {
        'csv_upload': csv_upload,
        'errors': errors,
        'has_errors': len(errors) > 0
    }
    
    return render(request, 'meal_planner/admin/csv_result.html', context)


@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_admin_user), name='dispatch')
class CSVHistoryView(ListView):
    """
    View upload history.
    
    Shows all CSV uploads by the current admin user.
    """
    
    model = RecipeCSVUpload
    template_name = 'meal_planner/admin/csv_history.html'
    context_object_name = 'uploads'
    paginate_by = 20
    
    def get_queryset(self):
        """Get uploads for current user."""
        return RecipeCSVUpload.objects.filter(
            uploaded_by=self.request.user
        ).order_by('-uploaded_at')


@login_required
@user_passes_test(is_admin_user)
def csv_sample_download(request):
    """
    Download a sample CSV file.
    
    Provides a template CSV with example data.
    """
    import csv
    from django.http import HttpResponse
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="recipe_import_sample.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write headers
    headers = [
        'title', 'description', 'prep_time', 'cook_time', 'servings', 
        'difficulty', 'categories', 'meal_types', 'ingredients', 'instructions',
        'is_public', 'dietary_info'
    ]
    writer.writerow(headers)
    
    # Write sample rows
    sample_rows = [
        [
            'Classic Pancakes',
            'Fluffy homemade pancakes perfect for breakfast',
            '10',
            '15',
            '4',
            'easy',
            'Breakfast,American',
            'Breakfast',
            '2 cups flour, 2 tbsp sugar, 2 tsp baking powder, 1 tsp salt, 2 eggs, 1.5 cups milk, 3 tbsp melted butter',
            'Mix dry ingredients|Whisk wet ingredients separately|Combine wet and dry ingredients|Cook on griddle until bubbles form|Flip and cook until golden',
            'true',
            '{"tags": ["vegetarian", "kid-friendly"]}'
        ],
        [
            'Garden Salad',
            'Fresh and healthy garden salad with vinaigrette',
            '15',
            '0',
            '2',
            'easy',
            'Salads,Healthy',
            'Lunch,Dinner',
            '4 cups mixed greens, 1 cucumber, 2 tomatoes, 1/4 red onion, 1/2 cup croutons, 3 tbsp olive oil, 1 tbsp vinegar',
            'Wash and chop vegetables|Combine in large bowl|Mix oil and vinegar for dressing|Toss salad with dressing|Top with croutons',
            'true',
            'vegan,gluten-free'
        ]
    ]
    
    for row in sample_rows:
        writer.writerow(row)
    
    return response