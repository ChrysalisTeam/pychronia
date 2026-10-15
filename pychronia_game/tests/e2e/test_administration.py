# -*- coding: utf-8 -*-

import re
from urllib.parse import urlencode

import pytest
from django.core import mail

from pychronia_game.common import get_utc_now
from pychronia_game.datamanager import datamanager_administrator as dma
from pychronia_game.meta_administration_views import (
    compute_game_activation_token, GAME_ACTIVATION_EMAIL_SUBJECT,
)
from pychronia_game.tests.e2e import _configs, _pages

GAME_ID = _configs.GAME_ID
SECONDARY_GAME_ID = _configs.SECONDARY_GAME_ID


def _lock_secondary_instance(minutes=15):
    dma.change_game_instance_status(game_instance_id=SECONDARY_GAME_ID,
                                    maintenance_until=get_utc_now() + __import__("datetime").timedelta(minutes=minutes))


def _unlock_secondary_instance():
    dma.change_game_instance_status(game_instance_id=SECONDARY_GAME_ID, maintenance_until=None)


def _lock_form(page, instance_id):
    return page.locator('form:has(input[name="lock_instance"][value="%s"])' % instance_id)


def _unlock_form(page, instance_id):
    return page.locator('form:has(input[name="unlock_instance"][value="%s"])' % instance_id)


def _status_form(page, instance_id):
    return page.locator('form:has(input[name="change_instance_status"][value="%s"])' % instance_id)


def _backup_form(page, instance_id):
    return page.locator('form:has(input[name="backup_game_instance"][value="%s"])' % instance_id)


def _delete_form(page, instance_id):
    return page.locator('form:has(input[name="delete_game_instance"][value="%s"])' % instance_id)


# --- 1-2: access control ---

def test_administration_anonymous_redirects_to_admin_login(page, base_url):
    response = page.goto("%s/administration/" % base_url)
    assert "/admin/login/" in page.url
    assert "next=/administration/" in page.url


def test_administration_player_redirects_to_admin_login(player_page, base_url):
    response = player_page.goto("%s/administration/" % base_url)
    assert "/admin/login/" in player_page.url
    assert "next=/administration/" in player_page.url


# --- 3: superuser listing ---

def test_administration_lists_both_instances_as_superuser(superuser_page, base_url):
    response = superuser_page.goto("%s/administration/" % base_url)
    _pages.assert_page_ok(superuser_page, response)
    content = superuser_page.content()
    assert GAME_ID in content
    assert SECONDARY_GAME_ID in content
    assert "Not locked for maintenance" in content


# --- 4: create instance via admin form ---

def test_create_instance_via_admin_form(superuser_page, base_url):
    new_instance_id = "e2e-admin-created"
    assert not dma.game_instance_exists(new_instance_id)

    superuser_page.goto("%s/administration/" % base_url)
    form = superuser_page.locator("#game_creation_form form")
    form.locator("#id_game_instance_id").fill(new_instance_id)
    form.locator("#id_creator_login").fill("e2e_admin_creator")
    form.locator('input[name="create_game_instance"]').click()

    _pages.assert_page_ok(superuser_page)
    content = superuser_page.content()
    assert new_instance_id in content
    assert "successfully created" in content
    assert dma.game_instance_exists(new_instance_id)


# --- 5: lock/unlock toggles 503 ---

def test_lock_unlock_instance_toggles_503(superuser_page, base_url):
    superuser_page.goto("%s/administration/" % base_url)
    _lock_form(superuser_page, SECONDARY_GAME_ID).locator('input[type="submit"]').click()

    _pages.assert_page_ok(superuser_page)
    content = superuser_page.content()
    assert "successfully locked" in content
    assert "LOCKED for maintenance" in content

    response = _pages.goto_as(superuser_page, base_url, SECONDARY_GAME_ID, "anyuser")
    assert response.status == 503

    superuser_page.goto("%s/administration/" % base_url)
    _unlock_form(superuser_page, SECONDARY_GAME_ID).locator('input[type="submit"]').click()

    _pages.assert_page_ok(superuser_page)
    content = superuser_page.content()
    assert "successfully unlocked" in content
    assert "Not locked for maintenance" in content

    response = _pages.goto_as(superuser_page, base_url, SECONDARY_GAME_ID, "anyuser")
    _pages.assert_page_ok(superuser_page, response)


# --- 6: edit_instance_db requires maintenance ---

def test_edit_instance_db_while_in_maintenance_shows_editor(superuser_page, base_url):
    _lock_secondary_instance()

    response = superuser_page.goto("%s/administration/edit/%s/" % (base_url, SECONDARY_GAME_ID))
    _pages.assert_page_ok(superuser_page, response)
    assert superuser_page.locator("#yaml_editor").count() == 1
    content = superuser_page.content()
    assert "Current DB content is displayed here for editing." in content


def test_edit_instance_db_while_not_in_maintenance_is_refused(superuser_page, base_url):
    response = superuser_page.goto("%s/administration/edit/%s/" % (base_url, SECONDARY_GAME_ID))
    _pages.assert_page_ok(superuser_page, response)
    assert superuser_page.locator("#yaml_editor").count() == 0
    content = superuser_page.content()
    assert "NOT in maintenance" in content
    assert "DB modification is now forbidden" in content


# --- 7: status change, backup, enforced-login ticket ---

