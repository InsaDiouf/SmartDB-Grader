from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, StudentProfile, TeacherProfile


class StudentProfileInline(admin.StackedInline):
    """Affiche le profil étudiant dans l'administration de l'utilisateur."""
    model = StudentProfile
    can_delete = False
    verbose_name_plural = 'Profil étudiant'
    
    fieldsets = (
        (None, {'fields': ('student_id', 'academic_year', 'specialization')}),
        (_('Statistiques'), {'fields': ('exercises_completed', 'average_score'), 'classes': ('collapse',)}),
    )


class TeacherProfileInline(admin.StackedInline):
    """Affiche le profil professeur dans l'administration de l'utilisateur."""
    model = TeacherProfile
    can_delete = False
    verbose_name_plural = 'Profil professeur'
    
    fieldsets = (
        (None, {'fields': ('department', 'title', 'specializations')}),
        (_('Statistiques'), {'fields': ('exercises_created', 'students_taught'), 'classes': ('collapse',)}),
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Personnalisation de l'administration des utilisateurs."""
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Informations personnelles'), {'fields': ('first_name', 'last_name', 'user_type', 'profile_picture', 'bio')}),
        (_('OAuth Info'), {'fields': ('oauth_provider', 'oauth_uid'), 'classes': ('collapse',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Dates importantes'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'user_type'),
        }),
    )
    list_display = ('email', 'first_name', 'last_name', 'user_type', 'is_staff')
    list_filter = ('user_type', 'is_staff', 'is_active', 'is_superuser', 'oauth_provider')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    def get_inlines(self, request, obj=None):
        """Affiche le profil approprié en fonction du type d'utilisateur."""
        if obj:
            if obj.user_type == 'student':
                return [StudentProfileInline]
            elif obj.user_type == 'teacher':
                return [TeacherProfileInline]
        return []
    
    def get_readonly_fields(self, request, obj=None):
        """Rend certains champs en lecture seule pour les utilisateurs existants."""
        if obj:
            return ['email', 'date_joined']
        return []
    
    def save_model(self, request, obj, form, change):
        """Logique personnalisée lors de la sauvegarde d'un utilisateur."""
        # Créer automatiquement un profil si nécessaire
        super().save_model(request, obj, form, change)
        
        if not change:  # Nouveau utilisateur
            if obj.user_type == 'student' and not hasattr(obj, 'student_profile'):
                StudentProfile.objects.create(user=obj)
            elif obj.user_type == 'teacher' and not hasattr(obj, 'teacher_profile'):
                TeacherProfile.objects.create(user=obj)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    """Administration des profils étudiants."""
    
    list_display = ('user', 'student_id', 'academic_year', 'specialization', 'exercises_completed', 'average_score')
    list_filter = ('academic_year', 'specialization')
    search_fields = ('user_email', 'userfirst_name', 'user_last_name', 'student_id')
    readonly_fields = ('exercises_completed', 'average_score', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('user', 'student_id', 'academic_year', 'specialization')}),
        (_('Statistiques'), {'fields': ('exercises_completed', 'average_score')}),
        (_('Métadonnées'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    """Administration des profils professeurs."""
    
    list_display = ('user', 'department', 'title', 'exercises_created', 'students_taught')
    list_filter = ('department', 'title')
    search_fields = ('user_email', 'userfirst_name', 'user_last_name', 'department', 'title')
    readonly_fields = ('exercises_created', 'students_taught', 'created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('user', 'department', 'title', 'specializations')}),
        (_('Statistiques'), {'fields': ('exercises_created', 'students_taught')}),
        (_('Métadonnées'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )