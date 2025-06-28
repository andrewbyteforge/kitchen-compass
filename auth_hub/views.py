"""
Views for the AuthHub application.

This module contains views for user authentication, dashboard,
profile management, and menu sharing functionality.
"""

import logging
import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import CreateView, UpdateView, ListView, DetailView


from .forms import (
    CustomUserCreationForm,
    UserProfileForm,
    MenuShareForm,
    SubscriptionUpgradeForm
)
from .models import (
    UserProfile,
    SubscriptionTier,
    MenuShare,
    ActivityLog
)

logger = logging.getLogger(__name__)


def log_activity(user, action, details=None, request=None):
    """
    Helper function to log user activities.
    
    Args:
        user: The user performing the action
        action: The action being performed
        details: Additional details about the action
        request: The HTTP request object (for IP and user agent)
    """
    activity = ActivityLog(
        user=user,
        action=action,
        details=details or {}
    )
    
    if request:
        # Get IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            activity.ip_address = x_forwarded_for.split(',')[0]
        else:
            activity.ip_address = request.META.get('REMOTE_ADDR')
        
        # Get user agent
        activity.user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    activity.save()
    logger.info(f"Activity logged: {user.email} - {action}")


class CustomLoginView(LoginView):
    """
    Custom login view with activity logging.
    
    Extends Django's LoginView to add logging and custom redirects.
    """
    
    template_name = 'login.html'
    redirect_authenticated_user = True
    
    def form_valid(self, form):
        """Log successful login."""
        response = super().form_valid(form)
        log_activity(
            self.request.user,
            'login',
            {'method': 'email_password'},
            self.request
        )
        messages.success(self.request, f'Welcome back, {self.request.user.first_name}!')
        return response
    
    def get_success_url(self):
        """Redirect to dashboard after login."""
        return reverse('auth_hub:dashboard')


class CustomLogoutView(LogoutView):
    """
    Custom logout view with activity logging.
    
    Extends Django's LogoutView to add logging.
    """
    
    next_page = 'auth_hub:login'
    
    def dispatch(self, request, *args, **kwargs):
        """Log logout activity before processing."""
        if request.user.is_authenticated:
            log_activity(request.user, 'logout', request=request)
        response = super().dispatch(request, *args, **kwargs)
        messages.info(request, 'You have been successfully logged out.')
        return response


