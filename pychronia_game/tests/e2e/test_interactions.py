# -*- coding: utf-8 -*-
"""
Short, focused interaction scenarios (design doc E2E_TESTS_PLAN.md, section 9's
bottom "interaction tests" list). Kept deliberately minimal: one happy-path test
per scenario, not exhaustive coverage (page/permission coverage lives in
test_pages_player.py / test_pages_superuser.py / test_permissions.py).

Facts below were confirmed against the real code/templates/live-rendered HTML
while writing this file (the plan's draft only sketched the intent):

- Message compose form (``pychronia_game/views/messaging_views.py:compose_message``,
  template ``messaging/compose.html``): the ``MessageComposeForm`` fields are
  rendered with a ``default`` prefix by the generic game-action-form machinery,
  so the real field ids are ``#id_default_recipients``, ``#id_default_subject``,
  ``#id_default_body`` (NOT ``#id_recipients`` / ``#id_subject`` / ``#id_body`` as
  one might guess from the form class alone). ``recipients`` is a
  ``Select2TagsField`` (a JS-enhanced multi-value tag widget), but the view's
  ``MessageComposeForm.__init__`` reads a plain ``?recipient=<email>`` GET
  parameter and uses it as the field's ``initial`` value, and the Select2 JS runs
  ``initMultipleHidden()`` on page load which immediately (synchronously, before
  any user interaction) materializes the required
  ``<input type="hidden" name="recipients" value="...">`` for that initial value.
  So navigating straight to ``messages/compose/?recipient=<email>`` and then only
  filling in subject/body is enough -- no Select2 interaction needed for this
  scenario. Submitting (``input[name="send_message"]``) redirects a non-master
  sender to ``messages/conversations/?message_sent=1``
  (``pychronia_game.views.standard_conversations``), where the subject shows up.
- Encrypted folder form (``encrypted_folder`` view in
  ``pychronia_game/views/info_views.py``, template
  ``information/encrypted_folder.html``): real field is
  ``#id_simple_password`` (name ``simple_password``), submit button is
  ``input[name="decrypt"]``. On success it renders
  ``information/personal_folder.html``, listing decrypted files as
  ``<li><a>filename</a></li>`` in the sidebar -- for ``guy2_report``/``evans`` this
  includes ``orb.jpg``.
- Admin dashboard pause toggle (``ability/admin_dashboard/``,
  ``AdminDashboardAbility`` in
  ``pychronia_game/views/admin_views/admin_dashboard_mod.py``): is a dynamic
  "admin widget" form identified by
  ``<input type="hidden" name="target_form_id" value="admin_dashboard.set_game_pause_state">``,
  with a checkbox ``#id_default_is_paused`` (name ``is_paused``). All submit
  buttons on that page are rendered ``disabled`` whenever
  ``disable_widgets`` is true in the template context, which happens whenever the
  current (possibly impersonated) session isn't in writable mode
  (``pychronia_game/context_processors.py``) -- so a superuser impersonating
  master must first call ``_pages.set_impersonation_writability(..., True)`` (a
  plain read-only impersonation, the default, would leave the submit button
  disabled and the click a no-op). Once paused, ANY page load by a non-master
  user adds a warning "Website currently in read-only mode, for maintenance."
  (``determine_actual_game_writability()`` in ``datamanager_modules.py``,
  surfaced via ``context_processors.py``) -- no POST attempt is needed to see it.
- Friendship proposal (``friendships/``, ``FriendshipManagementView`` in
  ``pychronia_game/views/profile_views.py``): the "propose friendship" form's
  ``other_username`` field is also a ``Select2TagsField``, but (unlike the
  message-compose recipients field) there is no GET-param prefill for it, so it
  really must be driven through the Select2 widget: click the container
  (``#s2id_id_default_other_username``) to focus/open it, type the target
  username, press Enter to commit it as the (single, ``max_selection_size=1``)
  tag. Validation is permissive: ``Select2TagsField.validate_value()`` is never
  overridden to check names against the autocomplete suggestion list
  (``choice_tags``), so any existing character username is accepted even if not
  offered in the dropdown. guy1+guy2 are already sealed friends per the baseline
  fixture, so this test instead uses guy3 (PLAYER_WITH_SECRET_QUESTION, not
  friends with anyone yet) proposing to guy2 (PLAIN_PLAYER), then guy2 accepting
  via the per-row action form (hidden inputs ``_action_=do_accept_friendship`` +
  ``other_username=guy3``).
"""

import pytest

from pychronia_game.tests.e2e import _configs, _pages

pytestmark = pytest.mark.usefixtures("fresh_zodb")

GAME_ID = _configs.GAME_ID


