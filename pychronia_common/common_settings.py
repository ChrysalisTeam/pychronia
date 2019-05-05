# -*- coding: utf-8 -*-

import sys, os, tempfile, random, logging, re

try:
    import PIL.Image  # that monolithic package has been exploded in several packages now

    sys.modules['Image'] = PIL.Image  # WORKAROUND - prevents "AccessInit: hash collision: 3 for both 1 and 1"
except ImportError:
    pass

try:
    import pymysql

    pymysql.install_as_MySQLdb()  # drop-in replacement
except ImportError:
    pass

import pychronia_common.default_logging_config  # base handlers

##################### SETTINGS TO BE OVERRIDDEN BY DEPLOYMENT-SPECIFIC CONF FILE ####################

SITE_ID = None
SECRET_KEY = None

SESSION_COOKIE_DOMAIN = None  # eg. ".mydomain.net"

SERVER_EMAIL = DEFAULT_FROM_EMAIL = "me@example.com"
EMAIL_HOST = ""
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_PORT = 25
EMAIL_SUBJECT_PREFIX = ""
EMAIL_USE_TLS = False

ADMINS = MANAGERS = ()  # admins are for 50 errors, managers for 404 errors with BrokenLinkEmailsMiddleware  - format : (('John', 'john@example.com'),)

ROOT_URLCONF = None

DEBUG = False

SITE_DOMAIN = None  # NO trailing slash, used to build absolute urls

FORCE_SCRIPT_NAME = None  # if not mounted at /

######################################################################################################


# Django-compat-patcher settings
DCP_LOGGING_LEVEL = None
DCP_ENABLE_WARNINGS = False  # to get DCP deprecation warnings


ugettext = lambda s: s  # dummy placeholder for makemessages

ROOT_PATH = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))  # base folder where pychronia packages are stored

INTERNAL_IPS = ()  # used for debug output etc.

ALLOWED_HOSTS = ['*']  # should be overridden by local settings

SESSION_COOKIE_NAME = 'sessionid'  # DO NOT CHANGE - needed for phpbb integration

MEDIA_URL = '/static/media/'  # examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_ROOT = os.path.join(ROOT_PATH, "media")  # for uploaded files, generated docs etc.

STATIC_URL = "/static/resources/"  #### or http://chrysalis-game.com/static/resources/ for proper mime-types
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'  # deprecated but required by djangocms
STATIC_ROOT = os.path.join(ROOT_PATH, "static")  # where collectstatic cmd will place files
STATICFILES_DIRS = ()

USE_ETAGS = False  # demandes heavy processing to compute response hashes

# in templates, use DATE_FORMAT, DATETIME_FORMAT, SHORT_DATE_FORMAT or SHORT_DATETIME_FORMAT as date formats!
USE_TZ = False  # we use naive datetimes ATM...
TIME_ZONE = 'UTC'
USE_L10N = True
USE_I18N = True
LANGUAGE_CODE = 'en'
LANGUAGES = (
    ('fr', ugettext('French')),
    ('en', ugettext('English')),
)
LOCALE_PATHS = ()  # in addition to application-local "locale/" dirs

APPEND_SLASH = True  # so handy for mistyped urls...

IGNORABLE_404_URLS = (  # ONLY SOON IN 1.5
    re.compile(r'\.(php|cgi)$'),
)

# TEST_RUNNER = "" # override this to use another runner, eg. for pytest


# List of callables that know how to import templates from various sources
____TEMPLATE_LOADERS = (

)

# Use Django templates using the new Django 1.8 TEMPLATES settings
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'OPTIONS': {
            'debug': False,
            'context_processors': [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.debug",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.contrib.messages.context_processors.messages",
                # note that we use our own version in pychronia-game!  FIXME what ??
                "sekizai.context_processors.sekizai",
                'pychronia_common.context_processors.google_analytics',
            ],
            'loaders': [
                'apptemplates.Loader',  # allows the use of {% extends "admin:admin/base.html" %}
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
        },
    },
]

