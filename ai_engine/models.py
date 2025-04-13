from django.db import models
from django.conf import settings


class AIModel(models.Model):
    """Définition d'un modèle d'IA utilisable pour les évaluations."""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Configuration technique
    model_id = models.CharField(
        max_length=100,
        help_text="Identifiant du modèle dans Ollama (ex: deepseek-coder:latest)"
    )
    endpoint_url = models.URLField(
        default="http://localhost:11434/api/generate",
        help_text="URL de l'API Ollama"
    )
    
    # Paramètres par défaut
    default_temperature = models.FloatField(default=0.7)
    default_max_tokens = models.IntegerField(default=2048)
    
    # Métriques de performance
    accuracy_score = models.FloatField(
        default=0.0,
        help_text="Score de précision (0-1) basé sur les évaluations manuelles"
    )
    
    # Statut
    is_active = models.BooleanField(default=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name


class AIPromptTemplate(models.Model):
    """Template de prompt pour différentes tâches d'évaluation."""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Contenu du template
    prompt_text = models.TextField(
        help_text="Template de prompt avec variables (ex: {exercise}, {submission}, {correction})"
    )
    
    # Type de tâche
    TASK_TYPE_CHOICES = (
        ('evaluation', 'Évaluation complète'),
        ('grading', 'Notation uniquement'),
        ('feedback', 'Feedback détaillé'),
        ('plagiarism', 'Détection de plagiat'),
    )
    task_type = models.CharField(
        max_length=20,
        choices=TASK_TYPE_CHOICES,
        default='evaluation'
    )
    
    # Modèle recommandé
    recommended_model = models.ForeignKey(
        AIModel,
        on_delete=models.SET_NULL,
        null=True,
        related_name='prompt_templates'
    )
    
    # Variables disponibles
    available_variables = models.JSONField(
        default=list,
        help_text="Liste des variables utilisables dans ce template"
    )
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.task_type})"


class AIEvaluationJob(models.Model):
    """Tâche d'évaluation par l'IA, pour le suivi et l'historique."""
    
    # Relations
    submission = models.ForeignKey(
        'submissions.Submission',
        on_delete=models.CASCADE,
        related_name='ai_jobs'
    )
    model = models.ForeignKey(
        AIModel,
        on_delete=models.SET_NULL,
        null=True,
        related_name='evaluation_jobs'
    )
    prompt_template = models.ForeignKey(
        AIPromptTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name='evaluation_jobs'
    )
    
    # Contenu des requêtes
    prompt_used = models.TextField(
        help_text="Prompt complet envoyé à l'IA"
    )
    
    # Statut
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Résultats
    response_json = models.JSONField(
        null=True,
        blank=True,
        help_text="Réponse complète de l'API en JSON"
    )
    
    # Métriques et performances
    processing_time = models.FloatField(
        null=True, 
        blank=True,
        help_text="Temps de traitement en secondes"
    )
    token_usage = models.IntegerField(
        default=0,
        help_text="Nombre de tokens utilisés"
    )
    
    # Erreurs
    error_message = models.TextField(blank=True)
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Évaluation IA pour {self.submission}"


class AIFeedback(models.Model):
    """Feedback des utilisateurs sur les évaluations de l'IA pour améliorer le système."""
    
    # Relations
    evaluation_job = models.ForeignKey(
        AIEvaluationJob,
        on_delete=models.CASCADE,
        related_name='user_feedback'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_feedback'
    )
    
    # Contenu du feedback
    rating = models.IntegerField(
        help_text="Note de 1 à 5 sur la qualité de l'évaluation"
    )
    comment = models.TextField(blank=True)
    
    # Type d'erreur (si applicable)
    ERROR_TYPE_CHOICES = (
        ('none', 'Aucune erreur'),
        ('too_harsh', 'Trop sévère'),
        ('too_lenient', 'Trop indulgent'),
        ('missed_points', 'Points importants manqués'),
        ('incorrect', 'Évaluation incorrecte'),
        ('other', 'Autre problème'),
    )
    error_type = models.CharField(
        max_length=20,
        choices=ERROR_TYPE_CHOICES,
        default='none'
    )
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Feedback de {self.user.email} - Note: {self.rating}/5"
    
    class Meta:
        unique_together = ('evaluation_job', 'user')