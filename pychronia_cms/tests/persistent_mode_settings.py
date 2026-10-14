# -*- coding: utf-8 -*-

import os, sys

from pychronia_cms.common_settings import *

from pychronia_common.tests.persistent_mode_settings import *  # simple overrides

ROOT_URLCONF = 'pychronia_cms.tests._test_urls'

_curdir = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'chryscms_local',  # TEMPORARY (do not commit): local MariaDB sandbox
        'USER': 'root',
        'PASSWORD': '',
        'HOST': 'localhost',
    }
}
