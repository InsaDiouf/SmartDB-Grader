import logging
import asyncio
from django.utils import timezone
from django.db import transaction
from .services import AIEvaluationService
from submissions.models import Submission, Evaluation, FeedbackItem, FeedbackCategory

logger = logging.getLogger(__name__)


class SubmissionEvaluator:
    """
    Classe principale pour l'évaluation des soumissions d'exercices.
    Coordonne le processus complet d'évaluation, de l'envoi à l'IA à 
    l'enregistrement des résultats.
    """
    
    def __init__(self):
        """Initialisation de l'évaluateur."""
        self.ai_service = AIEvaluationService()
    
    async def evaluate_submission(self, submission_id):
        """
        Évaluer une soumission spécifique et enregistrer les résultats.
        
        Args:
            submission_id: ID de la soumission à évaluer
            
        Returns:
            Evaluation: Instance de l'évaluation créée ou None en cas d'échec
        """
        try:
            submission = Submission.objects.get(id=submission_id)
        except Submission.DoesNotExist:
            logger.error(f"Soumission {submission_id} introuvable.")
            return None
        
        # Vérifier si la soumission est prête à être évaluée
        if submission.status != 'pending':
            logger.warning(f"Soumission {submission_id} non prête pour évaluation (statut: {submission.status}).")
            return None
        
        # Mettre à jour le statut de la soumission
        submission.status = 'processing'
        submission.save()
        
        try:
            # Envoyer à l'IA pour évaluation
            evaluation_result = await self.ai_service.evaluate_submission(submission)
            
            if not evaluation_result:
                submission.status = 'error'
                submission.save()
                logger.error(f"Échec de l'évaluation pour la soumission {submission_id}.")
                return None
            
            # Enregistrer les résultats de l'évaluation
            evaluation = self._save_evaluation_results(submission, evaluation_result)
            
            # Mettre à jour le statut de la soumission
            submission.status = 'completed'
            submission.processed_at = timezone.now()
            submission.save()
            
            return evaluation
            
        except Exception as e:
            logger.exception(f"Erreur lors de l'évaluation de la soumission {submission_id}: {str(e)}")
            submission.status = 'error'
            submission.save()
            return None
    
    @transaction.atomic
    def _save_evaluation_results(self, submission, evaluation_result):
        """
        Enregistrer les résultats de l'évaluation dans la base de données.
        
        Args:
            submission: Instance de la soumission évaluée
            evaluation_result: Résultats de l'évaluation par l'IA
            
        Returns:
            Evaluation: Instance de l'évaluation créée
        """
        # Créer ou mettre à jour l'évaluation
        try:
            evaluation = Evaluation.objects.get(submission=submission)
        except Evaluation.DoesNotExist:
            evaluation = Evaluation(submission=submission)
        
        # Extraire la note
        score = 0
        if isinstance(evaluation_result, dict):
            if 'score' in evaluation_result:
                score = float(evaluation_result['score'])
            elif 'grade' in evaluation_result:
                score = float(evaluation_result['grade'])
        
        # Normaliser la note sur le total des points de l'exercice
        total_points = submission.exercise.total_points
        if score > total_points:
            # Si la note est sur 20 mais l'exercice est sur un autre total
            if score <= 20 and total_points != 20:
                score = (score / 20) * total_points
        
        # Calculer le pourcentage
        percentage = (score / total_points * 100) if total_points > 0 else 0
        
        # Mettre à jour l'évaluation
        evaluation.score = score
        evaluation.percentage = percentage
        
        # Extraire le feedback général
        if isinstance(evaluation_result, dict):
            if 'feedback' in evaluation_result:
                evaluation.general_feedback = evaluation_result['feedback']
            elif 'general_comment' in evaluation_result:
                evaluation.general_feedback = evaluation_result['general_comment']
            
            # Enregistrer la structure complète pour le feedback détaillé
            evaluation.detailed_feedback = evaluation_result
        else:
            # Si le résultat n'est pas un dict, l'enregistrer en texte
            evaluation.general_feedback = str(evaluation_result)
            evaluation.detailed_feedback = {"raw_result": str(evaluation_result)}
        
        evaluation.created_by_ai = True
        evaluation.reviewed_by_teacher = False
        evaluation.save()
        
        # Créer les éléments de feedback détaillés
        self._create_feedback_items(evaluation, evaluation_result)
        
        # Mettre à jour les statistiques de l'étudiant
        self._update_student_statistics(submission.student, evaluation)
        
        return evaluation
    
    def _create_feedback_items(self, evaluation, evaluation_result):
        """
        Créer des éléments de feedback détaillés à partir des résultats de l'IA.
        
        Args:
            evaluation: Instance de l'évaluation
            evaluation_result: Résultats de l'évaluation par l'IA
        """
        # Supprimer les anciens éléments de feedback
        FeedbackItem.objects.filter(evaluation=evaluation).delete()
        
        if not isinstance(evaluation_result, dict):
            return
        
        # Catégorie par défaut pour les feedbacks
        default_category, _ = FeedbackCategory.objects.get_or_create(
            name="Général",
            defaults={"description": "Commentaires généraux sur la soumission"}
        )
        
        # Chercher les éléments de feedback dans la structure de résultats
        order = 0
        
        # Cas 1: Liste de points forts/faibles
        if 'strengths' in evaluation_result and isinstance(evaluation_result['strengths'], list):
            for item in evaluation_result['strengths']:
                FeedbackItem.objects.create(
                    evaluation=evaluation,
                    category=default_category,
                    title="Point fort",
                    content=item,
                    feedback_type="positive",
                    order=order
                )
                order += 1
        
        if 'weaknesses' in evaluation_result and isinstance(evaluation_result['weaknesses'], list):
            for item in evaluation_result['weaknesses']:
                FeedbackItem.objects.create(
                    evaluation=evaluation,
                    category=default_category,
                    title="Point à améliorer",
                    content=item,
                    feedback_type="improvement",
                    order=order
                )
                order += 1
        
        # Cas 2: Liste de commentaires détaillés
        if 'detailed_feedback' in evaluation_result and isinstance(evaluation_result['detailed_feedback'], list):
            for item in evaluation_result['detailed_feedback']:
                if isinstance(item, dict):
                    # S'il y a une structure avec type et contenu
                    title = item.get('title', 'Commentaire')
                    content = item.get('content', '')
                    feedback_type = item.get('type', 'suggestion')
                    
                    FeedbackItem.objects.create(
                        evaluation=evaluation,
                        category=default_category,
                        title=title,
                        content=content,
                        feedback_type=feedback_type,
                        order=order
                    )
                    order += 1
                elif isinstance(item, str):
                    # Si c'est juste une chaîne de caractères
                    FeedbackItem.objects.create(
                        evaluation=evaluation,
                        category=default_category,
                        title="Commentaire",
                        content=item,
                        feedback_type="suggestion",
                        order=order
                    )
                    order += 1
        
        # Cas 3: Si pas de structure spécifique mais qu'il y a un feedback général
        if order == 0 and evaluation.general_feedback:
            FeedbackItem.objects.create(
                evaluation=evaluation,
                category=default_category,
                title="Évaluation globale",
                content=evaluation.general_feedback,
                feedback_type="suggestion",
                order=0
            )
    
    def _update_student_statistics(self, student, evaluation):
        """
        Mettre à jour les statistiques du profil étudiant.
        
        Args:
            student: Instance de l'utilisateur étudiant
            evaluation: Instance de l'évaluation
        """
        try:
            # Vérifier si l'étudiant a un profil
            if hasattr(student, 'student_profile'):
                profile = student.student_profile
                
                # Incrémenter le nombre d'exercices complétés
                profile.exercises_completed += 1
                
                # Calculer la moyenne mise à jour
                completed_count = profile.exercises_completed
                current_avg = profile.average_score
                new_score = evaluation.score_out_of_20
                
                # Formule pour mettre à jour la moyenne
                if completed_count > 1:
                    new_avg = ((current_avg * (completed_count - 1)) + new_score) / completed_count
                else:
                    new_avg = new_score
                
                profile.average_score = new_avg
                profile.save()
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des statistiques de l'étudiant: {str(e)}")


