"""
Celery configuration for KitchenCompass.

Handles asynchronous task processing for calendar sync and other background jobs.
"""

import os
from celery import Celery

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kitchen_compass.settings')

# Create Celery app
app = Celery('kitchen_compass')

# Load config from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery is working."""
    print(f'Request: {self.request!r}')