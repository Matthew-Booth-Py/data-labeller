"""URL routes for suggestion and feedback endpoints."""

from django.urls import path

from .views import DocumentSuggestView, FeedbackView, ModelStatusView, ModelTrainView

urlpatterns = [
    path("documents/<str:document_id>/suggest", DocumentSuggestView.as_view(), name="document-suggest"),
    path("feedback", FeedbackView.as_view(), name="feedback"),
    path("model/status", ModelStatusView.as_view(), name="model-status"),
    path("model/train", ModelTrainView.as_view(), name="model-train"),
]

