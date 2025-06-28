"""
URL configuration for the AuthHub application.
This module defines URL patterns for authentication, dashboard,
profile management, and menu sharing functionality.
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'auth_hub'

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
   
    # Password reset URLs
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='auth_hub/password_reset.html',
            email_template_name='auth_hub/emails/password_reset_email.html',
            success_url='/auth/password-reset/done/'
        ),
        name='password_reset'
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='auth_hub/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='auth_hub/password_reset_confirm.html',
            success_url='/auth/password-reset/complete/'
        ),
        name='password_reset_confirm'
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='auth_hub/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
   
    # Dashboard and Profile URLs
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('profile/', views.ProfileUpdateView.as_view(), name='profile_update'),
   
    # Menu Sharing URLs
    path('share/create/', views.MenuShareCreateView.as_view(), name='menu_share_create'),
    path('share/list/<str:view_type>/', views.MenuShareListView.as_view(), name='menu_share_list'),
    path('share/accept/<str:token>/', views.MenuShareAcceptView.as_view(), name='menu_share_accept'),
    path('share/revoke/<int:pk>/', views.MenuShareRevokeView.as_view(), name='menu_share_revoke'),
   
    # Subscription URLs
    path('subscription/', views.SubscriptionView.as_view(), name='subscription_detail'),
    path('subscription/upgrade/', views.SubscriptionUpgradeView.as_view(), name='subscription_upgrade'),
    path('subscription/cancel-downgrade/', views.SubscriptionCancelDowngradeView.as_view(), name='subscription_cancel_downgrade'),
   
    # API URLs
    path('api/share-limit/', views.check_share_limit, name='api_share_limit'),
    path('api/activity-log/', views.activity_log_api, name='api_activity_log'),

    # Microsoft OAuth
    path('microsoft/login/', views.microsoft_auth_start, name='microsoft_login'),
    path('callback/microsoft/', views.microsoft_auth_callback, name='microsoft_callback'),
    path('microsoft/disconnect/', views.disconnect_microsoft, name='microsoft_disconnect'),
]