#-*- coding: utf-8 -*-
from django.utils.encoding import smart_str
import mimetypes
import os


class ServerBase(object):
    def __init__(self, *args, **kwargs):
        pass

    def get_mimetype(self, path):
        return mimetypes.guess_type(path, strict=False)[0] or 'application/octet-stream'

    def default_headers(self, **kwargs):
        self.save_as_header(**kwargs)
        self.size_header(**kwargs)

    def save_as_header(self, response, save_as=None, path=None, **kwargs):
        """
        * if save_as is False the header will not be added
        * if save_as is a filename, it will be used in the header
        * if save_as is None the filename will be determined from the file path
        """
        if save_as == False:
            return
        if save_as:
            filename = save_as
        else:
            filename = os.path.basename(path)
        response['Content-Disposition'] = smart_str('attachment; filename=%s' % filename)

    def size_header(self, response, size=None, path=None, **kwargs):
        if size is None and path:
            try:
                size = os.stat(path).st_size
            except EnvironmentError:
                pass
        if size is not None:
            response['Content-Length'] = str(size)

