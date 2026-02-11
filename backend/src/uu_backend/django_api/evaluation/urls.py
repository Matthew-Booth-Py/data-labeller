"""URL routes for evaluation endpoints."""

from django.urls import path, re_path

from .views import EvaluationPrefixView, EvaluationRootView

urlpatterns = [
    path("evaluation", EvaluationRootView.as_view(), name="evaluation-root"),
    re_path(
        r"^evaluation/(?P<subpath>.+)$",
        EvaluationPrefixView.as_view(),
        name="evaluation-prefix",
    ),
]
