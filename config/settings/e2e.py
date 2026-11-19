"""Settings of the Playwright end-to-end tests of the game site (see pychronia_game/tests/e2e/conftest.py)."""

import os
import tempfile

from config.settings.game import *

from config.settings._dev_base import *  # DEBUG, SITE_DOMAIN, SECRET_KEY...

from config.settings._game_dev_base import *  # ROOT_URLCONF, GAME_FILES_ROOT, ZODB_RESET_ALLOWED...

E2E_WORK_DIR = tempfile.mkdtemp(prefix="pychronia_e2e_")  # removed by pytest_unconfigure() of conftest.py

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(E2E_WORK_DIR, "django.db"),  # unused, pytest-django creates and uses the test DB below
        # A FILE, not the default in-memory sqlite test DB: the in-process live server thread (and its per-request
        # threads) must see the same DB as the main thread, which creates the superuser at session start
        "TEST": {"NAME": os.path.join(E2E_WORK_DIR, "django_test.db")},
    }
}
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
