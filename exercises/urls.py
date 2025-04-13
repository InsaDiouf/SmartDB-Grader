from django.urls import path
from . import views

app_name = 'exercises'

urlpatterns = [
    # Gestion des exercices
    path('', views.ExerciseListView.as_view(), name='exercise_list'),
    path('<int:pk>/', views.ExerciseDetailView.as_view(), name='exercise_detail'),
    path('create/', views.ExerciseCreateView.as_view(), name='exercise_create'),
    path('<int:pk>/update/', views.ExerciseUpdateView.as_view(), name='exercise_update'),
    path('<int:pk>/delete/', views.ExerciseDeleteView.as_view(), name='exercise_delete'),
    
    # Gestion des corrections
    path('<int:pk>/add-correction/', views.add_correction_view, name='add_correction'),
    
    # Gestion des assignations
    path('<int:pk>/assign/', views.assign_exercise_view, name='assign_exercise'),
    path('<int:pk>/remove-assignment/<int:assignment_id>/', views.remove_assignment_view, name='remove_assignment'),
    
    # Gestion des catégories
    path('topics/', views.TopicListView.as_view(), name='topic_list'),
    path('topics/create/', views.TopicCreateView.as_view(), name='topic_create'),
    path('topics/<int:pk>/update/', views.TopicUpdateView.as_view(), name='topic_update'),
]