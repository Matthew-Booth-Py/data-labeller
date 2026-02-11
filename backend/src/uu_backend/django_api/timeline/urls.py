from django.urls import path

from .views import TimelineRangeView, TimelineView

urlpatterns = [
    path("timeline", TimelineView.as_view(), name="timeline"),
    path("timeline/range", TimelineRangeView.as_view(), name="timeline-range"),
]
