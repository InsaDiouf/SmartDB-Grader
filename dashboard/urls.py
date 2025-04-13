from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Vue principale du tableau de bord
    path('', views.dashboard_view, name='dashboard'),
    
    # API pour récupérer des statistiques
    path('exercise/<int:exercise_id>/stats/', views.exercise_stats_view, name='exercise_stats'),
]