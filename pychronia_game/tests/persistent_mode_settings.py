# -*- coding: utf-8 -*-

import time

from pychronia_game.common_settings import *

from pychronia_common.tests.persistent_mode_settings import *  # simple overrides

from pychronia_game.tests.common_test_settings import *  # simple overrides

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

    # we activate ALL views
    activable_views = dm.ACTIVABLE_VIEWS_REGISTRY.keys()
    dm.set_activated_game_views(activable_views)

    player_name, player_name_bis, player_name_ter, player_name_quater = dm.get_character_usernames()[0:4]

    # we give first player access to everything
    assert not dm.get_character_properties(player_name)["is_npc"]
    dm.update_permissions(player_name, dm.PERMISSIONS_REGISTRY)

    # we can (or not) see all articles
    dm.set_encyclopedia_index_visibility(False)

    # we fill the messages
    email_guy1 = dm.get_character_email(player_name)
    email_guy2 = dm.get_character_email(player_name_bis)
    email_guy3 = dm.get_character_email(player_name_ter)
    email_guy4 = dm.get_character_email(player_name_quater)
    email_external = sorted(dm.global_contacts.keys())[0]

    dm.set_wiretapping_targets(player_name_ter, [player_name])

    # first, spam emails to fill messaging pages
    for i in range(100):
        # will be intercepted by player_name_ter
        _msg_id = dm.post_message(sender_email=email_guy4, recipient_emails=email_guy1, subject="Flood %s" % i,
                                  body="Ceci est le message %s" % i)

        if i % 2:
            dm.set_dispatched_message_state_flags(username=player_name,
                                                  msg_id=_msg_id,
                                                  has_archived=True)

    msg_id1 = dm.post_message(sender_email=email_guy1, recipient_emails=email_guy2, subject="NULL TEST", body="hello",
                              transferred_msg="UNEXISTING_TRANSFERRED_MSG_SYZH")  # wrong transferred_msg shouldn't fail
    msg1 = dm.get_dispatched_message_by_id(msg_id1)
    msg_id2 = dm.post_message(sender_email=email_guy2, recipient_emails=email_guy1, subject="RE:%s" % msg1["subject"],
                              body="hello world", parent_id=msg_id1)
    msg2 = dm.get_dispatched_message_by_id(msg_id2)
    msg_id3 = dm.post_message(sender_email=email_guy1, recipient_emails=email_guy2, subject="Bis:%s" % msg2["subject"],
                              body="hello hello", parent_id=msg_id2)

    msg_id4 = dm.post_message(sender_email=email_guy1, recipient_emails=email_external, subject="Ask master TEST",
                              body="for something")
    msg4 = dm.get_dispatched_message_by_id(msg_id4)
    msg_id5 = dm.post_message(sender_email=email_external, recipient_emails=email_guy1,
                              subject="RE:%s TEST" % msg4["subject"], body="answer something", parent_id=msg_id4)
    msg5 = dm.get_dispatched_message_by_id(msg_id5)
    msg_id6 = dm.post_message(sender_email=email_guy1, recipient_emails=email_external,
                              subject="Bis:%s TEST" % msg5["subject"], body="ask for something", parent_id=msg_id5)

    msg_id7 = dm.post_message(sender_email=email_guy3, recipient_emails=email_guy4, subject="Vol de Tapis",
                              body="Je pense qu'on doit voler les tapis de guy1")
    msg7 = dm.get_dispatched_message_by_id(msg_id7)

    time.sleep(1)

    msg_id8 = dm.post_message(sender_email=email_guy4, recipient_emails=[email_guy3], subject="RE:%s" % msg7["subject"],
                              body="T'as raison ils sont si doux", parent_id=msg_id7)
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

    # NOPE no more auto-friendship here
    #dm.propose_friendship(player_name, player_name_bis)
    #dm.propose_friendship(player_name_bis, player_name)  # accept friendship

    logging.info("Finished special game fixture script...")


## OVERRIDES FOR INTEGRATION OF REAL CHRYSALIS FIXTURES, if they're in ../Chrysalis relatively to this depot's root ##
import pychronia_game, os

