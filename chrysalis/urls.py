
from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings

admin.autodiscover()

urlpatterns = patterns('',

    #{'document_root': settings.MEDIA_ROOT, 'show_indexes': False}),
                             
    

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    #(r'^admin/filebrowser/', include('filebrowser.urls')), # TO BE PUT BEFORE "admin/" !!
    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
   # url(r'^weblog/', include('zinnia.urls')),
 #   url(r'^comments/', include('django.contrib.comments.urls')),
    (r'^', include('cms.urls')), # this MUST end with '/' or be empty
)

from pprint import pprint
pprint(urlpatterns)
