"""
Bootstrap of the e2e suite.

Django is already set up by pytest-django, with the e2e settings given by the pytest.ini of this folder
(config.settings.e2e: sqlite + ZODB FileStorage in a temp work dir).
"""

import os
import shutil

import pytest

from django.conf import settings as django_settings
from django.contrib.auth.models import User

from pychronia_game.tests._safety import ensure_throwaway_databases

E2E_SETTINGS_MODULE = "config.settings.e2e"

if django_settings.SETTINGS_MODULE != E2E_SETTINGS_MODULE:
    # eg. this folder was given to pytest along with paths outside of it, so the root pyproject.toml was used
    raise pytest.UsageError(
        "The e2e suite must run with %r settings, not %r: launch it separately, eg. 'pytest pychronia_game/tests/e2e', "
        "so that its own pytest.ini is used" % (E2E_SETTINGS_MODULE, django_settings.SETTINGS_MODULE)
    )

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"  # Playwright's sync API runs an event loop in the main thread

from pychronia_game.datamanager.datamanager_administrator import (  # noqa: E402
    reset_zodb_structure,
    create_game_instance,
    retrieve_game_instance,
)

from pychronia_game.tests.e2e import _configs, _pages, _server, _zodb_snapshot  # noqa: E402

E2E_WORK_DIR = django_settings.E2E_WORK_DIR
ACTIVE_DIR = os.path.join(E2E_WORK_DIR, "active")
PRISTINE_DIR = os.path.join(E2E_WORK_DIR, "pristine")


def pytest_addoption(parser):
    parser.addoption("--e2e-debug", action="store_true", default=False, help="Shortcut for --headed --slowmo 500")


def pytest_configure(config):
    # As early as possible: before tests are collected, before pytest-django creates its SQL test DB,
    # and before the session fixture wipes the ZODB
    try:
        ensure_throwaway_databases()
    except RuntimeError as exc:
        raise pytest.UsageError(str(exc)) from exc

    config.addinivalue_line("markers", "e2e: Playwright browser end-to-end tests")

    headed = config.option.e2e_debug or bool(os.environ.get("PYCHRONIA_E2E_HEADED"))
    if headed and not config.option.headed:
        config.option.headed = True

    slowmo = os.environ.get("PYCHRONIA_E2E_SLOWMO")
    if config.option.e2e_debug and not slowmo:
        slowmo = "500"
    if slowmo and not config.option.slowmo:
        config.option.slowmo = float(slowmo)


def pytest_unconfigure(config):
    # after all fixtures are torn down, including pytest-django's django_db_setup which deletes the SQL test DB file
    shutil.rmtree(E2E_WORK_DIR, ignore_errors=True)


def pytest_collection_modifyitems(config, items):
    for item in items:
        item.add_marker(pytest.mark.e2e)


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    """
    Overrides the fixture of pytest-django, which only creates the test DBs used by collected tests (via
    "django_db" marks etc.), ie. none here: the "default" test DB is always created (and migrated) here.
    """
    from django.test.utils import setup_databases, teardown_databases

    with django_db_blocker.unblock():
        db_cfg = setup_databases(verbosity=0, interactive=False, aliases={"default"}, serialized_aliases=set())
    yield
    with django_db_blocker.unblock():
        teardown_databases(db_cfg, verbosity=0)


@pytest.fixture(scope="session", autouse=True)
def e2e_environment(django_db_setup, django_db_blocker):
    """
    The SQL DB is pytest-django's test DB (a file, see config/settings/e2e.py), created and migrated once
    by django_db_setup, and shared by the whole session like the live server: tests aren't marked "django_db"
    (a per-test rollback or flush couldn't undo the commits of the live server thread anyway, and would delete
    the superuser), so DB access stays unblocked for the whole session, in the live server threads too.
    """
    with django_db_blocker.unblock():
        yield from _setup_e2e_environment()


def _setup_e2e_environment():
    os.makedirs(ACTIVE_DIR, exist_ok=True)

    User.objects.create_superuser(_configs.SUPERUSER_USERNAME, "e2e_admin@example.com", _configs.SUPERUSER_PASSWORD)

    reset_zodb_structure()
    # English instances, since e2e tests check English UI strings (the UI defaults to the game language)
    create_game_instance(
        game_instance_id=_configs.GAME_ID, creator_login="e2e_creator", game_language="en", skip_randomizations=True
    )
    create_game_instance(
        game_instance_id=_configs.SECONDARY_GAME_ID,
        creator_login="e2e_creator",
        game_language="en",
        skip_randomizations=True,
    )

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
    _zodb_snapshot.close_active_zodb()  # releases the gamedata.fs file, for the final cleanup of E2E_WORK_DIR


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
    _pages.login_as_player(
        page, base_url, _configs.GAME_ID, _configs.BOOSTED_PLAYER, _configs.PLAYER_CREDENTIALS[_configs.BOOSTED_PLAYER]
    )
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
