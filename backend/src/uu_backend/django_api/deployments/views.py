"""DRF views for deployment endpoints."""

from pydantic import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.ingestion.converter import get_converter
from uu_backend.models.deployment import DeploymentVersionCreate
from uu_backend.models.taxonomy import SchemaField
from uu_backend.repositories import get_repository
from uu_backend.services.extraction_service import get_extraction_service


class _UploadFileShim:
    """Minimal UploadFile-compatible wrapper for Django uploaded files."""

    def __init__(self, upload):
        self.file = upload.file
        self.filename = upload.name


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _validation_error_response(exc: ValidationError) -> Response:
    return Response({"detail": exc.errors()}, status=422)


def _run_deployment_extract(project_id: str, deployment_version: dict, file_obj: _UploadFileShim):
    converter = get_converter()
    extraction_service = get_extraction_service()

    conversion = converter.convert(file_obj.file, file_obj.filename)
    if not conversion.success:
        return None, Response({"detail": f"File conversion failed: {conversion.error}"}, status=400)

    schema_fields = [
        SchemaField.model_validate(field) for field in deployment_version["schema_fields"]
    ]
    extracted_data = extraction_service.extract_structured_from_snapshot(
        content=conversion.content,
        filename=file_obj.filename,
        document_type_name=deployment_version["document_type_name"],
        schema_fields=schema_fields,
        system_prompt=deployment_version.get("system_prompt"),
        model=deployment_version.get("model"),
    )

    payload = {
        "project_id": project_id,
        "deployment_version_id": deployment_version["id"],
        "deployment_version": deployment_version["version"],
        "document_type_id": deployment_version["document_type_id"],
        "document_type_name": deployment_version["document_type_name"],
        "filename": file_obj.filename,
        "extracted_data": extracted_data,
    }
    return payload, None


class DeploymentsPrefixView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        body = request.data if isinstance(request.data, dict) else {}

        if parts == ["versions"]:
            try:
                parsed = DeploymentVersionCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            try:
                created = repository.create_deployment_version(
                    project_id=parsed.project_id,
                    document_type_id=parsed.document_type_id,
                    prompt_version_id=parsed.prompt_version_id,
                    created_by=parsed.created_by,
                    set_active=parsed.set_active,
                )
                return Response({"version": _jsonable(created)})
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            except Exception as exc:
                return Response(
                    {"detail": f"Failed to create deployment version: {exc}"}, status=500
                )

        if (
            len(parts) == 5
            and parts[0] == "projects"
            and parts[2] == "versions"
            and parts[4] == "activate"
        ):
            activated = repository.activate_deployment_version(parts[1], parts[3])
            if not activated:
                return Response(
                    {"detail": "Deployment version not found for this project"}, status=404
                )
            return Response({"status": "activated", "active_version": _jsonable(activated)})

        if len(parts) == 3 and parts[0] == "projects" and parts[2] == "extract":
            upload = request.FILES.get("file")
            if upload is None:
                return Response({"detail": "file is required"}, status=422)
            active = repository.get_active_deployment_version(parts[1])
            if not active:
                return Response(
                    {"detail": "No active deployment version found for this project"}, status=404
                )
            payload, error_response = _run_deployment_extract(
                parts[1], active, _UploadFileShim(upload)
            )
            if error_response:
                return error_response
            return Response(payload)

        if (
            len(parts) == 5
            and parts[0] == "projects"
            and parts[2] == "versions"
            and parts[4] == "extract"
        ):
            upload = request.FILES.get("file")
            if upload is None:
                return Response({"detail": "file is required"}, status=422)
            version = repository.get_deployment_version(parts[3])
            if not version or version.get("project_id") != parts[1]:
                return Response(
                    {"detail": "Deployment version not found for this project"}, status=404
                )
            payload, error_response = _run_deployment_extract(
                parts[1], version, _UploadFileShim(upload)
            )
            if error_response:
                return error_response
            return Response(payload)

        if len(parts) == 5 and parts[0] == "projects" and parts[2] == "v" and parts[4] == "extract":
            upload = request.FILES.get("file")
            if upload is None:
                return Response({"detail": "file is required"}, status=422)
            deployment_version = repository.get_deployment_version_by_name(parts[1], parts[3])
            if not deployment_version:
                return Response(
                    {"detail": "Named deployment version not found for this project"}, status=404
                )
            payload, error_response = _run_deployment_extract(
                parts[1], deployment_version, _UploadFileShim(upload)
            )
            if error_response:
                return error_response
            return Response(payload)

        return Response({"detail": "Not Found"}, status=404)

    def get(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        if len(parts) == 3 and parts[0] == "projects" and parts[2] == "versions":
            versions = repository.list_deployment_versions(parts[1])
            return Response({"versions": _jsonable(versions), "total": len(versions)})
        if len(parts) == 3 and parts[0] == "projects" and parts[2] == "active":
            active = repository.get_active_deployment_version(parts[1])
            if not active:
                return Response(
                    {"detail": "No active deployment version found for this project"}, status=404
                )
            return Response({"version": _jsonable(active)})
        return Response({"detail": "Not Found"}, status=404)
