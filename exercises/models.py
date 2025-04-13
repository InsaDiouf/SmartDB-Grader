from django.db import models
from django.conf import settings
from django.utils.text import slugify
import uuid
import os

def exercise_file_path(instance, filename):
    """Générer le chemin pour les fichiers d'exercice."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('exercises', filename)


def correction_file_path(instance, filename):
    """Générer le chemin pour les fichiers de correction."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('corrections', filename)


class Topic(models.Model):
    """Catégorie/thématique pour les exercices."""
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def _str_(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class DifficultyLevel(models.Model):
    """Niveau de difficulté pour les exercices."""
    
    name = models.CharField(max_length=50)  # Facile, Moyen, Difficile, Avancé
    value = models.IntegerField()  # 1, 2, 3, 4
    description = models.TextField(blank=True)
    
    def _str_(self):
        return self.name


class Exercise(models.Model):
    """Modèle principal pour les exercices."""
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    
    # Contenu
    description = models.TextField()
    
    # Relations
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_exercises'
    )
    topic = models.ForeignKey(
        Topic, 
        on_delete=models.SET_NULL,
        null=True, 
        related_name='exercises'
    )
    difficulty = models.ForeignKey(
        DifficultyLevel,
        on_delete=models.SET_NULL,
        null=True
    )
    
    # Fichier du sujet (PDF)
    file = models.FileField(upload_to=exercise_file_path, blank=True, null=True)
    file_content_text = models.TextField(
        blank=True, 
        help_text="Texte extrait du fichier PDF pour l'indexation et la recherche"
    )
    
    # Options et paramètres
    time_limit_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Temps limite pour compléter l'exercice (en minutes)"
    )
    max_attempts = models.PositiveIntegerField(
        default=1,
        help_text="Nombre maximum de tentatives autorisées"
    )
    total_points = models.PositiveIntegerField(
        default=20,
        help_text="Nombre total de points pour cet exercice"
    )
    
    # Visibilité et statut
    is_published = models.BooleanField(default=False)
    publication_date = models.DateTimeField(blank=True, null=True)
    deadline = models.DateTimeField(blank=True, null=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def _str_(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Vérifier si la date limite est dépassée."""
        from django.utils import timezone
        if self.deadline:
            return timezone.now() > self.deadline
        return False
    
    @property
    def has_corrections(self):
        """Vérifier si l'exercice a des corrections."""
        return self.corrections.exists()


class ExerciseCorrection(models.Model):
    """Correction de référence pour un exercice."""
    
    exercise = models.ForeignKey(
        Exercise, 
        on_delete=models.CASCADE,
        related_name='corrections'
    )
    
    # Contenu de la correction
    text_content = models.TextField(
        blank=True,
        help_text="Contenu textuel de la correction"
    )
    file = models.FileField(
        upload_to=correction_file_path, 
        blank=True, 
        null=True,
        help_text="Fichier PDF de la correction"
    )
    
    # Options et métadonnées
    is_primary = models.BooleanField(
        default=False,
        help_text="Indique si cette correction est la référence principale"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_corrections'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def _str_(self):
        return f"Correction pour {self.exercise.title}"
    
    class Meta:
        unique_together = ('exercise', 'is_primary')


class ExerciseAssignment(models.Model):
    """Attribution d'exercices à des étudiants ou groupes spécifiques."""
    
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    
    # Pour attribution individuelle
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assigned_exercises',
        blank=True,
        null=True
    )
    
    # Options d'affectation
    custom_deadline = models.DateTimeField(blank=True, null=True)
    note_to_student = models.TextField(blank=True)
    
    # Métadonnées
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    def _str_(self):
        if self.assigned_to:
            return f"{self.exercise.title} assigné à {self.assigned_to.email}"
        return f"{self.exercise.title} assigné à plusieurs étudiants"
    
    @property
    def effective_deadline(self):
        """Retourne la date limite effective (personnalisée ou celle de l'exercice)."""
        return self.custom_deadline or self.exercise.deadline
