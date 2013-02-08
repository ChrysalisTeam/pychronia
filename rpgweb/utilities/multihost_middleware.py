# File: django_multihost.py
#
# A simple middleware component that lets you use a single Django
# instance to server multiple distinct hosts.
#
# Example usage (in settings.py):
#   MIDDLEWARE_CLASSES = (
#      ...,
#      'django_multihost.MultiHostMiddleware',
#   )
#   MULTIHOST_URLCONF_MAP = {
#     'domain1.com'     : 'app1.urls',
#     'domain1.com:8080': 'app1.urls',
#     'domain2.com'     : 'app2.urls',
#   }
#
# If a host wasn't found, settings.ROOT_URLCONF will be used.
#

from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.core.exceptions import MiddlewareNotUsed

class MultiHostMiddleware:

    def __init__(self):
        if not hasattr(settings, 'MULTIHOST_URLCONF_MAP'):
            raise MiddlewareNotUsed

    def process_request(self, request):
        try:
            host = request.META["HTTP_HOST"]
            if host[-3:] == ":80":
                host = host[:-3] # ignore default port number, if present
            request.urlconf = settings.MULTIHOST_URLCONF_MAP[host]
        except KeyError:
            pass # use default urlconf (settings.ROOT_URLCONF)

    def process_response(self, request, response):
        if getattr(request, "urlconf", None):
            patch_vary_headers(response, ('Host',))
        return response
