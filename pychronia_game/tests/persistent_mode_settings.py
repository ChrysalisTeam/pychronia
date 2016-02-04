# -*- coding: utf-8 -*-

from pychronia_game.common_settings import *

from pychronia_common.tests.persistent_mode_settings import * # simple overrides

from pychronia_game.tests.common_test_settings import * # simple overrides

import time




_curdir = os.path.dirname(os.path.realpath(__file__))

# we override transient test DBs with persistent ones
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(_curdir, "django.db")
    }
}

ZODB_FILE = os.path.join(_curdir, "gamedata.fs")
ZODB_URL = None






def GAME_INITIAL_FIXTURE_SCRIPT(dm):
    """
    Called just before conversion of initial data tree, and coherence check.
    """
    logging.info("Loading special game fixture script...")

    #return # TODO TEMPORARY
    from persistent.list import PersistentList

    # we activate ALL views
    activable_views = dm.ACTIVABLE_VIEWS_REGISTRY.keys()
    dm.set_activated_game_views(activable_views)


    player_name, player_name_bis, player_name_ter, player_name_quater = dm.get_character_usernames()[0:4]

    # we give first player access to everything
    assert not dm.get_character_properties(player_name)["is_npc"]
    dm.update_permissions(player_name, PersistentList(dm.PERMISSIONS_REGISTRY))

    # we can (or not) see all articles
    dm.set_encyclopedia_index_visibility(False)

    # we fill the messages
    email_guy1 = dm.get_character_email(player_name)
    email_guy2 = dm.get_character_email(player_name_bis)
    email_guy3 = dm.get_character_email(player_name_ter)
    email_guy4 = dm.get_character_email(player_name_quater)
    email_external = sorted(dm.global_contacts.keys())[0]

    dm.set_wiretapping_targets(player_name_ter, [player_name])

    msg_id1 = dm.post_message(sender_email=email_guy1, recipient_emails=email_guy2, subject="NULL TEST", body="hello", transferred_msg="UNEXISTING_TRANSFERRED_MSG_SYZH")  # wrong transferred_msg shouldn't fail
    msg1 = dm.get_dispatched_message_by_id(msg_id1)
    msg_id2 = dm.post_message(sender_email=email_guy2, recipient_emails=email_guy1, subject="RE:%s" % msg1["subject"], body="hello world", parent_id=msg_id1)
    msg2 = dm.get_dispatched_message_by_id(msg_id2)
    msg_id3 = dm.post_message(sender_email=email_guy1, recipient_emails=email_guy2, subject="Bis:%s" % msg2["subject"], body="hello hello", parent_id=msg_id2)

    msg_id4 = dm.post_message(sender_email=email_guy1, recipient_emails=email_external, subject="Ask master TEST", body="for something")
    msg4 = dm.get_dispatched_message_by_id(msg_id4)
    msg_id5 = dm.post_message(sender_email=email_external, recipient_emails=email_guy1, subject="RE:%s TEST" % msg4["subject"], body="answer something", parent_id=msg_id4)
    msg5 = dm.get_dispatched_message_by_id(msg_id5)
    msg_id6 = dm.post_message(sender_email=email_guy1, recipient_emails=email_external, subject="Bis:%s TEST" % msg5["subject"], body="ask for something", parent_id=msg_id5)
    
    msg_id7 = dm.post_message(sender_email=email_guy3, recipient_emails=email_guy4, subject="Vol de Tapis", body="Je pense qu'on doit voler les tapis de guy1")
    msg7 = dm.get_dispatched_message_by_id(msg_id7)
    
    time.sleep(1)
    
    msg_id8 = dm.post_message(sender_email=email_guy4, recipient_emails=email_guy3, subject = "RE:%s" % msg7["subject"], body="T'as raison ils sont si doux", parent_id=msg_id7)
    msg8 = dm.get_dispatched_message_by_id(msg_id8)

    tpl = dm.get_message_template("feedback_akaris_threats_geoip")
    assert tpl["transferred_msg"] is None
    tpl["transferred_msg"] = "unexisting_transferred_msg_id_sozj"  # wrong transferred_msg shouldn't break stuffs
    # transient mode here, no need to commit

    # we distribute auction items
    gem = dm.get_gem_items().keys()[0]
    dm.transfer_object_to_character(gem, player_name)
    item = dm.get_non_gem_items().keys()[0]
    dm.transfer_object_to_character(item, player_name)

    dm.propose_friendship(player_name, player_name_bis)
    dm.propose_friendship(player_name_bis, player_name) # accept friendship

    logging.info("Finished special game fixture script...")


## OVERRIDES FOR INTEGRATION OF REAL CHRYSALIS FIXTURES, if they're in ../Chrysalis relatively to this depot's root ##
import pychronia_game, os
_external_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(pychronia_game.__file__))))
_chrysalis_data_dir = os.path.join(_external_dir, "Chrysalis")
if os.path.exists(_chrysalis_data_dir):
    GAME_FILES_ROOT = _chrysalis_data_dir + os.sep
    GAME_INITIAL_DATA_PATH = os.path.join(_chrysalis_data_dir, "script_fixtures")

