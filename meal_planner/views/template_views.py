"""
Template Views - Template Management and Calendar Sync Features

This module contains views for meal plan templates and calendar synchronization
with external services like Microsoft Outlook.
"""

import json
import logging
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView

from auth_hub.models import ActivityLog
from ..models import MealPlan, MealSlot, MealType, MealPlanTemplate
from ..forms import MealPlanTemplateForm, ApplyTemplateForm

logger = logging.getLogger(__name__)


class MealPlanTemplateListView(LoginRequiredMixin, ListView):
    """
    List view for meal plan templates.
    """
    model = MealPlanTemplate
    template_name = 'meal_planner/template_list.html'
    context_object_name = 'templates'
    paginate_by = 12
    
    def get_queryset(self):
        """Get templates available to user."""
        return MealPlanTemplate.objects.filter(
            Q(owner=self.request.user) | Q(is_public=True)
        ).select_related('owner').annotate(
            slot_count=Count('template_slots')
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add user's templates count to context."""
        context = super().get_context_data(**kwargs)
        context['user_templates_count'] = MealPlanTemplate.objects.filter(
            owner=self.request.user
        ).count()
        return context


@method_decorator(login_required, name='dispatch')
class MealPlanTemplateCreateView(CreateView):
    """
    Create a new meal plan template.
    """
    model = MealPlanTemplate
    form_class = MealPlanTemplateForm
    template_name = 'meal_planner/template_form.html'
    success_url = reverse_lazy('meal_planner:template_list')
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Set owner and create template."""
        form.instance.owner = self.request.user
        
        try:
            response = super().form_valid(form)
            
            # Log activity
            ActivityLog.objects.create(
                user=self.request.user,
                action='create_template',
                details=f"Created template: {self.object.name}"
            )
            
            messages.success(
                self.request,
                f"Template '{self.object.name}' created successfully!"
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error creating template for user {self.request.user.username}: {str(e)}"
            )
            messages.error(
                self.request,
                "An error occurred while creating the template."
            )
            return self.form_invalid(form)


@method_decorator(login_required, name='dispatch')
class MealPlanTemplateUpdateView(UserPassesTestMixin, UpdateView):
    """
    Update an existing meal plan template.
    """
    model = MealPlanTemplate
    form_class = MealPlanTemplateForm
    template_name = 'meal_planner/template_form.html'
    success_url = reverse_lazy('meal_planner:template_list')
    
    def test_func(self):
        """Check if user owns this template."""
        template = self.get_object()
        return template.owner == self.request.user
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Update template."""
        try:
            response = super().form_valid(form)
            
            # Log activity
            ActivityLog.objects.create(
                user=self.request.user,
                action='update_template',
                details=f"Updated template: {self.object.name}"
            )
            
            messages.success(
                self.request,
                f"Template '{self.object.name}' updated successfully!"
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error updating template for user {self.request.user.username}: {str(e)}"
            )
            messages.error(
                self.request,
                "An error occurred while updating the template."
            )
            return self.form_invalid(form)


@method_decorator(login_required, name='dispatch')
class MealPlanTemplateDeleteView(UserPassesTestMixin, DeleteView):
    """
    Delete a meal plan template.
    """
    model = MealPlanTemplate
    template_name = 'meal_planner/template_confirm_delete.html'
    success_url = reverse_lazy('meal_planner:template_list')
    
    def test_func(self):
        """Check if user owns this template."""
        template = self.get_object()
        return template.owner == self.request.user
    
    def delete(self, request, *args, **kwargs):
        """Log deletion and show success message."""
        template = self.get_object()
        template_name = template.name
        
        try:
            # Log activity
            ActivityLog.objects.create(
                user=request.user,
                action='delete_template',
                details=f"Deleted template: {template_name}"
            )
            
            response = super().delete(request, *args, **kwargs)
            
            messages.success(
                request,
                f"Template '{template_name}' deleted successfully."
            )
            
            return response
            
        except Exception as e:
            logger.error(
                f"Error deleting template {template.pk} for user "
                f"{request.user.username}: {str(e)}"
            )
            messages.error(
                request,
                "An error occurred while deleting the template."
            )
            return redirect('meal_planner:template_list')


@login_required
def apply_template(request):
    """
    Apply a template to create a new meal plan.
    """
    if request.method == 'POST':
        form = ApplyTemplateForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                template = form.cleaned_data['template']
                start_date = form.cleaned_data['start_date']
                name = form.cleaned_data.get('name') or None
                
                # Check if user can create meal plan
                try:
                    profile = request.user.profile
                    subscription_tier = profile.subscription_tier
                    
                    if subscription_tier.max_menus != -1:
                        active_count = MealPlan.objects.filter(
                            owner=request.user,
                            is_active=True
                        ).count()
                        if active_count >= subscription_tier.max_menus:
                            messages.error(
                                request,
                                f"You've reached your meal plan limit ({subscription_tier.max_menus})."
                            )
                            return redirect('meal_planner:template_list')
                except Exception as e:
                    logger.warning(f"Error checking meal plan limits: {str(e)}")
                    # Continue anyway
                
                # Create meal plan from template
                meal_plan = template.create_meal_plan(start_date, name)
                
                # Log activity
                ActivityLog.objects.create(
                    user=request.user,
                    action='apply_template',
                    details=f"Created meal plan from template: {template.name}"
                )
                
                messages.success(
                    request,
                    f"Meal plan created from template '{template.name}'!"
                )
                
                return redirect('meal_planner:meal_plan_detail', pk=meal_plan.pk)
                
            except Exception as e:
                logger.error(
                    f"Error applying template for user {request.user.username}: {str(e)}"
                )
                messages.error(request, "An error occurred while applying the template.")
    else:
        form = ApplyTemplateForm(user=request.user)
    
    return render(request, 'meal_planner/apply_template.html', {
        'form': form
    })


@login_required
def create_meal_slots_for_plan(request):
    """
    Create meal slots for an existing meal plan.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body)
        meal_plan_id = data.get('meal_plan_id')
        
        if not meal_plan_id:
            return JsonResponse({'success': False, 'error': 'meal_plan_id required'})
        
        # Get the meal plan
        meal_plan = get_object_or_404(MealPlan, id=meal_plan_id, owner=request.user)
        
        # Get all meal types
        meal_types = MealType.objects.all().order_by('display_order')
        
        if not meal_types.exists():
            # Create default meal types if none exist
            meal_types = [
                MealType.objects.create(name='Breakfast', display_order=1),
                MealType.objects.create(name='Lunch', display_order=2),
                MealType.objects.create(name='Dinner', display_order=3),
                MealType.objects.create(name='Snack', display_order=4),
            ]
        
        # Create meal slots for each day and meal type
        created_count = 0
        current_date = meal_plan.start_date
        
        while current_date <= meal_plan.end_date:
            for meal_type in meal_types:
                # Create slot if it doesn't exist
                slot, created = MealSlot.objects.get_or_create(
                    meal_plan=meal_plan,
                    date=current_date,
                    meal_type=meal_type,
                    defaults={
                        'servings': 1,
                        'notes': ''
                    }
                )
                if created:
                    created_count += 1
            
            current_date += timedelta(days=1)
        
        logger.info(f"Created {created_count} meal slots for plan {meal_plan.name}")
        
        return JsonResponse({
            'success': True, 
            'message': f'Created {created_count} meal slots',
            'created_count': created_count
        })
        
    except Exception as e:
        logger.error(f"Error creating meal slots: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})


@method_decorator(login_required, name='dispatch')
class CalendarSyncSettingsView(TemplateView):
    """
    View for managing calendar synchronization settings.
    """
    template_name = 'meal_planner/calendar_sync_settings.html'
    
    def get_context_data(self, **kwargs):
        """Add calendar sync data to context."""
        context = super().get_context_data(**kwargs)
        
        # Check if Microsoft account is connected
        context['microsoft_connected'] = hasattr(
            self.request.user, 
            'microsoft_token'
        )
        
        if context['microsoft_connected']:
            token = self.request.user.microsoft_token
            context['sync_enabled'] = token.calendar_sync_enabled
            context['last_sync'] = token.last_sync
            
            # Get sync statistics
            try:
                from ..models import CalendarEvent
                context['synced_events'] = CalendarEvent.objects.filter(
                    user=self.request.user,
                    sync_status='synced'
                ).count()
                
                context['pending_events'] = CalendarEvent.objects.filter(
                    user=self.request.user,
                    sync_status='pending'
                ).count()
                
                context['error_events'] = CalendarEvent.objects.filter(
                    user=self.request.user,
                    sync_status='error'
                ).count()
            except ImportError:
                # CalendarEvent model doesn't exist yet
                context['synced_events'] = 0
                context['pending_events'] = 0
                context['error_events'] = 0
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle enabling/disabling sync."""
        if hasattr(request.user, 'microsoft_token'):
            token = request.user.microsoft_token
            action = request.POST.get('action')
            
            if action == 'enable':
                token.calendar_sync_enabled = True
                token.save()
                messages.success(request, "Calendar sync enabled!")
                
                # Trigger immediate sync
                try:
                    from ..tasks import sync_user_calendar
                    sync_user_calendar.delay(request.user.id)
                except ImportError:
                    logger.warning("Calendar sync tasks not available")
                
            elif action == 'disable':
                token.calendar_sync_enabled = False
                token.save()
                messages.info(request, "Calendar sync disabled.")
            
            elif action == 'sync_now':
                # Trigger manual sync
                try:
                    from ..tasks import sync_user_calendar
                    sync_user_calendar.delay(request.user.id)
                    messages.info(request, "Calendar sync started. Check back in a few moments.")
                except ImportError:
                    messages.warning(request, "Calendar sync is not available.")
        
        return redirect('meal_planner:calendar_sync_settings')


@login_required
def sync_meal_plan(request, pk):
    """
    Sync a specific meal plan to Outlook calendar.
    
    Args:
        request: HTTP request
        pk: Primary key of the meal plan
        
    Returns:
        JSON response with sync status
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST request required'})
    
    try:
        # Get the meal plan
        meal_plan = get_object_or_404(MealPlan, pk=pk, owner=request.user)
        
        # Check if user has Microsoft account connected
        if not hasattr(request.user, 'microsoft_token'):
            return JsonResponse({
                'success': False,
                'error': 'Please connect your Microsoft account first',
                'redirect': reverse('meal_planner:calendar_sync_settings')
            })
        
        # Check if sync is enabled
        if not request.user.microsoft_token.calendar_sync_enabled:
            return JsonResponse({
                'success': False,
                'error': 'Calendar sync is disabled. Please enable it in settings.',
                'redirect': reverse('meal_planner:calendar_sync_settings')
            })
        
        # Import and trigger sync task
        try:
            from ..tasks import sync_meal_plan_to_outlook
            
            # For immediate feedback, we'll use a synchronous approach
            # In production, you might want to use Celery for async processing
            result = sync_meal_plan_to_outlook(meal_plan.id, request.user.id)
            
            if result['success']:
                # Log the sync
                ActivityLog.objects.create(
                    user=request.user,
                    action='outlook_sync',
                    details=f"Synced meal plan '{meal_plan.name}' to Outlook"
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f"Successfully synced {result['events_created']} meals to Outlook!",
                    'details': result
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Sync failed')
                })
        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'Calendar sync functionality is not available'
            })
            
    except Exception as e:
        logger.error(f"Error syncing meal plan {pk}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while syncing'
        })


@login_required
def outlook_sync_status(request):
    """
    Get the current Outlook sync status for the user.
    
    Returns:
        JSON response with sync status information
    """
    try:
        status = {
            'connected': hasattr(request.user, 'microsoft_token'),
            'sync_enabled': False,
            'last_sync': None,
            'events_count': 0
        }
        
        if status['connected']:
            token = request.user.microsoft_token
            status['sync_enabled'] = token.calendar_sync_enabled
            status['last_sync'] = token.last_sync.isoformat() if token.last_sync else None
            
            # Get event counts
            try:
                from ..models import CalendarEvent
                status['events_count'] = CalendarEvent.objects.filter(
                    user=request.user,
                    sync_status='synced'
                ).count()
            except ImportError:
                status['events_count'] = 0
        
        return JsonResponse(status)
        
    except Exception as e:
        logger.error(f"Error getting sync status: {str(e)}")
        return JsonResponse({'error': 'Failed to get sync status'}, status=500)


@login_required
def sync_all_meal_plans(request):
    """
    Sync all active meal plans to Outlook calendar.
    
    Returns:
        JSON response with sync results
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST request required'})
    
    try:
        # Check if user has Microsoft account connected
        if not hasattr(request.user, 'microsoft_token'):
            return JsonResponse({
                'success': False,
                'error': 'Please connect your Microsoft account first',
                'redirect': reverse('meal_planner:calendar_sync_settings')
            })
        
        # Check if sync is enabled
        if not request.user.microsoft_token.calendar_sync_enabled:
            return JsonResponse({
                'success': False,
                'error': 'Calendar sync is disabled. Please enable it in settings.',
                'redirect': reverse('meal_planner:calendar_sync_settings')
            })
        
        # Get all active meal plans for the user
        active_meal_plans = MealPlan.objects.filter(
            owner=request.user,
            is_active=True,
            end_date__gte=timezone.now().date()  # Only sync current/future plans
        )
        
        if not active_meal_plans.exists():
            return JsonResponse({
                'success': False,
                'error': 'No active meal plans to sync'
            })
        
        # Import sync function
        try:
            from ..tasks import sync_meal_plan_to_outlook
            
            total_results = {
                'plans_synced': 0,
                'total_events_created': 0,
                'total_events_updated': 0,
                'errors': []
            }
            
            # Sync each active meal plan
            for meal_plan in active_meal_plans:
                try:
                    result = sync_meal_plan_to_outlook(meal_plan.id, request.user.id)
                    
                    if result['success']:
                        total_results['plans_synced'] += 1
                        total_results['total_events_created'] += result.get('events_created', 0)
                        total_results['total_events_updated'] += result.get('events_updated', 0)
                    else:
                        total_results['errors'].append(f"{meal_plan.name}: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    logger.error(f"Error syncing meal plan {meal_plan.id}: {str(e)}")
                    total_results['errors'].append(f"{meal_plan.name}: {str(e)}")
            
            # Log the sync
            ActivityLog.objects.create(
                user=request.user,
                action='outlook_sync_all',
                details=f"Synced {total_results['plans_synced']} meal plans to Outlook"
            )
            
            # Prepare response
            if total_results['plans_synced'] > 0:
                message = (
                    f"Successfully synced {total_results['plans_synced']} meal plan(s)! "
                    f"Created {total_results['total_events_created']} events, "
                    f"updated {total_results['total_events_updated']} events."
                )
                
                if total_results['errors']:
                    message += f" Some plans had errors: {len(total_results['errors'])}"
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'details': total_results
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to sync any meal plans',
                    'details': total_results
                })
        except ImportError:
            return JsonResponse({
                'success': False,
                'error': 'Calendar sync functionality is not available'
            })
            
    except Exception as e:
        logger.error(f"Error in sync_all_meal_plans: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while syncing'
        })


