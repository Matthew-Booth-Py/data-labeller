"""ASGI config for the migration Django project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.local")

application = get_asgi_application()
