# Plan — Playwright end-to-end test suite for `pychronia_game`

Status: PLAN ONLY (uncommitted, repo root). Target branch: a new worktree branched from `dev`.

---

## 0. Goal (restated)

Add `pychronia_game/tests/e2e/`, a **pytest + Playwright** suite that:

1. is **excluded from the default pytest run** (`pytest` at repo root must keep running only the existing unit tests);
2. **initializes the test ZODB once** per session (same way as `common_test_settings.py` + `BaseGameTestCase` do), then keeps a **pristine copy** of it;
3. **before each test case**, copies the pristine ZODB over the "active" ZODB location used by the live server;
4. visits **every page of the portal**, **as a player** and **again as a superuser**, in **each configuration**;
5. also tests the **`administration/`** meta-admin pages;
6. **forces permissions** on one player so that permission-gated pages are reachable;
7. runs **headless by default**, with an on-demand **headed + slowed-down** mode.

---

## 1. Worktree setup

```bash
cd P:/Workspace/Pychronia
git worktree add -b e2e-playwright ../Pychronia-e2e dev
cd ../Pychronia-e2e
uv sync                                   # reuses uv.lock (new venv in the worktree)
uv add --group dev pytest-playwright       # pulls "playwright" too
uv run playwright install chromium         # browser binaries (once per machine)
```

Notes:
- The two uncommitted local edits on `dev` (`pychronia_cms/tests/persistent_mode_settings.py`, `pychronia_game/tests/persistent_mode_settings.py` → local MariaDB) are **not** carried into the worktree. They don't matter: the e2e suite uses its **own settings module** (sqlite + ZODB `FileStorage`), never MariaDB/RelStorage, so that copying the ZODB is a plain file copy.
- **`../Chrysalis/` is never used.** The suite relies only on the versioned default test fixtures (`pychronia_game/tests/test_game_files/`). It does not import `persistent_mode_settings.py`, which is where the `../Chrysalis` override lives. As a guard, `e2e_settings.py` asserts that `GAME_FILES_ROOT` is inside `pychronia_game/tests/test_game_files`.

---

## 2. Excluding the suite from default pytest runs

`pyproject.toml` currently has:

```toml
[tool.pytest.ini_options]
testpaths = ["pychronia_game/tests"]
```

`testpaths` contains the e2e folder, so it must be excluded explicitly:

```toml
[tool.pytest.ini_options]
testpaths = ["pychronia_game/tests"]
norecursedirs = ["e2e", "____backup", "test_game_files", ".*", "__pycache__"]
markers = ["e2e: Playwright browser end-to-end tests (run with: pytest pychronia_game/tests/e2e)"]
```

- `norecursedirs` matches basenames during collection. Passing the folder explicitly (`pytest pychronia_game/tests/e2e`) still collects it, because explicit args bypass `norecursedirs`. **Verify this at implementation time.** Fallback if not: `addopts = "--ignore-glob=*/tests/e2e/*"`, run with `-p no:...`/`--override-ini addopts=`, or a dedicated `pychronia_game/tests/e2e/pytest.ini` used via `-c`.
- Also add a safety net in `e2e/conftest.py`: `pytest_collection_modifyitems` marks every item `e2e`.
- Make sure the existing unit-test conftest/bootstrap (if any) doesn't fight with the e2e one. The e2e `conftest.py` must set `DJANGO_SETTINGS_MODULE` **before** `setup_pychronia_env` is imported (it calls `django.setup()` at import time).
- `pytest-playwright` registers its plugin globally. That is harmless for unit tests, since its fixtures only activate when requested.

---

## 3. Settings module: `pychronia_game/tests/e2e/e2e_settings.py`

Built like `transient_mode_settings.py`, but with **stable, known paths** inside a per-run work dir:

