from django.urls import path

from backend.core import views

app_name = "core"
urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
]
