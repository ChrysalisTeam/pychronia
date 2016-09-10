# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


class ReverseProxyFixer(object):
    """
    Sets 'REMOTE_ADDR' based on 'HTTP_X_FORWARDED_FOR', if the latter is set.

    Based on http://djangosnippets.org/snippets/1706/
    """

    def process_request(self, request):
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            ip = request.META['HTTP_X_FORWARDED_FOR'].split(",")[0].strip()
            request.META['REMOTE_ADDR'] = ip
