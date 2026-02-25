"""Base Django settings for phased migration."""

from pathlib import Path

import environ

from uu_backend.config import get_settings

# /backend/src/uu_backend/django_project/settings/base.py -> /backend
BASE_DIR = Path(__file__).resolve().parents[4]
env = environ.Env()

app_settings = get_settings()

DEBUG = env.bool("DJANGO_DEBUG", default=app_settings.debug)
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-migration-phase-key-change-me",
)
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "0.0.0.0"],  # nosec B104
)

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "uu_backend.django_api.apps.DjangoApiConfig",
    "uu_backend.django_data.apps.DjangoDataConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "uu_backend.django_project.urls"
ASGI_APPLICATION = "uu_backend.django_project.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": env.db(
        "DJANGO_DATABASE_URL",
        default="postgres://uu:uu@localhost:5432/uu_django",
    )
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / "staticfiles")

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = app_settings.cors_origins
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Unstructured Unlocked Django API",
    "DESCRIPTION": "Phased migration API surface",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Prefer explicit Celery URLs; fall back to REDIS_URL for backward compatibility.
redis_url = env("REDIS_URL", default=None)
CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default=redis_url or "redis://localhost:6379/0",
)
CELERY_RESULT_BACKEND = env(
    "CELERY_RESULT_BACKEND",
    default=redis_url or "redis://localhost:6379/1",
)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
