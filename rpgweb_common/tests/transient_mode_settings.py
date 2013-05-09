# -*- coding: utf-8 -*-

import os, tempfile, random

from rpgweb_common.tests.common_test_settings import *


TEMP_DIR = tempfile.mkdtemp()
UNICITY_STRING = str(random.randint(100000, 1000000000))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TEMP_DIR, "django.db.%s" % UNICITY_STRING),
        'TEST_NAME': os.path.join(TEMP_DIR, "djangotest.db.%s" % UNICITY_STRING),
    }
}
