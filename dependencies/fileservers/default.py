#-*- coding: utf-8 -*-
import os
import stat
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.utils.http import http_date
from django.views.static import was_modified_since
from .base import ServerBase


class DefaultServer(ServerBase):
    """
    Serve static files from the local filesystem through django.
    This is a bad idea for most situations other than testing.

    This will only work for files that can be accessed in the local filesystem.
    """
    def serve(self, request, path, **kwargs):
        # the following code is largely borrowed from `django.views.static.serve`
        # and django-filetransfers: filetransfers.backends.default
        if not os.path.exists(path):
            raise Http404('"%s" does not exist' % path)
        # Respect the If-Modified-Since header.
        statobj = os.stat(path)
        mimetype = self.get_mimetype(path)
        if not was_modified_since(request.META.get('HTTP_IF_MODIFIED_SINCE'),
                                  statobj[stat.ST_MTIME], statobj[stat.ST_SIZE]):
            return HttpResponseNotModified(content_type=mimetype)
        with open(path, 'rb') as fd:
            response = HttpResponse(fd.read(), content_type=mimetype)
        response["Last-Modified"] = http_date(statobj[stat.ST_MTIME])
        self.default_headers(request=request, response=response, path=path, **kwargs)
        return response
