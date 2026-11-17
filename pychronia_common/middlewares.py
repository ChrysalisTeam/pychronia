from django.utils.deprecation import MiddlewareMixin


class ReverseProxyFixer(MiddlewareMixin):
    """
    Sets 'REMOTE_ADDR' based on 'HTTP_X_FORWARDED_FOR', if the latter is set.

    Based on http://djangosnippets.org/snippets/1706/
    """

    def process_request(self, request):
        if "x-forwarded-for" in request.headers:
            ip = request.headers["x-forwarded-for"].split(",")[0].strip()
            request.META["REMOTE_ADDR"] = ip
