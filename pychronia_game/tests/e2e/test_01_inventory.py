# -*- coding: utf-8 -*-
"""
Meta-tests over the page inventory itself (see _inventory.py).

These don't touch the browser or the ZODB at all: they just check that
inner_game_urlpatterns has been fully and sanely classified, so that new pages can't
silently escape e2e coverage as the app evolves. The actual "visit every page" tests
live in test_pages_player.py / test_pages_superuser.py, which parametrize over
_inventory.iter_inventory_entries().
"""

from pychronia_game.urls import inner_game_urlpatterns
from pychronia_game.tests.e2e import _inventory


def test_inventory_is_complete():
    """Every URL pattern in inner_game_urlpatterns must end up classified into exactly
    one category (plain_get/parametrized/ajax_or_non_html/excluded). This is the guard
    against new pages silently escaping e2e coverage."""
    entries = list(_inventory.iter_inventory_entries())

    assert len(entries) == len(inner_game_urlpatterns), (
        "Inventory entry count (%d) doesn't match inner_game_urlpatterns (%d) -- "
        "some URL pattern isn't being picked up by _build_inventory()"
        % (len(entries), len(inner_game_urlpatterns)))

    for entry in entries:
        assert entry.category in _inventory.ALL_CATEGORIES, entry
        assert entry.name, entry
        assert entry.entry_id, entry
        assert entry.access in ("anonymous", "authenticated", "character", "master"), entry

    entry_ids = [entry.entry_id for entry in entries]
    assert len(entry_ids) == len(set(entry_ids)), "Duplicate entry_id(s) found in the inventory"

    # Every view intentionally classified as "excluded" must be one of the known
    # dangerous/special ones -- catches typos in EXCLUDED_NAMES just as much as omissions.
    excluded_names_found = {entry.name for entry in entries if entry.category == _inventory.CATEGORY_EXCLUDED}
    assert excluded_names_found == set(_inventory.EXCLUDED_NAMES), (excluded_names_found, _inventory.EXCLUDED_NAMES)


def test_inventory_has_sane_category_counts():
    """Loose sanity check so that a wholesale miscategorization (eg. an import error
    silently emptying a category) doesn't go unnoticed."""
    counts = {category: len(_inventory.entries_by_category(category)) for category in _inventory.ALL_CATEGORIES}
    assert sum(counts.values()) == len(inner_game_urlpatterns)
    assert counts[_inventory.CATEGORY_EXCLUDED] == len(_inventory.EXCLUDED_NAMES)
    assert counts[_inventory.CATEGORY_PLAIN_GET] > 40
    assert counts[_inventory.CATEGORY_PARAMETRIZED] >= 7
    assert counts[_inventory.CATEGORY_AJAX_OR_NON_HTML] >= 7


def test_every_plain_get_entry_has_exactly_one_sample_path():
    for entry in _inventory.iter_inventory_entries(_inventory.CATEGORY_PLAIN_GET):
        samples = entry.sample_paths()
        assert len(samples) == 1, entry
        assert not samples[0].path.startswith("/"), entry


def test_every_parametrized_entry_has_a_sample_provider():
    for entry in _inventory.iter_inventory_entries(_inventory.CATEGORY_PARAMETRIZED):
        if entry.entry_id == "view_single_message__msg_id":
            continue  # its sample is only computable with a live `dm` (see test below)
        samples = entry.sample_paths()
        assert samples, entry
        for sample in samples:
            assert not sample.path.startswith("/"), entry


def test_ajax_and_excluded_entries_expose_no_sample_paths():
    for category in (_inventory.CATEGORY_AJAX_OR_NON_HTML, _inventory.CATEGORY_EXCLUDED):
        for entry in _inventory.iter_inventory_entries(category):
            assert entry.sample_paths() == [], entry


def test_view_single_message_sample_needs_live_dm(game):
    """The one parametrized entry whose sample value is created at runtime by the
    baseline tweaks (a posted message id), looked up live via the `game` fixture."""
    entry = _inventory.get_entry("view_single_message__msg_id")
    assert entry.sample_paths(None) == []
    samples = entry.sample_paths(game)
    assert samples
    assert all("messages/view_single_message/" in sample.path for sample in samples)
