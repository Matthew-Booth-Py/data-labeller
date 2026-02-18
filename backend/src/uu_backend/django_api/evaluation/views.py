"""Evaluation API views."""

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from asgiref.sync import async_to_sync, sync_to_async
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from uu_backend.django_data.models import EvaluationRunModel
from uu_backend.models.evaluation import (
    EvaluationRun,
    EvaluationRunCreate,
    EvaluationRunListResponse,
    EvaluationRunResponse,
    EvaluationSummary,
)
from uu_backend.services.evaluation_service import get_evaluation_service

logger = logging.getLogger(__name__)


@csrf_exempt
def test_endpoint(request):
    """Simple test endpoint."""
    logger.info("=== TEST ENDPOINT HIT ===")
    print("=== TEST ENDPOINT HIT ===")
    return JsonResponse({"status": "ok", "message": "Test endpoint working"})


@csrf_exempt
@require_http_methods(["GET"])
def get_task_status(request, task_id: str):
    """Get status of a Celery task."""
    from celery.result import AsyncResult
    
    result = AsyncResult(task_id)
    
    if result.ready():
        if result.successful():
            evaluation_id = result.result
            # Fetch the evaluation run
            try:
                evaluation_run = EvaluationRunModel.objects.get(id=evaluation_id)
                return JsonResponse({
                    "status": "completed",
                    "task_id": task_id,
                    "evaluation_id": evaluation_id,
                    "evaluated_at": evaluation_run.evaluated_at.isoformat()
                })
            except EvaluationRunModel.DoesNotExist:
                return JsonResponse({
                    "status": "completed",
                    "task_id": task_id,
                    "evaluation_id": evaluation_id,
                })
        else:
            return JsonResponse({
                "status": "failed",
                "task_id": task_id,
                "error": str(result.result)
            }, status=500)
    else:
        return JsonResponse({
            "status": "pending",
            "task_id": task_id,
            "state": result.state
        })


