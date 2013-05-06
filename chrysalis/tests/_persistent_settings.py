# -*- coding: utf-8 -*-

from ._test_settings import *

DEBUG = True


RESTRUCTUREDTEXT_FILTER_SETTINGS["raw_enabled"] = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'pakal_devs',
        'HOST': 'Web225',
        'USER': 'pakal_devs',
        'PASSWORD': '0851fda3',
    }
}
