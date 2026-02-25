"""Celery tasks for evaluation."""

import logging
from uuid import uuid4

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_evaluation_task(
    self, document_id: str, project_id: str = None, run_extraction: bool = True, notes: str = None
):
    """
    Run evaluation as a background task.

    Args:
        document_id: Document ID to evaluate
        project_id: Optional project ID
        run_extraction: Whether to run extraction
        notes: Optional notes

    Returns:
        Evaluation run ID
    """
    logger.info(f"[CELERY] Starting evaluation task for document {document_id}")

    try:
        from uu_backend.django_data.models import EvaluationRunModel
        from uu_backend.services.evaluation_service import get_evaluation_service

        # Run evaluation
        evaluation_service = get_evaluation_service()

        # Since we're in a synchronous Celery task, we need to run the async function
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                evaluation_service.evaluate_document(
                    document_id=document_id, run_extraction=run_extraction
                )
            )
        finally:
            loop.close()

        logger.info(
            f"[CELERY] Evaluation completed, got {len(result.field_comparisons)} comparisons"
        )

        # Save to database
        evaluation_id = str(uuid4())
        EvaluationRunModel.objects.create(
            id=evaluation_id,
            document_id=document_id,
            project_id=project_id,
            metrics=result.metrics.model_dump(),
            field_comparisons=[fc.model_dump() for fc in result.field_comparisons],
            instance_comparisons={
                k: [ic.model_dump() for ic in v] for k, v in result.instance_comparisons.items()
            },
            extraction_time_ms=result.extraction_time_ms,
            evaluation_time_ms=result.evaluation_time_ms,
            notes=notes,
        )

        logger.info(f"[CELERY] Evaluation saved with ID {evaluation_id}")
        return evaluation_id

    except ValueError as e:
        logger.error(
            f"[CELERY] Evaluation failed with non-retriable validation error: {e}", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(f"[CELERY] Evaluation failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
