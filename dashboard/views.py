from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Max, Min, Sum, Q, F, Value, Case, When, CharField
from django.db.models.functions import TruncDate, Extract
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.http import JsonResponse

from exercises.models import Exercise, ExerciseAssignment
from submissions.models import Submission, Evaluation

User = get_user_model()


@login_required
def dashboard_view(request):
    """Vue principale du tableau de bord, adaptée selon le type d'utilisateur."""
    
    if request.user.is_student:
        return student_dashboard(request)
    elif request.user.is_teacher:
        return teacher_dashboard(request)
    else:
        # Rediriger vers la page d'accueil par défaut
        from django.shortcuts import redirect
        return redirect('home')


def student_dashboard(request):
    """Tableau de bord pour les étudiants."""
    
    student = request.user
    
    # Récupérer les exercices assignés à l'étudiant
    assignments = ExerciseAssignment.objects.filter(
        assigned_to=student
    ).select_related('exercise')
    
    # Exercices en cours (date limite non dépassée)
    current_assignments = [
        a for a in assignments 
        if not a.exercise.is_expired and a.exercise.is_published
    ]
    
    # Exercices récemment soumis
    recent_submissions = Submission.objects.filter(
        student=student
    ).order_by('-submitted_at')[:5]
    
    # Statistiques globales
    total_submissions = Submission.objects.filter(student=student).count()
    
    # Calculer la note moyenne si des évaluations existent
    evaluations = Evaluation.objects.filter(submission__student=student)
    # Utiliser le champ score au lieu de score_out_of_20
    avg_score_raw = evaluations.aggregate(avg=Avg('score'))['avg'] or 0
    # Si score est sur 1.0, convertir en note sur 20
    avg_score = avg_score_raw * 20 if avg_score_raw <= 1.0 else avg_score_raw
    
    # Progression dans le temps (pour les graphiques)
    submissions_by_month = Submission.objects.filter(
        student=student
    ).annotate(
        month=Extract('submitted_at', 'month')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    # Utiliser score au lieu de score_out_of_20
    scores_by_month = evaluations.annotate(
        month=Extract('created_at', 'month')
    ).values('month').annotate(
        avg_score_raw=Avg('score')
    ).order_by('month')
    
    # Convertir les valeurs après récupération des données
    scores_by_month_converted = []
    for data in scores_by_month:
        score_raw = data['avg_score_raw'] or 0
        # Si score est sur 1.0, convertir en note sur 20
        data['avg_score'] = score_raw * 20 if score_raw <= 1.0 else score_raw
        scores_by_month_converted.append(data)
    
    context = {
        'current_assignments': current_assignments,
        'recent_submissions': recent_submissions,
        'total_submissions': total_submissions,
        'avg_score': round(avg_score, 2) if avg_score else 0,
        'submissions_by_month': list(submissions_by_month),
        'scores_by_month': scores_by_month_converted,
    }
    
    return render(request, 'dashboard/student_dashboard.html', context)


def teacher_dashboard(request):
    """Tableau de bord pour les professeurs."""
    
    teacher = request.user
    
    # Exercices créés par le professeur
    exercises = Exercise.objects.filter(author=teacher)
    
    # Soumissions récentes pour les exercices du professeur
    recent_submissions = Submission.objects.filter(
        exercise__author=teacher
    ).order_by('-submitted_at')[:10]
    
    # Statistiques globales
    total_exercises = exercises.count()
    total_submissions = Submission.objects.filter(exercise__author=teacher).count()
    
    # Nombre d'étudiants uniques qui ont soumis des exercices
    unique_students = Submission.objects.filter(
        exercise__author=teacher
    ).values('student').distinct().count()
    
    # Taux moyen de réussite
    avg_score_pct = Evaluation.objects.filter(
        submission_exercise_author=teacher
    ).aggregate(avg=Avg('percentage'))['avg'] or 0
    
    # Distribution des notes (pour graphiques)
    score_distribution = Evaluation.objects.filter(
        submission_exercise_author=teacher
    ).annotate(
        range=Case(
            When(percentage__lt=20, then=Value('0-20%')),
            When(percentage__lt=40, then=Value('20-40%')),
            When(percentage__lt=60, then=Value('40-60%')),
            When(percentage__lt=80, then=Value('60-80%')),
            default=Value('80-100%'),
            output_field=CharField(),
        )
    ).values('range').annotate(count=Count('id')).order_by('range')
    
    # Activité par jour (derniers 30 jours)
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    daily_activity = Submission.objects.filter(
        exercise__author=teacher,
        submitted_at__gte=thirty_days_ago
    ).annotate(
        day=TruncDate('submitted_at')
    ).values('day').annotate(count=Count('id')).order_by('day')
    
    # Calcul des tâches à faire
    pending_evaluations = recent_submissions.filter(status='pending').count()
    
    # Exercices sans correction
    exercises_without_correction = 0
    for exercise in exercises:
        if not exercise.corrections.exists():
            exercises_without_correction += 1
    
    # Exercices qui expirent bientôt (dans la semaine)
    now = timezone.now()
    expiring_soon = timezone.now() + timezone.timedelta(days=7)
    expiring_exercises = exercises.filter(
        deadline__gt=now,
        deadline__lt=expiring_soon
    ).count()
    
    # Obtenir les données de performance par sujet/catégorie
    from django.db.models import Subquery, OuterRef
    
    # Supposons que vous ayez un modèle Topic pour les catégories d'exercices
    from exercises.models import Topic  # Ajustez selon votre projet
    
    topics = Topic.objects.all()
    topic_performance = []
    
    for topic in topics:
        avg = Evaluation.objects.filter(
            submission_exercise_topic=topic,
            submission_exercise_author=teacher
        ).aggregate(avg=Avg('score'))['avg']
        
        if avg is not None:
            topic_performance.append({
                'name': topic.name,
                'avg_score': avg * 20 if avg <= 1.0 else avg  # Convertir en score sur 20 si nécessaire
            })
    
    context = {
        'exercises': exercises,
        'recent_submissions': recent_submissions,
        'total_exercises': total_exercises,
        'total_submissions': total_submissions,
        'unique_students': unique_students,
        'avg_score_pct': round(avg_score_pct, 2),
        'score_distribution': list(score_distribution),
        'daily_activity': list(daily_activity),
        'pending_evaluations': pending_evaluations,
        'exercises_without_correction': exercises_without_correction,
        'expiring_exercises': expiring_exercises,
        'topics': topics,
        'topic_performance': topic_performance,
    }
    
    return render(request, 'dashboard/teacher_dashboard.html', context)


@login_required
def exercise_stats_view(request, exercise_id):
    """Vue pour les statistiques détaillées d'un exercice spécifique."""
    
    if not request.user.is_teacher:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Récupérer les statistiques pour l'exercice demandé
    stats = Submission.objects.filter(
        exercise_id=exercise_id
    ).aggregate(
        count=Count('id'),
        avg_score=Avg('evaluation__score'),
        max_score=Max('evaluation__score'),
        min_score=Min('evaluation__score'),
        avg_percentage=Avg('evaluation__percentage'),
    )
    
    # Ajouter des statistiques de répartition
    score_distribution = Evaluation.objects.filter(
        submission__exercise_id=exercise_id
    ).annotate(
        range=Case(
            When(percentage__lt=20, then=Value('0-20%')),
            When(percentage__lt=40, then=Value('20-40%')),
            When(percentage__lt=60, then=Value('40-60%')),
            When(percentage__lt=80, then=Value('60-80%')),
            default=Value('80-100%'),
            output_field=CharField(),
        )
    ).values('range').annotate(count=Count('id')).order_by('range')
    
    # Formater les statistiques
    result = {
        'submission_count': stats['count'],
        'avg_score': round(stats['avg_score'], 2) if stats['avg_score'] else 0,
        'max_score': stats['max_score'] or 0,
        'min_score': stats['min_score'] or 0,
        'avg_percentage': round(stats['avg_percentage'], 2) if stats['avg_percentage'] else 0,
        'score_distribution': list(score_distribution),
    }
    
    return JsonResponse(result)