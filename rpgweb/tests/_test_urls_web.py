# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from ..urls import * # including OUR HTTPXXX handlers


# root urlpatterns of rpgweb application
urlpatterns = patterns('',
        url(r'^(?P<game_instance_id>\w+)/', include(web_game_urlpatterns)),
        url(r'^', include(support_urlpatterns)),
        url(r'^', include('django.contrib.staticfiles.urls')), # UNNEEDED WITH RUNSERVER, ACTUALLY
)



