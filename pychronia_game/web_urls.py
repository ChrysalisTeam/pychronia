 # -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.all_urls import * # including OUR HTTPXXX handlers

# root urlpatterns of pychronia_game application
urlpatterns = patterns('',
        url(r'^', include(game_admin_urlpatterns)),
        url(r'^', include(support_urlpatterns)),
        url(r'^(?P<game_instance_id>\w+)/', include(web_game_urlpatterns)),
)
