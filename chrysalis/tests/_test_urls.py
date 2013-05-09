# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import * # default HTTP404 etc.
from django.conf import settings
from django.contrib.staticfiles.urls import urlpatterns as staticfiles_urlpatterns


from ..urls import urlpatterns as site_urls

test_urls = patterns('',

    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:], 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),

)

urlpatterns = test_urls + site_urls # all test urls

# static files are served automagically by django's runserver, but not by cherrypy etc.
urlpatterns = staticfiles_urlpatterns + urlpatterns # works in DEBUG mode only

