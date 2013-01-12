# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.conf.urls.defaults import * # default HTTP404 etc.
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

# ... the rest of your URLconf goes here ...



from ..urls import urlpatterns as site_urls



test_urls = patterns('',
     (r'^i18n/', include('django.conf.urls.i18n')), # set language

    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:], 'django.views.static.serve',
        {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),

    ############url(r'', include('django.contrib.staticfiles.urls')), # UNNEEDED WITH RUNSERVER
)


urlpatterns = test_urls + site_urls # all test urls

urlpatterns += staticfiles_urlpatterns() # in DEV only
