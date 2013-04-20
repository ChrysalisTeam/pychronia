# -*- coding: utf-8 -*-

import sys, os, tempfile, random, logging

ugettext = lambda s: s # dummy placeholder for makemessages

try:
    import PIL.Image # that package has been exploded in several packages now
    sys.modules['Image'] = PIL.Image # prevents AccessInit: hash collision: 3 for both 1 and 1
except ImportError:
    pass

# Make this unique, and don't share it with anybody.
SECRET_KEY = None # TO OVERRIDE

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print "ROOT PATH:", ROOT_PATH

TEMP_DIR = tempfile.mkdtemp()
UNICITY_STRING = str(random.randint(100000, 1000000000))


SESSION_COOKIE_DOMAIN = None # TO BE OVERRIDDEN - eg. ".mydomain.net"
SESSION_COOKIE_NAME = 'sessionid' # DO NOT CHANGE - needed for phpbb integration


DEBUG = False
TEMPLATE_DEBUG = False
TEMPLATE_STRING_IF_INVALID = "" # or "<INVALID %s>" to debug


MEDIA_URL = '/media/' # examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_ROOT = None # TO OVERRIDE


STATIC_URL = "/static/"
#>>>> STATIC_ROOT = "" # where collectstatic cmd will place files
STATICFILES_DIRS = ()

LOCALE_PATHS = () # TODO use this instead of application "locale" dirs

SERVER_EMAIL = DEFAULT_FROM_EMAIL = ""
EMAIL_HOST = ""
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_PORT = 25
EMAIL_SUBJECT_PREFIX = ""
EMAIL_USE_TLS = False


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TEMP_DIR, "django.db.%s" % UNICITY_STRING),
        'TEST_NAME': os.path.join(TEMP_DIR, "djangotest.db.%s" % UNICITY_STRING),
    }
}


TIME_ZONE = 'Europe/Paris'
USE_L10N = True
USE_I18N = True
LANGUAGE_CODE = 'en'
LANGUAGES = (
  ('fr', ugettext('French')),
  ('en', ugettext('English')),
)

APPEND_SLASH = True # so handy for mistyped urls...

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)
TEMPLATE_DIRS = () # Don't forget to use absolute paths, not relative paths.


TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.i18n",
    "django.core.context_processors.debug",
    "django.core.context_processors.media",
    "django.core.context_processors.request",
    "django.core.context_processors.static",
    #"django.contrib.messages.context_processors.messages",
    "sekizai.context_processors.sekizai",
)


MIDDLEWARE_CLASSES = None # TO OVERRIDE

ROOT_URLCONF = None # TO OVERRIDE


INSTALLED_APPS = [
    'sessionprofile', # keeps track of sessions/users in DB table, for PHPBB integration
    'templateaddons', # assing and headers
    'django_select2', # advanced select box

    'debug_toolbar',

    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions', # only these sessions are scalable for "sharding"
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.markup',

    'south',
    'sekizai',

    'rpgweb_common', # common templates, tags, static files etc.
    
    'django_wsgiserver',
]
ADMIN_MEDIA_PREFIX = "/admin/" # FIXME - temp compatibility with wsgi server


AUTO_RENDER_SELECT2_STATICS = False

try:
    import sentry.client
    INSTALLED_APPS.append('sentry.client')
except ImportError:
    pass # sentry is optional



## DJANGO CONTRIB MESSAGES CONF ##
from django.contrib.messages import constants as message_constants
MESSAGE_LEVEL = message_constants.DEBUG # Set MESSAGE_TAGS setting to control corresponding CSS classes


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
CMS_CACHE_DURATIONS = {
    'menus': 60 * 60,
    'content': 60,
    'permissions': 60 * 60,
}



## DJANGO DEBUG TOOLBAR CONF ##
DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
    'SHOW_TOOLBAR_CALLBACK': lambda *args, **kwargs: True, # always, at the moment
    'ENABLE_STACKTRACES' : True,
    'HIDE_DJANGO_SQL': True,
    'SHOW_TEMPLATE_CONTEXT': True,
}


## DJANGO LOCALEURL CONF ##
'''
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

## DJANGO CONTRIB RST CONF ##
RESTRUCTUREDTEXT_FILTER_SETTINGS = {"initial_header_level": 2,
                                    "doctitle_xform": False, # important, to have even lone titles stay in the html fragment
                                    "sectsubtitle_xform": False,
                                    'file_insertion_enabled': False,  # SECURITY MEASURE (file hacking)
                                    'raw_enabled': False, } # SECURITY MEASURE (script tag)

