"""URL patterns for evaluation API."""

from django.urls import path
from . import views

urlpatterns = [
    path("evaluation/run", views.run_evaluation, name="run_evaluation"),
    path("evaluation/task/<str:task_id>", views.get_task_status, name="get_task_status"),
    path("evaluation/results", views.list_evaluation_runs, name="list_evaluation_runs"),
    path("evaluation/results/<str:evaluation_id>", views.get_evaluation_run, name="get_evaluation_run"),
    path("evaluation/summary", views.get_evaluation_summary, name="get_evaluation_summary"),
    path("evaluation/results/<str:evaluation_id>/delete", views.delete_evaluation_run, name="delete_evaluation_run"),
    
    # Field Prompt endpoints
    path("evaluation/field-prompts/active/by-document-type", views.list_active_field_prompts_by_document_type, name="list_active_field_prompts_by_document_type"),
    path("evaluation/field-prompts/list", views.list_field_prompt_versions, name="list_field_prompt_versions"),
    path("evaluation/field-prompts", views.create_field_prompt_version, name="create_field_prompt_version"),
    path("evaluation/field-prompts/version/<str:version_id>", views.get_field_prompt_version, name="get_field_prompt_version"),
    path("evaluation/field-prompts/version/<str:version_id>", views.update_field_prompt_version, name="update_field_prompt_version"),
    path("evaluation/field-prompts/version/<str:version_id>", views.delete_field_prompt_version, name="delete_field_prompt_version"),
]
