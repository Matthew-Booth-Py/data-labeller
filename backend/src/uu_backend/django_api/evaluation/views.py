"""DRF views for evaluation endpoints."""

from datetime import datetime
from uuid import uuid4

from pydantic import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.models.evaluation import (
    BenchmarkDataset,
    BenchmarkDatasetCreate,
    BenchmarkDatasetDocument,
    BenchmarkDatasetDocumentCreate,
    BenchmarkRunCreate,
    EvaluationSummary,
    ExtractionEvaluationCreate,
    FieldPromptVersion,
    FieldPromptVersionCreate,
    FieldPromptVersionUpdate,
    ProjectEvaluationCreate,
    PromptVersion,
    PromptVersionCreate,
    PromptVersionUpdate,
)
from uu_backend.repositories import get_repository
from uu_backend.services.evaluation_service import get_evaluation_service


def _validation_error_response(exc: ValidationError) -> Response:
    return Response({"detail": exc.errors()}, status=422)


def _parse_int(value: str | None, default: int, *, min_value: int | None = None, max_value: int | None = None):
    if value is None:
        parsed = default
    else:
        try:
            parsed = int(value)
        except ValueError:
            return None
    if min_value is not None and parsed < min_value:
        return None
    if max_value is not None and parsed > max_value:
        return None
    return parsed


def _parse_optional_bool(value: str | None):
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return None


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


class EvaluationRootView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        repository = get_repository()
        limit = _parse_int(request.query_params.get("limit"), 100, min_value=1, max_value=1000)
        offset = _parse_int(request.query_params.get("offset"), 0, min_value=0)
        if limit is None:
            return Response({"detail": "limit must be an integer between 1 and 1000"}, status=422)
        if offset is None:
            return Response({"detail": "offset must be an integer >= 0"}, status=422)

        evaluations, total = repository.list_evaluations(
            document_id=request.query_params.get("document_id"),
            document_type_id=request.query_params.get("document_type_id"),
            prompt_version_id=request.query_params.get("prompt_version_id"),
            limit=limit,
            offset=offset,
        )
        return Response({"evaluations": _jsonable(evaluations), "total": total})


class EvaluationPrefixView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        if not parts:
            return Response({"detail": "Not Found"}, status=404)

        if parts == ["benchmarks", "datasets"]:
            datasets = repository.list_benchmark_datasets(document_type_id=request.query_params.get("document_type_id"))
            payload = []
            for dataset in datasets:
                dataset_id = dataset.get("id") if isinstance(dataset, dict) else getattr(dataset, "id", None)
                loaded = repository.get_benchmark_dataset(dataset_id) if dataset_id else None
                payload.append(
                    BenchmarkDataset.model_validate(
                        {
                            **dataset,
                            "documents": (loaded or {}).get("documents", []),
                        }
                    ).model_dump(mode="json")
                )
            return Response(payload)

        if len(parts) == 3 and parts[:2] == ["benchmarks", "runs"]:
            run = repository.get_benchmark_run(parts[2])
            if not run:
                return Response({"detail": "Benchmark run not found"}, status=404)
            return Response(_jsonable(run))

        if len(parts) == 2 and parts[0] == "results":
            evaluation = repository.get_evaluation(parts[1])
            if not evaluation:
                return Response({"detail": "Evaluation not found"}, status=404)
            return Response({"evaluation": _jsonable(evaluation)})

        if parts == ["summary", "aggregate"]:
            summary_data = repository.get_evaluation_summary(
                prompt_version_id=request.query_params.get("prompt_version_id"),
                document_type_id=request.query_params.get("document_type_id"),
            )
            if not summary_data:
                return Response({"detail": "No evaluations found matching the criteria"}, status=404)

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
                earliest_evaluation=(
                    datetime.fromisoformat(summary_data["earliest_evaluation"])
                    if summary_data.get("earliest_evaluation")
                    else None
                ),
                latest_evaluation=(
                    datetime.fromisoformat(summary_data["latest_evaluation"])
                    if summary_data.get("latest_evaluation")
                    else None
                ),
            )
            return Response({"summary": summary.model_dump(mode="json")})

        if parts == ["compare", "prompts"]:
            document_type_id = request.query_params.get("document_type_id")
            prompt_versions = repository.list_prompt_versions(document_type_id=document_type_id)
            if not prompt_versions:
                return Response({"detail": "No prompt versions found"}, status=404)

            comparisons = []
            for pv in prompt_versions:
                pv_id = pv.id if hasattr(pv, "id") else pv.get("id")
                summary_data = repository.get_evaluation_summary(
                    prompt_version_id=pv_id,
                    document_type_id=document_type_id,
                )
                if not summary_data:
                    continue
                comparisons.append(
                    EvaluationSummary(
                        prompt_version_id=summary_data.get("prompt_version_id"),
                        prompt_version_name=summary_data.get("prompt_version_name"),
                        document_type_id=summary_data.get("document_type_id"),
                        total_evaluations=summary_data["total_evaluations"],
                        avg_accuracy=summary_data["avg_accuracy"],
                        avg_precision=summary_data["avg_precision"],
                        avg_recall=summary_data["avg_recall"],
                        avg_f1_score=summary_data["avg_f1_score"],
                        field_performance=summary_data.get("field_performance", {}),
                        earliest_evaluation=(
                            datetime.fromisoformat(summary_data["earliest_evaluation"])
                            if summary_data.get("earliest_evaluation")
                            else None
                        ),
                        latest_evaluation=(
                            datetime.fromisoformat(summary_data["latest_evaluation"])
                            if summary_data.get("latest_evaluation")
                            else None
                        ),
                    )
                )

            comparisons.sort(key=lambda item: item.avg_f1_score, reverse=True)
            return Response(
                {
                    "comparisons": [item.model_dump(mode="json") for item in comparisons],
                    "document_type_id": document_type_id,
                }
            )

        if parts == ["prompts"]:
            is_active_raw = request.query_params.get("is_active")
            is_active = _parse_optional_bool(is_active_raw)
            if is_active_raw is not None and is_active is None:
                return Response({"detail": "is_active must be boolean"}, status=422)
            prompt_versions = repository.list_prompt_versions(
                document_type_id=request.query_params.get("document_type_id"),
                is_active=is_active,
            )
            return Response({"prompt_versions": _jsonable(prompt_versions), "total": len(prompt_versions)})

        if len(parts) == 2 and parts[0] == "prompts":
            prompt_version = repository.get_prompt_version(parts[1])
            if not prompt_version:
                return Response({"detail": "Prompt version not found"}, status=404)
            return Response({"prompt_version": _jsonable(prompt_version)})

        if parts == ["prompts", "active", "current"]:
            prompt_version = repository.get_active_prompt_version(request.query_params.get("document_type_id"))
            if not prompt_version:
                return Response(
                    {"detail": "No active prompt version found for this document type"},
                    status=404,
                )
            return Response({"prompt_version": _jsonable(prompt_version)})

        if parts == ["field-prompts", "list"]:
            is_active_raw = request.query_params.get("is_active")
            is_active = _parse_optional_bool(is_active_raw)
            if is_active_raw is not None and is_active is None:
                return Response({"detail": "is_active must be boolean"}, status=422)
            field_prompt_versions = repository.list_field_prompt_versions(
                document_type_id=request.query_params.get("document_type_id"),
                field_name=request.query_params.get("field_name"),
                is_active=is_active,
            )
            return Response(
                {
                    "field_prompt_versions": _jsonable(field_prompt_versions),
                    "total": len(field_prompt_versions),
                }
            )

        if len(parts) == 3 and parts[:2] == ["field-prompts", "version"]:
            field_prompt_version = repository.get_field_prompt_version(parts[2])
            if not field_prompt_version:
                return Response({"detail": "Field prompt version not found"}, status=404)
            return Response({"field_prompt_version": _jsonable(field_prompt_version)})

        if parts == ["field-prompts", "active", "current"]:
            document_type_id = request.query_params.get("document_type_id")
            field_name = request.query_params.get("field_name")
            if not document_type_id:
                return Response({"detail": "document_type_id is required"}, status=422)
            if not field_name:
                return Response({"detail": "field_name is required"}, status=422)
            field_prompt_version = repository.get_active_field_prompt_version(document_type_id, field_name)
            if not field_prompt_version:
                return Response(
                    {"detail": "No active field prompt version found for this field"},
                    status=404,
                )
            return Response({"field_prompt_version": _jsonable(field_prompt_version)})

        if parts == ["field-prompts", "active", "by-document-type"]:
            document_type_id = request.query_params.get("document_type_id")
            if not document_type_id:
                return Response({"detail": "document_type_id is required"}, status=422)
            prompts = repository.list_active_field_prompt_versions(document_type_id)
            versions = repository.list_active_field_prompt_version_names(document_type_id)
            timestamps = repository.list_active_field_prompt_version_timestamps(document_type_id)
            return Response(
                {
                    "field_prompts": prompts,
                    "field_versions": versions,
                    "field_version_updated_at": timestamps,
                    "total": len(prompts),
                }
            )

        return Response({"detail": "Not Found"}, status=404)

    def post(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        body = request.data if isinstance(request.data, dict) else {}

        if parts == ["benchmarks", "datasets"]:
            try:
                parsed = BenchmarkDatasetCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            try:
                dataset = repository.create_benchmark_dataset(parsed.model_dump(exclude={"documents"}))
                dataset_id = dataset["id"] if isinstance(dataset, dict) else dataset.id
                for doc in parsed.documents:
                    repository.add_benchmark_dataset_document(
                        dataset_id=dataset_id,
                        document_id=doc.document_id,
                        split=doc.split,
                        tags=doc.tags,
                        doc_subtype=doc.doc_subtype,
                    )
                loaded = repository.get_benchmark_dataset(dataset_id)
                if not loaded:
                    raise ValueError("Failed to load created dataset")
                return Response(BenchmarkDataset.model_validate(loaded).model_dump(mode="json"))
            except Exception as exc:
                return Response({"detail": f"Failed to create benchmark dataset: {exc}"}, status=400)

        if len(parts) == 4 and parts[0] == "benchmarks" and parts[1] == "datasets" and parts[3] == "documents":
            try:
                parsed = BenchmarkDatasetDocumentCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            dataset = repository.get_benchmark_dataset(parts[2])
            if not dataset:
                return Response({"detail": "Benchmark dataset not found"}, status=404)

            doc = repository.add_benchmark_dataset_document(
                dataset_id=parts[2],
                document_id=parsed.document_id,
                split=parsed.split,
                tags=parsed.tags,
                doc_subtype=parsed.doc_subtype,
            )
            return Response(BenchmarkDatasetDocument.model_validate(doc).model_dump(mode="json"))

        if parts == ["run-benchmark"]:
            try:
                parsed = BenchmarkRunCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            try:
                evaluation_service = get_evaluation_service()
                result = evaluation_service.evaluate_benchmark(
                    dataset_id=parsed.dataset_id,
                    prompt_version_id=parsed.prompt_version_id,
                    baseline_run_id=parsed.baseline_run_id,
                    use_llm_refinement=parsed.use_llm_refinement,
                    use_structured_output=parsed.use_structured_output,
                    comparator_mode=parsed.comparator_mode,
                    fuzzy_threshold=parsed.fuzzy_threshold,
                    evaluated_by=parsed.evaluated_by,
                    notes=parsed.notes,
                    required_field_gates=parsed.required_field_gates,
                )
                return Response(result.model_dump(mode="json"))
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            except Exception as exc:
                return Response({"detail": f"Benchmark evaluation failed: {exc}"}, status=500)

        if parts == ["run"]:
            try:
                parsed = ExtractionEvaluationCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            try:
                evaluation_service = get_evaluation_service()
                evaluation = evaluation_service.evaluate_extraction(
                    document_id=parsed.document_id,
                    prompt_version_id=parsed.prompt_version_id,
                    use_llm_refinement=parsed.use_llm_refinement,
                    use_structured_output=parsed.use_structured_output,
                    comparator_mode=parsed.comparator_mode,
                    fuzzy_threshold=parsed.fuzzy_threshold,
                    evaluated_by=parsed.evaluated_by,
                    notes=parsed.notes,
                )
                return Response({"evaluation": _jsonable(evaluation)})
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            except Exception as exc:
                return Response({"detail": f"Evaluation failed: {exc}"}, status=500)

        if parts == ["run-project"]:
            try:
                parsed = ProjectEvaluationCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            try:
                evaluation_service = get_evaluation_service()
                evaluations = evaluation_service.evaluate_project(
                    document_type_id=parsed.document_type_id,
                    prompt_version_id=parsed.prompt_version_id,
                    use_llm_refinement=parsed.use_llm_refinement,
                    use_structured_output=parsed.use_structured_output,
                    comparator_mode=parsed.comparator_mode,
                    fuzzy_threshold=parsed.fuzzy_threshold,
                    evaluated_by=parsed.evaluated_by,
                    notes=parsed.notes,
                )
                return Response(
                    {
                        "evaluations": _jsonable(evaluations),
                        "total": len(evaluations),
                        "successful": len(evaluations),
                        "failed": 0,
                    }
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            except Exception as exc:
                return Response({"detail": f"Project evaluation failed: {exc}"}, status=500)

        if parts == ["prompts"]:
            try:
                parsed = PromptVersionCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            prompt_version = PromptVersion(
                id=str(uuid4()),
                name=parsed.name or "0.0",
                document_type_id=parsed.document_type_id,
                system_prompt=parsed.system_prompt,
                user_prompt_template=parsed.user_prompt_template,
                description=parsed.description,
                is_active=parsed.is_active,
                created_by=parsed.created_by,
                created_at=datetime.utcnow(),
            )
            version_id = repository.create_prompt_version(prompt_version)
            return Response({"id": version_id, "message": "Prompt version created successfully"})

        if parts == ["field-prompts"]:
            try:
                parsed = FieldPromptVersionCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            field_prompt_version = FieldPromptVersion(
                id=str(uuid4()),
                name=parsed.name or "0.0",
                document_type_id=parsed.document_type_id,
                field_name=parsed.field_name,
                extraction_prompt=parsed.extraction_prompt,
                description=parsed.description,
                is_active=parsed.is_active,
                created_by=parsed.created_by,
                created_at=datetime.utcnow(),
            )
            version_id = repository.create_field_prompt_version(field_prompt_version)
            return Response({"id": version_id, "message": "Field prompt version created successfully"})

        return Response({"detail": "Not Found"}, status=404)

    def patch(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        body = request.data if isinstance(request.data, dict) else {}

        if len(parts) == 2 and parts[0] == "prompts":
            try:
                parsed = PromptVersionUpdate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            updates = {}
            if parsed.name is not None:
                updates["name"] = parsed.name
            if parsed.system_prompt is not None:
                updates["system_prompt"] = parsed.system_prompt
            if parsed.user_prompt_template is not None:
                updates["user_prompt_template"] = parsed.user_prompt_template
            if parsed.description is not None:
                updates["description"] = parsed.description
            if parsed.is_active is not None:
                updates["is_active"] = parsed.is_active

            if not updates:
                return Response({"detail": "No fields to update"}, status=400)

            success = repository.update_prompt_version(parts[1], updates)
            if not success:
                return Response({"detail": "Prompt version not found"}, status=404)
            return Response({"message": "Prompt version updated successfully"})

        if len(parts) == 3 and parts[:2] == ["field-prompts", "version"]:
            try:
                parsed = FieldPromptVersionUpdate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            updates = {}
            if parsed.name is not None:
                updates["name"] = parsed.name
            if parsed.extraction_prompt is not None:
                updates["extraction_prompt"] = parsed.extraction_prompt
            if parsed.description is not None:
                updates["description"] = parsed.description
            if parsed.is_active is not None:
                updates["is_active"] = parsed.is_active

            if not updates:
                return Response({"detail": "No fields to update"}, status=400)

            success = repository.update_field_prompt_version(parts[2], updates)
            if not success:
                return Response({"detail": "Field prompt version not found"}, status=404)
            return Response({"message": "Field prompt version updated successfully"})

        return Response({"detail": "Not Found"}, status=404)

    def delete(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]

        if len(parts) == 2 and parts[0] == "results":
            success = repository.delete_evaluation(parts[1])
            if not success:
                return Response({"detail": "Evaluation not found"}, status=404)
            return Response({"message": "Evaluation deleted successfully"})

        if len(parts) == 2 and parts[0] == "prompts":
            success = repository.delete_prompt_version(parts[1])
            if not success:
                return Response({"detail": "Prompt version not found"}, status=404)
            return Response({"message": "Prompt version deleted successfully"})

        if len(parts) == 3 and parts[:2] == ["field-prompts", "version"]:
            success = repository.delete_field_prompt_version(parts[2])
            if not success:
                return Response({"detail": "Field prompt version not found"}, status=404)
            return Response({"message": "Field prompt version deleted successfully"})

        return Response({"detail": "Not Found"}, status=404)