# no need for CSRF by default
MIDDLEWARE = (
    'django.middleware.gzip.GZipMiddleware',
    'pychronia_common.middlewares.ReverseProxyFixer',
    # TODO Later 'django.middleware.http.ConditionalGetMiddleware', # checks E-tag and last-modification-time to avoid sending data
    #'django.middleware.common.BrokenLinkEmailsMiddleware', FIXME - ONLY SOON IN 1.5
    ##'sessionprofile.middleware.SessionProfileMiddleware',  # to bridge auth with PHPBB (ABORTED)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

# to be extended in specific settings #
INSTALLED_APPS = [
    'pychronia_common',  # common templates, tags, static files etc. BEFORE OTHER APPS for overrides!

    'djangocms_admin_style',  # must come BEFORE admin

    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions',  # only these sessions are scalable for "sharding"
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'django.contrib.messages',  # for both game and cms now

    'sekizai',

    'sessionprofile',  # keeps track of sessions/users in DB table, for PHPBB integration
    'templateaddons',  # assign and headers tags
    'django_select2',  # advanced select box
    'easy_thumbnails',
]

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# use a basic in-process cache by default
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'pychronia-cache',
    }
}
# cache key prefix
KEY_PREFIX = "pychronia"

## activate django-sentry if present ##
try:
    import sentry.client

    INSTALLED_APPS.append('sentry.client')
except ImportError:
    pass  # sentry is optional

############# DJANGO-APP CONFS ############


## AUTHENTICATION CONF ##
LOGIN_REDIRECT_URL = '/'  # changed from /accounts/profile/
LOGIN_URL = '/admin/login/'
LOGOUT_URL = '/admin/logout/'
PASSWORD_RESET_TIMEOUT_DAYS = 3

## DJANGO-SELECT2 CONF ##
AUTO_RENDER_SELECT2_STATICS = False
GENERATE_RANDOM_SELECT2_ID = False

## DJANGO CONTRIB MESSAGES CONF ##
from django.contrib.messages import constants as message_constants

MESSAGE_LEVEL = message_constants.DEBUG  # minimum recorded level
# Set MESSAGE_TAGS setting if needed, to control corresponding CSS classes


## DJANGO CONTRIB RST CONF ##

CMSPLUGIN_RST_CONTENT_PREFIX = """

.. |nbsp| unicode:: 0xA0 
   :trim:
    
.. |br| raw:: html

   <br />
   
"""

CMSPLUGIN_RST_SETTINGS_OVERRIDES = {"initial_header_level": 2,  # minimum "h2" when rendered to html
                                    'smart_quotes': "alt"}
#"'language_code': "fr" ## SEEMS BROKEN!


## EASY-THUMBNAILS CONF ##
THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    # 'easy_thumbnails.processors.scale_and_crop', # superseded by "scale_and_crop_with_subject_location"
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
)

# do not change THUMBNAIL_DEFAULT_STORAGE, THUMBNAIL_MEDIA_ROOT and THUMBNAIL_MEDIA_URL, by default
THUMBNAIL_DEBUG = False  # NOT used by custom game_file_img tag
THUMBNAIL_QUALITY = 85
THUMBNAIL_BASEDIR = 'thumbs'  # prefix of relative path
THUMBNAIL_PREFIX = ""  # prefix subdirectory of image file itself
THUMBNAIL_EXTENSION = "jpg"
THUMBNAIL_TRANSPARENCY_EXTENSION = "png"
THUMBNAIL_PRESERVE_EXTENSIONS = True  # or a tuple like ('png',)
THUMBNAIL_CHECK_CACHE_MISS = True  # can regenerate SQL table from storage - unset it if everything works fine


# override these to activate Google Analytics stats
GOOGLE_ANALYTICS_PROPERTY_ID = None
GOOGLE_ANALYTICS_DOMAIN = None
