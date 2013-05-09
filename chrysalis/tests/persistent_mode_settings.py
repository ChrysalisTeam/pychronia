# -*- coding: utf-8 -*-

from chrysalis.common_settings import *

from rpgweb_common.tests.persistent_mode_settings import * # simple overrides


ROOT_URLCONF = 'chrysalis.tests._test_urls'

_curdir = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(_curdir, "django.db")
    }
}
