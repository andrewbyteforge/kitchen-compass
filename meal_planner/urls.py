"""
Meal Planner URL Configuration
Updated to work with the new modularized views structure.
"""
from django.urls import path
from . import views

# Import CSV upload views
from meal_planner.views.csv_upload_views import (
    CSVUploadView,
    csv_preview_view,
    csv_process_view,
    csv_result_view,
    CSVHistoryView,
    csv_sample_download
)

app_name = 'meal_planner'

urlpatterns = [
    # Main views
    path('', views.MealPlanCalendarView.as_view(), name='calendar'),
    path('plans/', views.MealPlanListView.as_view(), name='meal_plan_list'),
    path('plans/<int:pk>/', views.MealPlanDetailView.as_view(), name='meal_plan_detail'),
   
    # Meal plan CRUD
    path('plans/create/', views.MealPlanCreateView.as_view(), name='meal_plan_create'),
    path('plans/<int:pk>/edit/', views.MealPlanUpdateView.as_view(), name='meal_plan_update'),
    path('plans/<int:pk>/delete/', views.MealPlanDeleteView.as_view(), name='meal_plan_delete'),

    # Shopping list
    path('plans/<int:pk>/shopping-list/', views.generate_shopping_list, name='shopping_list'),
    path('plans/<int:pk>/shopping-list/download/', views.download_shopping_list, name='download_shopping_list'),
   

    # AJAX endpoints for meal slots
    path('slots/<int:pk>/update/', views.update_meal_slot, name='update_meal_slot'),
    path('slots/<int:pk>/delete/', views.delete_meal_slot, name='delete_meal_slot'),
    path('slots/create/', views.create_meal_slot, name='create_meal_slot'),
    path('test/', views.test_endpoint, name='test_endpoint'),
   
    # Templates
    path('templates/', views.MealPlanTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.MealPlanTemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/edit/', views.MealPlanTemplateUpdateView.as_view(), name='template_update'),
    path('templates/<int:pk>/delete/', views.MealPlanTemplateDeleteView.as_view(), name='template_delete'),
    path('templates/apply/', views.apply_template, name='apply_template'),
    path('create-slots-for-plan/', views.create_meal_slots_for_plan, name='create_meal_slots_for_plan'),
   
    # Calendar sync
    path('calendar-sync/', views.CalendarSyncSettingsView.as_view(), name='calendar_sync_settings'),    
    path('plans/<int:pk>/sync/', views.sync_meal_plan, name='sync_meal_plan'),
    path('sync-status/', views.outlook_sync_status, name='outlook_sync_status'),
    path('sync-all/', views.sync_all_meal_plans, name='sync_all_meal_plans'),
    path('microsoft/switch-account/', views.microsoft_switch_account, name='microsoft_switch_account'),
    path('api/connected-account/', views.get_connected_account, name='get_connected_account'),
    
    # CSV Upload URLs (Admin only)
    path('admin/csv/upload/', CSVUploadView.as_view(), name='csv_upload'),
    path('admin/csv/preview/<int:upload_id>/', csv_preview_view, name='csv_preview'),
    path('admin/csv/process/<int:upload_id>/', csv_process_view, name='csv_process'),
    path('admin/csv/result/<int:upload_id>/', csv_result_view, name='csv_result'),
    path('admin/csv/history/', CSVHistoryView.as_view(), name='csv_history'),
    path('admin/csv/sample/', csv_sample_download, name='csv_sample'),
]