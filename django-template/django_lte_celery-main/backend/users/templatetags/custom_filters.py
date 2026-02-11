import re
import urllib.parse
from datetime import datetime
from django import template
from django.utils.translation import gettext as _
from django.conf import settings
from django.utils import timezone

register = template.Library()


@register.filter
def lang_name(lang_code):
    return dict(settings.LANGUAGES).get(lang_code, lang_code)


@register.filter
def lang_flag(lang_code):
    return settings.LANGUAGE_TO_EMOJI.get(lang_code, '')

@register.filter
def is_active(request, url_pattern):
    """Example of use: request|is_active:'core:dashboard' """
    if isinstance(request, str):
        return ''
    
    pattern = f'{request.resolver_match.namespace}:{request.resolver_match.url_name}'
    return 'active' if pattern == url_pattern else ''


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current
    request's parameters, only with the specified GET parameters added or changed.

    It also removes any empty parameters to keep things neat,
    so you can remove a parm by setting it to ``""``.

    For example, if you're on the page ``/things/?with_frosting=true&page=5``,
    then

    <a href="/things/?{% param_replace page=3 %}">Page 3</a>

    would expand to

    <a href="/things/?with_frosting=true&page=3">Page 3</a>

    Based on
    https://stackoverflow.com/questions/22734695/next-and-before-links-for-a-django-paginated-query/22735278#22735278
    """
    d = context['request'].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    for k in [k for k, v in d.items() if not v]:
        del d[k]
        
    return urllib.parse.urlencode(d)