@login_required
def microsoft_switch_account(request):
    """
    Switch Microsoft account by disconnecting current and reconnecting.
    """
    try:
        # Delete existing token if it exists
        if hasattr(request.user, 'microsoft_token'):
            request.user.microsoft_token.delete()
            logger.info(f"Disconnected Microsoft account for user {request.user.username}")
        
        # Redirect to connect with forced account selection
        return redirect('auth_hub:microsoft_login')
        
    except Exception as e:
        logger.error(f"Error switching Microsoft account: {str(e)}")
        messages.error(request, "Error switching accounts. Please try again.")
        return redirect('meal_planner:calendar_sync_settings')


@login_required
def get_connected_account(request):
    """
    Get the connected Microsoft account details.
    """
    try:
        if hasattr(request.user, 'microsoft_token'):
            try:
                from auth_hub.services.microsoft_auth import OutlookCalendarService
                service = OutlookCalendarService(request.user)
                
                import requests
                headers = {'Authorization': f'Bearer {service.access_token}'}
                response = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return JsonResponse({
                        'email': data.get('mail') or data.get('userPrincipalName'),
                        'name': data.get('displayName'),
                        'connected': True
                    })
            except ImportError:
                logger.warning("Microsoft auth service not available")
        
        return JsonResponse({'connected': False})
        
    except Exception as e:
        logger.error(f"Error getting connected account: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)