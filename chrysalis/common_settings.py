# -*- coding: utf-8 -*-

from rpgweb_common.common_settings import *



INSTALLED_APPS += [
    'chrysalis',

    'registration', # views for user registration

    'cms',
    'mptt',
    'menus',

    'cmsplugin_rst',
    'cmsplugin_simple_gallery',

    # 'cms.plugins.flash',
    # 'cms.plugins.googlemap',
    'cms.plugins.link',
    'cms.plugins.snippet',
    'cms.plugins.text',

    ## too weak ##
    # 'cms.plugins.file',
    # 'cms.plugins.picture',
    # 'cms.plugins.teaser',
    # 'cms.plugins.video',

    ## OR BETTER: ##
    'filer',

    'cmsplugin_filer_file',
    'cmsplugin_filer_folder',
    'cmsplugin_filer_image',
    'cmsplugin_filer_teaser',
    'cmsplugin_filer_video',
    'jplayer', # cmsplugin too

    'django.contrib.comments', # for zinnia blog
    'tagging',
    'zinnia',
    'cmsplugin_zinnia',
]


TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS + ("cms.context_processors.media",) # for CMS_MEDIA_URL


MIDDLEWARE_CLASSES += (
# #'cms.middleware.multilingual.MultilingualURLMiddleware',
'cms.middleware.page.CurrentPageMiddleware',
'cms.middleware.user.CurrentUserMiddleware',
'cms.middleware.toolbar.ToolbarMiddleware',
)


# global django overrides, easier than overridding models get_absolute_url() methods
ABSOLUTE_URL_OVERRIDES = {
    'auth.user': (lambda u: "/") # access to user data, eg. u.username
}


############# DJANGO-APP CONFS ############



## DJANGO CONTRIB RST CONF ##
# on the public portal, only superuser write RST docs
# so we trust him for "raw" directive (not file insertion though)
RESTRUCTUREDTEXT_FILTER_SETTINGS["raw_enabled"] = True


## DJANGO CMS CONF ##
CMS_TEMPLATES = (
 #        ('stasis_main.html', ugettext('index')),
 #       ('templatemo_main.html', ugettext('emeraud')),
 ('cms_index.html', ugettext('Home')),
)
CMS_REDIRECTS = True # handy for "dummy" menu entries
CMS_SOFTROOT = False # no need to cut the menu in sections
CMS_PUBLIC_FOR = "all" # no restricted to "staff"
CMS_PERMISSION = False # no fine grained restrictions ATM
CMS_TEMPLATE_INHERITANCE = True
CMS_LANGUAGE_FALLBACK = True
CMS_MULTILINGUAL_PATCH_REVERSE = False
CMS_PLACEHOLDER_CONF = {} # unused atm
CMS_PLUGIN_CONTEXT_PROCESSORS = []
CMS_PLUGIN_PROCESSORS = []
PLACEHOLDER_FRONTEND_EDITING = True
CMS_HIDE_UNTRANSLATED = False
CMS_LANGUAGE_CONF = {} # fallbacks ordering
CMS_LANGUAGES = (
    ('fr', ugettext('French')),
    ('en', ugettext('English')),
)
CMS_CACHE_DURATIONS = { # in seconds
    'menus': 60 * 60,
    'content': 60,
    'permissions': 60 * 60,
}


## SIMPLEGALLERY CONF ##
CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS = {
    'size': (240, 180),
    'crop': True,
    'quality': 80,
}


## ORIGINAL ZINNIA CONF ##
# note: if error "Unknown column 'zinnia_entry.content_placeholder_id' in 'field list" => python manage.py reset zinnia
ZINNIA_ENTRY_BASE_MODEL = 'cmsplugin_zinnia.placeholder.EntryPlaceholder'
ZINNIA_PAGINATION = 1
ZINNIA_UPLOAD_TO = "uploads/zinnia"
ZINNIA_PROTOCOL = "http"
ZINNIA_COPYRIGHT = "ChrysalisGame"
ZINNIA_USE_TWITTER = False # todo later


## CMSPLUGIN ZINNIA CONF ##
CMSPLUGIN_ZINNIA_HIDE_ENTRY_MENU = True
CMSPLUGIN_ZINNIA_TEMPLATES = []
CMSPLUGIN_ZINNIA_APP_MENUS = []


## CMSPLUGIN JPLAYER CONF ##
JPLAYER_BASE_PATH = STATIC_URL + "libs/jquery-jplayer-2.3.0/" # for Jplayer SWF object mainly


## DJANGO REGISTRATION CONF ##
ACCOUNT_ACTIVATION_DAYS = 7


'''
## DJANGO LOCALEURL CONF - OBSOLETE TO DELETE ASAP
 
LOCALE_INDEPENDENT_PATHS = ()
LOCALE_INDEPENDENT_MEDIA_URL = True
PREFIX_DEFAULT_LOCALE = True # whether we must enforce a locale in url even for default language
USE_ACCEPT_LANGUAGE = True # use http headres to choose the right language
LOCALE_INDEPENDENT_PATHS = (
      '^/$',
      '^/files/',
      '^/admin/',
      '^/media/',
      '^/static/',
      '^/i18n/', # TO BE REMOVED
      )
'''
