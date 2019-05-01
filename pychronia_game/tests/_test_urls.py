# -*- coding: utf-8 -*-



from ..urls import *  # including OUR HTTPXXX handlers
from django.contrib.staticfiles.urls import urlpatterns as staticfiles_urlpatterns

# static files are served automagically by django's runserver, but not by cherrypy etc., so we add this here
urlpatterns = staticfiles_urlpatterns + urlpatterns  # works in DEBUG mode only
