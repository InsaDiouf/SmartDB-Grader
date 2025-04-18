# Generated by Django 5.0.6 on 2025-04-17 23:49

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('submissions', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIModel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('model_id', models.CharField(help_text='Identifiant du modèle dans Ollama (ex: deepseek-coder:latest)', max_length=100)),
                ('endpoint_url', models.URLField(default='http://localhost:11434/api/generate', help_text="URL de l'API Ollama")),
                ('default_temperature', models.FloatField(default=0.7)),
                ('default_max_tokens', models.IntegerField(default=2048)),
                ('accuracy_score', models.FloatField(default=0.0, help_text='Score de précision (0-1) basé sur les évaluations manuelles')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='AIPromptTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('prompt_text', models.TextField(help_text='Template de prompt avec variables (ex: {exercise}, {submission}, {correction})')),
                ('task_type', models.CharField(choices=[('evaluation', 'Évaluation complète'), ('grading', 'Notation uniquement'), ('feedback', 'Feedback détaillé'), ('plagiarism', 'Détection de plagiat')], default='evaluation', max_length=20)),
                ('available_variables', models.JSONField(default=list, help_text='Liste des variables utilisables dans ce template')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recommended_model', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='prompt_templates', to='ai_engine.aimodel')),
            ],
        ),
        migrations.CreateModel(
            name='AIEvaluationJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prompt_used', models.TextField(help_text="Prompt complet envoyé à l'IA")),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('processing', 'En cours'), ('completed', 'Terminé'), ('failed', 'Échoué')], default='pending', max_length=20)),
                ('response_json', models.JSONField(blank=True, help_text="Réponse complète de l'API en JSON", null=True)),
                ('processing_time', models.FloatField(blank=True, help_text='Temps de traitement en secondes', null=True)),
                ('token_usage', models.IntegerField(default=0, help_text='Nombre de tokens utilisés')),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_jobs', to='submissions.submission')),
                ('model', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluation_jobs', to='ai_engine.aimodel')),
                ('prompt_template', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluation_jobs', to='ai_engine.aiprompttemplate')),
            ],
        ),
        migrations.CreateModel(
            name='AIFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.IntegerField(help_text="Note de 1 à 5 sur la qualité de l'évaluation")),
                ('comment', models.TextField(blank=True)),
                ('error_type', models.CharField(choices=[('none', 'Aucune erreur'), ('too_harsh', 'Trop sévère'), ('too_lenient', 'Trop indulgent'), ('missed_points', 'Points importants manqués'), ('incorrect', 'Évaluation incorrecte'), ('other', 'Autre problème')], default='none', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('evaluation_job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_feedback', to='ai_engine.aievaluationjob')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_feedback', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('evaluation_job', 'user')},
            },
        ),
    ]
