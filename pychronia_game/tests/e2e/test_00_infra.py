# -*- coding: utf-8 -*-

import pytest
from django.conf import settings as django_settings

from pychronia_game.datamanager.datamanager_administrator import retrieve_game_instance
from pychronia_game.tests.e2e import _configs, _pages, _server, _zodb_snapshot
from pychronia_game.tests.e2e.conftest import PRISTINE_DIR

pytestmark = pytest.mark.usefixtures("fresh_zodb")

GAME_ID = _configs.GAME_ID


def test_root_refuses_access(page, base_url):
    response = page.goto(base_url + "/")
    assert response.status == 200
    assert "not allowed" in page.content()


def test_robots_txt(page, base_url):
    response = page.goto(base_url + "/robots.txt")
    assert response.status == 200
    assert "Disallow" in page.content()


def test_player_login_smoke(player_page, base_url):
    response = player_page.goto("%s/%s/%s/" % (base_url, GAME_ID, _configs.BOOSTED_PLAYER))
    _pages.assert_page_ok(player_page, response)


def test_superuser_can_reach_administration(superuser_page, base_url):
    response = superuser_page.goto("%s/administration/" % base_url)
    _pages.assert_page_ok(superuser_page, response)
    assert GAME_ID in superuser_page.content()


def test_anonymous_administration_redirects_to_admin_login(page, base_url):
    response = page.goto("%s/administration/" % base_url)
    assert "/admin/login/" in page.url


def test_superuser_impersonates_player_via_url(superuser_page, base_url):
    response = _pages.goto_as(superuser_page, base_url, GAME_ID, _configs.BOOSTED_PLAYER, "profile/")
    _pages.assert_page_ok(superuser_page, response)


def test_zodb_restore_isolation(base_url):
    """Proves, within a single test (rather than relying on undeclared pytest execution
    order across two separate tests), that the restore the `fresh_zodb` fixture performs
    before each test (see this module's `pytestmark`) actually resets ZODB state: writes
    a sentinel value, runs that exact restore call directly, then re-opens a fresh
    connection and checks the sentinel is gone."""
    dm = retrieve_game_instance(_configs.GAME_ID)
    pristine_value = dm.get_global_parameter("game_theoretical_length_days")
    assert pristine_value != 999999
    dm.set_global_parameter("game_theoretical_length_days", 999999)
    dm.commit()
    dm.close()

    _server.wait_for_idle_server()
    _zodb_snapshot.restore_zodb(django_settings.ZODB_FILE, PRISTINE_DIR)

    dm = retrieve_game_instance(_configs.GAME_ID)
    try:
        assert dm.get_global_parameter("game_theoretical_length_days") == pristine_value
    finally:
        dm.close()