@csrf_exempt
@require_http_methods(["POST"])
def run_evaluation(request):
    """Run evaluation on a document - queues a Celery task."""
    logger.info("=== RUN EVALUATION REQUEST RECEIVED ===")
    try:
        data = json.loads(request.body)
        logger.info(f"Request data: {data}")
        create_request = EvaluationRunCreate(**data)
        logger.info(f"Parsed request: document_id={create_request.document_id}, run_extraction={create_request.run_extraction}")
        
        # Queue evaluation as Celery task
        logger.info("[VIEW] Queueing evaluation task...")
        from uu_backend.tasks.evaluation_tasks import run_evaluation_task
        
        task = run_evaluation_task.delay(
            document_id=create_request.document_id,
            project_id=create_request.project_id,
            run_extraction=create_request.run_extraction,
            notes=create_request.notes
        )
        
        logger.info(f"[VIEW] Task queued with ID {task.id}")
        
        # Return immediately with task ID
        return JsonResponse({
            "status": "queued",
            "task_id": task.id,
            "message": "Evaluation started in background"
        }, status=202)
        
    except Exception as e:
        logger.error(f"Error running evaluation: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def list_evaluation_runs(request):
    """List evaluation runs with optional filters."""
    try:
        project_id = request.GET.get("project_id")
        document_id = request.GET.get("document_id")
        limit = int(request.GET.get("limit", 50))
        offset = int(request.GET.get("offset", 0))
        
        # Build query
        queryset = EvaluationRunModel.objects.all()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        if document_id:
            queryset = queryset.filter(document_id=document_id)
        
        # Get total count
        total = queryset.count()
        
        # Apply pagination
        evaluation_runs = queryset[offset:offset + limit]
        
        # Convert to response models
        runs = []
        for eval_run in evaluation_runs:
            # Reconstruct EvaluationResult from stored data
            from uu_backend.models.evaluation import (
                EvaluationMetrics,
                EvaluationResult,
                FieldComparison,
                InstanceComparison,
            )
            
            metrics = EvaluationMetrics(**eval_run.metrics)
            field_comparisons = [FieldComparison(**fc) for fc in eval_run.field_comparisons]
            instance_comparisons = {
                k: [InstanceComparison(**ic) for ic in v]
                for k, v in eval_run.instance_comparisons.items()
            }
            
            result = EvaluationResult(
                document_id=eval_run.document_id,
                metrics=metrics,
                field_comparisons=field_comparisons,
                instance_comparisons=instance_comparisons,
                extraction_time_ms=eval_run.extraction_time_ms,
                evaluation_time_ms=eval_run.evaluation_time_ms
            )
            
            run = EvaluationRun(
                id=eval_run.id,
                document_id=eval_run.document_id,
                project_id=eval_run.project_id,
                result=result,
                notes=eval_run.notes,
                evaluated_at=eval_run.evaluated_at
            )
            runs.append(run)
        
        response = EvaluationRunListResponse(runs=runs, total=total)
        return JsonResponse(response.model_dump(), safe=False)
        
    except Exception as e:
        logger.error(f"Error listing evaluation runs: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def get_evaluation_run(request, evaluation_id: str):
    """Get a specific evaluation run."""
    try:
        eval_run = EvaluationRunModel.objects.get(id=evaluation_id)
        
        # Reconstruct EvaluationResult
        from uu_backend.models.evaluation import (
            EvaluationMetrics,
            EvaluationResult,
            FieldComparison,
            InstanceComparison,
        )
        
        metrics = EvaluationMetrics(**eval_run.metrics)
        field_comparisons = [FieldComparison(**fc) for fc in eval_run.field_comparisons]
        instance_comparisons = {
            k: [InstanceComparison(**ic) for ic in v]
            for k, v in eval_run.instance_comparisons.items()
        }
        
        result = EvaluationResult(
            document_id=eval_run.document_id,
            metrics=metrics,
            field_comparisons=field_comparisons,
            instance_comparisons=instance_comparisons,
            extraction_time_ms=eval_run.extraction_time_ms,
            evaluation_time_ms=eval_run.evaluation_time_ms
        )
        
        run = EvaluationRun(
            id=eval_run.id,
            document_id=eval_run.document_id,
            project_id=eval_run.project_id,
            result=result,
            notes=eval_run.notes,
            evaluated_at=eval_run.evaluated_at
        )
        
        response = EvaluationRunResponse(run=run)
        return JsonResponse(response.model_dump())
        
    except EvaluationRunModel.DoesNotExist:
        return JsonResponse({"error": "Evaluation run not found"}, status=404)
    except Exception as e:
        logger.error(f"Error getting evaluation run: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def get_evaluation_summary(request):
    """Get aggregated evaluation metrics."""
    try:
        project_id = request.GET.get("project_id")
        
        # Build query
        queryset = EvaluationRunModel.objects.all()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        evaluation_runs = list(queryset)
        
        if not evaluation_runs:
            # Return empty summary
            summary = EvaluationSummary(
                project_id=project_id,
                total_evaluations=0,
                total_documents=0,
                avg_accuracy=0.0,
                avg_precision=0.0,
                avg_recall=0.0,
                avg_f1_score=0.0,
                field_performance={},
                match_type_distribution={}
            )
            return JsonResponse(summary.model_dump())
        
        # Calculate aggregated metrics
        total_evaluations = len(evaluation_runs)
        unique_documents = len(set(run.document_id for run in evaluation_runs))
        
        # Aggregate flattened metrics
        accuracies = []
        precisions = []
        recalls = []
        f1_scores = []
        match_type_dist = {}
        
        # Aggregate field metrics
        from collections import defaultdict
        field_stats = defaultdict(lambda: {
            "total_occurrences": 0,
            "correct_predictions": 0,
            "incorrect_predictions": 0,
            "missing_predictions": 0,
            "confidences": []
        })
        
        for eval_run in evaluation_runs:
            metrics = eval_run.metrics
            flattened = metrics.get("flattened", {})
            
            accuracies.append(flattened.get("accuracy", 0.0))
            precisions.append(flattened.get("precision", 0.0))
            recalls.append(flattened.get("recall", 0.0))
            f1_scores.append(flattened.get("f1_score", 0.0))
            
            # Aggregate match types
            for match_type, count in flattened.get("match_type_distribution", {}).items():
                match_type_dist[match_type] = match_type_dist.get(match_type, 0) + count
            
            # Aggregate field metrics
            for field_name, field_metric in metrics.get("field_metrics", {}).items():
                stats = field_stats[field_name]
                stats["total_occurrences"] += field_metric.get("total_occurrences", 0)
                stats["correct_predictions"] += field_metric.get("correct_predictions", 0)
                stats["incorrect_predictions"] += field_metric.get("incorrect_predictions", 0)
                stats["missing_predictions"] += field_metric.get("missing_predictions", 0)
                stats["confidences"].append(field_metric.get("avg_confidence", 0.0))
        
        # Calculate averages
        avg_accuracy = sum(accuracies) / len(accuracies)
        avg_precision = sum(precisions) / len(precisions)
        avg_recall = sum(recalls) / len(recalls)
        avg_f1_score = sum(f1_scores) / len(f1_scores)
        
        # Build field performance
        from uu_backend.models.evaluation import FieldMetrics
        field_performance = {}
        
        for field_name, stats in field_stats.items():
            total = stats["total_occurrences"]
            correct = stats["correct_predictions"]
            total_pred = correct + stats["incorrect_predictions"]
            
            accuracy = correct / total if total > 0 else 0.0
            precision = correct / total_pred if total_pred > 0 else 0.0
            recall = correct / total if total > 0 else 0.0
            avg_confidence = sum(stats["confidences"]) / len(stats["confidences"]) if stats["confidences"] else 0.0
            
            field_performance[field_name] = FieldMetrics(
                field_name=field_name,
                total_occurrences=total,
                correct_predictions=correct,
                incorrect_predictions=stats["incorrect_predictions"],
                missing_predictions=stats["missing_predictions"],
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                avg_confidence=avg_confidence,
                match_type_distribution={}
            )
        
        summary = EvaluationSummary(
            project_id=project_id,
            total_evaluations=total_evaluations,
            total_documents=unique_documents,
            avg_accuracy=avg_accuracy,
            avg_precision=avg_precision,
            avg_recall=avg_recall,
            avg_f1_score=avg_f1_score,
            field_performance=field_performance,
            match_type_distribution=match_type_dist
        )
        
        return JsonResponse(summary.model_dump())
        
    except Exception as e:
        logger.error(f"Error getting evaluation summary: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_evaluation_run(request, evaluation_id: str):
    """Delete an evaluation run."""
    try:
        eval_run = EvaluationRunModel.objects.get(id=evaluation_id)
        eval_run.delete()
        
        return JsonResponse({"status": "deleted", "id": evaluation_id})
        
    except EvaluationRunModel.DoesNotExist:
        return JsonResponse({"error": "Evaluation run not found"}, status=404)
    except Exception as e:
        logger.error(f"Error deleting evaluation run: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
