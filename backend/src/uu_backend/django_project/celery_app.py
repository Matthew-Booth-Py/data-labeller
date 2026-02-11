"""Celery application for migration phases."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.local")

app = Celery("uu_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["uu_backend"])
