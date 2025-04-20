from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, View
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.core.exceptions import PermissionDenied

from .models import Submission, Evaluation, FeedbackItem, FeedbackCategory
from .forms import SubmissionForm, EvaluationReviewForm, FeedbackItemForm, NewFeedbackItemForm
from exercises.models import Exercise
from ai_engine.evaluator import evaluate_submission
from accounts.views import TeacherRequiredMixin


@login_required
def submit_exercise_view(request, exercise_id):
    """Vue pour soumettre une réponse à un exercice."""
    
    # Vérifier que l'utilisateur est un étudiant
    if not request.user.is_student:
        raise PermissionDenied("Seuls les étudiants peuvent soumettre des réponses.")
    
    exercise = get_object_or_404(Exercise, pk=exercise_id)
    
    # Vérifier que l'exercice est disponible
    if not exercise.is_published:
        raise Http404("Cet exercice n'est pas disponible.")
    
    if exercise.deadline and exercise.deadline < timezone.now():
        messages.error(request, "La date limite de soumission est dépassée.")
        return redirect('exercises:exercise_detail', pk=exercise_id)
    
    # Vérifier le nombre de tentatives
    existing_submissions = Submission.objects.filter(
        exercise=exercise,
        student=request.user
    )
    
    if existing_submissions.count() >= exercise.max_attempts:
        messages.error(
            request, 
            f"Vous avez atteint le nombre maximum de tentatives ({exercise.max_attempts})."
        )
        return redirect('exercises:exercise_detail', pk=exercise_id)
    
    if request.method == 'POST':
        form = SubmissionForm(
            request.POST, 
            request.FILES,
            exercise=exercise,
            student=request.user
        )
        
        if form.is_valid():
            # Créer la soumission
            submission = form.save(commit=False)
            submission.exercise = exercise
            submission.student = request.user
            submission.attempt_number = existing_submissions.count() + 1
            
            # Traitement du fichier PDF
            if form.cleaned_data.get('file'):
                submission.file = form.cleaned_data['file']
                # TODO: Extraction du texte du PDF avec PyPDF2
            
            submission.save()
            
            messages.success(request, "Votre réponse a été soumise avec succès.")
            
            # Lancer l'évaluation automatique en arrière-plan
            try:
                # Note: Dans une application réelle, cette tâche devrait être asynchrone
                # via Celery ou un système de file d'attente similaire
                evaluate_submission(submission.id)
            except Exception as e:
                # Ne pas bloquer l'utilisateur en cas d'erreur d'évaluation
                print(f"Erreur lors de l'évaluation automatique: {str(e)}")
            
            return redirect('submissions:submission_detail', pk=submission.pk)
    else:
        form = SubmissionForm(exercise=exercise, student=request.user)
    
    return render(request, 'submissions/submit_form.html', {
        'form': form,
        'exercise': exercise,
        'existing_submissions': existing_submissions,
    })


class SubmissionDetailView(LoginRequiredMixin, DetailView):
    """Vue pour afficher les détails d'une soumission."""
    
    model = Submission
    template_name = 'submissions/submission_detail.html'
    context_object_name = 'submission'
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        
        # Vérifier les permissions d'accès
        if user.is_teacher or obj.student == user:
            return obj
        
        # Si aucune condition n'est remplie, refuser l'accès
        raise PermissionDenied("Vous n'avez pas accès à cette soumission.")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submission = self.get_object()
        
        # Ajouter l'évaluation si disponible
        if hasattr(submission, 'evaluation'):
            context['evaluation'] = submission.evaluation
            context['feedback_items'] = submission.evaluation.feedback_items.all().order_by('order')
        
        # Ajouter le formulaire de révision pour les professeurs
        if self.request.user.is_teacher and hasattr(submission, 'evaluation'):
            context['review_form'] = EvaluationReviewForm(instance=submission.evaluation)
            context['new_feedback_form'] = NewFeedbackItemForm()
            context['feedback_categories'] = FeedbackCategory.objects.all()
        
        # Informations sur l'exercice
        context['exercise'] = submission.exercise
        
        # Vérifier si la soumission est en cours de traitement
        context['is_processing'] = submission.status == 'processing'
        
        # Récupérer les autres soumissions du même étudiant pour cet exercice
        context['other_submissions'] = Submission.objects.filter(
            exercise=submission.exercise,
            student=submission.student
        ).exclude(id=submission.id).order_by('-submitted_at')
        
        return context


