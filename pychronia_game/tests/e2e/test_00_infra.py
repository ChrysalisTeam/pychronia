# -*- coding: utf-8 -*-

from pychronia_game.tests.e2e import _configs, _pages

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


def test_zodb_restore_isolation_step1_writes(game):
    assert game.get_global_parameter("game_theoretical_length_days") != 999999
    game.set_global_parameter("game_theoretical_length_days", 999999)


def test_zodb_restore_isolation_step2_sees_pristine_state(game):
    assert game.get_global_parameter("game_theoretical_length_days") != 999999
