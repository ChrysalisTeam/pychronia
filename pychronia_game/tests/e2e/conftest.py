# -*- coding: utf-8 -*-

import os
import shutil
import tempfile

import pytest

# DJANGO_SETTINGS_MODULE must be set, and the work dir must exist, BEFORE `setup_pychronia_env`
# is imported anywhere (it calls django.setup() at import time, which freezes settings).
E2E_WORK_DIR = tempfile.mkdtemp(prefix="pychronia_e2e_")
os.environ["PYCHRONIA_E2E_WORK_DIR"] = E2E_WORK_DIR
os.environ["DJANGO_SETTINGS_MODULE"] = "pychronia_game.tests.e2e.e2e_settings"
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"  # Playwright's sync API runs an event loop in the main thread

import setup_pychronia_env  # noqa: E402  (import order is load-bearing, see above)

from django.conf import settings as django_settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.management import call_command  # noqa: E402

from pychronia_game.datamanager.datamanager_administrator import (  # noqa: E402
    reset_zodb_structure, create_game_instance, retrieve_game_instance,
)

from pychronia_game.tests.e2e import _configs, _pages, _server, _zodb_snapshot  # noqa: E402

ACTIVE_DIR = os.path.join(E2E_WORK_DIR, "active")
PRISTINE_DIR = os.path.join(E2E_WORK_DIR, "pristine")


def pytest_addoption(parser):
    parser.addoption("--e2e-debug", action="store_true", default=False,
                     help="Shortcut for --headed --slowmo 500")


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: Playwright browser end-to-end tests")

    headed = config.option.e2e_debug or bool(os.environ.get("PYCHRONIA_E2E_HEADED"))
    if headed and not config.option.headed:
        config.option.headed = True

    slowmo = os.environ.get("PYCHRONIA_E2E_SLOWMO")
    if config.option.e2e_debug and not slowmo:
        slowmo = "500"
    if slowmo and not config.option.slowmo:
        config.option.slowmo = float(slowmo)


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session", autouse=True)
def e2e_environment():
    os.makedirs(ACTIVE_DIR, exist_ok=True)

    call_command("migrate", run_syncdb=True, verbosity=0)
    User.objects.create_superuser(_configs.SUPERUSER_USERNAME, "e2e_admin@example.com", _configs.SUPERUSER_PASSWORD)

    reset_zodb_structure()
    create_game_instance(game_instance_id=_configs.GAME_ID, creator_login="e2e_creator", skip_randomizations=True)
    create_game_instance(game_instance_id=_configs.SECONDARY_GAME_ID, creator_login="e2e_creator",
                         skip_randomizations=True)

    dm = retrieve_game_instance(_configs.GAME_ID)
    _configs.apply_baseline_tweaks(dm)
    dm.commit()
    dm.close()

    _zodb_snapshot.close_active_zodb()
    _zodb_snapshot.snapshot_zodb(django_settings.ZODB_FILE, PRISTINE_DIR)

    server = _server.LiveServerRunner()
    server.start()
    django_settings.SITE_DOMAIN = server.base_url

    yield server.base_url

    server.stop()
    shutil.rmtree(E2E_WORK_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def base_url(e2e_environment):
    """Overrides pytest-playwright's own `base_url` fixture, so relative page.goto() calls
    resolve against our in-process live server."""
    return e2e_environment


@pytest.fixture
def fresh_zodb(e2e_environment):
    """Restores the pristine ZODB snapshot before the test runs. NOT autouse: it's costly
    (a FileStorage file copy plus an idle-server poll) and most of the suite's ~250
    page-visit parametrizations are read-only, so modules that actually need a clean
    per-test game state opt in with `pytestmark = pytest.mark.usefixtures("fresh_zodb")`
    at the top of the file (or request the `game` fixture, which already depends on this
    one) instead of paying this cost for every single test unconditionally."""
    _server.wait_for_idle_server()
    _zodb_snapshot.restore_zodb(django_settings.ZODB_FILE, PRISTINE_DIR)
    yield


@pytest.fixture
def game(fresh_zodb):
    """Opens a datamanager on the active (just-restored) ZODB, for arrange steps.
    Commits and closes before the browser interacts with the server."""
    dm = retrieve_game_instance(_configs.GAME_ID)
    dm._set_user(dm.get_global_parameter("master_login"))
    yield dm
    dm.commit()
    dm.close()


@pytest.fixture(scope="session")
def player_storage_state(browser, base_url):
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    _pages.login_as_player(page, base_url, _configs.GAME_ID, _configs.BOOSTED_PLAYER,
                           _configs.PLAYER_CREDENTIALS[_configs.BOOSTED_PLAYER])
    state = context.storage_state()
    context.close()
    return state


@pytest.fixture(scope="session")
def superuser_storage_state(browser, base_url):
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    _pages.login_as_superuser(page, base_url, _configs.SUPERUSER_USERNAME, _configs.SUPERUSER_PASSWORD)
    state = context.storage_state()
    context.close()
    return state


@pytest.fixture
def player_page(browser, base_url, player_storage_state):
    context = browser.new_context(base_url=base_url, storage_state=player_storage_state)
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def superuser_page(browser, base_url, superuser_storage_state):
    context = browser.new_context(base_url=base_url, storage_state=superuser_storage_state)
    page = context.new_page()
    yield page
    context.close()
