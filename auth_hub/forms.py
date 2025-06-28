"""
Forms for the AuthHub application.

This module contains forms for user registration, profile updates,
and menu sharing functionality.
"""

import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, Submit, Div, HTML
from crispy_bootstrap5.bootstrap5 import FloatingField

from .models import UserProfile, MenuShare, SubscriptionTier

logger = logging.getLogger(__name__)


class CustomUserCreationForm(UserCreationForm):
    """
    Custom user registration form with email as the primary identifier.
    
    This form extends Django's UserCreationForm to require email
    and create a user profile automatically.
    """
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        }),
        help_text='We\'ll never share your email with anyone else.'
    )
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    
    dietary_restrictions = forms.MultipleChoiceField(
        choices=[
            ('vegetarian', '🥗 Vegetarian'),
            ('vegan', '🌱 Vegan'),
            ('gluten_free', '🌾 Gluten-Free'),
            ('dairy_free', '🥛 Dairy-Free'),
            ('nut_free', '🥜 Nut-Free'),
            ('halal', '☪️ Halal'),
            ('kosher', '✡️ Kosher'),
            ('low_carb', '🥖 Low Carb'),
            ('keto', '🥑 Keto'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Select any dietary restrictions you have'
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        """Initialize form with Crispy Forms helper."""
        super().__init__(*args, **kwargs)
        
        # Customize password help texts
        self.fields['password1'].help_text = 'Must be at least 8 characters long'
        self.fields['password2'].help_text = 'Enter the same password as before'
        
        # Crispy Forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'mt-4'
        self.helper.layout = Layout(
            HTML('<h4 class="mb-4">Create Your KitchenCompass Account</h4>'),
            Div(
                FloatingField('email'),
                css_class='mb-3'
            ),
            Div(
                Div(
                    FloatingField('first_name'),
                    css_class='col-md-6'
                ),
                Div(
                    FloatingField('last_name'),
                    css_class='col-md-6'
                ),
                css_class='row'
            ),
            Div(
                FloatingField('password1'),
                css_class='mb-3'
            ),
            Div(
                FloatingField('password2'),
                css_class='mb-3'
            ),
            HTML('<h5 class="mt-4 mb-3">Dietary Preferences (Optional)</h5>'),
            Field('dietary_restrictions'),
            HTML('<hr class="my-4">'),
            Submit('submit', 'Create Account', css_class='btn btn-primary btn-lg w-100')
        )
    
    def clean_email(self):
        """Validate that email is unique."""
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email
    
    def save(self, commit=True):
        """Save user and create associated profile."""
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']  # Use email as username
        
        if commit:
            user.save()
            
            # Create user profile with dietary restrictions
            profile = UserProfile.objects.create(
                user=user,
                dietary_restrictions=self.cleaned_data.get('dietary_restrictions', [])
            )
            
            logger.info(f"New user registered: {user.email}")
            
        return user


class UserProfileForm(forms.ModelForm):
    """
    Form for updating user profile information.
    
    Allows users to update their personal information and preferences.
    """
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'
        })
    )
    
    dietary_restrictions = forms.MultipleChoiceField(
        choices=[
            ('vegetarian', '🥗 Vegetarian'),
            ('vegan', '🌱 Vegan'),
            ('gluten_free', '🌾 Gluten-Free'),
            ('dairy_free', '🥛 Dairy-Free'),
            ('nut_free', '🥜 Nut-Free'),
            ('halal', '☪️ Halal'),
            ('kosher', '✡️ Kosher'),
            ('low_carb', '🥖 Low Carb'),
            ('keto', '🥑 Keto'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Update your dietary restrictions'
    )
    
    class Meta:
        model = UserProfile
        fields = ['dietary_restrictions']
    
    def __init__(self, *args, **kwargs):
        """Initialize form with user data."""
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
        
        # Crispy Forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h4 class="mb-4">Profile Information</h4>'),
            Div(
                Div(
                    Field('first_name'),
                    css_class='col-md-6'
                ),
                Div(
                    Field('last_name'),
                    css_class='col-md-6'
                ),
                css_class='row mb-3'
            ),
            Field('email', readonly=True),
            HTML('<h5 class="mt-4 mb-3">Dietary Preferences</h5>'),
            Field('dietary_restrictions'),
            HTML('<hr class="my-4">'),
            Submit('submit', 'Update Profile', css_class='btn btn-primary')
        )
    
    def save(self, commit=True):
        """Save profile and update user information."""
        profile = super().save(commit=False)
        
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.save()
            
            logger.info(f"Profile updated for user: {self.user.email}")
        
        if commit:
            profile.save()
            
        return profile


class MenuShareForm(forms.ModelForm):
    """
    Form for sharing menus with other users.
    
    Allows users to share their menus via email invitation.
    """
    
    shared_with_email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter recipient\'s email address'
        }),
        label='Share with',
        help_text='Enter the email address of the person you want to share your menus with'
    )
    
    permissions_choices = [
        ('view', 'View Only - Can see your menus but not edit them'),
        ('edit', 'Can Edit - Can view and modify your menus'),
        ('full', 'Full Access - Can view, edit, and reshare your menus'),
    ]
    
    permissions = forms.ChoiceField(
        choices=permissions_choices,
        initial='view',
        widget=forms.RadioSelect,
        label='Permissions',
        help_text='Choose what the recipient can do with your shared menus'
    )
    
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add a personal message (optional)'
        }),
        label='Personal Message',
        help_text='This message will be included in the invitation email'
    )
    
    class Meta:
        model = MenuShare
        fields = ['shared_with_email']
    
    def __init__(self, *args, **kwargs):
        """Initialize form with user context."""
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Crispy Forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            HTML('<h4 class="mb-4">Share Your Menus</h4>'),
            FloatingField('shared_with_email'),
            HTML('<h5 class="mt-4 mb-3">Access Permissions</h5>'),
            Field('permissions'),
            HTML('<div class="mt-4">'),
            Field('message'),
            HTML('</div>'),
            HTML('<hr class="my-4">'),
            Submit('submit', 'Send Invitation', css_class='btn btn-primary')
        )
    
    def clean_shared_with_email(self):
        """Validate email and check sharing limits."""
        email = self.cleaned_data.get('shared_with_email')
        
        if email == self.user.email:
            raise ValidationError("You cannot share menus with yourself.")
        
        # Check if already shared
        if MenuShare.objects.filter(
            owner=self.user,
            shared_with_email=email,
            is_active=True
        ).exists():
            raise ValidationError("You have already shared your menus with this email.")
        
        # Check sharing limits based on subscription
        profile = self.user.profile
        if not profile.can_share_menus:
            raise ValidationError(
                "Your current subscription doesn't allow menu sharing. "
                "Please upgrade to share your menus."
            )
        
        if profile.remaining_shares <= 0:
            raise ValidationError(
                f"You've reached your sharing limit of {profile.subscription_tier.max_shared_menus} "
                f"people. Please upgrade your subscription to share with more people."
            )
        
        return email
    
    def save(self, commit=True):
        """Save menu share with permissions."""
        share = super().save(commit=False)
        share.owner = self.user
        
        # Set permissions based on selection
        permissions = self.cleaned_data.get('permissions', 'view')
        share.can_view = True  # Always true
        share.can_edit = permissions in ['edit', 'full']
        share.can_reshare = permissions == 'full'
        
        if commit:
            share.save()
            logger.info(
                f"Menu share created: {self.user.email} → {share.shared_with_email}"
            )
            
        return share


class SubscriptionUpgradeForm(forms.Form):
    """
    Form for upgrading or downgrading subscription tier.
   
    Allows users to select and change to a different subscription tier.
    """
   
    subscription_tier = forms.ModelChoiceField(
        queryset=SubscriptionTier.objects.filter(is_active=True),  # Include ALL tiers
        widget=forms.RadioSelect,
        empty_label=None,
        label='Choose Your Plan'
    )
   
    def __init__(self, *args, **kwargs):
        """Initialize form with current user's tier."""
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
       
        # Exclude only the current tier (since they can't change to the same tier)
        if self.user and hasattr(self.user, 'profile'):
            current_tier = self.user.profile.subscription_tier
            if current_tier:
                self.fields['subscription_tier'].queryset = self.fields[
                    'subscription_tier'
                ].queryset.exclude(id=current_tier.id)
       
        # Crispy Forms helper
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'subscription-form'
        self.helper.layout = Layout(
            Field('subscription_tier', template='auth_hub/subscription_tier_radio.html'),
            Submit('submit', 'Continue', css_class='btn btn-primary btn-lg mt-4')
        )

