import json
import time
import logging
import httpx
from django.conf import settings
from django.utils import timezone
from .models import AIModel, AIPromptTemplate, AIEvaluationJob

logger = logging.getLogger(__name__)


class AIEvaluationService:
    """Service pour gérer les évaluations via l'API Ollama/DeepSeek."""
    
    def __init__(self, model_id=None):
        """Initialiser le service avec un modèle spécifique ou le modèle par défaut."""
        if model_id:
            try:
                self.ai_model = AIModel.objects.get(id=model_id, is_active=True)
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
        # Récupérer ou créer une tâche d'évaluation
        evaluation_job = AIEvaluationJob.objects.create(
            submission=submission,
            model=self.ai_model,
            status='processing'
        )
        
        # Récupérer le template de prompt approprié
        if prompt_template_id:
            try:
                prompt_template = AIPromptTemplate.objects.get(id=prompt_template_id)
            except AIPromptTemplate.DoesNotExist:
                prompt_template = AIPromptTemplate.objects.filter(
                    task_type='evaluation'
                ).first()
        else:
            # Utiliser le template d'évaluation par défaut
            prompt_template = AIPromptTemplate.objects.filter(
                task_type='evaluation'
            ).first()
        
        if not prompt_template:
            evaluation_job.status = 'failed'
            evaluation_job.error_message = "Aucun template de prompt disponible"
            evaluation_job.save()
            return None
            
        evaluation_job.prompt_template = prompt_template
        evaluation_job.save()
        
        # Préparer les données pour le prompt
        exercise = submission.exercise
        student = submission.student
        correction = None
        
        # Récupérer la correction si disponible
        if exercise.has_corrections:
            correction = exercise.corrections.filter(is_primary=True).first()
            if not correction:
                correction = exercise.corrections.first()
        
        # Préparer les variables pour le template
        prompt_variables = {
            'exercise_title': exercise.title,
            'exercise_description': exercise.description,
            'exercise_content': exercise.file_content_text,
            'submission_content': submission.file_content_text,
            'student_name': student.get_full_name(),
            'total_points': exercise.total_points,
        }
        
        # Ajouter la correction si disponible
        if correction:
            prompt_variables['correction_content'] = correction.text_content
        
        # Formater le prompt
        try:
            formatted_prompt = prompt_template.prompt_text.format(**prompt_variables)
        except KeyError as e:
            evaluation_job.status = 'failed'
            evaluation_job.error_message = f"Variable manquante dans le template: {str(e)}"
            evaluation_job.save()
            return None
        
        # Enregistrer le prompt utilisé
        evaluation_job.prompt_used = formatted_prompt
        evaluation_job.save()
        
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
            evaluation_job.status = 'failed'
            evaluation_job.error_message = f"Erreur de requête: {str(e)}"
            evaluation_job.save()
            logger.error(f"Erreur lors de la requête AI: {str(e)}")
            return None
        except Exception as e:
            # Gérer les autres erreurs
            evaluation_job.status = 'failed'
            evaluation_job.error_message = f"Erreur inattendue: {str(e)}"
            evaluation_job.save()
            logger.error(f"Erreur inattendue: {str(e)}")
            return None
        
        # Calculer le temps de traitement
        processing_time = time.time() - start_time
        
        # Mettre à jour le job avec les résultats
        evaluation_job.status = 'completed'
        evaluation_job.completed_at = timezone.now()
        evaluation_job.processing_time = processing_time
        evaluation_job.response_json = result
        
        # Extraire les tokens utilisés si disponible
        if 'usage' in result and 'total_tokens' in result['usage']:
            evaluation_job.token_usage = result['usage']['total_tokens']
            
        evaluation_job.save()
        
        # Extraire et retourner les résultats formatés
        try:
            evaluation_result = self._parse_ai_response(result)
            return evaluation_result
        except Exception as e:
            logger.error(f"Erreur lors du parsing de la réponse AI: {str(e)}")
            evaluation_job.status = 'failed'
            evaluation_job.error_message = f"Erreur de parsing: {str(e)}"
            evaluation_job.save()
            return None
    
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