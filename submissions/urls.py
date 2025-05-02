from django.urls import path
from . import views

app_name = 'submissions'

urlpatterns = [
    # Gestion des soumissions
    path('exercise/<int:exercise_id>/submit/', views.submit_exercise_view, name='submit_exercise'),
    path('<int:pk>/', views.SubmissionDetailView.as_view(), name='submission_detail'),
    path('student/<int:student_id>/', views.StudentSubmissionsListView.as_view(), name='student_submissions'),
    path('exercise/<int:exercise_id>/all/', views.ExerciseSubmissionsListView.as_view(), name='exercise_submissions'),
    
    # Gestion des évaluations
    path('test-evaluation/<int:submission_id>/', views.test_evaluation, name='test_evaluation'),
    path('manual-evaluation/<int:pk>/', views.manual_evaluation, name='manual_evaluation'),
    path('<int:submission_id>/review/', views.evaluation_review_view, name='evaluation_review'),
    path('<int:submission_id>/add-feedback/', views.add_feedback_item_view, name='add_feedback'),
    path('feedback/<int:feedback_item_id>/edit/', views.edit_feedback_item_view, name='edit_feedback'),
    path('feedback/<int:feedback_item_id>/delete/', views.delete_feedback_item_view, name='delete_feedback'),
    
    # API pour vérification asynchrone
    path('<int:submission_id>/check-status/', views.check_evaluation_status_view, name='check_evaluation_status'),
]