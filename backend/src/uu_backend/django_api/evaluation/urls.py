"""URL routes for evaluation endpoints."""

from django.urls import path, re_path

from .views import EvaluationPrefixProxyView, EvaluationRootProxyView

urlpatterns = [
    path("evaluation", EvaluationRootProxyView.as_view(), name="evaluation-root"),
    re_path(
        r"^evaluation/(?P<subpath>.+)$",
        EvaluationPrefixProxyView.as_view(),
        name="evaluation-prefix",
    ),
]

