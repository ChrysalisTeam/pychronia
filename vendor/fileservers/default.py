import os
import re
import stat
from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.utils.http import http_date
from django.views.static import was_modified_since
from .base import ServerBase


_RANGE_RE = re.compile(r"^\s*bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*$", re.IGNORECASE)


def parse_single_byte_range(range_header, size):
    """
    Returns an inclusive (start, end) tuple for a single "bytes=" range, None if the header
    must be ignored (absent, malformed or multi-range: we then serve the full file), or
    False if the range is unsatisfiable.
    """
    if not range_header:
        return None
    match = _RANGE_RE.match(range_header)
    if not match:
        return None  # includes multi-range requests, which are legitimately answered with a 200
    start, end = match.groups()
    if not start and not end:
        return None
    if not start:  # suffix range, e.g. "bytes=-500" = last 500 bytes
        length = int(end)
        if not length:
            return False
        return (max(size - length, 0), size - 1)
    start = int(start)
    end = int(end) if end else size - 1
    if start >= size or end < start:
        return False
    return (start, min(end, size - 1))


class DefaultServer(ServerBase):
    """
    Serve static files from the local filesystem through django.
    This is a bad idea for most situations other than testing.

    This will only work for files that can be accessed in the local filesystem.

    Single byte-range requests are honored (HTTP 206), since HTML5 media players need
    them to seek inside audio/video files.
    """

    def serve(self, request, path, **kwargs):
        # the following code is largely borrowed from `django.views.static.serve`
        # and django-filetransfers: filetransfers.backends.default
        if not os.path.exists(path):
            raise Http404('"%s" does not exist' % path)
        # Respect the If-Modified-Since header.
        statobj = os.stat(path)
        size = statobj[stat.ST_SIZE]
        mimetype = self.get_mimetype(path)
        if not was_modified_since(request.headers.get("if-modified-since"), statobj[stat.ST_MTIME]):
            return HttpResponseNotModified(content_type=mimetype)

        byte_range = parse_single_byte_range(request.headers.get("range"), size)

        if byte_range is False:
            response = HttpResponse(status=416, content_type=mimetype)
            response["Content-Range"] = "bytes */%d" % size
            response["Accept-Ranges"] = "bytes"
            return response

        with open(path, "rb") as fd:
            if byte_range:
                start, end = byte_range
                fd.seek(start)
                response = HttpResponse(fd.read(end - start + 1), content_type=mimetype, status=206)
                response["Content-Range"] = "bytes %d-%d/%d" % (start, end, size)
            else:
                response = HttpResponse(fd.read(), content_type=mimetype)
        response["Last-Modified"] = http_date(statobj[stat.ST_MTIME])
        response["Accept-Ranges"] = "bytes"
        if byte_range:
            kwargs["size"] = end - start + 1
        self.default_headers(request=request, response=response, path=path, **kwargs)
        return response
