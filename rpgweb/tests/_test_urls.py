# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import * # default HTTP404 etc.

from ..utilities import config
from ..urls import urlpatterns as game_urls



test_urls = patterns('',
    (r'^%s(?P<path>.*)$' % config.MEDIA_URL[1:], 'django.views.static.serve',
                    {'document_root': config.MEDIA_ROOT, 'show_indexes': False}),
    (r'^i18n/', include('django.conf.urls.i18n')), # to set language
    (r'^jsi18n/$', 'django.views.i18n.javascript_catalog', {'packages': ('rpgweb',)}),

    url(r'', include('django.contrib.staticfiles.urls')), # UNNEEDED WITH RUNSERVER
)

urlpatterns = test_urls + game_urls # all test urls
