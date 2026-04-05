from django.urls import path

from .views import ProjectDetailView, ProjectDocumentMembershipView, ProjectsListView

urlpatterns = [
    path("projects", ProjectsListView.as_view(), name="projects-list"),
    path("projects/<str:project_id>", ProjectDetailView.as_view(), name="projects-detail"),
    path(
        "projects/<str:project_id>/documents",
        ProjectDocumentMembershipView.as_view(),
        name="projects-documents",
    ),
    path(
        "projects/<str:project_id>/documents/<str:document_id>",
        ProjectDocumentMembershipView.as_view(),
        name="projects-documents-detail",
    ),
]
