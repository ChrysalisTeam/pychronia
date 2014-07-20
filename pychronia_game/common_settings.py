# -*- coding: utf-8 -*-

from pychronia_common.common_settings import *



TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS + ("pychronia_game.context_processors.pychronia_template_context",)


_old_middlewares = list(MIDDLEWARE_CLASSES)
if "debug_toolbar.middleware.DebugToolbarMiddleware" in _old_middlewares:
    _old_middlewares.remove("debug_toolbar.middleware.DebugToolbarMiddleware") # not for anthropia, bugs with ZODB late access...

# beware of ordering here
# no need for CSRF in pychronia_game, data is not sensitive
MIDDLEWARE_CLASSES = (('pychronia_game.middlewares.MobileHostMiddleware',) +
                     tuple(_old_middlewares) +
                     ('pychronia_game.middlewares.ZodbTransactionMiddleware',
                     'pychronia_game.middlewares.AuthenticationMiddleware',
                     'pychronia_game.middlewares.PeriodicProcessingMiddleware',
                     'django_cprofile_middleware.middleware.ProfilerMiddleware',)) # use in DEBUG mode with '?prof' at the end of URL



INSTALLED_APPS += [
    'pychronia_game',
    'django.contrib.messages', # not in pychronia_common, as long as it doesn't get displayed (and thus emptied) by ALL templates
]




############# DJANGO-APP CONFS ############


## EASY-THUMBNAILS CONF ##

THUMBNAIL_DEFAULT_STORAGE = 'pychronia_game.storage.ProtectedGameFileSystemStorage' # important
THUMBNAIL_MEDIA_ROOT = '' # NOT used by default
THUMBNAIL_MEDIA_URL = '' # NOT used by default

THUMBNAIL_ALIASES = { '': {
    # project-wide aliases here
    'default' : { # NECESSARY
        'autocrop': True, # remove useless whitespace
        'size': (300, 200), # one of these can be 0
        #'crop': "scale", # True or <smart|scale|W,H>
    },
    'item_avatar' : {
        'autocrop': True, # remove useless whitespace
        'size': (150, 220), # one of these can be 0
        #'crop': "smart", # True or <smart|scale|W,H>
    },
    'character_avatar' : {
        'autocrop': False, # remove useless whitespace
        'size': (100, 100), # one of these can be 0
        #'crop': "smart", # True or <smart|scale|W,H>
    },
    'contact_avatar' : {
        'autocrop': False, # remove useless whitespace
        'size': (60, 60), # one of these can be 0
        #'crop': "smart", # True or <smart|scale|W,H>
    },
    'medium_width' : {
        'autocrop': False, # remove useless whitespace
        'size': (500, 0), # one of these can be 0
        #'crop': "scale", # True or <smart|scale|W,H>
    },
    'giant_width' : {
        'autocrop': False, # remove useless whitespace
        'size': (800, 0), # one of these can be 0
        #'crop': "scale", # True or <smart|scale|W,H>
    },
}}


