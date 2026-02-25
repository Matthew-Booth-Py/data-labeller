"""Test Django settings."""

from .base import *  # noqa: F403

SECRET_KEY = "test-secret-key"  # nosec B105
DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
