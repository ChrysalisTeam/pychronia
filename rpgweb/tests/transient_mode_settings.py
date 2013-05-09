# -*- coding: utf-8 -*-


from rpgweb.common_settings import *

from rpgweb_common.tests.transient_mode_settings import * # simple overrides

from rpgweb.tests.common_test_settings import * # simple overrides


ROOT_URLCONF = 'rpgweb.tests._test_urls_web'

ZODB_FILE = os.path.join(TEMP_DIR, 'gamedata.fs.%s' % UNICITY_STRING)
ZODB_URL = None
