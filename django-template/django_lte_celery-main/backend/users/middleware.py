from django.utils import translation


class UserLanguageMiddleware:
    """
    Middleware to set the language based on the authenticated user's
    platform_language preference.

    - For authenticated users: activates user.platform_language
    - For anonymous users: does nothing (falls back to LocaleMiddleware)
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_language = getattr(request.user, 'platform_language', None)
            if user_language:
                translation.activate(user_language)
                # Optional but recommended: update the request's LANGUAGE_CODE
                request.LANGUAGE_CODE = translation.get_language()

        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response