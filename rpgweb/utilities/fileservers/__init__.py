#-*- coding: utf-8 -*-

from django .conf import settings
BACKEND_NAME = getattr(settings, "FILE_SERVER_BACKEND", "default")

from .default import DefaultServer as default
from .nginx import NginxXAccelRedirectServer as nginx
from .xsendfile import ApacheXSendfileServer as xsendfile

def serve_file(request, path, backend_name=BACKEND_NAME, **kwargs):
    backend = globals()[backend_name]
    return backend().serve(request=request, path=path, **kwargs)