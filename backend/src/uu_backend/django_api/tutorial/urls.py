"""URL routes for tutorial endpoints."""

from django.urls import path

from .views import (
    TutorialResetView,
    TutorialSampleDocumentsView,
    TutorialSetupView,
    TutorialStatusView,
)

urlpatterns = [
    path("tutorial/setup", TutorialSetupView.as_view(), name="tutorial-setup"),
    path("tutorial/status", TutorialStatusView.as_view(), name="tutorial-status"),
    path("tutorial/reset", TutorialResetView.as_view(), name="tutorial-reset"),
    path("tutorial/sample-documents", TutorialSampleDocumentsView.as_view(), name="tutorial-sample-documents"),
]

