# -*- coding: utf-8 -*-

import os, sys

from pychronia_cms.common_settings import *

from pychronia_common.tests.persistent_mode_settings import *  # simple overrides

ROOT_URLCONF = 'pychronia_cms.tests._test_urls'

_curdir = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
    '__default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(_curdir, "django.db")
    },
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'chrysalis_cms_dev_empty',
        'USER': 'root',
        'PASSWORD': 'root',
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
