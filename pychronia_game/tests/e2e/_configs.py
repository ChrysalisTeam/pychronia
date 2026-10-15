# -*- coding: utf-8 -*-

from persistent.list import PersistentList

GAME_ID = "e2egame"
SECONDARY_GAME_ID = "e2egame2"

BOOSTED_PLAYER = "guy1"
PLAIN_PLAYER = "guy2"
PLAYER_WITH_SECRET_QUESTION = "guy3"
DISABLED_PLAYER = "guy4"

EMAIL_DOMAIN = "pangea.com"
EXTERNAL_CONTACT_EMAIL = "othercontact@anything.fr"

PLAYER_CREDENTIALS = {"guy1": "elixir", "guy2": "awesome", "guy3": "awesome2"}
MASTER_LOGIN = "master"
MASTER_PASSWORD = "ultimate"

SUPERUSER_USERNAME = "e2e_admin"
SUPERUSER_PASSWORD = "e2e_admin_pwd"


def _email(username):
    return "%s@%s" % (username, EMAIL_DOMAIN)


def apply_baseline_tweaks(dm):
    """Enriches the bare default test fixture so that pages show real content.
    Runs once, at session init, and gets baked into the pristine ZODB snapshot."""

    dm._set_user(dm.get_global_parameter("master_login"))  # lets us call privileged datamanager APIs

    dm.set_game_state(True)
    dm.set_activated_game_views(list(dm.ACTIVABLE_VIEWS_REGISTRY))

    dm.update_permissions(BOOSTED_PLAYER, PersistentList(dm.PERMISSIONS_REGISTRY))

    msg1_id = dm.post_message(sender_email=_email(PLAIN_PLAYER), recipient_emails=[_email(BOOSTED_PLAYER)],
                              subject="Hello", body="Hi, how are you?")
    dm.post_message(sender_email=_email(BOOSTED_PLAYER), recipient_emails=[_email(PLAIN_PLAYER)],
                    subject="Re: Hello", body="I'm fine, thanks!", parent_id=msg1_id)
    dm.post_message(sender_email=_email(BOOSTED_PLAYER), recipient_emails=[EXTERNAL_CONTACT_EMAIL],
                    subject="External note", body="Reaching out to an external contact.")
    dm.set_dispatched_message_state_flags(username=BOOSTED_PLAYER, msg_id=msg1_id, has_archived=True)

    dm.set_wiretapping_targets(PLAYER_WITH_SECRET_QUESTION, [BOOSTED_PLAYER])

    dm.transfer_object_to_character("sacred_chest", BOOSTED_PLAYER)
    dm.transfer_object_to_character("several_misc_gems2", BOOSTED_PLAYER)

    dm.propose_friendship(BOOSTED_PLAYER, PLAIN_PLAYER)
    dm.propose_friendship(PLAIN_PLAYER, BOOSTED_PLAYER)  # seals the friendship


def _apply_paused(dm):
    dm.set_game_state(False)


def _apply_no_activated_views(dm):
    dm.set_activated_game_views([])


def _apply_encyclopedia_index_hidden(dm):
    dm.set_encyclopedia_index_visibility(False)


CONFIGS = {
    "baseline": None,
    "paused": _apply_paused,
    "no_activated_views": _apply_no_activated_views,
    "encyclopedia_index_hidden": _apply_encyclopedia_index_hidden,
}


def apply_config(dm, config_id):
    """Applies a named per-test configuration variant, after the ZODB has been restored
    to its pristine state. See CONFIGS for the available variants."""
    tweak = CONFIGS[config_id]
    if tweak is not None:
        dm._set_user(dm.get_global_parameter("master_login"))
        tweak(dm)