class RegisterView(CreateView):
    """
    User registration view.
    
    Handles new user registration with profile creation.
    """
    
    form_class = CustomUserCreationForm
    template_name = 'register.html'
    success_url = reverse_lazy('auth_hub:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        """Redirect authenticated users to dashboard."""
        if request.user.is_authenticated:
            return redirect('auth_hub:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Create user and log them in."""
        response = super().form_valid(form)
        
        # Log the user in
        user = authenticate(
            username=form.cleaned_data['email'],
            password=form.cleaned_data['password1']
        )
        login(self.request, user)
        
        # Log activity
        log_activity(
            user,
            'register',
            {
                'dietary_restrictions': form.cleaned_data.get('dietary_restrictions', [])
            },
            self.request
        )
        
        messages.success(
            self.request,
            f'Welcome to KitchenCompass, {user.first_name}! '
            f'Your account has been created successfully.'
        )
        
        return response


@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    """
    Main dashboard view for logged-in users.
    
    Displays user stats, recent menus, and subscription information.
    """
    
    template_name = 'dashboard.html'
    
    def get(self, request):
        """Display the dashboard."""
        profile = request.user.profile
        
        # Get recent activity
        recent_activities = ActivityLog.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]
        
        # Get shared menus (both sent and received)
        shared_by_me = MenuShare.objects.filter(
            owner=request.user,
            is_active=True
        ).order_by('-created_at')[:5]
        
        shared_with_me = MenuShare.objects.filter(
            shared_with_user=request.user,
            is_active=True,
            accepted_at__isnull=False
        ).order_by('-accepted_at')[:5]
        
        # Calculate stats
        stats = {
            'menus_created': profile.menus_created,
            'recipes_saved': profile.recipes_saved,
            'active_shares': shared_by_me.count(),
            'received_shares': shared_with_me.count(),
        }
        
        context = {
            'profile': profile,
            'stats': stats,
            'recent_activities': recent_activities,
            'shared_by_me': shared_by_me,
            'shared_with_me': shared_with_me,
            'can_share': profile.can_share_menus,
            'remaining_shares': profile.remaining_shares,
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class ProfileUpdateView(UpdateView):
    """
    View for updating user profile.
    
    Allows users to update their profile information and preferences.
    """
    
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'profile_update.html'
    success_url = reverse_lazy('auth_hub:dashboard')
    
    def get_object(self, queryset=None):
        """Get the current user's profile."""
        return self.request.user.profile
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Log profile update."""
        response = super().form_valid(form)
        
        log_activity(
            self.request.user,
            'profile_updated',
            {'fields_updated': list(form.changed_data)},
            self.request
        )
        
        messages.success(self.request, 'Your profile has been updated successfully.')
        return response


@method_decorator(login_required, name='dispatch')
class MenuShareCreateView(CreateView):
    """
    View for creating menu shares.
    
    Allows users to share their menus with others via email.
    """
    
    model = MenuShare
    form_class = MenuShareForm
    template_name = 'auth_hub/menu_share_create.html'
    success_url = reverse_lazy('auth_hub:dashboard')
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Send invitation email and log activity."""
        response = super().form_valid(form)
        share = form.instance
        
        # Send invitation email
        self._send_invitation_email(share, form.cleaned_data.get('message', ''))
        
        # Log activity
        log_activity(
            self.request.user,
            'menu_shared',
            {
                'shared_with': share.shared_with_email,
                'permissions': {
                    'view': share.can_view,
                    'edit': share.can_edit,
                    'reshare': share.can_reshare,
                }
            },
            self.request
        )
        
        messages.success(
            self.request,
            f'Invitation sent to {share.shared_with_email}. '
            f'They have 7 days to accept the invitation.'
        )
        
        return response
    
    def _send_invitation_email(self, share, personal_message):
        """Send invitation email to recipient."""
        accept_url = self.request.build_absolute_uri(
            reverse('auth_hub:menu_share_accept', kwargs={'token': share.token})
        )
        
        context = {
            'share': share,
            'sender': self.request.user,
            'personal_message': personal_message,
            'accept_url': accept_url,
            'expires_in_days': 7,
        }
        
        html_message = render_to_string('auth_hub/emails/menu_share_invitation.html', context)
        plain_message = render_to_string('auth_hub/emails/menu_share_invitation.txt', context)
        
        send_mail(
            subject=f'{self.request.user.get_full_name()} wants to share their KitchenCompass menus with you',
            message=plain_message,
            from_email=None,  # Use DEFAULT_FROM_EMAIL
            recipient_list=[share.shared_with_email],
            html_message=html_message,
            fail_silently=False,
        )


@method_decorator(login_required, name='dispatch')
class MenuShareListView(ListView):
    """
    View for listing menu shares.
    
    Displays both sent and received menu shares.
    """
    
    model = MenuShare
    template_name = 'auth_hub/menu_share_list.html'
    context_object_name = 'shares'
    paginate_by = 20
    
    def get_queryset(self):
        """Get shares based on view type."""
        view_type = self.kwargs.get('view_type', 'sent')
        
        if view_type == 'sent':
            return MenuShare.objects.filter(
                owner=self.request.user
            ).order_by('-created_at')
        else:  # received
            return MenuShare.objects.filter(
                Q(shared_with_email=self.request.user.email) |
                Q(shared_with_user=self.request.user)
            ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        """Add view type to context."""
        context = super().get_context_data(**kwargs)
        context['view_type'] = self.kwargs.get('view_type', 'sent')
        return context


class MenuShareAcceptView(View):
    """
    View for accepting menu share invitations.
    
    Handles the acceptance of menu share invitations via token.
    """
    
    def get(self, request, token):
        """Display invitation details."""
        share = get_object_or_404(MenuShare, token=token)
        
        # Check if invitation is valid
        if not share.is_active:
            messages.error(request, 'This invitation has been revoked.')
            return redirect('auth_hub:login')
        
        if share.is_expired:
            messages.error(request, 'This invitation has expired.')
            return redirect('auth_hub:login')
        
        if share.accepted_at:
            messages.info(request, 'This invitation has already been accepted.')
            return redirect('auth_hub:dashboard' if request.user.is_authenticated else 'auth_hub:login')
        
        context = {
            'share': share,
            'is_authenticated': request.user.is_authenticated,
            'is_correct_user': request.user.is_authenticated and request.user.email == share.shared_with_email,
        }
        
        return render(request, 'auth_hub/menu_share_accept.html', context)
    
    @method_decorator(login_required)
    def post(self, request, token):
        """Accept the invitation."""
        share = get_object_or_404(MenuShare, token=token)
        
        # Validate
        if request.user.email != share.shared_with_email:
            messages.error(request, 'This invitation was sent to a different email address.')
            return redirect('auth_hub:dashboard')
        
        if not share.is_active or share.is_expired:
            messages.error(request, 'This invitation is no longer valid.')
            return redirect('auth_hub:dashboard')
        
        # Accept invitation
        share.accept_invitation(request.user)
        
        # Log activity
        log_activity(
            request.user,
            'menu_accepted',
            {'from_user': share.owner.email},
            request
        )
        
        messages.success(
            request,
            f'You now have access to {share.owner.get_full_name()}\'s menus!'
        )
        
        return redirect('auth_hub:dashboard')


@method_decorator(login_required, name='dispatch')
class MenuShareRevokeView(View):
    """
    View for revoking menu shares.
    
    Allows users to revoke access to their shared menus.
    """
    
    def post(self, request, pk):
        """Revoke the share."""
        share = get_object_or_404(MenuShare, pk=pk, owner=request.user)
        
        if not share.is_active:
            messages.info(request, 'This share has already been revoked.')
        else:
            share.revoke()
            messages.success(
                request,
                f'Menu access for {share.shared_with_email} has been revoked.'
            )
        
        return redirect('auth_hub:menu_share_list', view_type='sent')


@method_decorator(login_required, name='dispatch')
class SubscriptionView(DetailView):
    """
    View for displaying subscription details.
    
    Shows current subscription and available upgrades.
    """
    
    model = UserProfile
    template_name = 'subscription_detail.html'
    context_object_name = 'profile'
    
    def get_object(self, queryset=None):
        """Get current user's profile."""
        return self.request.user.profile
    
    def get_context_data(self, **kwargs):
        """Add subscription tiers to context."""
        context = super().get_context_data(**kwargs)
        context['all_tiers'] = SubscriptionTier.objects.filter(
            is_active=True
        ).order_by('price')
        context['current_tier'] = self.object.subscription_tier
        return context


@method_decorator(login_required, name='dispatch')
class SubscriptionUpgradeView(View):
    """
    View for upgrading or downgrading subscription.
    
    Handles subscription tier changes (Stripe integration placeholder).
    """
    
    template_name = 'subscription_upgrade.html'
    
    def get(self, request):
        """Display upgrade/downgrade options."""
        form = SubscriptionUpgradeForm(user=request.user)
        profile = request.user.profile
        
        # Check if user has pending downgrade
        pending_downgrade = None
        if hasattr(profile, 'pending_subscription_tier') and profile.pending_subscription_tier:
            pending_downgrade = profile.pending_subscription_tier
        
        context = {
            'form': form,
            'current_tier': profile.subscription_tier,
            'pending_downgrade': pending_downgrade,
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        """Process upgrade or downgrade."""
        form = SubscriptionUpgradeForm(request.POST, user=request.user)
        profile = request.user.profile
        
        if form.is_valid():
            new_tier = form.cleaned_data['subscription_tier']
            current_tier = profile.subscription_tier
            
            # Check if it's an upgrade or downgrade
            if new_tier.price > current_tier.price:
                # UPGRADE - Process immediately
                # TODO: Integrate with Stripe for payment processing
                
                # For now, just upgrade directly (for testing)
                with transaction.atomic():
                    profile.subscription_tier = new_tier
                    profile.subscription_updated_at = timezone.now()
                    
                    # Clear any pending downgrade
                    if hasattr(profile, 'pending_subscription_tier'):
                        profile.pending_subscription_tier = None
                        profile.pending_tier_change_date = None
                    
                    profile.save()
                
                # Log activity
                log_activity(
                    request.user,
                    'subscription_upgraded',
                    {
                        'from_tier': current_tier.name,
                        'to_tier': new_tier.name,
                        'price_change': float(new_tier.price - current_tier.price)
                    },
                    request
                )
                
                messages.success(
                    request,
                    f'Congratulations! You\'ve been upgraded to {new_tier.name}. '
                    f'Your new features are available immediately!'
                )
                
            else:
                # DOWNGRADE - Schedule for end of billing period
                with transaction.atomic():
                    # Check content limits before allowing downgrade
                    content_check = self._check_content_limits(profile, new_tier)
                    
                    if not content_check['can_downgrade']:
                        messages.error(
                            request,
                            f'Cannot downgrade to {new_tier.name}: {content_check["reason"]}'
                        )
                        return redirect('auth_hub:subscription_detail')
                    
                    # Schedule the downgrade
                    profile.pending_subscription_tier = new_tier
                    # For testing, set to 30 days from now. In production, this would be the billing period end
                    profile.pending_tier_change_date = timezone.now() + timedelta(days=30)
                    profile.save()
                
                # Log activity
                log_activity(
                    request.user,
                    'subscription_downgrade_scheduled',
                    {
                        'from_tier': current_tier.name,
                        'to_tier': new_tier.name,
                        'scheduled_date': profile.pending_tier_change_date.isoformat(),
                        'price_change': float(new_tier.price - current_tier.price)
                    },
                    request
                )
                
                messages.warning(
                    request,
                    f'Your downgrade to {new_tier.name} has been scheduled. '
                    f'You\'ll continue to enjoy {current_tier.name} features until '
                    f'{profile.pending_tier_change_date.strftime("%B %d, %Y")}. '
                    f'You can cancel this downgrade anytime before then.'
                )
            
            return redirect('auth_hub:subscription_detail')
        
        context = {
            'form': form,
            'current_tier': profile.subscription_tier,
        }
        return render(request, self.template_name, context)
    
    def _check_content_limits(self, profile, new_tier):
        """
        Check if user's content exceeds the limits of the new tier.
        
        Returns dict with 'can_downgrade' bool and 'reason' string.
        """
        # Check recipe limits
        if new_tier.max_recipes != -1 and profile.recipes_saved > new_tier.max_recipes:
            return {
                'can_downgrade': False,
                'reason': f'You have {profile.recipes_saved} recipes but {new_tier.name} only allows {new_tier.max_recipes}.'
            }
        
        # Check menu limits
        if new_tier.max_menus != -1 and profile.menus_created > new_tier.max_menus:
            return {
                'can_downgrade': False,
                'reason': f'You have {profile.menus_created} meal plans but {new_tier.name} only allows {new_tier.max_menus}.'
            }
        
        # Check active shares
        active_shares = MenuShare.objects.filter(owner=profile.user, is_active=True).count()
        if new_tier.max_shared_menus != -1 and active_shares > new_tier.max_shared_menus:
            return {
                'can_downgrade': False,
                'reason': f'You have {active_shares} active menu shares but {new_tier.name} only allows {new_tier.max_shared_menus}.'
            }
        
        return {'can_downgrade': True, 'reason': ''}


@method_decorator(login_required, name='dispatch')
class SubscriptionCancelDowngradeView(View):
    """
    View for canceling a pending subscription downgrade.
    """
    
    def post(self, request):
        """Cancel the pending downgrade."""
        profile = request.user.profile
        
        if not hasattr(profile, 'pending_subscription_tier') or not profile.pending_subscription_tier:
            messages.error(request, 'No pending downgrade to cancel.')
            return redirect('auth_hub:subscription_detail')
        
        # Cancel the downgrade
        with transaction.atomic():
            old_pending_tier = profile.pending_subscription_tier
            profile.pending_subscription_tier = None
            profile.pending_tier_change_date = None
            profile.save()
        
        # Log activity
        log_activity(
            request.user,
            'subscription_downgrade_cancelled',
            {
                'cancelled_tier': old_pending_tier.name,
                'current_tier': profile.subscription_tier.name
            },
            request
        )
        
        messages.success(
            request,
            f'Your downgrade to {old_pending_tier.name} has been cancelled. '
            f'You\'ll continue with your {profile.subscription_tier.name} subscription.'
        )
        
        return redirect('auth_hub:subscription_detail')



# API Views for AJAX functionality
@login_required
def check_share_limit(request):
    """API endpoint to check remaining share limit."""
    profile = request.user.profile
    return JsonResponse({
        'can_share': profile.can_share_menus,
        'remaining_shares': profile.remaining_shares if profile.remaining_shares != float('inf') else 'unlimited',
        'max_shares': profile.subscription_tier.max_shared_menus if profile.subscription_tier else 0,
    })


@login_required
def activity_log_api(request):
    """API endpoint for fetching activity logs."""
    page = request.GET.get('page', 1)
    activities = ActivityLog.objects.filter(
        user=request.user
    ).order_by('-created_at')
    
    paginator = Paginator(activities, 20)
    page_obj = paginator.get_page(page)
    
    data = {
        'activities': [
            {
                'id': activity.id,
                'action': activity.get_action_display(),
                'details': activity.details,
                'created_at': activity.created_at.isoformat(),
                'ip_address': activity.ip_address,
            }
            for activity in page_obj
        ],
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number,
    }
    
    return JsonResponse(data)



# Add these imports
import uuid
from django.urls import reverse
from django.http import HttpResponseRedirect
from auth_hub.services.microsoft_auth import MicrosoftAuthService

# Add these view functions

@login_required
def microsoft_auth_start(request):
    """
    Initiate Microsoft OAuth flow.
    
    Redirects user to Microsoft login page.
    """
    try:
        # Debug: Check if settings are loaded
        from django.conf import settings
        logger.info(f"Microsoft Auth Settings Check:")
        logger.info(f"CLIENT_ID exists: {'CLIENT_ID' in settings.MICROSOFT_AUTH}")
        logger.info(f"CLIENT_ID value: {settings.MICROSOFT_AUTH.get('CLIENT_ID', 'NOT SET')[:10]}...")  # Only log first 10 chars
        
        # Generate state for CSRF protection
        state = str(uuid.uuid4())
        request.session['oauth_state'] = state
        
        # Get auth URL
        auth_service = MicrosoftAuthService()
        auth_url = auth_service.get_auth_url(state)
        
        # Log the authentication attempt
        ActivityLog.objects.create(
            user=request.user,
            action='microsoft_auth_start',
            details='Started Microsoft OAuth flow'
        )
        
        return HttpResponseRedirect(auth_url)
        
    except Exception as e:
        logger.error(f"Error starting Microsoft auth: {str(e)}")
        messages.error(request, f"Failed to start Microsoft authentication: {str(e)}")
        return redirect('auth_hub:dashboard')


@login_required
def microsoft_auth_callback(request):
    """
    Handle Microsoft OAuth callback.
    
    Processes the authorization code and saves tokens.
    """
    try:
        # Verify state
        state = request.GET.get('state')
        if state != request.session.get('oauth_state'):
            raise Exception("Invalid state parameter")
        
        # Check for errors
        error = request.GET.get('error')
        if error:
            raise Exception(f"OAuth error: {request.GET.get('error_description', error)}")
        
        # Get authorization code
        code = request.GET.get('code')
        if not code:
            raise Exception("No authorization code received")
        
        # Exchange code for tokens
        auth_service = MicrosoftAuthService()
        token_data = auth_service.get_token_from_code(code)
        
        # Save tokens
        auth_service.save_tokens(request.user, token_data)
        
        # Log success
        ActivityLog.objects.create(
            user=request.user,
            action='microsoft_auth_complete',
            details='Successfully connected Microsoft account'
        )
        
        messages.success(request, "Successfully connected your Microsoft account!")
        
        # Redirect to calendar sync settings
        return redirect('meal_planner:calendar_sync_settings')
        
    except Exception as e:
        logger.error(f"Error in Microsoft auth callback: {str(e)}")
        messages.error(request, "Failed to connect Microsoft account.")
        return redirect('auth_hub:dashboard')


@login_required
def disconnect_microsoft(request):
    """
    Disconnect Microsoft account and remove tokens.
    """
    try:
        # Delete OAuth token
        if hasattr(request.user, 'microsoft_token'):
            request.user.microsoft_token.delete()
        
        # Delete any calendar events
        from meal_planner.models import CalendarEvent
        CalendarEvent.objects.filter(user=request.user).delete()
        
        # Log disconnection
        ActivityLog.objects.create(
            user=request.user,
            action='microsoft_disconnect',
            details='Disconnected Microsoft account'
        )
        
        messages.success(request, "Microsoft account disconnected successfully.")
        
    except Exception as e:
        logger.error(f"Error disconnecting Microsoft account: {str(e)}")
        messages.error(request, "Failed to disconnect Microsoft account.")
    
    return redirect('meal_planner:calendar_sync_settings')

@login_required
def microsoft_disconnect(request):
    """Disconnect Microsoft account and clear session."""
    try:
        if hasattr(request.user, 'microsoft_token'):
            request.user.microsoft_token.delete()
            
        # Clear any Microsoft-related session data
        keys_to_remove = [k for k in request.session.keys() if 'microsoft' in k.lower()]
        for key in keys_to_remove:
            del request.session[key]
        
        messages.success(request, 'Microsoft account disconnected successfully.')
        logger.info(f"Disconnected Microsoft account for user {request.user.username}")
        
    except Exception as e:
        logger.error(f"Error disconnecting Microsoft account: {str(e)}")
        messages.error(request, 'Error disconnecting Microsoft account.')
    
    return redirect('meal_planner:calendar_sync_settings')