def test_change_instance_status_shows_success_message(superuser_page, base_url):
    superuser_page.goto("%s/administration/" % base_url)
    with superuser_page.expect_navigation():
        _status_form(superuser_page, SECONDARY_GAME_ID).locator('select[name="new_status"]').select_option("terminated")

    _pages.assert_page_ok(superuser_page)
    content = superuser_page.content()
    assert "status changed to 'terminated'" in content
    assert dma.get_game_instance_metadata_copy(SECONDARY_GAME_ID)["status"] == "terminated"


def test_backup_instance_shows_success_message(superuser_page, base_url):
    superuser_page.goto("%s/administration/" % base_url)
    form = _backup_form(superuser_page, SECONDARY_GAME_ID)
    form.locator('input[name="backup_comment"]').fill("e2e test backup")
    form.locator('input[type="submit"]').click()

    _pages.assert_page_ok(superuser_page)
    content = superuser_page.content()
    assert "backup with comment 'e2e-test-backup'" in content
    assert "done" in content
    assert "e2e-test-backup" in dma.list_backups_for_game_instance(SECONDARY_GAME_ID)[0]


def test_compute_enforced_login_ticket_and_use_it(superuser_page, page, base_url):
    superuser_page.goto("%s/administration/" % base_url)
    form = superuser_page.locator("#session_token_form form")
    form.locator('input[name="game_instance_id"]').fill(GAME_ID)
    form.locator('input[name="login"]').fill(_configs.BOOSTED_PLAYER)
    form.locator('input[name="is_observer"]').uncheck()
    form.locator('input[name="compute_enforced_session_ticket"]').click()

    _pages.assert_page_ok(superuser_page)
    content = superuser_page.content()
    assert "Auto-connection token" in content

    token_display = superuser_page.locator("#session_token_form span").inner_text().strip()
    assert "session_ticket=" in token_display

    target_url = "%s/%s/%s/?%s" % (base_url, GAME_ID, _configs.BOOSTED_PLAYER, token_display)
    response = page.goto(target_url)
    _pages.assert_page_ok(page, response)
    assert ("Welcome to Anthropia, %s" % _configs.BOOSTED_PLAYER.capitalize()) in page.content()


# --- 8: delete instance (secondary only, after deletable status) ---

def test_delete_instance_only_on_secondary_after_terminated(superuser_page, base_url):
    dma.change_game_instance_status(game_instance_id=SECONDARY_GAME_ID, new_status=dma.GAME_STATUSES.terminated)

    superuser_page.goto("%s/administration/" % base_url)
    assert _delete_form(superuser_page, GAME_ID).count() == 0  # GAME_ID is still active, no delete button
    assert _delete_form(superuser_page, SECONDARY_GAME_ID).count() == 1

    superuser_page.once("dialog", lambda dialog: dialog.accept())
    _delete_form(superuser_page, SECONDARY_GAME_ID).locator('input[type="submit"]').click()

    _pages.assert_page_ok(superuser_page)
    content = superuser_page.content()
    assert "was deleted" in content
    assert not dma.game_instance_exists(SECONDARY_GAME_ID)
    assert dma.game_instance_exists(GAME_ID)


# --- 9: anonymous create_instance sends activation mail ---

def test_create_instance_anonymous_sends_activation_mail(page, base_url):
    if hasattr(mail, "outbox"):
        mail.outbox.clear()
    new_instance_id = "e2e-anon-created"
    creator_email = "e2e_anon_creator@example.com"
    assert not dma.game_instance_exists(new_instance_id)

    response = page.goto("%s/administration/create/" % base_url)
    _pages.assert_page_ok(page, response)
    assert page.locator("#id_game_instance_id").count() == 1

    page.fill("#id_game_instance_id", new_instance_id)
    page.fill("#id_creator_login", "e2e_anon_creator")
    page.fill("#id_creator_email", creator_email)
    page.click('input[name="create_game_instance"]')

    _pages.assert_page_ok(page)
    assert "activation email has been sent" in page.content()

    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    assert sent.to == [creator_email]
    assert "Chrysalis RPG" in sent.subject
    match = re.search(r"token=([^&\s\]]+)", sent.body)
    assert match, sent.body
    assert not dma.game_instance_exists(new_instance_id)  # not created yet, only upon activation


# --- 10: activate_instance ---

def test_activate_instance_with_valid_token_creates_and_logs_in(page, base_url):
    new_instance_id = "e2e-activate-created"
    creator_login = "e2e_activate_creator"
    assert not dma.game_instance_exists(new_instance_id)

    token = compute_game_activation_token(game_instance_id=new_instance_id, creator_login=creator_login,
                                          creator_email=None)
    url = "%s/administration/activate/?%s" % (base_url, urlencode({"token": token}))

    response = page.goto(url)
    _pages.assert_page_ok(page, response)
    assert dma.game_instance_exists(new_instance_id)
    assert ("Welcome to Anthropia, %s" % _configs.MASTER_LOGIN.capitalize()) in page.content()


def test_activate_instance_with_bad_token_is_forbidden(page, base_url):
    response = page.goto("%s/administration/activate/?token=not-a-valid-token" % base_url)
    assert response.status == 403


# --- 11: Django admin smoke ---

def test_django_admin_index_smoke(superuser_page, base_url):
    response = superuser_page.goto("%s/admin/" % base_url)
    _pages.assert_page_ok(superuser_page, response)
