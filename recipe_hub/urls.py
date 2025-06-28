"""
Recipe Hub URL Configuration

Defines all URL patterns for recipe-related views.
"""

from django.urls import path
from . import views

app_name = 'recipe_hub'

urlpatterns = [
    # Recipe list views
    path('', views.RecipeListView.as_view(), name='recipe_list'),
    path('my-recipes/', views.UserRecipeListView.as_view(), name='user_recipes'),
    path('favorites/', views.FavoriteRecipesView.as_view(), name='favorite_recipes'),
    path('category/<slug:slug>/', views.CategoryRecipesView.as_view(), name='category_recipes'),
    
    # Recipe CRUD
    path('create/', views.RecipeCreateView.as_view(), name='recipe_create'),
    path('import/', views.import_recipe, name='recipe_import'),
    path('import/csv/', views.import_recipe_csv, name='recipe_import_csv'),
    path('<slug:slug>/', views.RecipeDetailView.as_view(), name='recipe_detail'),
    path('<slug:slug>/edit/', views.RecipeUpdateView.as_view(), name='recipe_update'),
    path('<slug:slug>/delete/', views.RecipeDeleteView.as_view(), name='recipe_delete'),
    
    # Recipe interactions
    path('<int:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('<int:pk>/rate/', views.rate_recipe, name='rate_recipe'),
    path('<int:pk>/comment/', views.add_comment, name='add_comment'),
]