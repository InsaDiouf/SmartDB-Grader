from django import forms
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from .models import Submission, Evaluation, FeedbackItem


class SubmissionForm(forms.ModelForm):
    """Formulaire pour soumettre une réponse à un exercice."""
    
    file = forms.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
        widget=forms.FileInput(
            attrs={
                'class': 'form-control',
                'accept': 'application/pdf',
                'data-browse-on-zone-click': 'true',
            }
        )
    )
    
    class Meta:
        model = Submission
        fields = ['file']
    
    def __init__(self, *args, **kwargs):
        self.exercise = kwargs.pop('exercise', None)
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        # Vérifier la taille du fichier (limite à 5 Mo)
        if file and file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("La taille du fichier ne doit pas dépasser 5 Mo.")
        
        return file
    
    def clean(self):
        cleaned_data = super().clean()
        
        if self.exercise and self.student:
            # Vérifier si l'exercice est encore ouvert
            if self.exercise.deadline and self.exercise.deadline < timezone.now():
                raise forms.ValidationError(
                    "La date limite de soumission est dépassée."
                )
            
            # Vérifier le nombre de tentatives
            existing_attempts = Submission.objects.filter(
                exercise=self.exercise,
                student=self.student
            ).count()
            
            if existing_attempts >= self.exercise.max_attempts:
                raise forms.ValidationError(
                    f"Vous avez atteint le nombre maximum de tentatives ({self.exercise.max_attempts})."
                )
        
        return cleaned_data


class EvaluationReviewForm(forms.ModelForm):
    """Formulaire pour réviser une évaluation générée par l'IA."""
    
    class Meta:
        model = Evaluation
        fields = ['score', 'general_feedback', 'reviewed_by_teacher']
        widgets = {
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': '0'}),
            'general_feedback': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'reviewed_by_teacher': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)
        
        # Rendre le champ reviewed_by_teacher caché et toujours True
        self.fields['reviewed_by_teacher'].widget = forms.HiddenInput()
        self.fields['reviewed_by_teacher'].initial = True
    
    def clean_score(self):
        score = self.cleaned_data.get('score')
        max_points = self.instance.submission.exercise.total_points
        
        if score > max_points:
            raise forms.ValidationError(f"La note ne peut pas dépasser {max_points} points.")
        elif score < 0:
            raise forms.ValidationError("La note ne peut pas être négative.")
        
        return score


class FeedbackItemForm(forms.ModelForm):
    """Formulaire pour modifier un élément de feedback."""
    
    class Meta:
        model = FeedbackItem
        fields = ['title', 'content', 'feedback_type', 'point_impact']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'feedback_type': forms.Select(attrs={'class': 'form-select'}),
            'point_impact': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
        }


class NewFeedbackItemForm(FeedbackItemForm):
    """Formulaire pour ajouter un nouvel élément de feedback."""
    
    class Meta(FeedbackItemForm.Meta):
        fields = FeedbackItemForm.Meta.fields + ['category']
        widgets = {
            **FeedbackItemForm.Meta.widgets,
            'category': forms.Select(attrs={'class': 'form-select'}),
        }