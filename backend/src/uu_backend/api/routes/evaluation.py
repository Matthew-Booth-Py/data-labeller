"""API routes for extraction evaluation."""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.models.evaluation import (
    BenchmarkDataset,
    BenchmarkDatasetCreate,
    BenchmarkDatasetDocument,
    BenchmarkDatasetDocumentCreate,
    BenchmarkRunCreate,
    BenchmarkRunResult,
    ExtractionEvaluationCreate,
    ExtractionEvaluationListResponse,
    ExtractionEvaluationResponse,
    EvaluationSummary,
    EvaluationSummaryResponse,
    ProjectEvaluationCreate,
    ProjectEvaluationResponse,
    PromptComparisonResponse,
    PromptVersion,
    PromptVersionCreate,
    PromptVersionUpdate,
)
from uu_backend.services.evaluation_service import get_evaluation_service

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# Evaluation endpoints


@router.post("/benchmarks/datasets", response_model=BenchmarkDataset)
def create_benchmark_dataset(request: BenchmarkDatasetCreate):
    """Create a benchmark dataset and optional split assignments."""
    sqlite_client = get_sqlite_client()
    try:
        dataset = sqlite_client.create_benchmark_dataset(request.model_dump(exclude={"documents"}))
        for doc in request.documents:
            sqlite_client.add_benchmark_dataset_document(
                dataset_id=dataset["id"],
                document_id=doc.document_id,
                split=doc.split,
                tags=doc.tags,
                doc_subtype=doc.doc_subtype,
            )
        loaded = sqlite_client.get_benchmark_dataset(dataset["id"])
        if not loaded:
            raise ValueError("Failed to load created dataset")
        return BenchmarkDataset.model_validate(loaded)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create benchmark dataset: {str(e)}")


@router.get("/benchmarks/datasets", response_model=list[BenchmarkDataset])
def list_benchmark_datasets(
    document_type_id: Optional[str] = Query(None, description="Filter by document type"),
):
    """List benchmark datasets."""
    sqlite_client = get_sqlite_client()
    datasets = sqlite_client.list_benchmark_datasets(document_type_id=document_type_id)
    return [
        BenchmarkDataset.model_validate(
            {
                **dataset,
                "documents": sqlite_client.get_benchmark_dataset(dataset["id"]).get("documents", []),
            }
        )
        for dataset in datasets
    ]


@router.post("/benchmarks/datasets/{dataset_id}/documents", response_model=BenchmarkDatasetDocument)
def add_benchmark_dataset_document(dataset_id: str, request: BenchmarkDatasetDocumentCreate):
    """Add or update a benchmark dataset document assignment."""
    sqlite_client = get_sqlite_client()
    dataset = sqlite_client.get_benchmark_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Benchmark dataset not found")
    doc = sqlite_client.add_benchmark_dataset_document(
        dataset_id=dataset_id,
        document_id=request.document_id,
        split=request.split,
        tags=request.tags,
        doc_subtype=request.doc_subtype,
    )
    return BenchmarkDatasetDocument.model_validate(doc)


