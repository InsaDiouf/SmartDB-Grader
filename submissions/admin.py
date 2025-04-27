from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.db.models import F
from .models import Submission, Evaluation, FeedbackCategory, FeedbackItem


# Ajoutez cette classe de filtre personnalisée
class IsLateFilter(admin.SimpleListFilter):
    title = 'délai dépassé'
    parameter_name = 'is_late'
    
    def lookups(self, request, model_admin):
        return (
            ('yes', 'Oui'),
            ('no', 'Non'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(is_late=True)
        if self.value() == 'no':
            return queryset.filter(is_late=False)


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
    # Remplacez 'is_late' par le filtre personnalisé IsLateFilter
    list_filter = ('status', 'exercise__topic', IsLateFilter, 'submitted_at')
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
