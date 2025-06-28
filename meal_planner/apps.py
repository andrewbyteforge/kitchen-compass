from django.apps import AppConfig


class MealPlannerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meal_planner'
    
    def ready(self):
        """Import signal handlers when app is ready."""
        import meal_planner.signals