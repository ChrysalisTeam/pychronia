# -*- coding: utf-8 -*-

from rpgweb_common.common_settings import *



TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS + ("rpgweb.context_processors.rpgweb_template_context",)


# beware of ordering here
# no need for CSRF in rpgweb, data is not sensitive
MIDDLEWARE_CLASSES = (('rpgweb.middlewares.MobileHostMiddleware',) +
                     MIDDLEWARE_CLASSES +
                     ('rpgweb.middlewares.ZodbTransactionMiddleware',
                     'rpgweb.middlewares.AuthenticationMiddleware',
                     'rpgweb.middlewares.PeriodicProcessingMiddleware',
                     'debug_toolbar.middleware.DebugToolbarMiddleware',))


INSTALLED_APPS += [
    'rpgweb',
    'easy_thumbnails',
    'django.contrib.messages', # not in rpgweb_common, as long as it doesn't get displayed (and thus emptied) by ALL templates
]




############# DJANGO-APP CONFS ############


THUMBNAIL_DEBUG = True # NOT used by custom game_file_img tag
THUMBNAIL_QUALITY = 85
THUMBNAIL_DEFAULT_STORAGE = 'rpgweb.storage.ProtectedGameFileSystemStorage'
THUMBNAIL_MEDIA_ROOT = '' # NOT used by default
THUMBNAIL_MEDIA_URL = '' # NOT used by default
THUMBNAIL_BASEDIR = 'thumbs' # prefix of relative path
THUMBNAIL_PREFIX = "" # prefix subdirectory of image file itself
THUMBNAIL_EXTENSION = "jpg"
THUMBNAIL_TRANSPARENCY_EXTENSION = "png"
THUMBNAIL_PRESERVE_EXTENSIONS = True # or a tuple like ('png',)
THUMBNAIL_CHECK_CACHE_MISS = True # can regenerate SQL table from storage

THUMBNAIL_ALIASES = { '': {
    # project-wide aliases here
    'default' : { # NECESSARY
        'autocrop': True, # remove useless whitespace
        'size': (300, 200), # one of these can be 0
        #'crop': "scale", # True or <smart|scale|W,H>
    },
    'item_avatar' : {
        'autocrop': True, # remove useless whitespace
        'size': (150, 0), # one of these can be 0
        #'crop': "scale", # True or <smart|scale|W,H>
    }
}}


