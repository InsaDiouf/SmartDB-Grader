from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404
from django.core.exceptions import PermissionDenied

from .models import Exercise, ExerciseCorrection, Topic, ExerciseAssignment
from .forms import (
    ExerciseForm, ExerciseCorrectionForm, TopicForm, 
    ExerciseAssignmentForm, ExerciseFilterForm
)
from accounts.views import TeacherRequiredMixin


class ExerciseListView(LoginRequiredMixin, ListView):
    """Vue pour afficher la liste des exercices."""
    
    model = Exercise
    template_name = 'exercises/exercise_list.html'
    context_object_name = 'exercises'
    paginate_by = 10
    
    def get_queryset(self):
        user = self.request.user
        queryset = Exercise.objects.all()
        
        # Filtrer selon le type d'utilisateur
        if user.is_student:
            # Les étudiants ne voient que les exercices publiés
            queryset = queryset.filter(is_published=True)
            
            # Les exercices assignés spécifiquement à l'étudiant
            assigned_exercises = ExerciseAssignment.objects.filter(
                assigned_to=user
            ).values_list('exercise_id', flat=True)
            
            queryset = queryset.filter(
                Q(id__in=assigned_exercises) | 
                Q(publication_date__lte=timezone.now())
            )
        
        # Appliquer les filtres si présents
        form = ExerciseFilterForm(self.request.GET)
        if form.is_valid():
            # Filtrer par catégorie
            if form.cleaned_data.get('topic'):
                queryset = queryset.filter(topic=form.cleaned_data['topic'])
            
            # Filtrer par niveau de difficulté
            if form.cleaned_data.get('difficulty'):
                queryset = queryset.filter(difficulty=form.cleaned_data['difficulty'])
            
            # Filtrer par statut
            status = form.cleaned_data.get('status')
            if status == 'published':
                queryset = queryset.filter(is_published=True)
            elif status == 'draft':
                queryset = queryset.filter(is_published=False)
            elif status == 'expired':
                queryset = queryset.filter(
                    is_published=True,
                    deadline__lt=timezone.now()
                )
            
            # Recherche par titre ou description
            search_query = form.cleaned_data.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query)
                )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = ExerciseFilterForm(self.request.GET)
        context['is_teacher'] = self.request.user.is_teacher
        return context


class ExerciseDetailView(LoginRequiredMixin, DetailView):
    """Vue pour afficher les détails d'un exercice."""
    
    model = Exercise
    template_name = 'exercises/exercise_detail.html'
    context_object_name = 'exercise'
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        user = self.request.user
        
        # Vérifier les permissions d'accès
        if user.is_teacher or obj.author == user:
            return obj
        
        # Pour les étudiants, vérifier si l'exercice est publié ou assigné
        if user.is_student:
            is_assigned = ExerciseAssignment.objects.filter(
                exercise=obj, assigned_to=user
            ).exists()
            
            if obj.is_published and (
                is_assigned or 
                (obj.publication_date and obj.publication_date <= timezone.now())
            ):
                return obj
        
        # Si aucune condition n'est remplie, refuser l'accès
        raise PermissionDenied("Vous n'avez pas accès à cet exercice.")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        exercise = self.get_object()
        
        # Informations pour les professeurs
        context['is_teacher'] = user.is_teacher
        if user.is_teacher:
            context['corrections'] = exercise.corrections.all()
            context['assignments'] = exercise.assignments.all()
            context['submissions_count'] = exercise.submissions.count()
            
            # Préparer les données de soumission pour chaque assignation
            for assignment in context['assignments']:
                # Trouver la première soumission pour cet étudiant et cet exercice
                submission = exercise.submissions.filter(
                    student=assignment.assigned_to
                ).first()
                assignment.student_submission = submission
        
        # Informations pour les étudiants
        if user.is_student:
            # Vérifier si l'étudiant a déjà soumis des réponses
            context['student_submissions'] = exercise.submissions.filter(student=user).order_by('-submitted_at')
            
            # Vérifier si l'étudiant peut encore soumettre des réponses
            max_attempts = exercise.max_attempts
            current_attempts = context['student_submissions'].count()
            
            context['can_submit'] = (
                current_attempts < max_attempts and
                (not exercise.deadline or exercise.deadline > timezone.now())
            )
            
            context['remaining_attempts'] = max_attempts - current_attempts
            
            # Vérifier si l'exercice est assigné spécifiquement à l'étudiant
            context['assignment'] = ExerciseAssignment.objects.filter(
                exercise=exercise, assigned_to=user
            ).first()
            
        # Ajouter la date et l'heure actuelles pour les comparaisons dans le template
        context['now'] = timezone.now()
        
        return context


class ExerciseCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """Vue pour créer un nouvel exercice."""
    
    model = Exercise
    form_class = ExerciseForm
    template_name = 'exercises/exercise_form.html'
    
    def form_valid(self, form):
        form.instance.author = self.request.user
        
        # Générer le texte à partir du PDF pour la recherche
        if form.cleaned_data.get('file'):
            form.instance.file = form.cleaned_data['file']
            # TODO: Extraction du texte du PDF avec PyPDF2
        
        messages.success(self.request, "L'exercice a été créé avec succès.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('exercises:exercise_detail', kwargs={'pk': self.object.pk})


class ExerciseUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    """Vue pour modifier un exercice existant."""
    
    model = Exercise
    form_class = ExerciseForm
    template_name = 'exercises/exercise_form.html'
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if obj.author != self.request.user:
            raise PermissionDenied("Vous ne pouvez modifier que vos propres exercices.")
        return obj
    
    def form_valid(self, form):
        # Si un nouveau fichier est chargé, mettre à jour le contenu texte
        if form.cleaned_data.get('file'):
            # TODO: Extraction du texte du PDF avec PyPDF2
            pass
            
        messages.success(self.request, "L'exercice a été mis à jour avec succès.")
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('exercises:exercise_detail', kwargs={'pk': self.object.pk})


class ExerciseDeleteView(LoginRequiredMixin, TeacherRequiredMixin, DeleteView):
    """Vue pour supprimer un exercice."""
    
    model = Exercise
    template_name = 'exercises/exercise_confirm_delete.html'
    success_url = reverse_lazy('exercises:exercise_list')
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if obj.author != self.request.user:
            raise PermissionDenied("Vous ne pouvez supprimer que vos propres exercices.")
        return obj
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "L'exercice a été supprimé avec succès.")
        return super().delete(request, *args, **kwargs)


@login_required
def add_correction_view(request, pk):
    """Vue pour ajouter une correction à un exercice."""
    
    if not request.user.is_teacher:
        raise PermissionDenied("Seuls les professeurs peuvent ajouter des corrections.")
    
    exercise = get_object_or_404(Exercise, pk=pk)
    
    if request.method == 'POST':
        form = ExerciseCorrectionForm(request.POST, request.FILES)
        if form.is_valid():
            correction = form.save(commit=False)
            correction.exercise = exercise
            correction.author = request.user
            
            # Si c'est la première correction ou si elle est marquée comme principale
            if not exercise.corrections.exists() or form.cleaned_data['is_primary']:
                correction.is_primary = True
            
            # Extraction du texte du fichier PDF
            if form.cleaned_data.get('file'):
                # TODO: Extraction du texte du PDF avec PyPDF2
                pass
            
            correction.save()
            
            messages.success(request, "La correction a été ajoutée avec succès.")
            return redirect('exercises:exercise_detail', pk=exercise.pk)
    else:
        form = ExerciseCorrectionForm()
    
    return render(request, 'exercises/add_correction.html', {
        'form': form,
        'exercise': exercise
    })


@login_required
def assign_exercise_view(request, pk):
    """Vue pour assigner un exercice à un étudiant."""
    
    if not request.user.is_teacher:
        raise PermissionDenied("Seuls les professeurs peuvent assigner des exercices.")
    
    exercise = get_object_or_404(Exercise, pk=pk)
    
    if request.method == 'POST':
        form = ExerciseAssignmentForm(request.POST, exercise=exercise)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.exercise = exercise
            assignment.assigned_by = request.user
            assignment.save()
            
            messages.success(
                request, 
                f"L'exercice a été assigné à {assignment.assigned_to.get_full_name() or assignment.assigned_to.email}."
            )
            return redirect('exercises:exercise_detail', pk=exercise.pk)
    else:
        form = ExerciseAssignmentForm(exercise=exercise)
    
    return render(request, 'exercises/assign_exercise.html', {
        'form': form,
        'exercise': exercise
    })


@login_required
def remove_assignment_view(request, pk, assignment_id):
    """Vue pour supprimer une assignation d'exercice."""
    
    if not request.user.is_teacher:
        raise PermissionDenied("Seuls les professeurs peuvent modifier les assignations.")
    
    exercise = get_object_or_404(Exercise, pk=pk)
    assignment = get_object_or_404(ExerciseAssignment, pk=assignment_id, exercise=exercise)
    
    if request.method == 'POST':
        student_name = assignment.assigned_to.get_full_name() or assignment.assigned_to.email
        assignment.delete()
        messages.success(request, f"L'assignation pour {student_name} a été supprimée.")
        return redirect('exercises:exercise_detail', pk=exercise.pk)
    
    return render(request, 'exercises/remove_assignment_confirm.html', {
        'exercise': exercise,
        'assignment': assignment
    })


class TopicListView(LoginRequiredMixin, ListView):
    """Vue pour afficher la liste des catégories d'exercices."""
    
    model = Topic
    template_name = 'exercises/topic_list.html'
    context_object_name = 'topics'


class TopicCreateView(LoginRequiredMixin, TeacherRequiredMixin, CreateView):
    """Vue pour créer une nouvelle catégorie d'exercice."""
    
    model = Topic
    form_class = TopicForm
    template_name = 'exercises/topic_form.html'
    success_url = reverse_lazy('exercises:topic_list')
    
    def form_valid(self, form):
        messages.success(self.request, "La catégorie a été créée avec succès.")
        return super().form_valid(form)


class TopicUpdateView(LoginRequiredMixin, TeacherRequiredMixin, UpdateView):
    """Vue pour modifier une catégorie d'exercice."""
    
    model = Topic
    form_class = TopicForm
    template_name = 'exercises/topic_form.html'
    success_url = reverse_lazy('exercises:topic_list')
    
    def form_valid(self, form):
        messages.success(self.request, "La catégorie a été mise à jour avec succès.")
        return super().form_valid(form)