# -*- coding: utf-8 -*-
from django.utils.deprecation import MiddlewareMixin


class ReverseProxyFixer(MiddlewareMixin):
    """
    Sets 'REMOTE_ADDR' based on 'HTTP_X_FORWARDED_FOR', if the latter is set.

    Based on http://djangosnippets.org/snippets/1706/
    """

    def process_request(self, request):
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            ip = request.META['HTTP_X_FORWARDED_FOR'].split(",")[0].strip()
            request.META['REMOTE_ADDR'] = ip
