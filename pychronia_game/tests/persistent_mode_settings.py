# -*- coding: utf-8 -*-

from pychronia_game.common_settings import *

from pychronia_common.tests.persistent_mode_settings import * # simple overrides

from pychronia_game.tests.common_test_settings import * # simple overrides


ROOT_URLCONF = 'pychronia_game.tests._test_urls_web'


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



## FOR INTEGRATION ##
GAME_FILES_ROOT = "P:\\Chrysalis Depot\\Chrysalis V1\\"
GAME_INITIAL_DATA_PATH = r"P:\Chrysalis Depot\Chrysalis V1\script_fixtures"





def GAME_INITIAL_FIXTURE_SCRIPT(dm):
    """
    Called just before conversion of initial data tree, and coherency check.
    """
    return # TODO TEMPORARY
    from persistent.list import PersistentList

    # we activate ALL views
    activable_views = dm.ACTIVABLE_VIEWS_REGISTRY.keys()
    dm.set_activated_game_views(activable_views)

    # we give guy1 access to everything
    dm.update_permissions("guy1", PersistentList(dm.PERMISSIONS_REGISTRY))

    # we can see all articles
    dm.set_encyclopedia_index_visibility(True)

    # we fill the messages
    email_guy1 = dm.get_character_email("guy1")
    email_guy2 = dm.get_character_email("guy2")
    email_master = "judicators@acharis.com"

    msg_id1 = dm.post_message(sender_email=email_guy1, recipient_emails=email_guy2, subject="message1", body="hello")
    msg1 = dm.get_dispatched_message_by_id(msg_id1)
    msg_id2 = dm.post_message(sender_email=email_guy2, recipient_emails=email_guy1, subject="RE:%s" % msg1["subject"], body="hello world", parent_id=msg_id1)
    msg2 = dm.get_dispatched_message_by_id(msg_id2)
    msg_id3 = dm.post_message(sender_email=email_guy1, recipient_emails=email_guy2, subject="Bis:%s" % msg2["subject"], body="hello hello", parent_id=msg_id2)

    msg_id4 = dm.post_message(sender_email=email_guy1, recipient_emails=email_master, subject="Ask master", body="for something")
    msg4 = dm.get_dispatched_message_by_id(msg_id4)
    msg_id5 = dm.post_message(sender_email=email_master, recipient_emails=email_guy1, subject="RE:%s" % msg4["subject"], body="answer something", parent_id=msg_id4)
    msg5 = dm.get_dispatched_message_by_id(msg_id5)
    msg_id6 = dm.post_message(sender_email=email_guy1, recipient_emails=email_master, subject="Bis:%s" % msg5["subject"], body="ask for something", parent_id=msg_id5)

    # we distribute auction items
    dm.transfer_object_to_character("statue", "guy1")
    dm.transfer_object_to_character("several_misc_gems", "guy2")

    dm.propose_friendship("guy1", "guy2")
    dm.propose_friendship("guy2", "guy1") # accept friendship


