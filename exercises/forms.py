from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from .models import Exercise, ExerciseCorrection, Topic, DifficultyLevel, ExerciseAssignment


class ExerciseForm(forms.ModelForm):
    """Formulaire pour la création et modification d'exercices."""
    
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.all(),
        empty_label="Sélectionner une catégorie",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    difficulty = forms.ModelChoiceField(
        queryset=DifficultyLevel.objects.all(),
        empty_label="Sélectionner un niveau de difficulté",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    file = forms.FileField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    
    is_published = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    publication_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    
    deadline = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )
    
    class Meta:
        model = Exercise
        fields = [
            'title', 'description', 'topic', 'difficulty', 'file', 
            'time_limit_minutes', 'max_attempts', 'total_points',
            'is_published', 'publication_date', 'deadline'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'time_limit_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'max_attempts': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'total_points': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        is_published = cleaned_data.get('is_published')
        publication_date = cleaned_data.get('publication_date')
        deadline = cleaned_data.get('deadline')
        
        # Si l'exercice est publié, la date de publication est requise
        if is_published and not publication_date:
            cleaned_data['publication_date'] = timezone.now()
        
        # Vérifier que la date limite est après la date de publication
        if publication_date and deadline and publication_date >= deadline:
            self.add_error('deadline', 'La date limite doit être postérieure à la date de publication.')
        
        return cleaned_data


class ExerciseCorrectionForm(forms.ModelForm):
    """Formulaire pour ajouter une correction à un exercice."""
    
    file = forms.FileField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = ExerciseCorrection
        fields = ['text_content', 'file', 'is_primary']
        widgets = {
            'text_content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        text_content = cleaned_data.get('text_content')
        file = cleaned_data.get('file')
        
        # Vérifier qu'au moins un des deux champs est rempli
        if not text_content and not file:
            raise ValidationError("Vous devez fournir soit un contenu texte, soit un fichier PDF.")
        
        return cleaned_data


class TopicForm(forms.ModelForm):
    """Formulaire pour créer ou modifier une catégorie d'exercice."""
    
    class Meta:
        model = Topic
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ExerciseAssignmentForm(forms.ModelForm):
    """Formulaire pour assigner un exercice à un étudiant."""
    
    class Meta:
        model = ExerciseAssignment
        fields = ['assigned_to', 'custom_deadline', 'note_to_student']
        widgets = {
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'custom_deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'note_to_student': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
    
    def _init_(self, *args, **kwargs):
        # On peut passer un exercice spécifique pour filtrer les assignations
        exercise = kwargs.pop('exercise', None)
        super()._init_(*args, **kwargs)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Filtrer uniquement les étudiants
        self.fields['assigned_to'].queryset = User.objects.filter(user_type='student')
        
        # Si un exercice spécifique est fourni, exclure les étudiants déjà assignés
        if exercise:
            assigned_students = exercise.assignments.values_list('assigned_to', flat=True)
            self.fields['assigned_to'].queryset = self.fields['assigned_to'].queryset.exclude(
                id__in=assigned_students
            )
    
    def clean_custom_deadline(self):
        custom_deadline = self.cleaned_data.get('custom_deadline')
        if custom_deadline and custom_deadline < timezone.now():
            raise ValidationError("La date limite doit être dans le futur.")
        return custom_deadline


class ExerciseFilterForm(forms.Form):
    """Formulaire pour filtrer les exercices."""
    
    topic = forms.ModelChoiceField(
        queryset=Topic.objects.all(),
        required=False,
        empty_label="Toutes les catégories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    difficulty = forms.ModelChoiceField(
        queryset=DifficultyLevel.objects.all(),
        required=False,
        empty_label="Tous les niveaux",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rechercher...'}),
    )
    
    status = forms.ChoiceField(
        choices=[
            ('all', 'Tous les statuts'),
            ('published', 'Publiés'),
            ('draft', 'Brouillons'),
            ('expired', 'Expirés'),
        ],
        required=False,
        initial='all',
        widget=forms.Select(attrs={'class': 'form-select'})
    )