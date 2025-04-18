from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Administration Django
    path('admin/', admin.site.urls),
    
    # Page d'accueil
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    
    # Applications
    path('accounts/', include('accounts.urls')),
    path('exercises/', include('exercises.urls')),
    path('submissions/', include('submissions.urls')),
    path('dashboard/', include('dashboard.urls')),
    
    # OAuth (seulement si django-allauth est configuré)
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),]

# Ajouter les routes pour servir les médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Ajouter la barre de débogage en développement
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]
    
    # Page d'erreur personnalisée en développement
    urlpatterns += [
        path('404/', TemplateView.as_view(template_name='404.html'), name='404'),
        path('500/', TemplateView.as_view(template_name='500.html'), name='500'),
    ]