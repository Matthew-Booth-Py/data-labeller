"""DRF views for backend-persisted project workspace state."""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.models.project import (
    ProjectCreate,
    ProjectDocumentMembershipUpdate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from uu_backend.repositories import get_repository

logger = logging.getLogger(__name__)


class ProjectsListView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        repository = get_repository()
        projects = repository.list_projects()
        payload = ProjectListResponse(projects=projects, total=len(projects))
        return Response(payload.model_dump(mode="json"))

    def post(self, request):
        repository = get_repository()
        parsed = ProjectCreate.model_validate(request.data)
        project = repository.create_project(parsed)
        payload = ProjectResponse(project=project)
        return Response(payload.model_dump(mode="json"), status=status.HTTP_201_CREATED)


class ProjectDetailView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, project_id: str):
        repository = get_repository()
        project = repository.get_project(project_id)
        if not project:
            return Response({"detail": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = ProjectResponse(project=project)
        return Response(payload.model_dump(mode="json"))

    def patch(self, request, project_id: str):
        repository = get_repository()
        parsed = ProjectUpdate.model_validate(request.data)
        project = repository.update_project(project_id, parsed)
        if not project:
            return Response({"detail": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = ProjectResponse(project=project)
        return Response(payload.model_dump(mode="json"))

    def delete(self, request, project_id: str):
        repository = get_repository()
        deleted = repository.delete_project(project_id)
        if not deleted:
            return Response({"detail": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"status": "deleted", "project_id": project_id})


class ProjectDocumentMembershipView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, project_id: str):
        repository = get_repository()
        parsed = ProjectDocumentMembershipUpdate.model_validate(request.data)
        project = repository.add_documents_to_project(project_id, parsed.document_ids)
        if not project:
            return Response({"detail": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = ProjectResponse(project=project)
        return Response(payload.model_dump(mode="json"))

    def delete(self, request, project_id: str, document_id: str):
        repository = get_repository()
        project = repository.remove_document_from_project(project_id, document_id)
        if not project:
            return Response({"detail": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        payload = ProjectResponse(project=project)
        return Response(payload.model_dump(mode="json"))
