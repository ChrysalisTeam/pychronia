# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from ..all_urls import * # including OUR HTTPXXX handlers


# root urlpatterns of pychronia_game application
urlpatterns = patterns('',
        ##url(r'^%s(?P<path>.*)$' % config.MEDIA_URL[1:], 'django.views.static.serve', {'document_root': config.MEDIA_ROOT, 'show_indexes': False}), # usless ??
        url(r'^', include(support_urlpatterns)),
        url(r'^', include('django.contrib.staticfiles.urls')), # UNNEEDED WITH RUNSERVER, ACTUALLY
        url(r'^(?P<game_instance_id>\w+)/', include(mobile_game_urlpatterns)),
)