@login_required
def evaluation_review_view(request, submission_id):
    """Vue pour réviser une évaluation automatique."""
    
    # Vérifier que l'utilisateur est un professeur
    if not request.user.is_teacher:
        raise PermissionDenied("Seuls les professeurs peuvent réviser les évaluations.")
    
    submission = get_object_or_404(Submission, pk=submission_id)
    
    # Vérifier que l'évaluation existe
    if not hasattr(submission, 'evaluation'):
        messages.error(request, "Cette soumission n'a pas encore été évaluée.")
        return redirect('submissions:submission_detail', pk=submission_id)
    
    if request.method == 'POST':
        form = EvaluationReviewForm(request.POST, instance=submission.evaluation)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.reviewed_by_teacher = True
            evaluation.reviewing_teacher = request.user
            
            # Recalculer le pourcentage basé sur la nouvelle note
            max_points = submission.exercise.total_points
            if max_points > 0:
                evaluation.percentage = (evaluation.score / max_points) * 100
            
            evaluation.save()
            
            messages.success(request, "L'évaluation a été mise à jour avec succès.")
            return redirect('submissions:submission_detail', pk=submission_id)
    else:
        form = EvaluationReviewForm(instance=submission.evaluation)
    
    return render(request, 'submissions/evaluation_review.html', {
        'form': form,
        'submission': submission,
        'evaluation': submission.evaluation,
    })


@login_required
def add_feedback_item_view(request, submission_id):
    """Vue pour ajouter un nouvel élément de feedback."""
    
    # Vérifier que l'utilisateur est un professeur
    if not request.user.is_teacher:
        raise PermissionDenied("Seuls les professeurs peuvent ajouter des feedbacks.")
    
    submission = get_object_or_404(Submission, pk=submission_id)
    
    # Vérifier que l'évaluation existe
    if not hasattr(submission, 'evaluation'):
        messages.error(request, "Cette soumission n'a pas encore été évaluée.")
        return redirect('submissions:submission_detail', pk=submission_id)
    
    if request.method == 'POST':
        form = NewFeedbackItemForm(request.POST)
        if form.is_valid():
            feedback_item = form.save(commit=False)
            feedback_item.evaluation = submission.evaluation
            
            # Déterminer l'ordre (placer à la fin)
            last_order = submission.evaluation.feedback_items.order_by('-order').first()
            feedback_item.order = (last_order.order + 1) if last_order else 0
            
            feedback_item.save()
            
            # Marquer l'évaluation comme révisée par un professeur
            if not submission.evaluation.reviewed_by_teacher:
                submission.evaluation.reviewed_by_teacher = True
                submission.evaluation.reviewing_teacher = request.user
                submission.evaluation.save()
            
            messages.success(request, "Le feedback a été ajouté avec succès.")
            return redirect('submissions:submission_detail', pk=submission_id)
    else:
        form = NewFeedbackItemForm()
    
    return render(request, 'submissions/add_feedback.html', {
        'form': form,
        'submission': submission,
        'evaluation': submission.evaluation,
    })


@login_required
def edit_feedback_item_view(request, feedback_item_id):
    """Vue pour modifier un élément de feedback."""
    
    # Vérifier que l'utilisateur est un professeur
    if not request.user.is_teacher:
        raise PermissionDenied("Seuls les professeurs peuvent modifier les feedbacks.")
    
    feedback_item = get_object_or_404(FeedbackItem, pk=feedback_item_id)
    submission = feedback_item.evaluation.submission
    
    if request.method == 'POST':
        form = FeedbackItemForm(request.POST, instance=feedback_item)
        if form.is_valid():
            form.save()
            
            messages.success(request, "Le feedback a été mis à jour avec succès.")
            return redirect('submissions:submission_detail', pk=submission.pk)
    else:
        form = FeedbackItemForm(instance=feedback_item)
    
    return render(request, 'submissions/edit_feedback.html', {
        'form': form,
        'feedback_item': feedback_item,
        'submission': submission,
    })


