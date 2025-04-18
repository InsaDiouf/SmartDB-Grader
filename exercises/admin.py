from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import Topic, DifficultyLevel, Exercise, ExerciseCorrection, ExerciseAssignment


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    """Administration des catégories d'exercices."""
    
    list_display = ('name', 'exercise_count', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    
    def exercise_count(self, obj):
        """Affiche le nombre d'exercices associés à cette catégorie."""
        count = obj.exercises.count()
        return format_html('<span style="color: {};"><strong>{}</strong></span>',
                          'green' if count > 0 else 'grey', count)
    
    exercise_count.short_description = _('Nombre d\'exercices')


@admin.register(DifficultyLevel)
class DifficultyLevelAdmin(admin.ModelAdmin):
    """Administration des niveaux de difficulté."""
    
    list_display = ('name', 'value', 'exercise_count', 'colored_name')
    search_fields = ('name', 'description')
    list_editable = ('value',)
    
    def exercise_count(self, obj):
        """Affiche le nombre d'exercices associés à ce niveau de difficulté."""
        count = Exercise.objects.filter(difficulty=obj).count()
        return format_html('<span style="color: {};"><strong>{}</strong></span>',
                          'green' if count > 0 else 'grey', count)
    
    def colored_name(self, obj):
        """Affiche le nom avec une couleur basée sur la valeur."""
        colors = {
            1: '#28a745',  # Vert
            2: '#17a2b8',  # Bleu
            3: '#ffc107',  # Jaune
            4: '#dc3545',  # Rouge
        }
        color = colors.get(obj.value, '#6c757d')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.name)
    
    exercise_count.short_description = _('Nombre d\'exercices')
    colored_name.short_description = _('Nom coloré')


class ExerciseCorrectionInline(admin.TabularInline):
    """Affiche les corrections dans l'administration des exercices."""
    model = ExerciseCorrection
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    fields = ('author', 'is_primary', 'text_content', 'file', 'created_at')


class ExerciseAssignmentInline(admin.TabularInline):
    """Affiche les assignations dans l'administration des exercices."""
    model = ExerciseAssignment
    extra = 0
    readonly_fields = ('assigned_at',)
    fields = ('assigned_to', 'assigned_by', 'custom_deadline', 'assigned_at')


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    """Administration des exercices."""
    
    list_display = ('title', 'author', 'topic', 'difficulty_level', 'published_status', 'submission_count', 'created_at')
    list_filter = ('is_published', 'topic', 'difficulty', 'author')
    search_fields = ('title', 'description', 'author_email', 'authorfirst_name', 'author_last_name')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'submission_count')
    date_hierarchy = 'created_at'
    inlines = [ExerciseCorrectionInline, ExerciseAssignmentInline]
    
    fieldsets = (
        (None, {'fields': ('title', 'slug', 'description', 'author', 'topic', 'difficulty')}),
        (_('Contenu'), {'fields': ('file', 'file_content_text')}),
        (_('Paramètres'), {'fields': ('time_limit_minutes', 'max_attempts', 'total_points')}),
        (_('Publication'), {'fields': ('is_published', 'publication_date', 'deadline')}),
        (_('Statistiques'), {'fields': ('submission_count',), 'classes': ('collapse',)}),
        (_('Métadonnées'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def difficulty_level(self, obj):
        """Affiche le niveau de difficulté avec une couleur."""
        if not obj.difficulty:
            return '-'
        
        colors = {
            1: '#28a745',  # Vert
            2: '#17a2b8',  # Bleu
            3: '#ffc107',  # Jaune
            4: '#dc3545',  # Rouge
        }
        color = colors.get(obj.difficulty.value, '#6c757d')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', 
                          color, obj.difficulty.name)
    
    def published_status(self, obj):
        """Affiche le statut de publication avec une couleur."""
        if obj.is_published:
            return format_html('<span style="color: green;"><i class="fa fa-check"></i> Publié</span>')
        else:
            return format_html('<span style="color: grey;"><i class="fa fa-times"></i> Brouillon</span>')
    
    def submission_count(self, obj):
        """Affiche le nombre de soumissions pour cet exercice."""
        count = obj.submissions.count()
        return format_html('<span style="color: {};"><strong>{}</strong></span>',
                          'green' if count > 0 else 'grey', count)
    
    difficulty_level.short_description = _('Difficulté')
    published_status.short_description = _('Statut')
    submission_count.short_description = _('Soumissions')


@admin.register(ExerciseCorrection)
class ExerciseCorrectionAdmin(admin.ModelAdmin):
    """Administration des corrections d'exercices."""
    
    list_display = ('exercise', 'author', 'is_primary', 'has_file', 'created_at')
    list_filter = ('is_primary', 'author', 'created_at')
    search_fields = ('exercise_title', 'author_email', 'text_content')
    readonly_fields = ('created_at', 'updated_at')
    
    def has_file(self, obj):
        """Vérifie si la correction a un fichier."""
        if obj.file:
            return format_html('<span style="color: green;"><i class="fa fa-check"></i> Oui</span>')
        else:
            return format_html('<span style="color: grey;"><i class="fa fa-times"></i> Non</span>')
    
    has_file.short_description = _('Fichier')


@admin.register(ExerciseAssignment)
class ExerciseAssignmentAdmin(admin.ModelAdmin):
    """Administration des assignations d'exercices."""
    
    list_display = ('exercise', 'assigned_to', 'assigned_by', 'custom_deadline', 'assigned_at')
    list_filter = ('assigned_by', 'assigned_at')
    search_fields = ('exercise_title', 'assigned_toemail', 'assigned_tofirst_name', 'assigned_to_last_name')
    readonly_fields = ('assigned_at',)
    date_hierarchy = 'assigned_at'
    
    fieldsets = (
        (None, {'fields': ('exercise', 'assigned_to', 'assigned_by')}),
        (_('Paramètres'), {'fields': ('custom_deadline', 'note_to_student')}),
        (_('Métadonnées'), {'fields': ('assigned_at',)}),
    )