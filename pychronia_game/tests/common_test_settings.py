# -*- coding: utf-8 -*-


import os, random

## PYCHRONIA SPECIFIC CONF ##


ROOT_URLCONF = 'pychronia_game.tests._test_urls'

_curdir = os.path.dirname(os.path.realpath(__file__))
GAME_FILES_ROOT = os.path.join(_curdir, "test_game_files") + os.sep
GAME_FILES_URL = "/files/"

GAME_INITIAL_DATA_PATH = os.path.join(GAME_FILES_ROOT, "game_initial_data.yaml")

ACTIVATE_AIML_BOTS = True

ZODB_RESET_ALLOWED = True

BUG_REPORT_EMAIL = "bugreport@example.com"

PASSWORDS_POOL = [str(random.randint(100, 1000000000)) for i in range(50)]
assert len(set(PASSWORDS_POOL)) == len(PASSWORDS_POOL)

ACAPELA_CLIENT_ARGS = None

GAME_ALLOW_ENFORCED_LOGIN = True
