from django.contrib import admin
from .models import MealPlan, MealPlanTemplate

@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'created_at']
    list_filter = ['created_at', 'start_date', 'end_date']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'start_date'
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        ('Date Range', {
            'fields': ('start_date', 'end_date')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(MealPlanTemplate)
class MealPlanTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'duration_days', 'is_public', 'created_at']
    list_filter = ['is_public', 'duration_days', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        ('Template Settings', {
            'fields': ('duration_days', 'is_public')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )