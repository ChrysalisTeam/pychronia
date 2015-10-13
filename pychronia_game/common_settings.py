# -*- coding: utf-8 -*-

from pychronia_common.common_settings import *



TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS + ("pychronia_game.context_processors.pychronia_template_context",)


_old_middlewares = list(MIDDLEWARE_CLASSES)
if "debug_toolbar.middleware.DebugToolbarMiddleware" in _old_middlewares:
    # Django Debug Toolbar bugs on pychronia_game, troubles with ZODB late access...
    _old_middlewares.remove("debug_toolbar.middleware.DebugToolbarMiddleware")

# beware of ordering here
# no need for CSRF in pychronia_game, data is not sensitive
MIDDLEWARE_CLASSES = (tuple(_old_middlewares) +
                     ('pychronia_game.middlewares.ZodbTransactionMiddleware',
                     'pychronia_game.middlewares.AuthenticationMiddleware',
                     'pychronia_game.middlewares.PeriodicProcessingMiddleware',
                     'django_cprofile_middleware.middleware.ProfilerMiddleware',)) # use in DEBUG mode with '?prof' at the end of URL



INSTALLED_APPS += [
    'pychronia_game',
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
        'size': (300, 300), # one of these can be 0 to ignore that dimension
        #'crop': "scale", # True or <smart|scale|W,H>, scale means "only 1 dimension must fit", remove this setting to disable any cropping
    },

    'item_avatar' : { # Eg. in sales page
        'autocrop': True,
        'size': (150, 220),
    },
    'character_avatar' : { # Eg. in characters page
        'autocrop': False,
        'size': (100, 100),
    },
    'contact_avatar' : { # Eg. in list of email contacts
        'autocrop': False,
        'size': (60, 60),
    },

    'small_width' : {
        'autocrop': False,
        'size': (200, 0),
    },
    'medium_width' : {
        'autocrop': False,
        'size': (350, 0),
    },
    'big_width' : {
        'autocrop': False,
        'size': (500, 0),
    },
    'giant_width' : {
        'autocrop': False,
        'size': (800, 0),
    },
}}
### medium_width

