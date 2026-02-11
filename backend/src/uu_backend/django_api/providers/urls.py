"""URL routes for provider configuration endpoints."""

from django.urls import path

from .views import (
    OpenAIProviderModelDetailView,
    OpenAIProviderModelListView,
    OpenAIProviderModelTestView,
    OpenAIProviderStatusView,
    OpenAIProviderTestView,
)

urlpatterns = [
    path("providers/openai", OpenAIProviderStatusView.as_view(), name="providers-openai"),
    path("providers/openai/test", OpenAIProviderTestView.as_view(), name="providers-openai-test"),
    path("providers/openai/models", OpenAIProviderModelListView.as_view(), name="providers-openai-models"),
    path(
        "providers/openai/models/<str:model_id>",
        OpenAIProviderModelDetailView.as_view(),
        name="providers-openai-model-detail",
    ),
    path(
        "providers/openai/models/<str:model_id>/test",
        OpenAIProviderModelTestView.as_view(),
        name="providers-openai-model-test",
    ),
]

