import json
import time
import logging
import httpx
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
from .models import AIModel, AIPromptTemplate, AIEvaluationJob

logger = logging.getLogger(__name__)


class AIEvaluationService:
    """Service pour gérer les évaluations via l'API Ollama/DeepSeek."""
    
    def __init__(self, model_id=None):
        """Initialiser le service avec un modèle spécifique ou le modèle par défaut."""
        # Solution : utiliser un système d'initialisation différé
        self.ai_model = None
        self.model_id = model_id
        
        # Exécuter l'initialisation de manière synchrone si nous ne sommes pas dans un contexte async
        try:
            self._initialize_model()
        except Exception as e:
            logger.error(f"Erreur d'initialisation du modèle: {str(e)}")
    
    def _initialize_model(self):
        """Initialiser le modèle de manière synchrone."""
        if self.model_id:
            try:
                self.ai_model = AIModel.objects.get(id=self.model_id, is_active=True)
            except AIModel.DoesNotExist:
                self.ai_model = AIModel.objects.filter(is_active=True).first()
        else:
            # Utiliser le modèle par défaut
            self.ai_model = AIModel.objects.filter(is_active=True).first()
        
        if not self.ai_model:
            raise ValueError("Aucun modèle d'IA actif n'est disponible")
    
    async def evaluate_submission(self, submission, prompt_template_id=None):
        """
        Évaluer une soumission en utilisant l'IA.
        
        Args:
            submission: Instance du modèle Submission
            prompt_template_id: ID du template de prompt à utiliser (facultatif)
            
        Returns:
            dict: Résultat de l'évaluation
        """
        # Si le modèle n'est pas initialisé, essayer de l'initialiser de manière asynchrone
        if self.ai_model is None:
            try:
                await sync_to_async(self._initialize_model)()
            except Exception as e:
                logger.error(f"Erreur lors de l'initialisation asynchrone du modèle: {str(e)}")
                return None
        
        # Utiliser sync_to_async pour les opérations de base de données
        create_job = sync_to_async(AIEvaluationJob.objects.create)
        get_prompt_template = sync_to_async(AIPromptTemplate.objects.get)
        filter_prompt_template = sync_to_async(lambda: AIPromptTemplate.objects.filter(task_type='evaluation').first())
        
        # Récupérer ou créer une tâche d'évaluation
        evaluation_job = await create_job(
            submission=submission,
            model=self.ai_model,
            status='processing'
        )
        
        # Récupérer le template de prompt approprié
        prompt_template = None
        if prompt_template_id:
            try:
                prompt_template = await get_prompt_template(id=prompt_template_id)
            except AIPromptTemplate.DoesNotExist:
                prompt_template = await filter_prompt_template()
        else:
            # Utiliser le template d'évaluation par défaut
            prompt_template = await filter_prompt_template()
        
        if not prompt_template:
            # Mettre à jour le job de manière asynchrone
            await sync_to_async(self._update_job_status)(
                evaluation_job, 'failed', "Aucun template de prompt disponible"
            )
            return None
        
        # Mettre à jour le job de manière asynchrone
        await sync_to_async(self._update_job_with_template)(evaluation_job, prompt_template)
        
        # Préparer les données pour le prompt
        exercise = submission.exercise
        student = submission.student
        correction = None
        
        # Récupérer la correction si disponible
        if exercise.has_corrections:
            get_correction = sync_to_async(lambda: exercise.corrections.filter(is_primary=True).first() or exercise.corrections.first())
            correction = await get_correction()
        
        # Préparer les variables pour le template
        prompt_variables = {
            'exercise_title': exercise.title,
            'exercise_description': exercise.description,
            'exercise_content': exercise.file_content_text,
            'submission_content': submission.file_content_text,
            'student_name': await sync_to_async(student.get_full_name)(),
            'total_points': exercise.total_points,
        }
        
        # Ajouter la correction si disponible
        if correction:
            prompt_variables['correction_content'] = correction.text_content
        
        # Formater le prompt
        try:
            formatted_prompt = prompt_template.prompt_text.format(**prompt_variables)
        except KeyError as e:
            await sync_to_async(self._update_job_status)(
                evaluation_job, 'failed', f"Variable manquante dans le template: {str(e)}"
            )
            return None
        
        # Enregistrer le prompt utilisé
        await sync_to_async(self._update_job_prompt)(evaluation_job, formatted_prompt)
        
        # Préparer la requête pour l'API Ollama
        start_time = time.time()
        
        request_data = {
            "model": self.ai_model.model_id,
            "prompt": formatted_prompt,
            "temperature": self.ai_model.default_temperature,
            "max_tokens": self.ai_model.default_max_tokens,
            "stream": False,
            "format": "json"  # Demander une réponse formatée en JSON
        }
        
        # Faire la requête à l'API
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    self.ai_model.endpoint_url,
                    json=request_data
                )
                response.raise_for_status()
                result = response.json()
        except httpx.RequestError as e:
            # Gérer les erreurs de requête
            await sync_to_async(self._update_job_status)(
                evaluation_job, 'failed', f"Erreur de requête: {str(e)}"
            )
            logger.error(f"Erreur lors de la requête AI: {str(e)}")
            return None
        except Exception as e:
            # Gérer les autres erreurs
            await sync_to_async(self._update_job_status)(
                evaluation_job, 'failed', f"Erreur inattendue: {str(e)}"
            )
            logger.error(f"Erreur inattendue: {str(e)}")
            return None
        
        # Calculer le temps de traitement
        processing_time = time.time() - start_time
        
        # Mettre à jour le job avec les résultats
        await sync_to_async(self._update_job_result)(
            evaluation_job, 'completed', result, processing_time
        )
        
        # Extraire et retourner les résultats formatés
        try:
            evaluation_result = await sync_to_async(self._parse_ai_response)(result)
            return evaluation_result
        except Exception as e:
            logger.error(f"Erreur lors du parsing de la réponse AI: {str(e)}")
            await sync_to_async(self._update_job_status)(
                evaluation_job, 'failed', f"Erreur de parsing: {str(e)}"
            )
            return None
    
    def _update_job_status(self, job, status, error_message=None):
        """Mettre à jour le statut d'un job."""
        job.status = status
        if error_message:
            job.error_message = error_message
        job.save()
    
    def _update_job_with_template(self, job, template):
        """Mettre à jour le job avec un template."""
        job.prompt_template = template
        job.save()
    
    def _update_job_prompt(self, job, prompt):
        """Mettre à jour le prompt utilisé par un job."""
        job.prompt_used = prompt
        job.save()
    
    def _update_job_result(self, job, status, result, processing_time):
        """Mettre à jour un job avec les résultats."""
        job.status = status
        job.completed_at = timezone.now()
        job.processing_time = processing_time
        job.response_json = result
        
        # Extraire les tokens utilisés si disponible
        if 'usage' in result and 'total_tokens' in result['usage']:
            job.token_usage = result['usage']['total_tokens']
            
        job.save()
    
    def _parse_ai_response(self, response):
        """
        Parser la réponse brute de l'API en un format structuré.
        
        Args:
            response: Réponse JSON de l'API
            
        Returns:
            dict: Données structurées pour l'évaluation
        """
        # Extraction de la réponse générée
        if 'response' in response:
            try:
                # Tenter de parser le contenu JSON dans la réponse
                content = json.loads(response['response'])
                return content
            except json.JSONDecodeError:
                # Si ce n'est pas du JSON valide, essayer d'extraire manuellement
                text_response = response['response']
                
                # Chercher les sections communes dans la réponse texte
                result = {
                    'score': self._extract_score(text_response),
                    'feedback': self._extract_feedback(text_response),
                    'details': text_response,
                }
                return result
        
        # Fallback: retourner la réponse brute
        return response
    
    def _extract_score(self, text):
        """Extraire la note depuis une réponse texte."""
        try:
            # Chercher des patterns comme "Score: 15/20" ou "Note: 15"
            import re
            score_pattern = r'(?:score|note|grade)\s*:?\s*(\d+(?:[.,]\d+)?)\s*(?:\/\s*20)?'
            match = re.search(score_pattern, text.lower())
            if match:
                score = float(match.group(1).replace(',', '.'))
                # Si la note n'est pas sur 20, convertir
                if score > 20:
                    score = (score / 100) * 20
                return score
        except Exception:
            pass
        return 0  # Valeur par défaut
    
    def _extract_feedback(self, text):
        """Extraire le feedback général depuis une réponse texte."""
        try:
            import re
            # Chercher des sections comme "Feedback:" ou "Commentaire général:"
            patterns = [
                r'(?:feedback|commentaire général)\s*:?\s*(.*?)(?:\n\n|\n[A-Z]|$)',
                r'(?:remarques générales)\s*:?\s*(.*?)(?:\n\n|\n[A-Z]|$)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text.lower(), re.DOTALL)
                if match:
                    return match.group(1).strip()
            
            # Si pas de section spécifique, prendre les premiers paragraphes
            paragraphs = text.split('\n\n')
            if paragraphs:
                return paragraphs[0].strip()
        except Exception:
            pass
        return ""  # Valeur par défaut