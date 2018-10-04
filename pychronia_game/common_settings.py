# -*- coding: utf-8 -*-

from pychronia_common.common_settings import *

TEMPLATES[0]["OPTIONS"]["context_processors"].append("pychronia_game.context_processors.pychronia_template_context")

_old_middlewares = list(MIDDLEWARE_CLASSES)
if "debug_toolbar.middleware.DebugToolbarMiddleware" in _old_middlewares:
    # Django Debug Toolbar bugs on pychronia_game, troubles with ZODB late access...
    _old_middlewares.remove("debug_toolbar.middleware.DebugToolbarMiddleware")

# beware of ordering here
# no need for CSRF in pychronia_game, data is not sensitive
MIDDLEWARE_CLASSES = (tuple(_old_middlewares) +
                      ('pychronia_game.middlewares.ZodbTransactionMiddleware',
                       'pychronia_game.middlewares.AuthenticationMiddleware',
                       'pychronia_game.middlewares.PeriodicProcessingMiddleware',
                       'django_cprofile_middleware.middleware.ProfilerMiddleware',))  # use in DEBUG mode with '?prof' at the end of URL

INSTALLED_APPS += [
    'pychronia_game',
]

############# DJANGO-APP CONFS ############


## EASY-THUMBNAILS CONF ##

THUMBNAIL_DEFAULT_STORAGE = 'pychronia_game.storage.ProtectedGameFileSystemStorage'  # important
THUMBNAIL_MEDIA_ROOT = ''  # NOT used by default
THUMBNAIL_MEDIA_URL = ''  # NOT used by default

THUMBNAIL_ALIASES = {'': {
    # project-wide aliases here
    'default': {  # NECESSARY
        'autocrop': True,  # remove useless whitespace
        'size': (300, 300),  # one of these can be 0 to ignore that dimension
        #'crop': "scale", # True or <smart|scale|W,H>, scale means "only 1 dimension must fit", remove this setting to disable any cropping
    },

    'item_avatar': {  # Eg. in sales page
        'autocrop': True,
        'size': (150, 220),
    },
    'character_avatar': {  # Eg. in characters page
        'autocrop': False,
        'size': (100, 100),
    },
    'contact_avatar': {  # Eg. in list of email contacts
        'autocrop': False,
        'size': (60, 60),
    },

    'small_width': {
        'autocrop': False,
        'size': (200, 0),
    },
    'medium_width': {
        'autocrop': False,
        'size': (350, 0),
    },
    'big_width': {
        'autocrop': False,
        'size': (500, 0),
    },
    'giant_width': {
        'autocrop': False,
        'size': (800, 0),
    },
}}
### medium_width








def generate_mindstorm_settings(chrysalis_data_dir):

    # SELECT ONLY SOME FIXTURES, FOR MYSTERY PARTY

    _GAME_INITIAL_DATA_DIR = os.path.join(chrysalis_data_dir, "script_fixtures")
    assert os.path.isdir(_GAME_INITIAL_DATA_DIR)

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
        #radio_spots.yaml
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

    def GAME_INITIAL_FIXTURE_SCRIPT(dm):

        """ NOT ANYMORE
        # we give first player access to everything TEMPORARY
        player_name = "amethyst"
        assert not dm.get_character_properties(player_name)["is_npc"]
        dm.update_permissions(player_name, dm.PERMISSIONS_REGISTRY)
        """

        dm._set_user(dm.get_global_parameter("master_login"))  # to please some asserts...

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
            #"intercepted_messages",
            #"black_market",
            "business_escrow",
            #"chatroom",
            #"chess_challenge",
            "game_events",
            #"geoip_location",   # COULD be enabled!
            #"house_locking",
            "house_reports",
            "matter_analysis",
            "mercenaries_hiring",
            "personal_items_slideshow",
            "runic_translation",
            #"telecom_investigation",
            "view_sales",
            #"view_world_map_dynamic",
            #"wiretapping",  # IMPORTANT!!!
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
        email_predispatches = [  # format: (template_id, params, offset_days)
            ("lg_interview", dict(), -25),
            ("anonymous_threat_4", dict(), -20),
            ("lg_welcome_message", dict(), -19),
            ("waden_report_orb_analysis", dict(), -10),
            ("inspector_shark_arrival", dict(recipient_emails=[ml_address],), -7),
            ("security_measures", dict(recipient_emails=[ml_address],), -2),

            ("cynthia_location_description", dict(), -2),

            ("masslavian_initial_orb_hint", dict(), -1),
            ("dorian_initial_orb_hint", dict(), -1),
            ("lordanian_initial_orb_hint", dict(), -1),
            ("magnus_initial_orb_hint", dict(), -1),
            ("cynthia_initial_orb_hint", dict(), -1),
            ("sabarith_services_initial_instructions", dict(), -1),

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

        # initial objects
        dm.transfer_object_to_character("small_leather_bag", "loyd.georges")  # transfered by Rodok

        '''  # auction spots actually not included in YAML fixtures
        radio_spots = dm.radio_spots._table  # we bypass protections on "immutability"
        assert not dm.connection  # no need for transaction then
        for radio_spot in """
            01_news_auction_bidders_chosen
            10_commercial_anounces_weird
            20_alifir_conference_announce
            30_announce_nalavut_crisis_waves
            35_three_paintings_stolen
            40_news_council_explosion_alifir
            50_theft_alifir
            55_announce_lg_manor_theft
            62_news_akarith_riots
            64_news_alifir_blaze_&_councils
            65_wiremind_defeat_irony
            70_sabarim_riots_and_dorian_treason
            80_defeat_wiremind_standard
            """.split():
            del radio_spots[radio_spot]  # useless AUCTION-RELATED or REWRITTEN radio spots
        '''

    return (GAME_INITIAL_DATA_PATH, GAME_INITIAL_FIXTURE_SCRIPT)
