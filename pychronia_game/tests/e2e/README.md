# Playwright end-to-end tests for `pychronia_game`

This suite drives a real Chromium browser against the Chrysalis/Pychronia game portal,
running the Django app in-process (same Python process as pytest, in a background
thread) against a throwaway ZODB `FileStorage` + sqlite DB, so it is fully isolated
from any real database (MariaDB/RelStorage) or `../Chrysalis` fixture data. It is
**excluded from the default `pytest` run** at the repo root (see `norecursedirs` /
`markers` in `pyproject.toml`) -- you must target this folder explicitly.

## Install

```bash
cd P:/Workspace/Pychronia-e2e
uv sync
uv run playwright install chromium   # downloads the Chromium browser binary, once per machine
```

## Running

```bash
uv run pytest pychronia_game/tests/e2e -q                                    # whole suite, headless
uv run pytest pychronia_game/tests/e2e/test_permissions.py -q                # one file
uv run pytest pychronia_game/tests/e2e/test_interactions.py -q               # another file
uv run pytest pychronia_game/tests/e2e -q -k "friendship"                    # by keyword
```

Useful pytest-playwright options come for free: `--headed`, `--slowmo <ms>`,
`--browser chromium|firefox|webkit`, `--video=retain-on-failure`,
`--tracing=retain-on-failure`, `--screenshot=only-on-failure`.

### Debug / headed mode

One convenience is layered on top in `conftest.py`:

- `--e2e-debug`: shortcut for `--headed --slowmo 500` (so you can actually watch the
  browser work through a test).

Environment variable equivalents, handy for IDE run configurations (checked in
`pytest_configure`, so they apply even without passing CLI flags):

```bash
PYCHRONIA_E2E_HEADED=1 PYCHRONIA_E2E_SLOWMO=500 uv run pytest pychronia_game/tests/e2e -k profile
```

Headed runs should not be parallelized (single visible browser window, and the
in-process live server + ZODB file are shared process-global state).

## How ZODB isolation works

A pristine ZODB snapshot is built once per test session (fresh fixture data, game
started, boosted-player permissions granted, sample messages/friendships/items -- see
`_configs.apply_baseline_tweaks`). The `fresh_zodb` fixture (in `conftest.py`) closes
the live server's open ZODB connection and overwrites the active `gamedata.fs` with a
copy of that pristine snapshot, so a test using it starts from the exact same game state
regardless of what earlier tests wrote or committed.

`fresh_zodb` is **not autouse**: it's a real cost (a `FileStorage` file copy plus an
idle-server poll) worth paying only for tests that actually touch the live server/ZODB.
Every test module that does opts in at the top of the file with:

```python
pytestmark = pytest.mark.usefixtures("fresh_zodb")
```

(`test_01_inventory.py` is the one exception -- its tests are pure-Python checks over
`_inventory.py`'s static classification and never touch the browser or ZODB, aside from
one test that requests the `game` fixture directly, which itself depends on
`fresh_zodb`.) When adding a new test module that drives the browser or a `game`/
datamanager, add that same `pytestmark` line rather than relying on test file
ordering for isolation.

## Adding a new page to the inventory

`_inventory.py` (built by another concurrent work stream, alongside
`test_pages_player.py` / `test_pages_superuser.py`) enumerates every URL pattern in
`pychronia_game.urls.inner_game_urlpatterns` automatically, by introspecting each
view's `NAME` / `ACCESS` / `REQUIRES_CHARACTER_PERMISSION` / `REQUIRES_GLOBAL_PERMISSION`
class attributes -- so a brand new plain `GameView` subclass is picked up with **no
change needed here**. `test_01_inventory.py::test_inventory_is_complete` fails loudly
if a URL pattern can't be classified into one of `_inventory.CATEGORY_PLAIN_GET` /
`CATEGORY_PARAMETRIZED` / `CATEGORY_AJAX_OR_NON_HTML` / `CATEGORY_EXCLUDED`, so new
pages can't silently escape coverage.

You only need to touch `_inventory.py` by hand when a new page needs a **sample URL
parameter** (add it to `CATEGORY_PARAMETRIZED` with a sample-path provider) or is
genuinely dangerous/not meant to be navigated directly (add its view `NAME` to
`EXCLUDED_NAMES`, alongside `TEST_CAPTCHA` / `CHARACTERS_IDENTITIES` /
`DATABASE_OPERATIONS` / `FAIL_TEST` / `MEDIA_TEST` / `logout`). If a page needs a
*permission* to be forced in order to be reachable at all (`REQUIRES_CHARACTER_PERMISSION
= True`, i.e. gated by an `access_<NAME>` permission -- see
`AbstractGameView.get_access_permission_name()` in
`pychronia_game/datamanager/abstract_game_view.py`), add a representative case to
`test_permissions.py::PERMISSION_GATED_VIEWS` instead; permission names are not
hand-maintained anywhere else, so cross-check them against
`dm.PERMISSIONS_REGISTRY` if in doubt (it's a plain `Enum` of every valid permission
string, inspectable from any test using the `game` fixture).

## File layout (as of this writing)

```
pychronia_game/tests/e2e/
    conftest.py              # bootstrap, session ZODB init, live server, fixtures (game/player_page/superuser_page/...)
    e2e_settings.py          # dedicated Django settings module (sqlite + ZODB FileStorage, never MariaDB/../Chrysalis)
    _server.py                # in-process live server thread + request-idleness tracking
    _zodb_snapshot.py          # close/reset ZODB_INSTANCE, snapshot/restore pristine <-> active gamedata.fs
    _configs.py                # GAME_ID/credentials/apply_baseline_tweaks(dm)/apply_config(dm, config_id)
    _pages.py                  # login_as_player/login_as_superuser/goto_as/set_impersonation_writability/logout/assert_page_ok
    _inventory.py               # URL enumeration + access-rule computation, used by test_pages_player.py/test_pages_superuser.py
    test_00_infra.py            # infra smoke tests: server up, ZODB restore isolation, login/impersonation basics
    test_01_inventory.py         # meta-tests over the inventory itself (completeness, category sanity)
    test_pages_player.py         # visits every page as a plain game player (boosted vs plain identity)
    test_pages_superuser.py      # same, via Django-superuser impersonation (master and superuser-as-player passes)
    test_permissions.py           # forcing permissions (plan section 6): boosted vs plain player, no_activated_views, disabled login
    test_interactions.py          # a handful of end-to-end interaction scenarios (compose message, encrypted folder, pause toggle, logout, friendship)
    test_administration.py        # administration/ meta-admin pages (instance lock/unlock, activation emails, etc.)
```