@login_required
def delete_feedback_item_view(request, feedback_item_id):
    """Vue pour supprimer un élément de feedback."""
    
    # Vérifier que l'utilisateur est un professeur
    if not request.user.is_teacher:
        raise PermissionDenied("Seuls les professeurs peuvent supprimer les feedbacks.")
    
    feedback_item = get_object_or_404(FeedbackItem, pk=feedback_item_id)
    submission = feedback_item.evaluation.submission
    
    if request.method == 'POST':
        feedback_item.delete()
        messages.success(request, "Le feedback a été supprimé avec succès.")
        return redirect('submissions:submission_detail', pk=submission.pk)
    
    return render(request, 'submissions/delete_feedback_confirm.html', {
        'feedback_item': feedback_item,
        'submission': submission,
    })


class StudentSubmissionsListView(LoginRequiredMixin, ListView):
    """Vue pour afficher la liste des soumissions d'un étudiant."""
    
    model = Submission
    template_name = 'submissions/student_submissions.html'
    context_object_name = 'submissions'
    paginate_by = 10
    
    def get_queryset(self):
        # Pour les étudiants, montrer leurs propres soumissions
        if self.request.user.is_student:
            return Submission.objects.filter(
                student=self.request.user
            ).order_by('-submitted_at')
            
        # Pour les professeurs, si un ID étudiant est fourni
        elif self.request.user.is_teacher and 'student_id' in self.kwargs:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            student = get_object_or_404(User, pk=self.kwargs['student_id'], user_type='student')
            return Submission.objects.filter(
                student=student
            ).order_by('-submitted_at')
            
        # Sinon, liste vide
        return Submission.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Si c'est un professeur qui consulte les soumissions d'un étudiant
        if self.request.user.is_teacher and 'student_id' in self.kwargs:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            student = get_object_or_404(User, pk=self.kwargs['student_id'], user_type='student')
            context['student'] = student
            context['viewing_as_teacher'] = True
        else:
            context['viewing_as_teacher'] = False
        
        return context


class ExerciseSubmissionsListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """Vue pour afficher toutes les soumissions pour un exercice (pour les professeurs)."""
    
    model = Submission
    template_name = 'submissions/exercise_submissions.html'
    context_object_name = 'submissions'
    paginate_by = 20
    
    def get_queryset(self):
        self.exercise = get_object_or_404(Exercise, pk=self.kwargs['exercise_id'])
        
        # Vérifier que le professeur est l'auteur de l'exercice
        if self.exercise.author != self.request.user:
            return Submission.objects.none()
            
        return Submission.objects.filter(
            exercise=self.exercise
        ).order_by('-submitted_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exercise'] = self.exercise
        
        # Statistiques
        submissions = context['submissions']
        context['total_submissions'] = submissions.count()
        context['completed_evaluations'] = submissions.filter(status='completed').count()
        
        # Calculer la note moyenne
        evaluated_submissions = [s for s in submissions if hasattr(s, 'evaluation')]
        if evaluated_submissions:
            avg_score = sum(s.evaluation.score for s in evaluated_submissions) / len(evaluated_submissions)
            context['average_score'] = round(avg_score, 2)
            
            # Note maximale et minimale
            context['max_score'] = max(s.evaluation.score for s in evaluated_submissions)
            context['min_score'] = min(s.evaluation.score for s in evaluated_submissions)
        
        return context


@login_required
def check_evaluation_status_view(request, submission_id):
    """Vue API pour vérifier le statut d'une évaluation (utilisée par AJAX)."""
    
    submission = get_object_or_404(Submission, pk=submission_id)
    
    # Vérifier les permissions
    if not (request.user.is_teacher or submission.student == request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Retourner le statut
    data = {
        'status': submission.status,
        'has_evaluation': hasattr(submission, 'evaluation'),
    }
    
    # Si l'évaluation est complète, inclure l'URL pour rediriger
    if submission.status == 'completed' and hasattr(submission, 'evaluation'):
        data['redirect_url'] = reverse('submissions:submission_detail', kwargs={'pk': submission_id})
    
    return JsonResponse(data)