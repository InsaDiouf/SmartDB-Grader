from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import StudentProfile, TeacherProfile

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """Formulaire personnalisé d'inscription utilisateur."""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'})
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom'})
    )
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    user_type = forms.ChoiceField(
        choices=User.USER_TYPE_CHOICES,
        required=True,
        widget=forms.RadioSelect()
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'user_type', 'password1', 'password2')


class CustomAuthenticationForm(AuthenticationForm):
    """Formulaire personnalisé d'authentification."""
    
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe'})
    )


class UserProfileForm(forms.ModelForm):
    """Formulaire pour le profil utilisateur de base."""
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'profile_picture', 'bio')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class StudentProfileForm(forms.ModelForm):
    """Formulaire pour les informations spécifiques au profil étudiant."""
    
    class Meta:
        model = StudentProfile
        fields = ('student_id', 'academic_year', 'specialization')
        widgets = {
            'student_id': forms.TextInput(attrs={'class': 'form-control'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TeacherProfileForm(forms.ModelForm):
    """Formulaire pour les informations spécifiques au profil enseignant."""
    
    class Meta:
        model = TeacherProfile
        fields = ('department', 'title', 'specializations')
        widgets = {
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'specializations': forms.TextInput(attrs={'class': 'form-control'}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    """Formulaire personnalisé de changement de mot de passe."""
    
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Ancien mot de passe'})
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nouveau mot de passe'})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmation du nouveau mot de passe'})
    )