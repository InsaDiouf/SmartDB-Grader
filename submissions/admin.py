from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import Submission, Evaluation, FeedbackCategory, FeedbackItem


class EvaluationInline(admin.StackedInline):
    """Affiche l'évaluation dans l'administration des soumissions."""
    model = Evaluation
    can_delete = False
    verbose_name_plural = 'Évaluation'
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('score', 'percentage', 'general_feedback')}),
        (_('Traçabilité'), {'fields': ('created_by_ai', 'reviewed_by_teacher', 'reviewing_teacher')}),
        (_('Détails JSON'), {'fields': ('detailed_feedback',), 'classes': ('collapse',)}),
        (_('Métadonnées'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


class FeedbackItemInline(admin.TabularInline):
    """Affiche les éléments de feedback dans l'administration des évaluations."""
    model = FeedbackItem
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('title', 'category', 'feedback_type', 'point_impact', 'content', 'created_at')


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Administration des soumissions."""
    
    list_display = ('id', 'student', 'exercise', 'attempt_number', 'status_colored', 'score_display', 'is_late_display', 'submitted_at')
    list_filter = ('status', 'exercise__topic', 'is_late', 'submitted_at')
    search_fields = ('student_email', 'studentfirst_name', 'studentlast_name', 'exercise_title')
    readonly_fields = ('submitted_at', 'processed_at', 'file_content_text')
    date_hierarchy = 'submitted_at'
    inlines = [EvaluationInline]
    
    fieldsets = (
        (None, {'fields': ('student', 'exercise', 'attempt_number')}),
        (_('Fichier'), {'fields': ('file', 'file_content_text')}),
        (_('Statut'), {'fields': ('status', 'is_late')}),
        (_('Dates'), {'fields': ('submitted_at', 'processed_at')}),
    )
    
    def status_colored(self, obj):
        """Affiche le statut avec un code couleur."""
        status_colors = {
            'pending': '#ffc107',     # Jaune
            'processing': '#17a2b8',  # Bleu
            'completed': '#28a745',   # Vert
            'error': '#dc3545',       # Rouge
        }
        
        status_labels = {
            'pending': 'En attente',
            'processing': 'En traitement',
            'completed': 'Terminé',
            'error': 'Erreur',
        }
        
        color = status_colors.get(obj.status, '#6c757d')
        label = status_labels.get(obj.status, obj.status)
        
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, label)
    
    def score_display(self, obj):
        """Affiche la note si disponible."""
        if hasattr(obj, 'evaluation'):
            score = obj.evaluation.score_out_of_20
            color = 'green' if score >= 10 else 'red'
            return format_html('<span style="color: {};"><strong>{}/20</strong></span>', color, score)
        return '-'
    
    def is_late_display(self, obj):
        """Affiche si la soumission est en retard."""
        if obj.is_late:
            return format_html('<span style="color: #dc3545;"><i class="fa fa-clock"></i> En retard</span>')
        return format_html('<span style="color: #28a745;"><i class="fa fa-check"></i> À temps</span>')
    
    status_colored.short_description = _('Statut')
    score_display.short_description = _('Note')
    is_late_display.short_description = _('Délai')


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    """Administration des évaluations."""
    
    list_display = ('id', 'submission_info', 'score_display', 'percentage_display', 'evaluation_type', 'created_at')
    list_filter = ('created_by_ai', 'reviewed_by_teacher', 'created_at')
    search_fields = ('submission_studentemail', 'submissionexercise_title', 'general_feedback')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [FeedbackItemInline]
    
    fieldsets = (
        (None, {'fields': ('submission', 'score', 'percentage', 'general_feedback')}),
        (_('Traçabilité'), {'fields': ('created_by_ai', 'reviewed_by_teacher', 'reviewing_teacher')}),
        (_('Détails JSON'), {'fields': ('detailed_feedback',), 'classes': ('collapse',)}),
        (_('Métadonnées'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def submission_info(self, obj):
        """Affiche les informations de la soumission."""
        return format_html('{} - {}', obj.submission.student.email, obj.submission.exercise.title)
    
    def score_display(self, obj):
        """Affiche la note avec un code couleur."""
        score = obj.score_out_of_20
        color = 'green' if score >= 10 else 'red'
        return format_html('<span style="color: {};"><strong>{}/20</strong></span>', color, score)
    
    def percentage_display(self, obj):
        """Affiche le pourcentage avec un code couleur."""
        color = 'green' if obj.percentage >= 50 else 'red'
        return format_html('<span style="color: {};"><strong>{}%</strong></span>', color, int(obj.percentage))
    
    def evaluation_type(self, obj):
        """Affiche le type d'évaluation."""
        if obj.reviewed_by_teacher:
            return format_html('<span style="color: #17a2b8;"><i class="fa fa-user"></i> Révisée</span>')
        else:
            return format_html('<span style="color: #6c757d;"><i class="fa fa-robot"></i> IA</span>')
    
    submission_info.short_description = _('Soumission')
    score_display.short_description = _('Note')
    percentage_display.short_description = _('Pourcentage')
    evaluation_type.short_description = _('Type')


@admin.register(FeedbackCategory)
class FeedbackCategoryAdmin(admin.ModelAdmin):
    """Administration des catégories de feedback."""
    
    list_display = ('name', 'feedback_count', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    
    def feedback_count(self, obj):
        """Affiche le nombre d'éléments de feedback dans cette catégorie."""
        count = obj.feedback_items.count()
        return format_html('<span style="color: {};"><strong>{}</strong></span>',
                         'green' if count > 0 else 'grey', count)
    
    feedback_count.short_description = _('Nombre de feedbacks')


@admin.register(FeedbackItem)
class FeedbackItemAdmin(admin.ModelAdmin):
    """Administration des éléments de feedback."""
    
    list_display = ('title', 'evaluation_info', 'category', 'feedback_type_colored', 'point_impact_display', 'created_at')
    list_filter = ('feedback_type', 'category', 'created_at')
    search_fields = ('title', 'content', 'evaluation_submissionstudentemail', 'evaluationsubmissionexercise_title')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {'fields': ('evaluation', 'title', 'content')}),
        (_('Catégorisation'), {'fields': ('category', 'feedback_type', 'point_impact', 'order')}),
        (_('Métadonnées'), {'fields': ('created_at',)}),
    )
    
    def evaluation_info(self, obj):
        """Affiche les informations de l'évaluation."""
        student = obj.evaluation.submission.student.email
        exercise = obj.evaluation.submission.exercise.title
        return format_html('{} - {}', student, exercise)
    
    def feedback_type_colored(self, obj):
        """Affiche le type de feedback avec un code couleur."""
        type_colors = {
            'positive': '#28a745',     # Vert
            'improvement': '#ffc107',  # Jaune
            'error': '#dc3545',        # Rouge
            'suggestion': '#17a2b8',   # Bleu
        }
        
        type_labels = {
            'positive': 'Positif',
            'improvement': 'À améliorer',
            'error': 'Erreur',
            'suggestion': 'Suggestion',
        }
        
        color = type_colors.get(obj.feedback_type, '#6c757d')
        label = type_labels.get(obj.feedback_type, obj.feedback_type)
        
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, label)
    
    def point_impact_display(self, obj):
        """Affiche l'impact sur la note avec un code couleur."""
        if obj.point_impact == 0:
            return '-'
        
        color = 'green' if obj.point_impact > 0 else 'red'
        prefix = '+' if obj.point_impact > 0 else ''
        return format_html('<span style="color: {};"><strong>{}{}</strong></span>', color, prefix, obj.point_impact)
    
    evaluation_info.short_description = _('Évaluation')
    feedback_type_colored.short_description = _('Type')
    point_impact_display.short_description = _('Impact')