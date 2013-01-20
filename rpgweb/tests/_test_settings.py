# -*- coding: utf-8 -*-

from rpgweb_common.common_settings import *


TEST_DIR = os.path.dirname(os.path.abspath(__file__))

DEBUG = True
TEMPLATE_DEBUG = DEBUG


# Make this unique, and don't share it with anybody.
SECRET_KEY = '=%f!!2^yh5gk92728363982827p8725wsdfsdf2kz^$vbjy'

SITE_DOMAIN = "http://127.0.0.1" # NO trailing slash !

ROOT_URLCONF = 'rpgweb.tests._test_urls'


ZODB_FILE = os.path.join(TEMP_DIR, 'gamedata.fs.%s' % UNICITY_STRING)

GAME_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))



# rpgweb specific conf #

_curdir = os.path.dirname(os.path.realpath(__file__))
GAME_FILES_ROOT = os.path.join(_curdir, "test_game_files")
GAME_FILES_URL = "/files/"
GAME_INITIAL_DATA_PATH = os.path.join(GAME_FILES_ROOT, "game_initial_data.yaml")

ACTIVATE_AIML_BOTS = False

DB_RESET_ALLOWED = True



MEDIA_ROOT = os.path.join(GAME_ROOT, 'media')



print("SETTING UP RPGWEB TEST LOGGING")
import logging
logging.basicConfig()
logging.disable(0)
logging.getLogger("txn").setLevel(logging.WARNING) # ZODB transactions



TEMPLATE_CONTEXT_PROCESSORS = TEMPLATE_CONTEXT_PROCESSORS + ("rpgweb.context_processors.rpgweb_template_context",)




MIDDLEWARE_CLASSES = (
#'sessionprofile.middleware.SessionProfileMiddleware', NEEDED FOR PHPBB here too ?
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



INSTALLED_APPS += [
    'rpgweb',
]





