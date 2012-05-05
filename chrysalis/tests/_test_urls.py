# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import * # default HTTP404 etc.
from django.conf import settings

from ..urls import urlpatterns as site_urls



test_urls = patterns('',
     (r'^i18n/', include('django.conf.urls.i18n')), # set language            
    url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    url(r'', include('django.contrib.staticfiles.urls')),
)
 

urlpatterns = test_urls + site_urls # all test urls