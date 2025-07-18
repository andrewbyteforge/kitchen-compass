# Generated by Django 5.2.3 on 2025-07-13 13:43

import datetime
import django.core.validators
import django.db.models.deletion
import meal_planner.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MealPlanTemplateSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_offset', models.IntegerField(help_text='Days from start of plan (0 = first day)', validators=[django.core.validators.MinValueValidator(0)])),
                ('servings', models.IntegerField(default=1, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(20)])),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['day_offset', 'meal_type__display_order'],
            },
        ),
        migrations.CreateModel(
            name='MealSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('servings', models.IntegerField(default=1, help_text='Number of servings to prepare', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(20)])),
                ('notes', models.TextField(blank=True, help_text='Notes for this meal')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['date', 'meal_type__display_order'],
            },
        ),
        migrations.CreateModel(
            name='MealType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('display_order', models.IntegerField(default=0)),
                ('default_time', models.TimeField(blank=True, help_text='Default time for this meal', null=True)),
                ('icon', models.CharField(default='bi-egg-fried', help_text='Bootstrap icon class', max_length=50)),
            ],
            options={
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='RecipeCSVUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(help_text='CSV file containing recipe data', upload_to=meal_planner.models.csv_upload_path, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['csv'])])),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('partial', 'Partially Completed')], default='pending', max_length=20)),
                ('total_rows', models.IntegerField(default=0)),
                ('successful_imports', models.IntegerField(default=0)),
                ('failed_imports', models.IntegerField(default=0)),
                ('error_log', models.JSONField(blank=True, default=dict, help_text='Detailed error information for failed imports')),
                ('notes', models.TextField(blank=True, help_text='Admin notes about this upload')),
            ],
            options={
                'verbose_name': 'Recipe CSV Upload',
                'verbose_name_plural': 'Recipe CSV Uploads',
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='CalendarEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('outlook_event_id', models.CharField(help_text='ID of the event in Outlook calendar', max_length=255)),
                ('last_synced', models.DateTimeField(auto_now=True)),
                ('sync_status', models.CharField(choices=[('synced', 'Synced'), ('pending', 'Pending Sync'), ('error', 'Sync Error')], default='pending', max_length=20)),
                ('sync_error', models.TextField(blank=True, help_text='Error message if sync failed')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='calendar_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'meal_planner_calendar_event',
            },
        ),
        migrations.CreateModel(
            name='MealPlanTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name for this template', max_length=200)),
                ('description', models.TextField(blank=True, help_text='Description of this meal plan template')),
                ('duration_days', models.IntegerField(default=7, help_text='Number of days this template covers', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30)])),
                ('is_public', models.BooleanField(default=False, help_text='Allow other users to use this template')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meal_plan_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MealPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Name for this meal plan', max_length=200)),
                ('start_date', models.DateField(default=datetime.date.today, help_text='Start date of the meal plan')),
                ('end_date', models.DateField(help_text='End date of the meal plan')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this meal plan is currently active')),
                ('notes', models.TextField(blank=True, help_text='Optional notes for this meal plan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meal_plans', to=settings.AUTH_USER_MODEL)),
                ('created_from_template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_plans', to='meal_planner.mealplantemplate')),
            ],
            options={
                'ordering': ['-start_date', '-created_at'],
            },
        ),
    ]
