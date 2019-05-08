# -*- coding: utf-8 -*-

import time

from pychronia_game.common_settings import *

from pychronia_common.tests.persistent_mode_settings import *  # simple overrides

from pychronia_game.tests.common_test_settings import *  # simple overrides

_curdir = os.path.dirname(os.path.realpath(__file__))

# we override transient test DBs with persistent ones
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(_curdir, "django.db")
    }
}

ZODB_FILE = os.path.join(_curdir, "gamedata.fs")
ZODB_URL = None



## OVERRIDES FOR INTEGRATION OF REAL CHRYSALIS FIXTURES, if they're in ../Chrysalis relatively to this depot's root ##
import pychronia_game, os

_external_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(pychronia_game.__file__))))
_chrysalis_data_dir = os.path.join(_external_dir, "Chrysalis")
if os.path.exists(_chrysalis_data_dir):

    GAME_FILES_ROOT = _chrysalis_data_dir + os.sep

    GAME_INITIAL_DATA_PATH, GAME_INITIAL_FIXTURE_SCRIPT = \
        generate_auction_settings(GAME_FILES_ROOT)  # or generate_mindstorm_settings()

