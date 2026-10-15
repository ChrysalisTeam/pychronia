# -*- coding: utf-8 -*-

import os

from pychronia_game.common_settings import *

from pychronia_common.tests.common_test_settings import *  # DEBUG, SITE_DOMAIN, SECRET_KEY...

from pychronia_game.tests.common_test_settings import *  # ROOT_URLCONF, GAME_FILES_ROOT, ZODB_RESET_ALLOWED...

E2E_WORK_DIR = os.environ["PYCHRONIA_E2E_WORK_DIR"]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": os.path.join(E2E_WORK_DIR, "django.db")}}
ZODB_URL = None
ZODB_FILE = os.path.join(E2E_WORK_DIR, "active", "gamedata.fs")

DEBUG = True  # required by reset_zodb_structure(); also makes _test_urls serve static files
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"  # administration/create/ sends mails

# SITE_DOMAIN is overwritten at runtime by conftest.py once the live server's port is known
# (activation links and enforced-login redirects are built from it).

MIDDLEWARE = tuple(MIDDLEWARE) + ("pychronia_game.tests.e2e._server.InFlightRequestsMiddleware",)

# default test fixtures ONLY (never ../Chrysalis)
assert os.path.normpath(GAME_FILES_ROOT).endswith(os.path.join("tests", "test_game_files")), GAME_FILES_ROOT
GAME_INITIAL_FIXTURE_SCRIPT = None  # all data tweaks happen at runtime through the datamanager, see _configs.py
