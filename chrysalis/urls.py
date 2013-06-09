# -*- coding: utf-8 -*-

from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings
from cms.views import details
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy
from django.conf.urls.i18n import i18n_patterns

admin.autodiscover()



def css3pie_htc_view(request):
    from django.http import HttpResponse
    with open(settings.STATIC_URL + "libs/css3pie/PIE.htc", "rb") as f:
        content = f.read()
    return HttpResponse(content, mimetype="text/x-component") # beware of content type!


urlpatterns = patterns('',
    (r'^pie.htc', css3pie_htc_view),

    (r'^admin/', include(admin.site.urls)),

    (r'^i18n/', include('django.conf.urls.i18n')), # to set language
)

urlpatterns += i18n_patterns('',

    (r'^accounts/', include('userprofiles.urls')), # one-step registration

    url(r'^weblog/', include('zinnia.urls')), # TOO MANY URLS, but required by cms menu integration

    #url(r'^comments/', include('django.contrib.comments.urls')), useless ATM ?

    url(r'^$', RedirectView.as_view(url=reverse_lazy('pages-root'))), # REDIRECT TO CMS HOMEPAGE
    (r'^cms/', include('cms.urls')), # this MUST end with '/' or be empty
)


#from pprint import pprint
#pprint(urlpatterns)

''' UNUSED MODULES
    # Uncomment the admin/doc line below and add 'django.contrib.admindocs'
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    #(r'^admin/filebrowser/', include('filebrowser.urls')), # TO BE PUT BEFORE "admin/" !!
    
    
    # specific zinnia parts
   url(r'^weblog/categories/', include('zinnia.urls.categories')),
    url(r'^weblog/', include('zinnia.urls.entries')),
    url(r'^weblog/', include('zinnia.urls.archives')),
    #url(r'^feeds/', include('zinnia.urls.feeds')),


'''
