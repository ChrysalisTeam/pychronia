from django.urls import re_path
from django.views.static import serve
from django.conf import settings
from django.contrib.staticfiles.urls import urlpatterns as staticfiles_urlpatterns

from ..urls import urlpatterns as site_urls

test_urls = [

    re_path(r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:], serve,
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),

]

urlpatterns = test_urls + site_urls  # all test urls

# static files are served automagically by django's runserver, but not by cherrypy etc.
urlpatterns = staticfiles_urlpatterns + urlpatterns  # works in DEBUG mode only
