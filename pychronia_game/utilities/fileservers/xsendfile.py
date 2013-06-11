#-*- coding: utf-8 -*-
from django.http import HttpResponse
from .base import ServerBase


class ApacheXSendfileServer(ServerBase):
    def serve(self, request, path, **kwargs):
        response = HttpResponse()
        response['X-Sendfile'] = path

        # This is needed for lighttpd, hopefully this will
        # not be needed after this is fixed:
        # http://redmine.lighttpd.net/issues/2076
        response['Content-Type'] = self.get_mimetype(path)

        self.default_headers(request=request, response=response, path=path, **kwargs)
        return response