@router.post("/run-benchmark", response_model=BenchmarkRunResult)
def run_benchmark(request: BenchmarkRunCreate):
    """Run benchmark evaluation over a dataset with optional quality gates."""
    try:
        evaluation_service = get_evaluation_service()
        return evaluation_service.evaluate_benchmark(
            dataset_id=request.dataset_id,
            prompt_version_id=request.prompt_version_id,
            baseline_run_id=request.baseline_run_id,
            use_llm_refinement=request.use_llm_refinement,
            use_structured_output=request.use_structured_output,
            evaluated_by=request.evaluated_by,
            notes=request.notes,
            required_field_gates=request.required_field_gates,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark evaluation failed: {str(e)}")


@router.get("/benchmarks/runs/{run_id}", response_model=BenchmarkRunResult)
def get_benchmark_run(run_id: str):
    """Get a persisted benchmark run summary."""
    sqlite_client = get_sqlite_client()
    run = sqlite_client.get_benchmark_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    return BenchmarkRunResult.model_validate(run)


@router.post("/run", response_model=ExtractionEvaluationResponse)
def run_evaluation(request: ExtractionEvaluationCreate):
    """
    Run extraction evaluation on a document.

    Compares extraction results against ground truth annotations.
    Requires the document to be:
    1. Classified (has document type)
    2. Annotated (has ground truth labels)
    """
    try:
        evaluation_service = get_evaluation_service()
        evaluation = evaluation_service.evaluate_extraction(
            document_id=request.document_id,
            prompt_version_id=request.prompt_version_id,
            use_llm_refinement=request.use_llm_refinement,
            use_structured_output=request.use_structured_output,
            evaluated_by=request.evaluated_by,
            notes=request.notes,
        )
        return ExtractionEvaluationResponse(evaluation=evaluation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/run-project", response_model=ProjectEvaluationResponse)
def run_project_evaluation(request: ProjectEvaluationCreate):
    """
    Run extraction evaluation on all labeled documents in a project.

    Compares extraction results against ground truth annotations for all
    documents with the specified document type that have annotations.
    """
    try:
        evaluation_service = get_evaluation_service()
        evaluations = evaluation_service.evaluate_project(
            document_type_id=request.document_type_id,
            prompt_version_id=request.prompt_version_id,
            use_llm_refinement=request.use_llm_refinement,
            use_structured_output=request.use_structured_output,
            evaluated_by=request.evaluated_by,
            notes=request.notes,
        )
        return ProjectEvaluationResponse(
            evaluations=evaluations,
            total=len(evaluations),
            successful=len(evaluations),
            failed=0
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Project evaluation failed: {str(e)}")


@router.get("/{evaluation_id}", response_model=ExtractionEvaluationResponse)
def get_evaluation(evaluation_id: str):
    """Get a specific evaluation by ID."""
    sqlite_client = get_sqlite_client()
    evaluation = sqlite_client.get_evaluation(evaluation_id)

    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return ExtractionEvaluationResponse(evaluation=evaluation)


@router.get("", response_model=ExtractionEvaluationListResponse)
def list_evaluations(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    document_type_id: Optional[str] = Query(None, description="Filter by document type"),
    prompt_version_id: Optional[str] = Query(None, description="Filter by prompt version"),
    limit: int = Query(100, ge=1, le=1000, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """List evaluations with optional filters."""
    sqlite_client = get_sqlite_client()
    evaluations, total = sqlite_client.list_evaluations(
        document_id=document_id,
        document_type_id=document_type_id,
        prompt_version_id=prompt_version_id,
        limit=limit,
        offset=offset,
    )

    return ExtractionEvaluationListResponse(evaluations=evaluations, total=total)


@router.delete("/{evaluation_id}", response_model=dict)
def delete_evaluation(evaluation_id: str):
    """Delete a specific evaluation by ID."""
    sqlite_client = get_sqlite_client()
    success = sqlite_client.delete_evaluation(evaluation_id)

    if not success:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {"message": "Evaluation deleted successfully"}


@router.get("/summary/aggregate", response_model=EvaluationSummaryResponse)
def get_evaluation_summary(
    prompt_version_id: Optional[str] = Query(None, description="Filter by prompt version"),
    document_type_id: Optional[str] = Query(None, description="Filter by document type"),
):
    """
    Get aggregated evaluation metrics.

    Returns average accuracy, precision, recall, F1 across all evaluations
    matching the filters.
    """
    sqlite_client = get_sqlite_client()
    summary_data = sqlite_client.get_evaluation_summary(
        prompt_version_id=prompt_version_id,
        document_type_id=document_type_id,
    )

    if not summary_data:
        raise HTTPException(
            status_code=404,
            detail="No evaluations found matching the criteria"
        )

    # Convert to EvaluationSummary model
    summary = EvaluationSummary(
        prompt_version_id=summary_data.get("prompt_version_id"),
        prompt_version_name=summary_data.get("prompt_version_name"),
        document_type_id=summary_data.get("document_type_id"),
        total_evaluations=summary_data["total_evaluations"],
        avg_accuracy=summary_data["avg_accuracy"],
        avg_precision=summary_data["avg_precision"],
        avg_recall=summary_data["avg_recall"],
        avg_f1_score=summary_data["avg_f1_score"],
        field_performance=summary_data.get("field_performance", {}),
        earliest_evaluation=datetime.fromisoformat(summary_data["earliest_evaluation"]) if summary_data.get("earliest_evaluation") else None,
        latest_evaluation=datetime.fromisoformat(summary_data["latest_evaluation"]) if summary_data.get("latest_evaluation") else None,
    )

    return EvaluationSummaryResponse(summary=summary)


@router.get("/compare/prompts", response_model=PromptComparisonResponse)
def compare_prompt_versions(
    document_type_id: Optional[str] = Query(None, description="Filter by document type"),
):
    """
    Compare performance across different prompt versions.

    Returns aggregated metrics for each prompt version, allowing
    side-by-side comparison.
    """
    sqlite_client = get_sqlite_client()

    # Get all prompt versions
    prompt_versions = sqlite_client.list_prompt_versions(document_type_id=document_type_id)

    if not prompt_versions:
        raise HTTPException(
            status_code=404,
            detail="No prompt versions found"
        )

    # Get summary for each prompt version
    comparisons = []
    for pv in prompt_versions:
        summary_data = sqlite_client.get_evaluation_summary(
            prompt_version_id=pv.id,
            document_type_id=document_type_id,
        )

        if summary_data:
            summary = EvaluationSummary(
                prompt_version_id=summary_data.get("prompt_version_id"),
                prompt_version_name=summary_data.get("prompt_version_name"),
                document_type_id=summary_data.get("document_type_id"),
                total_evaluations=summary_data["total_evaluations"],
                avg_accuracy=summary_data["avg_accuracy"],
                avg_precision=summary_data["avg_precision"],
                avg_recall=summary_data["avg_recall"],
                avg_f1_score=summary_data["avg_f1_score"],
                field_performance=summary_data.get("field_performance", {}),
                earliest_evaluation=datetime.fromisoformat(summary_data["earliest_evaluation"]) if summary_data.get("earliest_evaluation") else None,
                latest_evaluation=datetime.fromisoformat(summary_data["latest_evaluation"]) if summary_data.get("latest_evaluation") else None,
            )
            comparisons.append(summary)

    # Sort by F1 score descending
    comparisons.sort(key=lambda x: x.avg_f1_score, reverse=True)

    return PromptComparisonResponse(
        comparisons=comparisons,
        document_type_id=document_type_id,
    )


# Prompt version endpoints


@router.post("/prompts", response_model=dict)
def create_prompt_version(request: PromptVersionCreate):
    """Create a new prompt version for extraction."""
    sqlite_client = get_sqlite_client()

    prompt_version = PromptVersion(
        id=str(uuid4()),
        name=request.name,
        document_type_id=request.document_type_id,
        system_prompt=request.system_prompt,
        user_prompt_template=request.user_prompt_template,
        description=request.description,
        is_active=request.is_active,
        created_by=request.created_by,
        created_at=datetime.utcnow(),
    )

    version_id = sqlite_client.create_prompt_version(prompt_version)

    return {"id": version_id, "message": "Prompt version created successfully"}


@router.get("/prompts/{version_id}", response_model=dict)
def get_prompt_version(version_id: str):
    """Get a specific prompt version by ID."""
    sqlite_client = get_sqlite_client()
    prompt_version = sqlite_client.get_prompt_version(version_id)

    if not prompt_version:
        raise HTTPException(status_code=404, detail="Prompt version not found")

    return {"prompt_version": prompt_version}


@router.get("/prompts", response_model=dict)
def list_prompt_versions(
    document_type_id: Optional[str] = Query(None, description="Filter by document type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List prompt versions with optional filters."""
    sqlite_client = get_sqlite_client()
    prompt_versions = sqlite_client.list_prompt_versions(
        document_type_id=document_type_id,
        is_active=is_active,
    )

    return {"prompt_versions": prompt_versions, "total": len(prompt_versions)}


@router.patch("/prompts/{version_id}", response_model=dict)
def update_prompt_version(version_id: str, request: PromptVersionUpdate):
    """Update a prompt version."""
    sqlite_client = get_sqlite_client()

    # Build updates dict from non-None fields
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.system_prompt is not None:
        updates["system_prompt"] = request.system_prompt
    if request.user_prompt_template is not None:
        updates["user_prompt_template"] = request.user_prompt_template
    if request.description is not None:
        updates["description"] = request.description
    if request.is_active is not None:
        updates["is_active"] = request.is_active

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    success = sqlite_client.update_prompt_version(version_id, updates)

    if not success:
        raise HTTPException(status_code=404, detail="Prompt version not found")

    return {"message": "Prompt version updated successfully"}


@router.delete("/prompts/{version_id}", response_model=dict)
def delete_prompt_version(version_id: str):
    """Delete a prompt version."""
    sqlite_client = get_sqlite_client()
    success = sqlite_client.delete_prompt_version(version_id)

    if not success:
        raise HTTPException(status_code=404, detail="Prompt version not found")

    return {"message": "Prompt version deleted successfully"}


@router.get("/prompts/active/current", response_model=dict)
def get_active_prompt_version(
    document_type_id: Optional[str] = Query(None, description="Document type ID"),
):
    """Get the currently active prompt version for a document type."""
    sqlite_client = get_sqlite_client()
    prompt_version = sqlite_client.get_active_prompt_version(document_type_id)

    if not prompt_version:
        raise HTTPException(
            status_code=404,
            detail="No active prompt version found for this document type"
        )

    return {"prompt_version": prompt_version}
