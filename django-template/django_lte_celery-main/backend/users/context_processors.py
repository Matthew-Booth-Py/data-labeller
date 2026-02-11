from django.conf import settings


def global_settings(request):
    """Expose some global settings in templates."""
    return {
        "NOW": settings.NOW,
        "APP_NAME": settings.APP_NAME,
        "APP_DOMAIN": settings.APP_DOMAIN,
        "APP_LOGO": settings.APP_LOGO,
        "APP_ICON": settings.APP_ICON,
        "SITE_URL": 'http://localhost:8000' if settings.DEBUG else settings.SITE_URL,
    }


def allauth_settings(request):
    """Expose some settings from django-allauth in templates."""
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }
