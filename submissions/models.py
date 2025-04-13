from django.db import models
from django.conf import settings
import uuid
import os

def submission_file_path(instance, filename):
    """Générer le chemin pour les fichiers de soumission."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('submissions', str(instance.student.id), filename)


class Submission(models.Model):
    """Soumission d'un exercice par un étudiant."""
    
    # Relations
    exercise = models.ForeignKey(
        'exercises.Exercise',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    
    # Fichier de soumission
    file = models.FileField(upload_to=submission_file_path)
    file_content_text = models.TextField(
        blank=True, 
        help_text="Texte extrait du fichier PDF pour l'analyse par l'IA"
    )
    
    # Statut de la soumission
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('completed', 'Traitement terminé'),
        ('error', 'Erreur')
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Informations sur la tentative
    attempt_number = models.PositiveIntegerField(default=1)
    
    # Métadonnées temporelles
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    def _str_(self):
        return f"Soumission de {self.student.email} pour {self.exercise.title}"
    
    class Meta:
        unique_together = ('exercise', 'student', 'attempt_number')
        ordering = ['-submitted_at']
    
    @property
    def is_late(self):
        """Vérifier si la soumission est en retard par rapport à la date limite."""
        assignment = self.exercise.assignments.filter(assigned_to=self.student).first()
        if assignment and assignment.effective_deadline:
            return self.submitted_at > assignment.effective_deadline
        elif self.exercise.deadline:
            return self.submitted_at > self.exercise.deadline
        return False
    
    @property
    def has_feedback(self):
        """Vérifier si la soumission a un retour d'évaluation."""
        return hasattr(self, 'evaluation')


class Evaluation(models.Model):
    """Évaluation d'une soumission générée par l'IA ou modifiée par le professeur."""
    
    submission = models.OneToOneField(
        Submission,
        on_delete=models.CASCADE,
        related_name='evaluation'
    )
    
    # Résultats d'évaluation
    score = models.FloatField(
        default=0.0,
        help_text="Note sur le total des points"
    )
    percentage = models.FloatField(
        default=0.0,
        help_text="Pourcentage de réussite (0-100)"
    )
    
    # Feedback
    general_feedback = models.TextField(
        blank=True,
        help_text="Commentaire général sur la soumission"
    )
    detailed_feedback = models.JSONField(
        default=dict,
        help_text="Feedback détaillé (structure JSON)"
    )
    
    # Traçabilité
    created_by_ai = models.BooleanField(
        default=True,
        help_text="Indique si l'évaluation a été générée par l'IA"
    )
    reviewed_by_teacher = models.BooleanField(
        default=False,
        help_text="Indique si l'évaluation a été revue par un professeur"
    )
    reviewing_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_evaluations'
    )
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def _str_(self):
        return f"Évaluation pour {self.submission}"
    
    @property
    def score_out_of_20(self):
        """Convertir le score en note sur 20."""
        max_points = self.submission.exercise.total_points
        if max_points == 0:
            return 0
        return (self.score / max_points) * 20


class FeedbackCategory(models.Model):
    """Catégorie de feedback pour une meilleure organisation."""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    
    def _str_(self):
        return self.name


class FeedbackItem(models.Model):
    """Élément de feedback spécifique pour une évaluation."""
    
    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        related_name='feedback_items'
    )
    
    # Catégorisation
    category = models.ForeignKey(
        FeedbackCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='feedback_items'
    )
    
    # Contenu
    title = models.CharField(max_length=200)
    content = models.TextField()
    
    # Type de feedback
    TYPE_CHOICES = (
        ('positive', 'Positif'),
        ('improvement', 'À améliorer'),
        ('error', 'Erreur'),
        ('suggestion', 'Suggestion')
    )
    feedback_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='improvement'
    )
    
    # Impact sur la note
    point_impact = models.FloatField(
        default=0.0,
        help_text="Impact positif ou négatif sur la note"
    )
    
    # Ordre d'affichage
    order = models.PositiveIntegerField(default=0)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    
    def _str_(self):
        return self.title
    
    class Meta:
        ordering = ['order', 'feedback_type']