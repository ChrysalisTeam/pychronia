#-*- coding: utf-8 -*-
from django.http import HttpResponse
from .base import ServerBase


class NginxXAccelRedirectServer(ServerBase):
    """
    This returns a response with only headers set, so that nginx actually does
    the serving
    """
    def serve(self, request, path, **kwargs):
        # we should not use get_mimetype() here, nginx does it
        response = HttpResponse()
        nginx_path = path # nothing to modify actually
        response['X-Accel-Redirect'] = nginx_path
        self.default_headers(request=request, response=response, path=path, **kwargs)
        return response
