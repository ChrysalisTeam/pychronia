# -*- coding: utf-8 -*-

from django.conf.urls import *
from django.contrib import admin
from django.conf import settings
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy
from django.conf.urls.i18n import i18n_patterns
from django.http.response import HttpResponse

from cms.views import details

from djangocms_page_sitemap.sitemap import ExtendedSitemap
from zinnia.sitemaps import EntrySitemap, CategorySitemap


admin.autodiscover()

ROBOTS_TEXT = """\
User-agent: *
Disallow: /static/ 
Disallow: /media/ 
Disallow: *.pdf

Sitemap: http://chrysalis-game.com/sitemap.xml
"""

sitemaps = {'cmspages': ExtendedSitemap,
            #'tags': TagSitemap,
            'blog': EntrySitemap,
            #'authors': AuthorSitemap,
            'categories': CategorySitemap, }

urlpatterns = patterns('',

                       url(r'^robots.txt$', lambda r: HttpResponse(ROBOTS_TEXT, content_type="text/plain")),

                       url(r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap',
                           {'sitemaps': sitemaps}),

                       url(r'^admin/', include(admin.site.urls)),

                       url(r'^i18n/', include('django.conf.urls.i18n')),  # to set language
                       )

urlpatterns += i18n_patterns('',

                             #(r'^accounts/', include('userprofiles.urls')), # one-step registration

                             url(r'^weblog/', include('zinnia.urls')),
                             # TOO MANY URLS, but required by cms menu integration  ## , namespace='zinnia')

                             #url(r'^comments/', include('django.contrib.comments.urls')), useless ATM ?

                             url(r'^$', RedirectView.as_view(url=reverse_lazy('pages-root'))),
                             # REDIRECT TO CMS HOMEPAGE
                             url(r'^cms/', include('cms.urls')),  # this MUST end with '/' or be empty
                             )

# Django Debug Toolbar
import debug_toolbar

urlpatterns += patterns('',
                        url(r'^__debug__/', include(debug_toolbar.urls)),
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