# Fonction utilitaire pour évaluer une soumission de manière asynchrone
async def evaluate_submission_async(submission_id):
    """
    Fonction utilitaire pour évaluer une soumission de manière asynchrone.
    
    Args:
        submission_id: ID de la soumission à évaluer
            
    Returns:
        Evaluation: Instance de l'évaluation créée ou None en cas d'échec
    """
    evaluator = SubmissionEvaluator()
    return await evaluator.evaluate_submission(submission_id)


# Fonction synchrone pour lancer l'évaluation (à utiliser dans les vues)
# Remplacer la fonction existante
def evaluate_submission(submission_id):
    """
    Fonction synchrone pour lancer l'évaluation (à utiliser dans les vues).
    
    Args:
        submission_id: ID de la soumission à évaluer
            
    Returns:
        Evaluation: Instance de l'évaluation créée ou None en cas d'échec
    """
    # Créer un nouvel event loop au lieu d'utiliser asyncio.run
    import asyncio
    try:
        # Pour les contextes où il n'y a pas déjà de loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(evaluate_submission_async(submission_id))
    except RuntimeError:
        # Si nous sommes déjà dans un contexte asynchrone
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(evaluate_submission_async(submission_id))
    finally:
        if 'loop' in locals() and loop is not asyncio.get_event_loop():
            loop.close()


# Fonction pour évaluer les soumissions en attente (à utiliser dans des tâches planifiées)
def evaluate_pending_submissions(limit=10):
    """
    Évaluer les soumissions en attente.
    
    Args:
        limit: Nombre maximum de soumissions à évaluer
            
    Returns:
        int: Nombre de soumissions traitées avec succès
    """
    pending_submissions = Submission.objects.filter(
        status='pending'
    ).order_by('submitted_at')[:limit]
    
    success_count = 0
    for submission in pending_submissions:
        try:
            result = evaluate_submission(submission.id)
            if result:
                success_count += 1
        except Exception as e:
            logger.exception(f"Erreur lors de l'évaluation de la soumission {submission.id}: {str(e)}")
    
    return success_count