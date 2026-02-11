from django.utils import timezone
from rest_framework import exceptions
from backend.users.models import APIKey
from django.utils.translation import gettext_lazy as _
from rest_framework.authentication import BaseAuthentication
from drf_spectacular.authentication import OpenApiAuthenticationExtension        

class APIKeyAuthentication(BaseAuthentication):
    keyword = 'Bearer'

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith(self.keyword):
            return None  # No authentication credentials were provided

        api_key = auth_header[len(self.keyword):].strip()

        try:
            api_key_obj = APIKey.objects.get(key=api_key)
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed(_('Invalid API Key'))

        if api_key_obj.expires_at and api_key_obj.expires_at < timezone.now():
            raise exceptions.AuthenticationFailed(_('API Key has expired'))

        return (api_key_obj.user, None)

# Add the following class at the end of the file
class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'backend.utils.auth.APIKeyAuthentication'
    name = 'APIKeyAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': 'Enter your API key with the `Bearer` prefix, e.g. "Bearer abcdefghijklmnopqrstuvwxyz123456" - You can generate API keys from the API Keys section of Account Settings.'
        }