_external_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(pychronia_game.__file__))))
_chrysalis_data_dir = os.path.join(_external_dir, "Chrysalis")
if os.path.exists(_chrysalis_data_dir):
    GAME_FILES_ROOT = _chrysalis_data_dir + os.sep


    # SELECT ONLY SOME FIXTURES, FOR MYSTERY PARTY

    _GAME_INITIAL_DATA_DIR = os.path.join(_chrysalis_data_dir, "script_fixtures")

    _selected_yaml_files = """
        descent_rpg
    
        abilities.yaml
        characters_factions.yaml
        game_items.yaml
        gamemaster_manual.yaml
        global_data.yaml
        locations.yaml
        messaging_core.yaml
        nightmare_captchas.yaml
        radio_spots.yaml
        static_pages.yaml
        
        encyclopedia/ability_related_subjects.yaml
        encyclopedia/midolian_and_yodic_subjects.yaml
        encyclopedia/pangea_misc_locations_and_events.yaml
        encyclopedia/sabarim_locations_and_characters.yaml
        
        messaging/abilities.yaml
        #messaging/cynthia_abduction.yaml
        #messaging/doctor_honoris_causa_and_nazur.yaml
        messaging/first_contacts.yaml
        messaging/geopolitics.yaml
        messaging/inquiries_between_players.yaml
        #messaging/magnus_society_family_exchanges.yaml
        #messaging/main_npcs_exchanges.yaml
        messaging/news.yaml
        messaging/npc_orbs.yaml
        #messaging/player_instructions.yaml
        #messaging/super_factions.yaml
        #messaging/wiremind.yaml
        
        mysteryparty/anthropia_game_data_overrides.yaml
        """.split()

    GAME_INITIAL_DATA_PATH = [os.path.join(_GAME_INITIAL_DATA_DIR, _selected_yaml_file)
                              for _selected_yaml_file in _selected_yaml_files
                              if _selected_yaml_file[0] != "#"]


    GAME_INITIAL_FIXTURE_SCRIPT_DEV = GAME_INITIAL_FIXTURE_SCRIPT

    def GAME_INITIAL_FIXTURE_SCRIPT(dm):

        ## NOPE GAME_INITIAL_FIXTURE_SCRIPT_DEV(dm)  # call initial dev setup

        # we give first player access to everything TEMPORARY
        player_name = "amethyst"
        assert not dm.get_character_properties(player_name)["is_npc"]
        dm.update_permissions(player_name, dm.PERMISSIONS_REGISTRY)


        # remove useless static pages, especially in encyclopedia
        excluded_static_pages = """
            salt_deserts
            cloudy_citadel
            nalavut_council
            hydroland
            belez_academy
            imuo_faculty
            jungle_harmonies_album
            alifir_deans
        """.split()

        for excluded_static_page in excluded_static_pages:
            del dm.data["static_pages"][excluded_static_page]  # no need to commit

        assert dm.get_global_parameter("game_theoretical_length_days")
        dm.set_global_parameter("game_theoretical_length_days", 1)

        activable_views = [
            #"artificial_intelligence",
            "auction_items_slideshow",
            #"black_market",
            "business_escrow",
            "chatroom",
            #"chess_challenge",
            "game_events",
            #"geoip_location",   # COULD be enabled!
            "house_locking",
            "house_reports",
            "matter_analysis",
            "mercenaries_hiring",
            "personal_items_slideshow",
            "runic_translation",
            #"telecom_investigation",
            "view_sales",
            #"view_world_map_dynamic",
            "wiretapping",
            "world_scan",
        ]
        dm.set_activated_game_views(activable_views)

        friendships = [
            ("amethyst", "garnet"),
            ("malachite", "spinel"),
            ("peridot", "topaz"),
            ##("cynthia", "waden"), NO not blind confidence
            ## ("opal", "lydia"), NO not blind confidence
            ]
        for (player_name, player_name_bis) in friendships:
            _domains1 = dm.get_character_properties(player_name)["domains"]
            _domains2 = dm.get_character_properties(player_name_bis)["domains"]
            assert (_domains1 == _domains2), (player_name, player_name_bis, _domains1, _domains2)
            dm.propose_friendship(player_name, player_name_bis)
            dm.propose_friendship(player_name_bis, player_name)

        # HERE we could complete address books of characters
        #for (name, character) in dm.get_character_sets().items():
        #    address_book = dm.get_character_address_book(name)

        ml_address = dm.get_global_parameter("all_players_mailing_list")
        email_predispatches = [
            ("lg_interview", dict(), -25),
            ("anonymous_threat_4", dict(), -20),
            ("lg_welcome_message", dict(), -19),
            ("waden_report_orb_analysis", dict(), -10),
            ("inspector_shark_arrival", dict(recipient_emails=[ml_address],), -7),
            ("security_measures", dict(recipient_emails=[ml_address],), -2),
        ]

        for idx, (template_id, params, offset_days) in enumerate(email_predispatches):
            if offset_days:
                assert "date_or_delay_mn" not in params
                params["date_or_delay_mn"] = offset_days * 24 * 60
                assert params["date_or_delay_mn"] < 0, params["date_or_delay_mn"]
            #print(">>>>>>>>> Preposting message with template_id=%s and params=%s" % (template_id, params))
            dm.post_message_with_template(template_id, **params)

        for item_name, item_data in dm.data["game_items"].items():
            if item_data["auction"] and len(item_data["auction"]) != 1:
                item_data["auction"] = ""  # remove old auction items (now only A, B, C...)
