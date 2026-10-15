# -*- coding: utf-8 -*-
"""
Permission-gating tests (design doc E2E_TESTS_PLAN.md, section 6, plus the
"no_activated_views" / permission rows of section 5.2's table).

Facts below were verified against the real code (not just copied from the plan,
which was a draft and got some view/permission names wrong):

- The permission name for a view with ``REQUIRES_CHARACTER_PERMISSION = True`` is
  always ``"access_" + NAME`` (see
  ``AbstractGameView.get_access_permission_name()`` in
  ``pychronia_game/datamanager/abstract_game_view.py``). This is registered
  automatically into ``dm.PERMISSIONS_REGISTRY`` for every such view.
- ``AbstractGameView.get_access_token()``: if ``user.is_master``, the view is
  immediately ``available`` -- EXCEPT for ``ACCESS=character`` views, where the
  ``(cls.ACCESS == UserAccess.character and not user.is_character)`` check runs
  *before* the master short-circuit, so master itself (not impersonating a
  character) always gets ``authentication_required`` there. For
  ``ACCESS=authenticated`` (and ``ACCESS=master``) views, master bypasses
  activation/permission checks entirely, deactivated or not.
- For a non-master character with the view's ``access_<NAME>`` permission, the
  view is ``available`` REGARDLESS of whether it is globally "activated" --
  permission overrides/bypasses the activation gate (same method, see the
  ``REQUIRES_CHARACTER_PERMISSION`` branch: permission granted returns
  ``available`` directly, without consulting ``view_is_globally_available``).
- The URL ``ability/wiretapping_management/`` is backed by ``WiretappingAbility``
  (``pychronia_game/views/abilities/wiretapping_management_mod.py``), whose real
  ``NAME`` is ``"wiretapping"`` (not ``"wiretapping_management"``) and whose
  ``TITLE`` is ``"Wiretapping"``. So its permission is ``access_wiretapping``.
  (There IS a function literally named ``wiretapping_management`` with a
  ``@register_view(...)(permission="manage_wiretaps")`` decorator in
  ``pychronia_game/views/__init__.py``, but it lives inside a huge
  ``''' ---------- DEPRECATED STUFFS --------- '''`` triple-quoted string
  (lines 165-591), i.e. it's dead code that is never actually imported/executed;
  the real view bound to that URL is the one imported from ``.abilities``.)
- ``chess_challenge`` and ``geoip_location`` are ``ACCESS=authenticated`` (not
  ``character``) with ``REQUIRES_CHARACTER_PERMISSION=True`` too, so their
  permissions are plainly ``access_chess_challenge`` / ``access_geoip_location``.
  The plan's doubt about "purchase_confidentiality_protection" and
  "view_others_belongings" turned out unfounded: both exist for real, registered
  via each view's ``EXTRA_PERMISSIONS`` class attribute
  (``wiretapping_management_mod.py`` / ``auction_views.py``), but they gate
  specific *actions* inside those views, not the view's own access.
- Access denial (``AccessDeniedError``, caught in ``transform_usage_error()`` in
  ``abstract_game_view.py``) redirects a real (non-anonymous) user back to
  ``/<game_id>/<username>/`` with a ``django.contrib.messages`` error
  "Access denied to page <TITLE>", rendered inside a
  ``<div class="notification_panel error">`` (see
  ``pychronia_common/templates/metalradiance_base.html``). When the user is
  impersonated (superuser impersonating master), the message is instead a
  *warning* "Currently impersonated user can't access view '<TITLE>'".
- A disabled player (``password=None`` in the fixture) fails
  ``authenticate_with_credentials`` with ``NormalUsageError("Wrong password")``
  (see ``datamanager_modules.py:authenticate_with_credentials``); the login view
  catches that inside ``action_failure_handler`` and just re-renders the login
  page with the error -- there is no redirect to a homepage.

All of the above was additionally double-checked empirically against the live
dev server (dumped HTML) while writing this file.
"""

import pytest

from pychronia_game.tests.e2e import _configs, _pages

pytestmark = pytest.mark.usefixtures("fresh_zodb")

GAME_ID = _configs.GAME_ID

# Representative sample of REQUIRES_CHARACTER_PERMISSION=True views: a mix of
# ACCESS=character and ACCESS=authenticated views (name, url_path, title_fragment).
PERMISSION_GATED_VIEWS = [
    ("house_locking", "ability/house_locking/", "Manor Security"),
    ("chess_challenge", "ability/chess_challenge/", "Chess Challenge"),
    ("geoip_location", "ability/geoip_location/", "Web Geolocation"),
    ("wiretapping_management", "ability/wiretapping_management/", "Wiretapping"),
]

# A view gated only by global activation (REQUIRES_GLOBAL_PERMISSION=True) but NOT
# behind any per-character permission (REQUIRES_CHARACTER_PERMISSION=False), used to
# exercise the plain "view not activated" redirect as opposed to "no permission".
ACTIVABLE_ONLY_VIEW_PATH = "ability/black_market/"


def _homepage_url(base_url, username):
    return "%s/%s/%s/" % (base_url, GAME_ID, username)


