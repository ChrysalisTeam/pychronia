

from ._test_settings import *
from persistent.list import PersistentList


# we override transient test DBs with persistent ones
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(TEST_DIR, "django.db")
    }
}
ZODB_FILE = os.path.join(TEST_DIR, "gamedata.fs")

ACTIVATE_AIML_BOTS = True


def GAME_INITIAL_FIXTURE_SCRIPT(dm):
    """
    Called just before conversion of initial data tree, and coherency check.
    """

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
    email_master = dm.data["global_parameters"]["master_email"]

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
