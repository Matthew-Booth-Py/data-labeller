"""URL patterns for evaluation API."""

from django.urls import path
from . import views

urlpatterns = [
    path("evaluation/test", views.test_endpoint, name="test_endpoint"),
    path("evaluation/run", views.run_evaluation, name="run_evaluation"),
    path("evaluation/task/<str:task_id>", views.get_task_status, name="get_task_status"),
    path("evaluation/results", views.list_evaluation_runs, name="list_evaluation_runs"),
    path("evaluation/results/<str:evaluation_id>", views.get_evaluation_run, name="get_evaluation_run"),
    path("evaluation/summary", views.get_evaluation_summary, name="get_evaluation_summary"),
    path("evaluation/results/<str:evaluation_id>/delete", views.delete_evaluation_run, name="delete_evaluation_run"),
]
