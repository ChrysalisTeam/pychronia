# -*- coding: utf-8 -*-
"""
Visits every page of the portal (see _inventory.py) as a plain game player, in both
directions: the boosted player (guy1, every permission + every view activated) should
reach everything his ACCESS tier allows, and the plain player (guy2, no extra permission)
should be redirected away from anything gated.

The bulk reachability check uses `page.context.request.get(..., max_redirects=0)`
(Playwright's APIRequestContext, which shares cookies with the logged-in browser context)
rather than a real `page.goto()`, so that ~60 pages x 2 identities stays fast: we only care
about the HTTP status/redirect here. A much smaller set of representative pages is also
driven through a real `page.goto()` + `_pages.assert_page_ok()` to catch rendering-level
regressions (Django error pages, broken templates) that a bare status code wouldn't catch.
"""

import pytest

from pychronia_game.tests.e2e import _configs, _inventory, _pages

GAME_ID = _configs.GAME_ID
BOOSTED_PLAYER = _configs.BOOSTED_PLAYER
PLAIN_PLAYER = _configs.PLAIN_PLAYER

# Per-page caveats NOT modeled by _inventory.compute_access_result (see its docstring):
# item_3d_view 404s for a non-owner regardless of ACCESS rules, and view_hidden_clue
# always 200s on a bare GET regardless of identity.
ITEM_3D_VIEW_ENTRY_ID = "item_3d_view__item"
ALWAYS_AVAILABLE_ENTRY_IDS = frozenset(["view_hidden_clue"])

NAVIGABLE_ENTRIES = [
    entry for entry in list(_inventory.iter_inventory_entries(_inventory.CATEGORY_PLAIN_GET))
    + list(_inventory.iter_inventory_entries(_inventory.CATEGORY_PARAMETRIZED))
    if entry.entry_id != "view_single_message__msg_id"  # covered separately, needs a live dm for its sample
]
NAVIGABLE_ENTRY_IDS = [entry.entry_id for entry in NAVIGABLE_ENTRIES]

# A handful of representative pages driven through a real browser navigation, for a
# rendering-level sanity check (menu/title present, no Django error page).
REPRESENTATIVE_ENTRY_IDS = frozenset([
    "homepage", "characters_view", "view_sales", "personal_items_slideshow",
    "character_profile", "friendship_management", "standard_conversations",
    "view_encyclopedia", "view_encyclopedia__current_article_id", "chatroom",
])


def _url_for(base_url, username, sample):
    return "%s/%s/%s/%s" % (base_url, GAME_ID, username, sample.path)


@pytest.mark.parametrize("entry", NAVIGABLE_ENTRIES, ids=NAVIGABLE_ENTRY_IDS)
def test_boosted_player_reaches_every_allowed_page(entry, player_page, base_url, game):
    """guy1 has every permission and every view activated, so he should reach everything
    his ACCESS tier allows (anonymous/authenticated/character), and get redirected away
    only from ACCESS=master pages."""
    expected_available = _inventory.expect_available(entry, BOOSTED_PLAYER, game)
    if entry.entry_id == ITEM_3D_VIEW_ENTRY_ID:
        expected_available = True  # guy1 owns "sacred_chest", per apply_baseline_tweaks
    if entry.entry_id in ALWAYS_AVAILABLE_ENTRY_IDS:
        expected_available = True

    for sample in entry.sample_paths(game):
        url = _url_for(base_url, BOOSTED_PLAYER, sample)
        response = player_page.context.request.get(url, max_redirects=0)
        if expected_available:
            assert response.status == 200, (entry.entry_id, url, response.status)
        else:
            assert response.status in (301, 302), (entry.entry_id, url, response.status)


@pytest.mark.parametrize("entry", NAVIGABLE_ENTRIES, ids=NAVIGABLE_ENTRY_IDS)
def test_plain_player_gated_pages_redirect(entry, page, base_url, game):
    """guy2 has no extra permission, so he should only reach the subset of pages that
    need no activation/permission at all."""
    if entry.entry_id == ITEM_3D_VIEW_ENTRY_ID:
        pytest.skip("item_3d_view ownership is checked separately below (404, not a redirect)")
    if entry.entry_id in ALWAYS_AVAILABLE_ENTRY_IDS:
        pytest.skip("always available regardless of identity, nothing to check here")

    _pages.login_as_player(page, base_url, GAME_ID, PLAIN_PLAYER, _configs.PLAYER_CREDENTIALS[PLAIN_PLAYER])
    expected_available = _inventory.expect_available(entry, PLAIN_PLAYER, game)

    for sample in entry.sample_paths(game):
        url = _url_for(base_url, PLAIN_PLAYER, sample)
        response = page.context.request.get(url, max_redirects=0)
        if expected_available:
            assert response.status == 200, (entry.entry_id, url, response.status)
        else:
            assert response.status in (301, 302), (entry.entry_id, url, response.status)


def test_item_3d_view_404s_for_non_owner(page, base_url):
    _pages.login_as_player(page, base_url, GAME_ID, PLAIN_PLAYER, _configs.PLAYER_CREDENTIALS[PLAIN_PLAYER])
    url = "%s/%s/%s/item3dview/sacred_chest/" % (base_url, GAME_ID, PLAIN_PLAYER)
    response = page.context.request.get(url, max_redirects=0)
    assert response.status == 404, response.status


def test_item_3d_view_200s_for_owner(player_page, base_url):
    url = "%s/%s/%s/item3dview/sacred_chest/" % (base_url, GAME_ID, BOOSTED_PLAYER)
    response = player_page.context.request.get(url, max_redirects=0)
    assert response.status == 200, response.status


@pytest.mark.parametrize("entry_id", sorted(REPRESENTATIVE_ENTRY_IDS))
def test_representative_pages_render_cleanly(entry_id, player_page, base_url, game):
    entry = _inventory.get_entry(entry_id)
    for sample in entry.sample_paths(game):
        url = _url_for(base_url, BOOSTED_PLAYER, sample)
        response = player_page.goto(url)
        _pages.assert_page_ok(player_page, response)


def test_anonymous_pages_smoke(page, base_url):
    """A handful of ACCESS=anonymous pages, visited by a never-logged-in visitor."""
    for entry_id in ("login", "runic_translation_open"):
        try:
            entry = _inventory.get_entry(entry_id)
        except KeyError:
            continue
        for sample in entry.sample_paths():
            url = "%s/%s/guest/%s" % (base_url, GAME_ID, sample.path)
            response = page.goto(url)
            _pages.assert_page_ok(page, response)
