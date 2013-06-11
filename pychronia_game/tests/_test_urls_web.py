# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from ..urls import * # including OUR HTTPXXX handlers
from django.contrib.staticfiles.urls import urlpatterns as staticfiles_urlpatterns

# root urlpatterns of pychronia_game application
urlpatterns = patterns('',
        url(r'^', include(support_urlpatterns)),
        url(r'^(?P<game_instance_id>\w+)/', include(web_game_urlpatterns)),
)

# static files are served automagically by django's runserver, but not by cherrypy etc.
urlpatterns = staticfiles_urlpatterns + urlpatterns # works in DEBUG mode only
