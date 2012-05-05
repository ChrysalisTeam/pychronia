# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import * # default HTTP404 etc.

#from ..utilities import config
from ..urls import urlpatterns as site_urls

test_urls = patterns('',           
    #(r'^%s(?P<path>.*)$' % config.MEDIA_URL[1:], 'django.views.static.serve',
    #    {'document_root': config.MEDIA_ROOT, 'show_indexes': False}),
    (r'^i18n/', include('django.conf.urls.i18n')), # set language
)

urlpatterns = test_urls + site_urls # all test urls