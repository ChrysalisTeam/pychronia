# -*- coding: utf-8 -*-
"""
Inventory of every URL exposed by ``pychronia_game.urls.inner_game_urlpatterns``.

This module is the single source of truth that other e2e test files parametrize over
("every page of the portal"). It is built once, at import time, directly from the live
URL patterns and their backing ``AbstractGameView`` subclasses (see
``pychronia_game/datamanager/abstract_game_view.py``), so it automatically stays in sync
as pages are added/removed/renamed. ``test_01_inventory.py`` asserts that every single URL
pattern ends up classified into exactly one category below (see ``CATEGORIES``) -- nothing
can silently fall through the cracks.

-----------------------------------------------------------------------------------------
How URL patterns map to GameViews
-----------------------------------------------------------------------------------------
Every entry in ``inner_game_urlpatterns`` -- whether declared as a plain function (eg.
``'homepage'``) or a class (eg. ``CharactersView.as_view``) -- resolves to a
``ClassInstantiationProxy`` whose ``.klass`` attribute is the actual ``AbstractGameView``
subclass (see ``register_view()`` in abstract_game_view.py: even plain functions get
wrapped into an on-the-fly GameView subclass). So for every URL pattern we can read
``callback.klass.NAME`` / ``.ACCESS`` / ``.REQUIRES_CHARACTER_PERMISSION`` /
``.REQUIRES_GLOBAL_PERMISSION`` / ``.EXTRA_PERMISSIONS`` uniformly. There is no
"plain Django view" left uncovered inside ``inner_game_urlpatterns``: all 76 patterns
(as of this writing) are GameView-backed.

-----------------------------------------------------------------------------------------
Categories
-----------------------------------------------------------------------------------------
- ``CATEGORY_PLAIN_GET``: no URL params; a bare GET should return 200 (or a well-defined
  redirect per access rules) for any identity that's allowed in.
- ``CATEGORY_PARAMETRIZED``: needs a sample path segment (or, for ``view_hidden_clue``,
  POST data) to be meaningful. ``entry.sample_paths(dm)`` computes real, currently-valid
  sample value(s) -- hardcoded when they come from the static YAML fixture, or looked up
  live via the ``dm``/``game`` fixture when they come from the runtime baseline tweaks
  (``_configs.apply_baseline_tweaks``), e.g. message ids.
- ``CATEGORY_AJAX_OR_NON_HTML``: views whose NAME contains "ajax", plus the
  ``webradio_xml_conf`` XML endpoint (NAME ``get_radio_xml_conf``). Not meant to be
  navigated directly as a "page"; exercised indirectly by the pages that call them.
- ``CATEGORY_EXCLUDED``: genuinely dangerous/special views that must never be blindly
  visited: ``test_captcha``, ``CHARACTERS_IDENTITIES``, ``DATABASE_OPERATIONS``,
  ``FAIL_TEST``, ``MEDIA_TEST``, and ``logout`` (gets its own dedicated test elsewhere).

-----------------------------------------------------------------------------------------
Access-control semantics (important for test_pages_player.py / test_pages_superuser.py)
-----------------------------------------------------------------------------------------
``AbstractGameView.get_access_token()`` (abstract_game_view.py ~L287-L315) is the ONE
place that decides availability. ``compute_access_result()`` below is a faithful,
side-effect-free reimplementation of that exact logic (it does NOT mutate ``dm.user`` --
it only resolves access for an arbitrary ``username`` against the live datamanager via its
read-only ``is_master``/``is_character``/``is_authenticated``/``has_permission``/
``is_game_view_activated`` methods, all of which accept an explicit username). This mirrors
section 8.2 of the plan:

- ``ACCESS=master`` views: any non-master identity gets ``authentication_required``
  (redirected to the homepage with an error notification, since the player/impersonated
  user IS authenticated already -- only a truly anonymous never-logged-in visitor would be
  bounced to the login page instead; see ``transform_usage_error`` in
  abstract_game_view.py ~L32-62 for that distinction, which lives one layer above
  ``get_access_token`` and is NOT reproduced here).
- ``ACCESS=character`` views + an identity impersonating "master": ``user.is_character``
  is False for "master" (master is never in ``get_character_usernames()``), so this
  ALSO returns ``authentication_required`` and redirects -- **confirmed in code**: a
  superuser impersonating master cannot reach character-only pages. To reach them, the
  superuser must impersonate an actual character (eg. the boosted player ``guy1``), i.e.
  the "superuser->player" pass mentioned in the plan. Master himself (the real game
  master, or superuser-as-master) is NOT a character and gets the same redirect.
- Global activation (``REQUIRES_GLOBAL_PERMISSION`` / ``entry.requires_activation``) and
  per-character permission (``REQUIRES_CHARACTER_PERMISSION`` / ``entry.requires_permission``,
  gated by the ``"access_" + NAME`` permission) are evaluated exactly as in
  ``get_access_token``: a character permission, if granted, overrides a globally
  deactivated view; otherwise deactivation blocks everyone except master.
- ``user.is_master`` short-circuits everything else to ``available`` -- the real game
  master (and a superuser impersonating "master") bypasses activation/permission checks,
  but NOT the ACCESS-tier check above (master still can't open character-only pages).

-----------------------------------------------------------------------------------------
Known per-page caveats for downstream test authors (not modeled by compute_access_result)
-----------------------------------------------------------------------------------------
- ``item_3d_view`` (``item3dview/<item>/``): independently of ``get_access_token``
  (ACCESS=authenticated, no permission gate), the view 404s if the *current* user doesn't
  own the item (``get_available_items_for_user()``). The sample item ``sacred_chest`` is
  owned only by BOOSTED_PLAYER (``guy1``); master/superuser-as-master see all items (200);
  PLAIN_PLAYER (``guy2``) will get a 404, not a redirect. See ``entry.notes``.
- ``view_hidden_clue`` (``clues/``): has no URL capture group at all; a bare GET always
  200s with an empty form regardless of identity. The "sample" is POST data
  (``clue_category``/``clue_code``), only meaningful for an interaction-style test.
- ``bug_report_treatment`` (``bug_report/``) and ``secret_question/<username>/`` and a few
  others return a response without the normal page chrome (menu/title) even on success;
  don't assume every ``plain_get``/``parametrized`` 200 has full page structure.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Tuple

from pychronia_game.common import UserAccess, AccessResult
from pychronia_game.urls import inner_game_urlpatterns

from . import _configs

# --------------------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------------------

CATEGORY_PLAIN_GET = "plain_get"
CATEGORY_PARAMETRIZED = "parametrized"
CATEGORY_AJAX_OR_NON_HTML = "ajax_or_non_html"
CATEGORY_EXCLUDED = "excluded"

ALL_CATEGORIES = frozenset([
    CATEGORY_PLAIN_GET,
    CATEGORY_PARAMETRIZED,
    CATEGORY_AJAX_OR_NON_HTML,
    CATEGORY_EXCLUDED,
])

# Views that must never be blindly visited by generic page-inventory tests.
# NAME values as actually registered (see AbstractGameView.NAME), not the URL fragments.
EXCLUDED_NAMES = frozenset([
    "test_captcha",            # /TEST_CAPTCHA/
    "CHARACTERS_IDENTITIES",   # exports a CSV of real-life identities
    "DATABASE_OPERATIONS",     # can reset game data
    "FAIL_TEST",               # deliberately raises an IOError
    "MEDIA_TEST",              # not dangerous per se, but a pure media smoke-test, excluded for simplicity
    "logout",                  # gets its own dedicated test (must not be hit incidentally while enumerating pages)
])

# Non-ajax-named endpoints that are nonetheless not real HTML "pages" (binary/XML/etc).
EXTRA_NON_HTML_NAMES = frozenset([
    "get_radio_xml_conf",   # webradio_xml_conf/ -- serves information/web_radio_conf.xml
])

# Entries with no URL capture group that must nonetheless be treated as "parametrized"
# (they need extra data -- query string / POST body -- to be meaningfully exercised).
FORCED_PARAMETRIZED_ENTRY_IDS = frozenset([
    "view_hidden_clue",   # clues/ -- POST clue_category/clue_code to see real content
])


# --------------------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------------------

class SamplePath:
    """A concrete, currently-valid way to exercise a (possibly parametrized) view.

    ``path`` is relative, with no leading slash, meant to be appended after
    ``{base_url}/{game_id}/{username}/`` (see ``_pages.goto_as``).
    ``method``/``data`` let a caller optionally exercise the POST branch of a view
    (eg. ``view_hidden_clue``); plain page-visit tests will normally just GET ``path``.
    """

    __slots__ = ("path", "method", "data", "description")

    def __init__(self, path, method="GET", data=None, description=""):
        self.path = path
        self.method = method
        self.data = data
        self.description = description

    def __repr__(self):
        return "SamplePath(%r, method=%r, data=%r)" % (self.path, self.method, self.data)


@dataclass(frozen=True)
class InventoryEntry:
    name: str                      # GameView NAME (may repeat across URL patterns, eg. view_encyclopedia)
    entry_id: str                  # unique identifier for THIS url pattern (name, possibly suffixed by its params)
    pattern: str                   # raw regex pattern string, straight from inner_game_urlpatterns
    url_params: Tuple[str, ...]    # named capture groups in the URL pattern, eg. ("current_article_id",)
    view_class: type               # the AbstractGameView subclass (callback.klass)
    access: str                    # UserAccess.{anonymous,authenticated,character,master}
    requires_permission: bool      # REQUIRES_CHARACTER_PERMISSION -- gated by access_permission_name
    requires_activation: bool      # REQUIRES_GLOBAL_PERMISSION -- must be in dm's activated_views, unless requires_permission overrides it
    access_permission_name: Optional[str]   # "access_<name>" iff requires_permission, else None
    extra_permissions: Tuple[str, ...]      # EXTRA_PERMISSIONS -- feature-specific, do NOT gate view access itself
    category: str
    sample_paths: Callable[[Optional[object]], list]   # fn(dm=None) -> list[SamplePath]; dm needed only for dynamic samples
    notes: str = ""

    def __str__(self):
        return "InventoryEntry(%s)" % self.entry_id


# --------------------------------------------------------------------------------------
# Sample value providers
# --------------------------------------------------------------------------------------
# Values below were checked against the actual default test fixture
# (pychronia_game/tests/test_game_files/game_initial_data.yaml and the files tree
# alongside it), NOT against ../Chrysalis or any other fixture. See the final report
# for the couple of plan-doc examples that turned out to already be correct, and which
# ones were double checked.

def _static_sample(path, **kwargs):
    return lambda dm=None: [SamplePath(path=path, **kwargs)]


def _sample_message_id(dm):
    """Looks up, live, the id of the "Hello" message created by apply_baseline_tweaks()
    (guy2 -> guy1, then archived for guy1). Requires the `game`/`dm` fixture (post-restore,
    post-baseline-tweaks ZODB)."""
    for msg in dm.get_all_dispatched_messages():
        if msg["subject"] == "Hello":
            return msg["id"]
    raise LookupError(
        "Baseline 'Hello' message (guy2 -> guy1) not found; "
        "check _configs.apply_baseline_tweaks() is still posting it under that subject.")


def _view_single_message_samples(dm):
    if dm is None:
        return []
    msg_id = _sample_message_id(dm)
    return [
        SamplePath(path="messages/view_single_message/%s/" % msg_id),
        SamplePath(path="messages/view_single_message/%s/?popup=1" % msg_id, description="popup rendering"),
    ]


# Keyed by entry_id (unique per URL pattern, see _build_entry_id below: name alone if the
# pattern has no URL params, else "name__param1_param2").
SAMPLE_PROVIDERS = {
    "encrypted_folder__folder": _static_sample(
        "encrypted_folders/guy2_report/",
        description="real encrypted folder from the default fixture; "
                     "POST simple_password='evans' to decrypt (see test_interactions.py)"),

    "item_3d_view__item": _static_sample(
        "item3dview/sacred_chest/",
        description="owned by BOOSTED_PLAYER (guy1) only, per apply_baseline_tweaks(); "
                     "has item_3d_settings in the YAML fixture. PLAIN_PLAYER (guy2) gets a 404 here, "
                     "not a redirect -- see module docstring."),

    "view_static_page__page_id": _static_sample(
        "pages/top-homepage/",
        description="static page id from the default YAML fixture (categories: content)"),

    "view_hidden_clue": _static_sample(
        "clues/",
        description="GET always 200s with an empty form regardless of identity; "
                     "POST clue_category='magic'&clue_code='kxz' (some_clue1 in the fixture) to see real content"),

    # Only the detail URL pattern (encyclopedia/<current_article_id>/) is parametrized;
    # the bare encyclopedia/ index is plain_get and needs no sample.
    "view_encyclopedia__current_article_id": _static_sample(
        "encyclopedia/lokon/",
        description="encyclopedia article id from the default YAML fixture"),

    "view_help_page__keyword": _static_sample(
        "manual/help-homepage/",
        description='static help page "help-homepage", backing the always-anonymous-available "homepage" view'),

    "secret_question__concerned_username": _static_sample(
        "secret_question/%s/" % _configs.PLAYER_WITH_SECRET_QUESTION,
        description="guy3 is the only default character with a non-null secret_question/secret_answer; "
                     "any other username would redirect to the homepage with an error instead of 200"),

    "view_single_message__msg_id": _view_single_message_samples,
}


# --------------------------------------------------------------------------------------
# Building the inventory from the live URL patterns
# --------------------------------------------------------------------------------------

def _build_entry_id(name, url_params):
    if not url_params:
        return name
    return "%s__%s" % (name, "_".join(url_params))


def _classify(name, entry_id, url_params):
    if name in EXCLUDED_NAMES:
        return CATEGORY_EXCLUDED
    if "ajax" in name.lower() or name in EXTRA_NON_HTML_NAMES:
        return CATEGORY_AJAX_OR_NON_HTML
    if entry_id in FORCED_PARAMETRIZED_ENTRY_IDS or url_params:
        return CATEGORY_PARAMETRIZED
    return CATEGORY_PLAIN_GET


_LITERAL_PATTERN_RE = re.compile(r"^[A-Za-z0-9_/\-]*$")  # no regex metachars: safe to use as a literal URL


def _literal_path_from_pattern(pattern):
    assert pattern.startswith("^") and pattern.endswith("$"), pattern
    literal = pattern[1:-1]
    assert _LITERAL_PATTERN_RE.match(literal), (
        "Pattern %r has capture groups or regex metacharacters; "
        "it can't be used as a literal plain_get path" % pattern)
    return literal


def _build_inventory():
    entries = []
    seen_entry_ids = set()

    for url_pattern in inner_game_urlpatterns:
        callback = url_pattern.callback
        view_class = getattr(callback, "klass", None)
        assert view_class is not None, (
            "URL pattern %r has a callback with no .klass -- it isn't GameView-backed, "
            "_inventory.py needs updating to handle it explicitly" % (url_pattern,))

        pattern_str = str(url_pattern.pattern)
        url_params = tuple(sorted(
            url_pattern.pattern.regex.groupindex,
            key=lambda group_name: url_pattern.pattern.regex.groupindex[group_name],
        ))

        name = view_class.NAME
        entry_id = _build_entry_id(name, url_params)
        assert entry_id not in seen_entry_ids, "Duplicate entry_id %r -- inventory needs a better disambiguation key" % entry_id
        seen_entry_ids.add(entry_id)

        category = _classify(name, entry_id, url_params)

        requires_permission = bool(view_class.REQUIRES_CHARACTER_PERMISSION)
        access_permission_name = view_class.get_access_permission_name() if requires_permission else None

        if category == CATEGORY_PARAMETRIZED:
            sample_paths = SAMPLE_PROVIDERS.get(entry_id)
            assert sample_paths is not None, (
                "No SAMPLE_PROVIDERS entry for parametrized view %r (entry_id=%r); "
                "add one so pages tests can exercise it" % (name, entry_id))
        elif category == CATEGORY_PLAIN_GET:
            sample_paths = _static_sample(_literal_path_from_pattern(pattern_str))
        else:
            sample_paths = lambda dm=None: []  # ajax_or_non_html / excluded: not meant to be navigated directly

        entries.append(InventoryEntry(
            name=name,
            entry_id=entry_id,
            pattern=pattern_str,
            url_params=url_params,
            view_class=view_class,
            access=view_class.ACCESS,
            requires_permission=requires_permission,
            requires_activation=bool(view_class.REQUIRES_GLOBAL_PERMISSION),
            access_permission_name=access_permission_name,
            extra_permissions=tuple(view_class.EXTRA_PERMISSIONS or ()),
            category=category,
            sample_paths=sample_paths,
        ))

    assert set(entry.category for entry in entries) <= ALL_CATEGORIES
    return entries


_INVENTORY = _build_inventory()


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------

def iter_inventory_entries(category=None):
    """Yields every InventoryEntry, one per URL pattern in inner_game_urlpatterns.

    If *category* is given (one of the CATEGORY_* constants), only entries of that
    category are yielded.
    """
    for entry in _INVENTORY:
        if category is None or entry.category == category:
            yield entry


def get_entry(entry_id):
    for entry in _INVENTORY:
        if entry.entry_id == entry_id:
            return entry
    raise KeyError(entry_id)


def entries_by_category(category):
    assert category in ALL_CATEGORIES, category
    return [entry for entry in _INVENTORY if entry.category == category]


# --------------------------------------------------------------------------------------
# Expected-access computation (plan section 8.2)
# --------------------------------------------------------------------------------------

def compute_access_result(entry, username, dm):
    """Faithfully mirrors AbstractGameView.get_access_token() (abstract_game_view.py),
    WITHOUT mutating dm.user, for an arbitrary *username* (eg. "master", "guy1", "guy2",
    or dm.anonymous_login == "guest").

    Returns one of the pychronia_game.common.AccessResult values:
      - AccessResult.available: expect HTTP 200 (barring page-specific 404s, see notes).
      - AccessResult.authentication_required: wrong kind of user for this ACCESS tier
        (eg. a non-master hitting an ACCESS=master view, or master/non-character hitting
        an ACCESS=character view) -- expect a redirect (to homepage if already
        authenticated/impersonating, to the login page only for a truly anonymous,
        non-impersonated real visitor -- see transform_usage_error()).
      - AccessResult.permission_required: character is logged in and the view is globally
        activated, but they lack the per-character "access_<name>" permission -- redirect.
      - AccessResult.globally_forbidden: the view requires activation and isn't activated
        (and no character-permission override applies) -- redirect, even for master... wait,
        no: master always short-circuits to `available` before this is reached.
    """
    is_master = dm.is_master(username)
    is_character = dm.is_character(username)
    is_authenticated = dm.is_authenticated(username)

    if ((entry.access == UserAccess.master and not is_master) or
            (entry.access == UserAccess.authenticated and not is_authenticated) or
            (entry.access == UserAccess.character and not is_character)):
        return AccessResult.authentication_required

    if is_master:
        return AccessResult.available

    view_is_globally_available = True
    if entry.requires_activation:
        if not dm.is_game_view_activated(entry.name):
            view_is_globally_available = False

    if entry.requires_permission:
        if dm.has_permission(username=username, permission=entry.access_permission_name):
            return AccessResult.available
        elif view_is_globally_available:
            return AccessResult.permission_required

    if not view_is_globally_available:
        return AccessResult.globally_forbidden

    return AccessResult.available


def expect_available(entry, username, dm):
    """Convenience boolean wrapper around compute_access_result(): True iff a plain GET
    of *entry* by *username* is expected to render (HTTP 200), False if a redirect is
    expected instead (see compute_access_result's docstring for which redirect target)."""
    return compute_access_result(entry, username, dm) == AccessResult.available