```python
from pychronia_game.common_settings import *
from pychronia_common.tests.common_test_settings import *
from pychronia_game.tests.common_test_settings import *   # ROOT_URLCONF=_test_urls, GAME_FILES_ROOT, GAME_INITIAL_DATA_PATH, ZODB_RESET_ALLOWED, GAME_ALLOW_ENFORCED_LOGIN...

E2E_WORK_DIR = os.environ["PYCHRONIA_E2E_WORK_DIR"]       # set by conftest (tmp_path_factory-like dir)

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3",
                         "NAME": os.path.join(E2E_WORK_DIR, "django.db")}}
ZODB_URL  = None
ZODB_FILE = os.path.join(E2E_WORK_DIR, "active", "gamedata.fs")        # the "active" ZODB

DEBUG = True                      # required by reset_zodb_structure(); also makes _test_urls serve static files
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"   # administration/create/ sends mails
ACTIVATE_AIML_BOTS = True        # as in common_test_settings; TBD: disable if it slows session init too much

# default test fixtures ONLY (never ../Chrysalis)
assert os.path.normpath(GAME_FILES_ROOT).endswith(os.path.join("tests", "test_game_files"))
GAME_INITIAL_FIXTURE_SCRIPT = None   # all data tweaks happen at runtime through the datamanager (§5)
```

- `utilities.config` is a lazy proxy over `django.conf.settings`, so these values are what the game reads.
- `SITE_DOMAIN` must point at the live server URL, because activation links are built from it. Set it from an env var that conftest fills once the port is known (or override at runtime with `override_settings`).
- If ROOT_URLCONF's staticfiles patterns are not enough under a non-`runserver` WSGI server, wrap the WSGI app in `StaticFilesHandler` (see §4).

---

## 4. Live server and ZODB snapshot/restore (core mechanism)

### 4.1 Server choice: in-process threaded server

Run Django **in the pytest process**, in a background thread, using `django.test.testcases.LiveServerThread` (with `StaticFilesHandler`) or a small `wsgiref`/`ThreadingWSGIServer` wrapper bound to `127.0.0.1:0`.

Why in-process rather than a `runserver` subprocess:
- On Windows, the server's open `FileStorage` **locks `gamedata.fs`**. You cannot overwrite it from outside.
- The ZODB `DB` object is cached process-wide in `datamanager_administrator.ZODB_INSTANCE` (`_ensure_zodb_is_open()` opens it once, under a lock). Only in-process can the fixture **close it and reset it to `None`**. The next request then reopens the freshly copied file.
- The fixture can also use the datamanager API directly (force permissions, set game state) on the same DB.

Playwright's **sync** API runs an event loop in the main thread. Django ORM calls made from that thread (e.g. creating the superuser) then raise `SynchronousOnlyOperation`. Set `os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"` in conftest. This is the known pytest-django + pytest-playwright workaround, and it's acceptable for tests.

### 4.2 Session-scoped initialization (once)

Fixture `e2e_environment` (session scope, autouse):

1. Create the work dir (`tmp_path_factory.mktemp("pychronia_e2e")`). Set the env vars, then import `setup_pychronia_env` (→ `django.setup()`).
2. Django DB: `call_command("migrate", run_syncdb=True, verbosity=0)`. Create the Django **superuser** `e2e_admin` / `e2e_admin_pwd` (`is_staff=True, is_superuser=True`).
3. ZODB init, mirroring `BaseGameTestCase.setUp` (`tests/_test_tools.py:227-299`):
   ```python
   reset_zodb_structure()
   create_game_instance(game_instance_id=GAME_ID, creator_login="ze_creator",
                        skip_randomizations=True)        # keeps the YAML passwords usable
   dm = retrieve_game_instance(GAME_ID)
   apply_baseline_tweaks(dm)    # §5.1: game started, all views activated, guy1 permissions (§6), messages, items...
   dm.commit(); close connection
   ```
   Also create a **second game instance**, so that `administration/` lists more than one row and the per-instance actions can be exercised without breaking the main one.
4. Close the DB fully: `ZODB_INSTANCE.close()` and `datamanager_administrator.ZODB_INSTANCE = None`. Copy `active/gamedata.fs` (+ `.index`; skip `.lock`/`.tmp`) to `pristine/`.
5. Also snapshot `django.db` → `pristine/django.db`. Sessions accumulate across tests otherwise. Optional, but cheap and keeps tests independent.
6. Start the live server thread. Yield its `base_url`. Stop it at teardown.

### 4.3 Per-test restore (autouse, function scope)

Fixture `fresh_zodb`:

