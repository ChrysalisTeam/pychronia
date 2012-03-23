
import sys, os, tempfile, random


TEST_DIR = os.path.dirname(os.path.normpath(__file__))


DEBUG = True
TEMPLATE_DEBUG = DEBUG
TEMPLATE_STRING_IF_INVALID = "" # "<INVALID %s>" # important

DB_RESET_ALLOWED = True

SERVER_EMAIL = DEFAULT_FROM_EMAIL = ""
EMAIL_HOST = ""
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_PORT = 25
EMAIL_SUBJECT_PREFIX = ""
EMAIL_USE_TLS = False 

SITE_DOMAIN = "http://127.0.0.1" # NO trailing slash !

# Make this unique, and don't share it with anybody.
SECRET_KEY = '=%f!!2^yh5gkp8725w2kz^$vbjy'


TEMP_DIR = tempfile.mkdtemp()
UNICITY_STRING = str(random.randint(100000, 1000000000))

DATABASE_ENGINE = 'django.db.backends.sqlite3'   #        # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
DATABASE_NAME = os.path.join(TEMP_DIR, "django.db.%s" % UNICITY_STRING) #os.path.join(os.path.dirname(__file__), 'pims_temp_db')  # Or path to database file if using sqlite3.
DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

ZODB_FILE = os.path.join(TEMP_DIR,'gamedata.fs.%s' % UNICITY_STRING)

GAME_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
MEDIA_ROOT = os.path.join(GAME_ROOT, 'static')
# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'


# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
)

TEMPLATE_CONTEXT_PROCESSORS = (
"django.core.context_processors.auth",
"django.core.context_processors.i18n",
"django.core.context_processors.debug",
"django.core.context_processors.media",
"django.core.context_processors.request",
"django.contrib.messages.context_processors.messages",

"rpgweb.context_processors.rpgweb_template_context",

)

MIDDLEWARE_CLASSES = (
'django.contrib.sessions.middleware.SessionMiddleware',
'django.contrib.messages.middleware.MessageMiddleware',
#'localeurl.middleware.LocaleURLMiddleware',
# 'django.middleware.locale.LocaleMiddleware', replaced by LocaleURLMiddleware
'django.middleware.common.CommonMiddleware',
'django.contrib.auth.middleware.AuthenticationMiddleware',
'rpgweb.middlewares.ZodbTransactionMiddleware',
'rpgweb.middlewares.AuthenticationMiddleware',
'rpgweb.middlewares.PeriodicProcessingMiddleware',
'debug_toolbar.middleware.DebugToolbarMiddleware',
)

SITE_ID = 1

TEMPLATE_DIRS = (
    os.path.join(GAME_ROOT, "templates")
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)


INSTALLED_APPS = [
    'debug_toolbar',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions', # only sessions are scalable for "sharding"
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.markup',
    'rpgweb',
]

try:
    import sentry.client
    INSTALLED_APPS.append('sentry.client')
except ImportError:
    pass # sentry is optional


ROOT_URLCONF = 'rpgweb.tests._test_urls'


from django.contrib.messages import constants as message_constants
MESSAGE_LEVEL = message_constants.DEBUG
# Set MESSAGE_TAGS to control corresponding CSS classes 

_curdir = os.path.dirname(os.path.realpath(__file__))
GAME_FILES_ROOT = os.path.join(_curdir, "test_game_files")
GAME_FILES_URL = "/files/"
GAME_INITIAL_DATA_PATH = os.path.join(GAME_FILES_ROOT, "game_initial_data.yaml")

ACTIVATE_AIML_BOTS = False

DB_RESET_ALLOWED = True

try:
  from local_settings import *
except ImportError:
  pass
