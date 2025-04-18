from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DetailView, UpdateView, ListView, FormView
from django.contrib.auth import get_user_model

from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, UserProfileForm,
    StudentProfileForm, TeacherProfileForm, CustomPasswordChangeForm
)
from .models import StudentProfile, TeacherProfile

User = get_user_model()


def register_view(request):
    """Vue pour l'inscription d'un nouvel utilisateur."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Créer l'utilisateur
                user = form.save()
                
                # Créer le profil correspondant au type d'utilisateur
                if user.is_student:
                    StudentProfile.objects.create(user=user)
                elif user.is_teacher:
                    TeacherProfile.objects.create(user=user)
                
                # Connecter l'utilisateur avec le backend spécifié
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, "Inscription réussie !")
                
                # Rediriger vers la page d'accueil
                return redirect('home')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """Vue pour la connexion d'un utilisateur."""
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=email, password=password)
            
            if user is not None:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"Bienvenue, {user.get_full_name() or user.email} !")
                
                # Rediriger vers la page demandée ou la page d'accueil
                next_page = request.GET.get('next', 'home')
                return redirect(next_page)
            else:
                messages.error(request, "Identifiants invalides.")
        else:
            messages.error(request, "Erreur de connexion. Veuillez vérifier vos identifiants.")
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Vue pour la déconnexion d'un utilisateur."""
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('home')


@login_required
def profile_view(request):
    """Vue pour afficher le profil de l'utilisateur connecté."""
    user = request.user
    
    # Déterminer le type de profil
    context = {
        'user': user,
        'is_student': user.is_student,
        'is_teacher': user.is_teacher,
    }
    
    # Ajouter les informations spécifiques au profil
    if user.is_student and hasattr(user, 'student_profile'):
        context['profile'] = user.student_profile
    elif user.is_teacher and hasattr(user, 'teacher_profile'):
        context['profile'] = user.teacher_profile
    
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile_view(request):
    """Vue pour modifier le profil de l'utilisateur connecté."""
    user = request.user
    
    # Préparer les formulaires appropriés
    if request.method == 'POST':
        # Formulaire du profil de base
        user_form = UserProfileForm(request.POST, request.FILES, instance=user)
        
        # Formulaire spécifique au type d'utilisateur
        if user.is_student and hasattr(user, 'student_profile'):
            profile_form = StudentProfileForm(request.POST, instance=user.student_profile)
        elif user.is_teacher and hasattr(user, 'teacher_profile'):
            profile_form = TeacherProfileForm(request.POST, instance=user.teacher_profile)
        else:
            profile_form = None
        
        # Validation et enregistrement
        if user_form.is_valid() and (profile_form is None or profile_form.is_valid()):
            with transaction.atomic():
                user_form.save()
                if profile_form:
                    profile_form.save()
                messages.success(request, "Profil mis à jour avec succès !")
                return redirect('accounts:profile')
        else:
            messages.error(request, "Erreur lors de la mise à jour du profil.")
    else:
        # Initialiser les formulaires
        user_form = UserProfileForm(instance=user)
        
        if user.is_student and hasattr(user, 'student_profile'):
            profile_form = StudentProfileForm(instance=user.student_profile)
        elif user.is_teacher and hasattr(user, 'teacher_profile'):
            profile_form = TeacherProfileForm(instance=user.teacher_profile)
        else:
            profile_form = None
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'is_student': user.is_student,
        'is_teacher': user.is_teacher,
    }
    
    return render(request, 'accounts/edit_profile.html', context)


@login_required
def change_password_view(request):
    """Vue pour changer le mot de passe de l'utilisateur."""
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Mise à jour de la session pour éviter la déconnexion
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été mis à jour avec succès !")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Erreur lors du changement de mot de passe.")
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})


class TeacherRequiredMixin(UserPassesTestMixin):
    """Mixin pour restreindre l'accès aux professeurs uniquement."""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_teacher


class StudentListView(LoginRequiredMixin, TeacherRequiredMixin, ListView):
    """Vue pour afficher la liste des étudiants (pour les professeurs)."""
    
    model = User
    template_name = 'accounts/student_list.html'
    context_object_name = 'students'
    
    def get_queryset(self):
        return User.objects.filter(user_type='student')


class StudentDetailView(LoginRequiredMixin, TeacherRequiredMixin, DetailView):
    """Vue pour afficher les détails d'un étudiant (pour les professeurs)."""
    
    model = User
    template_name = 'accounts/student_detail.html'
    context_object_name = 'student'
    
    def get_queryset(self):
        return User.objects.filter(user_type='student')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        
        # Ajouter les informations sur les exercices et les soumissions
        context['submissions'] = student.submissions.all().order_by('-submitted_at')
        context['assignments'] = student.assigned_exercises.all()
        
        return context