1. Wait until the server is idle. Keep an "in-flight requests" counter via a tiny WSGI wrapper or middleware, because a page's trailing AJAX calls (chat polling, audio notifications) can still be running.
2. Under the `datamanager_administrator` lock: close and reset `ZODB_INSTANCE`.
3. `shutil.copy2` the pristine `gamedata.fs` (+ `.index`) → `active/`. Delete any stale `.lock`/`.tmp`.
4. (Optional) restore `django.db`. This requires closing Django DB connections first (`django.db.connections.close_all()`).
5. The next HTTP request reopens the ZODB lazily.

Each test then gets a brand-new Playwright `context` (pytest-playwright's default `page` fixture already does this), so cookies and sessions never leak between tests.

### 4.4 Helper API exposed to tests

A `game` fixture opens a datamanager on the active DB (`retrieve_game_instance(GAME_ID)`) for **arrange** steps, e.g. toggling `set_game_state(False)` or deactivating views. It commits and closes the connection before the browser step.

---

## 5. Configurations

**Single data source.** The only game data is the default test fixture `pychronia_game/tests/test_game_files/game_initial_data.yaml` (as wired by `common_test_settings.py`). Every "configuration" is produced **at runtime** by tweaking the game through the datamanager API. This happens either once, in the session init (so it's baked into the pristine snapshot), or per test, right after the ZODB restore. Nothing reads `../Chrysalis`, and nothing uses `generate_mindstorm_settings` / `generate_auction_settings`.

Credentials are therefore static and known: `guy1/elixir` (boosted player), `guy2/awesome` (plain player), `guy3/awesome2` (has a secret question), and `master/ultimate`. `guy4` has its login disabled. They stay valid because the instance is created with `skip_randomizations=True`.

### 5.1 Baseline tweaks (session init → part of the pristine snapshot)

These enrich the bare fixture so that pages show real content, rather than empty lists:

| Tweak | API | Why |
|---|---|---|
| game started | `dm.set_game_state(True)` | normal play mode |
| all activable views activated | `dm.set_activated_game_views(list(dm.ACTIVABLE_VIEWS_REGISTRY))` | the YAML activates none |
| all permissions for `guy1` | `dm.update_permissions("guy1", PersistentList(dm.PERMISSIONS_REGISTRY))` | see §6 |
| messages between players, an external contact, and a reply thread; some archived | `dm.post_message(...)`, `dm.set_dispatched_message_state_flags(..., has_archived=True)` | conversations, all_dispatched/archived/queued, view_single_message pages show content |
| wiretapping: `guy3` taps `guy1` | `dm.set_wiretapping_targets("guy3", ["guy1"])` | intercepted_messages page has content |
| items distributed: `sacred_chest` (+ a gem) to `guy1` | `dm.transfer_object_to_character(...)` | item3dview, personal_items, view_sales show owned items |
| friendship `guy1`↔`guy2` | `dm.propose_friendship` both ways | friendships page; player→friend impersonation |

(The message/wiretapping/items steps reuse the *ideas* of the old auction fixture script, but on the default fixture's characters.)

### 5.2 Per-test configuration variants (parametrization, applied after the ZODB restore)

| id | Arrange step | Expectation |
|---|---|---|
| `baseline` | none | pages render normally |
| `paused` | `dm.set_game_state(False)` | pages still render; the player is read-only (writability notice); POST attempts are rejected with an error message |
| `no_activated_views` | `dm.set_activated_game_views([])` (the raw YAML state) | for `guy1`, views granted by `access_<NAME>` still work; for `guy2`, activable views redirect to home with an error notification; master/superuser unaffected |
| `encyclopedia_index_hidden` | `dm.set_encyclopedia_index_visibility(False)` | encyclopedia index is hidden for players; articles are still reachable by id |
| `instance_in_maintenance` | `change_game_instance_status` / maintenance lock (`datamanager_administrator`) | game pages return 503 (covered in §10) |

All tweaks go through one helper, `apply_config(dm, config_id)`, in `_configs.py`, so adding a variant is one function. Keep the default run bounded: `baseline` is run on every page × identity. `paused` and `no_activated_views` run on a representative subset, and the full matrix sits behind a `--e2e-full-matrix` flag (the whole set is ≈ pages × 2 identities × 3 variants ≈ 600 browser loads).

---

## 6. Forcing permissions

Several views are `ACCESS=character` with `REQUIRES_CHARACTER_PERMISSION=True` (house_locking, house_reports, runic_translation, wiretapping, mercenaries_hiring, matter_analysis, telecom_investigation, world_scan, artificial_intelligence) or need a permission (chess_challenge, geoip_location). Extra permissions include `purchase_confidentiality_protection` and `view_others_belongings`.

In the **session init** (so it's in the pristine snapshot), for the designated test player:

```python
dm.update_permissions("guy1", PersistentList(dm.PERMISSIONS_REGISTRY))   # same as test_game.py:4541
```

Only **one** player (`guy1`) is boosted (as requested). A second, un-boosted player (`guy2`) is used in a few negative tests: permission-gated page → redirected home, with the menu entry present but disabled.

---

## 7. Identities and how to log in

| Identity | How | Notes |
|---|---|---|
| **player** | GET `/<GAME_ID>/guest/login/` (sets test cookie), fill `secret_username`, `secret_password`, click `login` | lands on `/<GAME_ID>/<player>/` |
| **superuser** | GET `/admin/login/`, fill `username`/`password` (Django admin form) | Django superuser, **not** logged into the game ⇒ `is_superuser` game user, which can impersonate anyone |

The superuser pass covers **all** pages, including character-only ones:
- **Master/admin pages**: the superuser impersonates the master (`/<GAME_ID>/master/...`). If the URL username isn't honored directly, POST `_set_impersonation_target_=master` (see `authentication.py:9-10`, `middlewares.py:105-136`).
- **Character-only pages** (`ACCESS=character`): the master alone gets `authentication_required`, so these are visited with the superuser impersonating the boosted player (`/<GAME_ID>/<player>/...`), read-only and then writable (`_set_impersonation_writability_=true`) for one sample page.
- **Anonymous pages** (login, `my_runic_translation_open`, secret_question…) are also visited unauthenticated as a smoke test.

Optionally the real **game master** login (`master/ultimate` via the game login form) can be added as a third identity. It's cheap, since it's the same page list as superuser→master.

Speed: log in once per worker via the UI, save `context.storage_state()` to a file, and reuse it with `browser.new_context(storage_state=...)` per test. Django sessions live in the sqlite DB, so with the per-test `django.db` restore the snapshot must be taken **after** these logins, or simply don't restore `django.db`. **Decide at implementation.** Recommended: don't restore `django.db`, and log in via storage_state.

Keep one explicit UI-login test per identity, so the login forms themselves stay covered.

---

## 8. Page inventory (what "each page" means)

### 8.1 Enumerate programmatically + assert completeness

Don't hand-maintain the list blindly. Build it from `pychronia_game.urls.inner_game_urlpatterns`:
- `callback.klass` → `NAME`, `ACCESS`, `REQUIRES_CHARACTER_PERMISSION` for GameViews (see `test_game.py:4616-4627`);
- plain function views (`login`, `logout`, `bug_report_treatment`, `serve_game_file`…) are handled explicitly.

Then classify each URL into one of:

| Category | Examples | Treatment |
|---|---|---|
| plain GET page | homepage, view_encyclopedia, view_sales, view_characters, profile, friendships, messages/compose, messages/conversations, chatroom, auction_items, personal_items, personal_folder, world_map_*, public_webradio, personal_webradio_*, enigma_runes_*, ability/* , admin pages… | visited by both identities |
| parametrized | `encrypted_folders/guy2_report/`, `encyclopedia/lokon/`, `pages/<id>/`, `manual/help-homepage/`, `item3dview/sacred_chest/`, `messages/view_single_message/<obfuscated id>/` (+`?popup=1`), `secret_question/guy3/`, `clues/` with code `kxz`, `view_media/?url=...` | sample values from the default fixture, plus objects created by the baseline tweaks (e.g. ids of the posted messages, looked up via the datamanager) |
| ajax / non-HTML | `ajax_*`, `messages/ajax_*`, `webradio_xml_conf`, `ajax_chat` | not navigated; exercised indirectly by the pages that call them (assert no failed XHR, see §9) |
| dangerous / special | `TEST_CAPTCHA`, `CHARACTERS_IDENTITIES`, `DATABASE_OPERATIONS`, `FAIL_TEST`, `MEDIA_TEST`, `logout` | same exclusion list as `test_game.py:4510-4513`. `logout` gets a dedicated test. `FAIL_TEST` gets a dedicated "500 page renders" test only if useful |

A meta-test `test_inventory_is_complete` fails if a URL pattern in `inner_game_urlpatterns` is neither in a category nor explicitly excluded, so new pages can't silently escape coverage.

Also covered: `/<GAME_ID>/` (redirect to homepage), `/robots.txt`, and the bare root `/` (plain-text refusal).

### 8.2 Expected outcome matrix per (page, identity, state)

Computed from view metadata plus the datamanager, not hard-coded:
- `ACCESS=master` + player → redirected to the homepage, with an error notification;
- `ACCESS=character` + superuser→master → redirect (authentication required); hence the superuser→player pass;
- activable view not activated + no permission → redirect for the player;
- otherwise → **200 and rendered**.

---

## 9. What each page test asserts

For every visited page:
1. Final HTTP status of the main document is 200, or the expected redirect target matches.
2. No Django error page (`#summary h1` / "Traceback"/"Exception Value").
3. The page title / main content container is present (e.g. the menu and the page's `TITLE`), and the user indicator shows the right identity (player name / impersonated master).
4. **No uncaught JS errors**: collect `page.on("pageerror")`. Console errors are collected too and allowlisted where known (e.g. legacy Flash/jPlayer noise).
5. **No failed same-origin sub-requests** (`page.on("requestfailed")`, `response.status >= 400` for `/static/`, `/files/`, ajax). This also catches broken game-file hash URLs and missing static files, which is valuable after the Django/py3 migration.
6. Optionally `expect(page).to_have_screenshot()` is **off** by default (rendering is too brittle); screenshots are attached on failure only (`--screenshot=only-on-failure`, a pytest-playwright option).

A handful of **interaction tests** (still per identity where relevant), kept minimal:
- compose and send a message, then see it in conversations;
- unlock the encrypted folder with password `evans`;
- superuser: toggle game pause from the admin dashboard, and see the read-only notice as the player;
- logout;
- friendship proposal (needs two players).

---

## 10. `administration/` tests

The meta-admin pages are outside the game URL space and gated by `superuser_required` (Django `is_superuser`).

| Test | Identity | Expectation |
|---|---|---|
| `administration/` | anonymous | redirected to `/admin/login/?next=/administration/` |
| `administration/` | game player (logged into the game only) | same redirect (not a Django superuser) |
| `administration/` | superuser | lists both game instances with their statuses and links |
| create instance (form on `administration/`) | superuser | new instance appears in the list (restored by the next test's ZODB copy) |
| lock / unlock maintenance | superuser | locked instance's game pages return **503** (`middlewares.py:41-45`); unlock restores 200 |
| `administration/edit/<id>/` | superuser | only usable while locked; textarea with YAML/DB dump renders |
| change status, backup, compute enforced-login ticket | superuser | success message. The ticket URL (`?session_ticket=`) logs a browser in as that user (`GAME_ALLOW_ENFORCED_LOGIN=True`) |
| delete instance | superuser | **only on the secondary instance** |
| `administration/create/` | anonymous | form renders. Submit puts the activation mail into `django.core.mail.outbox` (locmem; reachable because the server is in-process) |
| `administration/activate/?token=` | anonymous | uses the token from the captured mail (or `compute_game_activation_token`), and the instance gets created / logged in as master; a bad token gives 403 |

Plus a smoke visit of Django's own `/admin/` index as superuser.

---

## 11. Headless / headed + slow-mo

pytest-playwright already provides `--headed`, `--slowmo <ms>`, `--browser`, `--video`, `--tracing`, `--screenshot`. The suite relies on them. Default = headless, chromium.

Convenience on top:
- a custom flag `--e2e-debug` ⇒ implies `--headed --slowmo 500`. Implement it in `pytest_configure` by setting `config.option.headed=True` and `config.option.slowmo=...` if not given explicitly;
- env var equivalents (`PYCHRONIA_E2E_HEADED=1`, `PYCHRONIA_E2E_SLOWMO=500`) for IDE run configs;
- headed runs must not be parallelized.

Examples:

```bash
uv run pytest pychronia_game/tests/e2e                                  # headless, default config
uv run pytest pychronia_game/tests/e2e --headed --slowmo 400 -k profile # watch a few tests
uv run pytest pychronia_game/tests/e2e --e2e-full-matrix                # every page × every config variant
uv run pytest pychronia_game/tests/e2e --tracing=retain-on-failure      # then: playwright show-trace
```

Parallelism (`pytest-xdist`) is **out of scope** for v1. The in-process server plus a single active ZODB file is per-process, so it would need one work dir and server per worker. That's doable later, since the work dir is already per-process.

---

## 12. File layout

```
pychronia_game/tests/e2e/
    __init__.py
    README.md                 # how to install browsers, run, debug, add a page
    conftest.py               # options, env/bootstrap, session init, live server, ZODB restore, identities, error collectors
    e2e_settings.py           # §3
    _server.py                # LiveServerThread wrapper + in-flight request counter + StaticFilesHandler
    _zodb_snapshot.py         # close/reset ZODB_INSTANCE, copy pristine<->active
    _inventory.py             # URL enumeration, categories, sample params, expected-access computation
    _pages.py                 # small helpers: login_as_player/superuser, impersonate(), assert_page_ok()
    test_00_infra.py          # server up, ZODB restore really isolates tests (write in test A, absent in test B), inventory completeness
    test_pages_player.py      # parametrized over inventory × game-state configs
    test_pages_superuser.py   # same, superuser→master and superuser→player impersonation
    test_permissions.py       # boosted vs non-boosted player, deactivated views
    test_administration.py    # §10
    test_interactions.py      # §9 short scenarios
    _configs.py               # apply_baseline_tweaks(dm) + apply_config(dm, config_id) — all runtime fixture tweaks (§5)
```

Artifacts (traces/videos/screenshots) go to `test-results/`, which is gitignored. The work dir lives under the pytest tmp dir.

---

## 13. Implementation order

1. Worktree + deps + `pyproject` exclusion; verify `pytest` (default) still collects only the unit tests and `pytest pychronia_game/tests/e2e` collects the e2e ones.
2. `e2e_settings.py` + conftest bootstrap + session ZODB init + snapshot. `test_00_infra`: one page loads.
3. ZODB per-test restore + isolation test (Windows file-lock behaviour is the main risk, so validate early).
4. Player/superuser login helpers + storage_state reuse.
5. Inventory + expected-access computation + completeness meta-test.
6. Player and superuser page tests in the `baseline` config. Fix or triage the real bugs found. They're likely after the py3/Django-4 migration; record them as `xfail(strict=True, reason=...)` with an issue note rather than masking them.
7. Runtime config variants (`paused`, `no_activated_views`, `encyclopedia_index_hidden`) + permission tests.
8. `administration/` tests (including the maintenance variant).
9. README; optional interaction tests.

---

## 14. Risks / open points

- **Windows file locks on `gamedata.fs`.** Mitigated by in-process server and explicit `ZODB_INSTANCE.close()`. Must also wait for in-flight requests (polling JS like chatroom/webradio). If needed, block those endpoints per test via `page.route` or navigate to `about:blank` before teardown.
- **`reset_zodb_structure()` requires `DEBUG` + `ZODB_RESET_ALLOWED`.** Both are set in e2e settings.
- **The Django ORM under Playwright's sync loop** needs `DJANGO_ALLOW_ASYNC_UNSAFE`.
- **AIML bots** (`ACTIVATE_AIML_BOTS=True` in test settings) may slow session init. Measure; disable for e2e if heavy, except for an `artificial_intelligence` page test.
- **Legacy media players** (Flash-era jPlayer/3D viewer/webradio) may log console errors. Use an allowlist rather than failing.
- **Runtime tweaks must stay coherent.** The datamanager runs coherence checks on commit, so a tweak that leaves inconsistent data (e.g. a message to an unknown email) fails the session init early. That's a feature, but keep the tweaks to public datamanager APIs only.
- **Run time**: estimate ~150 page loads per identity per state. Keep the default run bounded (§5.2) and put the full matrix behind a flag.
