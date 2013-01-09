
import sys, os, tempfile, random
ugettext = lambda s: s # dummy placeholder for makemessages

try:
    import PIL.Image
    sys.modules['Image'] = PIL.Image # prevents AccessInit: hash collision: 3 for both 1 and 1
except ImportError:
    pass

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH = os.path.dirname(os.path.dirname(TEST_DIR))
print "ROOT PATH:", ROOT_PATH

SESSION_COOKIE_DOMAIN = ".prolifik.net"
SESSION_COOKIE_NAME = 'sessionid' # DO NOT CHANGE - needed for phpbb integration

DEBUG = True
TEMPLATE_DEBUG = DEBUG
TEMPLATE_STRING_IF_INVALID = "" # "<INVALID %s>" # important

DEBUG_TOOLBAR_CONFIG = {
    'INTERCEPT_REDIRECTS': False,
    'SHOW_TOOLBAR_CALLBACK': lambda *args, **kwargs: True,
    'HIDE_DJANGO_SQL': False,
    'ENABLE_STACKTRACES' : True,
    'HIDE_DJANGO_SQL': True,
    'SHOW_TEMPLATE_CONTEXT': True,
}



SERVER_EMAIL = DEFAULT_FROM_EMAIL = ""
EMAIL_HOST = ""
EMAIL_HOST_USER = ""
EMAIL_HOST_PASSWORD = ""
EMAIL_PORT = 25
EMAIL_SUBJECT_PREFIX = ""
EMAIL_USE_TLS = False

SITE_DOMAIN = "http://127.0.0.1" # NO trailing slash !

# Make this unique, and don't share it with anybody.
SECRET_KEY = '=%f!!2^yh5gk982827p8725wsdfsdf2kz^$vbjy'


TEMP_DIR = tempfile.mkdtemp()
UNICITY_STRING = str(random.randint(100000, 1000000000))


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TEMP_DIR, "django.db.%s" % UNICITY_STRING)
    }
}



TIME_ZONE = 'Europe/Paris'
USE_L10N = True
USE_I18N = True
LANGUAGE_CODE = 'fr'
LANGUAGES = (
  ('fr', ugettext('French')),
  ('en', ugettext('English')),
)



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




# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(ROOT_PATH, "chrysalis", "media")

STATICFILES_DIRS = (
    os.path.join(ROOT_PATH, "common_static"),
)

### STATIC_ROOT = "" # where collectstatic cmd will place files
STATIC_URL = "/static/"
ADMIN_MEDIA_PREFIX = "/static/admin/" # deprecated but needed by django-cms


# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
"django.contrib.auth.context_processors.auth",
"django.core.context_processors.i18n",
"django.core.context_processors.debug",
"django.core.context_processors.media",
"django.core.context_processors.request",
"django.contrib.messages.context_processors.messages",
"django.core.context_processors.static",
"cms.context_processors.media",
"sekizai.context_processors.sekizai",
)

MIDDLEWARE_CLASSES = (
'sessionprofile.middleware.SessionProfileMiddleware',
'django.contrib.sessions.middleware.SessionMiddleware',
'django.contrib.messages.middleware.MessageMiddleware',
# 'localeurl.middleware.LocaleURLMiddleware',
# 'django.middleware.locale.LocaleMiddleware', replaced by LocaleURLMiddleware
'django.middleware.common.CommonMiddleware',
'django.contrib.auth.middleware.AuthenticationMiddleware',

# #'cms.middleware.multilingual.MultilingualURLMiddleware',
'cms.middleware.page.CurrentPageMiddleware',
'cms.middleware.user.CurrentUserMiddleware',
'cms.middleware.toolbar.ToolbarMiddleware',

'debug_toolbar.middleware.DebugToolbarMiddleware',
)

# ## NOPE SITE_ID = 2

TEMPLATE_DIRS = (
    os.path.join(ROOT_PATH, "common_templates")
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)


INSTALLED_APPS = [

    'sessionprofile', # keeps track of sessions/users in DB table, for PHPBB integration
    'templateaddons',

    'debug_toolbar',

    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.comments', # for blog
    'django.contrib.sessions', # only these sessions are scalable for "sharding"
    'django.contrib.messages',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django.contrib.markup',
    'chrysalis',

    'cms',
    'mptt',
    'menus',
    'south',
    'sekizai',



    'cmsplugin_rst',
    'cmsplugin_simple_gallery',

    # 'cms.plugins.flash',
    # 'cms.plugins.googlemap',

    'cms.plugins.link',
    'cms.plugins.snippet',
    'cms.plugins.text',

     ###########
    # 'cms.plugins.file',
    # 'cms.plugins.picture',
    # 'cms.plugins.teaser',
    # 'cms.plugins.video',
    # OR BETTER:
    'filer',
    'easy_thumbnails',
    'cmsplugin_filer_file',
    'cmsplugin_filer_folder',
    'cmsplugin_filer_image',
    'cmsplugin_filer_teaser',
    'cmsplugin_filer_video',

    'tagging',
    'zinnia',
    'cmsplugin_zinnia',

]


THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    # 'easy_thumbnails.processors.scale_and_crop',
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
)

CMS_SIMPLEGALLERY_THUMBNAIL_OPTIONS = {
    'size': (240, 180),
    'crop': True,
    'quality': 80,
}


ZINNIA_ENTRY_BASE_MODEL = 'cmsplugin_zinnia.placeholder.EntryPlaceholder'
CMSPLUGIN_ZINNIA_HIDE_ENTRY_MENU = True
CMSPLUGIN_ZINNIA_TEMPLATES = []
CMSPLUGIN_ZINNIA_APP_MENUS = []

ZINNIA_PAGINATION = 1
ZINNIA_UPLOAD_TO = "uploads/zinnia"
ZINNIA_PROTOCOL = "http"
ZINNIA_COPYRIGHT = "ChrysalisGame"
ZINNIA_USE_TWITTER = False # todo later


try:
    import sentry.client
    INSTALLED_APPS.append('sentry.client')
except ImportError:
    pass # sentry is optional


ROOT_URLCONF = 'chrysalis.tests._test_urls'


from django.contrib.messages import constants as message_constants
MESSAGE_LEVEL = message_constants.DEBUG
# Set MESSAGE_TAGS to control corresponding CSS classes

try:
    from local_settings import *
except ImportError:
    pass