def test_compose_message_then_see_it_in_conversations(player_page, base_url):
    recipient_email = _configs._email(_configs.PLAYER_WITH_SECRET_QUESTION)  # guy3@pangea.com
    subject = "E2E interaction test subject"

    player_page.goto("%s/%s/%s/messages/compose/?recipient=%s" % (
        base_url, GAME_ID, _configs.BOOSTED_PLAYER, recipient_email))
    player_page.fill("#id_default_subject", subject)
    player_page.fill("#id_default_body", "E2E interaction test body.")
    player_page.click('input[name="send_message"]')
    player_page.wait_for_load_state("networkidle")

    assert "messages/conversations/" in player_page.url
    _pages.assert_page_ok(player_page)
    assert subject in player_page.content()


def test_unlock_encrypted_folder(player_page, base_url):
    player_page.goto("%s/%s/%s/encrypted_folders/guy2_report/" % (base_url, GAME_ID, _configs.BOOSTED_PLAYER))
    player_page.fill("#id_simple_password", "evans")
    player_page.click('input[name="decrypt"]')
    player_page.wait_for_load_state("networkidle")

    _pages.assert_page_ok(player_page)
    assert "orb.jpg" in player_page.content()


def test_superuser_toggles_pause_and_player_sees_readonly_notice(superuser_page, page, base_url):
    # arrange: superuser impersonates master, needs writability to submit the admin widget form
    _pages.goto_as(superuser_page, base_url, GAME_ID, _configs.MASTER_LOGIN, "ability/admin_dashboard/")
    _pages.set_impersonation_writability(superuser_page, base_url, GAME_ID, True)
    _pages.goto_as(superuser_page, base_url, GAME_ID, _configs.MASTER_LOGIN, "ability/admin_dashboard/")

    pause_form = superuser_page.locator(
        'form:has(input[name="target_form_id"][value="admin_dashboard.set_game_pause_state"])')
    pause_form.locator("#id_default_is_paused").check()
    pause_form.locator('input[type="submit"]').click()
    superuser_page.wait_for_load_state("networkidle")

    _pages.assert_page_ok(superuser_page)
    assert superuser_page.locator("#id_default_is_paused").is_checked()

    # act/assert: an ordinary player immediately sees the read-only notice, with no POST needed
    _pages.login_as_player(page, base_url, GAME_ID, _configs.PLAIN_PLAYER,
                           _configs.PLAYER_CREDENTIALS[_configs.PLAIN_PLAYER])
    page.goto("%s/%s/%s/" % (base_url, GAME_ID, _configs.PLAIN_PLAYER))
    assert "Website currently in read-only mode" in page.content()


def test_logout_then_authenticated_page_redirects_to_login(page, base_url):
    # Uses a throwaway login (not the shared `player_page` fixture): that fixture's
    # storage_state is session-scoped and reused by every other test, so logging it
    # out here would invalidate guy1's session for the rest of the suite.
    _pages.login_as_player(page, base_url, GAME_ID, _configs.BOOSTED_PLAYER,
                           _configs.PLAYER_CREDENTIALS[_configs.BOOSTED_PLAYER])
    _pages.logout(page, base_url, GAME_ID)

    assert "guest/login" in page.url
    assert "successfully logged out" in page.content()

    # re-visiting an authenticated-only page (compose) must bounce back to login
    page.goto("%s/%s/%s/messages/compose/" % (base_url, GAME_ID, _configs.BOOSTED_PLAYER))
    assert "guest/login" in page.url or "/login/" in page.url


def test_friendship_proposal_end_to_end(page, base_url):
    proposer = _configs.PLAYER_WITH_SECRET_QUESTION  # guy3: not friends with anyone per baseline
    recipient = _configs.PLAIN_PLAYER  # guy2: not friends with guy3 either (only with guy1)

    # guy3 proposes friendship to guy2, via the real Select2 "tag" widget
    _pages.login_as_player(page, base_url, GAME_ID, proposer, _configs.PLAYER_CREDENTIALS[proposer])
    page.goto("%s/%s/%s/friendships/" % (base_url, GAME_ID, proposer))
    page.click("#s2id_id_default_other_username")
    page.keyboard.type(recipient)
    page.keyboard.press("Enter")
    page.click('input[name="request_friendship"]')
    page.wait_for_load_state("networkidle")
    _pages.assert_page_ok(page)
    assert ("friendship proposal to %s has been recorded" % recipient) in page.content()

    # guy2 accepts it
    _pages.logout(page, base_url, GAME_ID)
    _pages.login_as_player(page, base_url, GAME_ID, recipient, _configs.PLAYER_CREDENTIALS[recipient])
    page.goto("%s/%s/%s/friendships/" % (base_url, GAME_ID, recipient))
    accept_form = page.locator('form:has(input[name="other_username"][value="%s"])' % proposer)
    accept_form.locator('input[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    _pages.assert_page_ok(page)
    assert ("now friend with %s" % proposer) in page.content()

    # sealed for both: guy2's page already shows it; double check from guy3's side too
    page.goto("%s/%s/%s/friendships/" % (base_url, GAME_ID, proposer))
    assert recipient in page.content()
