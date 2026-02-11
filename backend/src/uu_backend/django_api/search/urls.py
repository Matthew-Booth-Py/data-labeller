from django.urls import path

from .views import AskView, SearchView

urlpatterns = [
    path("search", SearchView.as_view(), name="search"),
    path("ask", AskView.as_view(), name="ask"),
]
