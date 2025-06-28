"""
URL configuration for kitchen_compass project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Auth Hub app
    path('auth/', include('auth_hub.urls', namespace='auth_hub')),
    
    # Allauth URLs (for social auth in future)
    path('accounts/', include('allauth.urls')),


    path('recipes/', include('recipe_hub.urls')),


    path('meals/', include('meal_planner.urls')),
    
    # Home page redirect to login
    path('', RedirectView.as_view(url='/auth/login/', permanent=False), name='home'),
   
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)