@pytest.mark.parametrize("name,url_path,title_fragment", PERMISSION_GATED_VIEWS)
def test_boosted_player_reaches_permission_gated_view(player_page, base_url, name, url_path, title_fragment):
    """guy1 (BOOSTED_PLAYER) was granted every permission in PERMISSIONS_REGISTRY
    (see _configs.apply_baseline_tweaks), so it must reach every permission-gated
    view with a plain 200."""
    response = player_page.goto("%s/%s/%s/%s" % (base_url, GAME_ID, _configs.BOOSTED_PLAYER, url_path))
    _pages.assert_page_ok(player_page, response)
    assert title_fragment in player_page.content()


@pytest.mark.parametrize("name,url_path,title_fragment", PERMISSION_GATED_VIEWS)
def test_plain_player_denied_permission_gated_view(page, base_url, name, url_path, title_fragment):
    """guy2 (PLAIN_PLAYER) has no extra permission, so it gets bounced back to its
    homepage with an "Access denied" error notification; the gated page itself is
    never rendered."""
    _pages.login_as_player(page, base_url, GAME_ID, _configs.PLAIN_PLAYER,
                           _configs.PLAYER_CREDENTIALS[_configs.PLAIN_PLAYER])
    page.goto("%s/%s/%s/%s" % (base_url, GAME_ID, _configs.PLAIN_PLAYER, url_path))
    assert page.url == _homepage_url(base_url, _configs.PLAIN_PLAYER)
    assert "notification_panel" in page.content()
    assert "Access denied" in page.content()


def test_no_activated_views_permission_bypasses_activation_for_boosted_player(game, player_page, base_url):
    """With activated_views reset to the raw (empty) YAML state, guy1 still reaches
    a permission-gated view, because the access_<NAME> permission bypasses the
    activation gate entirely (see module docstring)."""
    _configs.apply_config(game, "no_activated_views")
    _, url_path, title_fragment = PERMISSION_GATED_VIEWS[0]  # house_locking
    response = player_page.goto("%s/%s/%s/%s" % (base_url, GAME_ID, _configs.BOOSTED_PLAYER, url_path))
    _pages.assert_page_ok(player_page, response)
    assert title_fragment in player_page.content()


def test_no_activated_views_still_blocks_plain_player(game, page, base_url):
    """With activated_views reset to empty, an ordinary activable view (no
    per-character permission involved) now redirects guy2 home with an error,
    since the view is no longer globally available to them."""
    _configs.apply_config(game, "no_activated_views")
    _pages.login_as_player(page, base_url, GAME_ID, _configs.PLAIN_PLAYER,
                           _configs.PLAYER_CREDENTIALS[_configs.PLAIN_PLAYER])
    page.goto("%s/%s/%s/%s" % (base_url, GAME_ID, _configs.PLAIN_PLAYER, ACTIVABLE_ONLY_VIEW_PATH))
    assert page.url == _homepage_url(base_url, _configs.PLAIN_PLAYER)
    assert "notification_panel" in page.content()
    assert "Access denied" in page.content()


def test_no_activated_views_master_unaffected(game, superuser_page, base_url):
    """Master bypasses the global activation gate entirely for ACCESS=authenticated
    views (the `if user.is_master: return available` short-circuit runs before the
    activation check), so even with no views activated, master reaches
    chess_challenge directly (no character impersonation needed)."""
    _configs.apply_config(game, "no_activated_views")
    _, url_path, title_fragment = PERMISSION_GATED_VIEWS[1]  # chess_challenge
    response = _pages.goto_as(superuser_page, base_url, GAME_ID, _configs.MASTER_LOGIN, url_path)
    _pages.assert_page_ok(superuser_page, response)
    assert title_fragment in superuser_page.content()


def test_master_alone_cannot_reach_character_only_view(superuser_page, base_url):
    """Unlike ACCESS=authenticated views, ACCESS=character views reject master
    itself with `authentication_required` (master is not "a character"); master
    must impersonate a character instead (see test_00_infra.py's
    test_superuser_impersonates_player_via_url). This is a real, somewhat
    surprising asymmetry in get_access_token(), worth locking down explicitly."""
    response = _pages.goto_as(superuser_page, base_url, GAME_ID, _configs.MASTER_LOGIN, "ability/house_locking/")
    assert response.status == 200  # redirected-then-rendered home page
    assert "can't access view" in superuser_page.content()


def test_disabled_player_login_fails(page, base_url):
    """guy4 (DISABLED_PLAYER) has password=None in the fixture, so any password
    attempt fails with "Wrong password"; the login view just re-renders the login
    form with that error -- it must NOT redirect to guy4's homepage."""
    page.goto("%s/%s/guest/login/" % (base_url, GAME_ID))
    page.fill("#id_secret_username", _configs.DISABLED_PLAYER)
    page.fill("#id_secret_password", "whatever")
    page.click("#login")
    page.wait_for_load_state("networkidle")
    assert "guest/login" in page.url
    assert ("/%s/%s/" % (GAME_ID, _configs.DISABLED_PLAYER)) not in page.url
    assert "Wrong password" in page.content()


def test_disabled_player_login_fails_with_blank_password(page, base_url):
    """Same as above, but leaving the password field blank (also falsy, so also
    rejected), to make sure there's no accidental "empty password accepted" path."""
    page.goto("%s/%s/guest/login/" % (base_url, GAME_ID))
    page.fill("#id_secret_username", _configs.DISABLED_PLAYER)
    page.click("#login")
    page.wait_for_load_state("networkidle")
    assert "guest/login" in page.url
    assert ("/%s/%s/" % (GAME_ID, _configs.DISABLED_PLAYER)) not in page.url
