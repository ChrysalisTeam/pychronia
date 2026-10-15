# -*- coding: utf-8 -*-
"""
Visits every page of the portal (see _inventory.py) as a Django superuser, exercising the
URL-based impersonation mechanism (see _pages.goto_as): a GET to
`{base_url}/{game_id}/{username}/{path}` from a superuser session transparently impersonates
`username`, with no POST required.

Two passes are needed to cover every ACCESS tier, since (confirmed in
abstract_game_view.get_access_token) a user impersonating "master" is NOT a character, so
ACCESS=character views are unreachable that way even for a superuser:
  - impersonating "master" covers ACCESS=master/authenticated/anonymous pages;
  - impersonating the boosted player (guy1) covers ACCESS=character pages (and doubles as
    an end-to-end check of the impersonation mechanism itself, since guy1's own direct
    login is already covered by test_pages_player.py).
"""

import pytest

from pychronia_game.tests.e2e import _configs, _inventory, _pages

pytestmark = pytest.mark.usefixtures("fresh_zodb")

GAME_ID = _configs.GAME_ID
BOOSTED_PLAYER = _configs.BOOSTED_PLAYER
MASTER_LOGIN = _configs.MASTER_LOGIN

NAVIGABLE_ENTRIES = _inventory.NAVIGABLE_ENTRIES
NAVIGABLE_ENTRY_IDS = _inventory.NAVIGABLE_ENTRY_IDS


@pytest.mark.parametrize("entry", NAVIGABLE_ENTRIES, ids=NAVIGABLE_ENTRY_IDS)
def test_superuser_impersonating_master_reaches_allowed_pages(entry, superuser_page, base_url, game):
    expected_available = _inventory.expect_available_for_page_visit(
        entry, MASTER_LOGIN, game, owns_sample_item=True)  # master/superuser sees every item

    for sample in entry.sample_paths(game):
        url = _inventory.url_for(base_url, GAME_ID, MASTER_LOGIN, sample)
        response = superuser_page.context.request.get(url, max_redirects=0)
        if expected_available:
            assert response.status == 200, (entry.entry_id, url, response.status)
        else:
            assert response.status in (301, 302), (entry.entry_id, url, response.status)
            _pages.assert_redirects_to_own_homepage(response, GAME_ID, MASTER_LOGIN)


@pytest.mark.parametrize("entry", NAVIGABLE_ENTRIES, ids=NAVIGABLE_ENTRY_IDS)
def test_superuser_impersonating_boosted_player_reaches_allowed_pages(entry, superuser_page, base_url, game):
    expected_available = _inventory.expect_available_for_page_visit(
        entry, BOOSTED_PLAYER, game, owns_sample_item=True)  # guy1 owns "sacred_chest", per apply_baseline_tweaks

    for sample in entry.sample_paths(game):
        url = _inventory.url_for(base_url, GAME_ID, BOOSTED_PLAYER, sample)
        response = superuser_page.context.request.get(url, max_redirects=0)
        if expected_available:
            assert response.status == 200, (entry.entry_id, url, response.status)
        else:
            assert response.status in (301, 302), (entry.entry_id, url, response.status)
            _pages.assert_redirects_to_own_homepage(response, GAME_ID, BOOSTED_PLAYER)


def test_superuser_impersonating_master_cannot_reach_character_only_pages(superuser_page, base_url, game):
    character_entries = [e for e in _inventory.iter_inventory_entries() if e.access == "character"]
    assert character_entries, "expected at least one ACCESS=character view in the inventory"
    entry = character_entries[0]
    for sample in entry.sample_paths(game):
        url = _inventory.url_for(base_url, GAME_ID, MASTER_LOGIN, sample)
        response = superuser_page.context.request.get(url, max_redirects=0)
        assert response.status in (301, 302), (entry.entry_id, url, response.status)
        _pages.assert_redirects_to_own_homepage(response, GAME_ID, MASTER_LOGIN)


def test_superuser_master_homepage_renders_cleanly(superuser_page, base_url):
    response = _pages.goto_as(superuser_page, base_url, GAME_ID, MASTER_LOGIN, "")
    _pages.assert_page_ok(superuser_page, response)


def test_superuser_impersonated_player_homepage_renders_cleanly(superuser_page, base_url):
    response = _pages.goto_as(superuser_page, base_url, GAME_ID, BOOSTED_PLAYER, "")
    _pages.assert_page_ok(superuser_page, response)
