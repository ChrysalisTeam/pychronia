# -*- coding: utf-8 -*-


import os, random

## PYCHRONIA SPECIFIC CONF ##

_curdir = os.path.dirname(os.path.realpath(__file__))
GAME_FILES_ROOT = os.path.join(_curdir, "test_game_files") + os.sep
GAME_FILES_URL = "/files/"

GAME_INITIAL_DATA_PATH = os.path.join(GAME_FILES_ROOT, "game_initial_data.yaml")

ACTIVATE_AIML_BOTS = False

ZODB_RESET_ALLOWED = True

MOBILE_HOST_NAMES = ["127.0.0.1:8000"]
ROOT_URLCONF_MOBILE = "pychronia_game.tests._test_urls_mobile" # thus if we use IP instead of localhost, we access the mobile version

WEB_SITE_ENTRY_URL_TEMPLATE = "http://localhost:8000/%s/"
MOBILE_SITE_ENTRY_URL_TEMPLATE = "http://127.0.0.1:8000/%s/"

BUG_REPORT_EMAIL = "bugreport@example.com"

PASSWORDS_POOL = [str(random.randint(100, 1000)) for i in range(50)]
