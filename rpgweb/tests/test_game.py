# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import os, sys, pytest



## TEST CONFIGURATION ##

os.environ["DJANGO_SETTINGS_MODULE"] = "rpgweb.tests._test_settings"
from django.conf import settings
settings._wrapped = None # forces lazy reloading, in case settings were already loaded

#from django.test.utils import setup_test_environment, teardown_test_environment
#setup_test_environment()
########################




from rpgweb.common import *

import rpgweb.datamanager as dm_module
from rpgweb.datamanager import *
from rpgweb.datamanager.datamanager_modules import *

import rpgweb.middlewares

# we want django-specific checker methods
# do NOT use the django.test.TestCase version, with SQL session management
from django.utils.unittest.case import TestCase 

from django.test.client import Client
import django.utils.translation

from rpgweb.abilities import *

if not config.DB_RESET_ALLOWED:
    raise RuntimeError("Can't launch tests - we must be in a production environment !!")





# dummy objects for delayed processing

def dummyfunc(*args, **kwargs):
    assert args
    assert kwargs


class dummyclass(object):
    def dummyfunc(self, *args, **kwargs):
        assert args
        assert kwargs



def for_datamanager_base(func):
    return func

def for_core_module(klass):
    # TODO - track proper testing of core module
    assert klass in MODULES_REGISTRY, klass
    return lambda func: func

def for_ability(klass):
    # TODO - track proper testing of ability module
    assert klass in SpecialAbilities.ABILITIES_REGISTRY.values(), klass
    return lambda func: func



TEST_GAME_INSTANCE_ID = "default"
ROOT_GAME_URL = "/rpgweb/%s" % TEST_GAME_INSTANCE_ID

sys.setrecursionlimit(120) # to help detect recursion problems

logging.basicConfig() ## FIXME
logging.disable(60)
logging.getLogger(0).setLevel(logging.DEBUG)











class TestUtilities(TestCase):


    def test_type_conversions(self):

        # test 1 #

        class dummy(object):
            def __init__(self):
                self.attr1 = ["hello"]
                self.attr2 = 34

        data = dict(abc=[1, 2, 3], efg=dummy(), hij=(1.0, 2), klm=set([8, ()]))

        newdata = utilities.convert_object_tree(data, utilities.python_to_zodb_types)

        self.assertTrue(isinstance(newdata, utilities.PersistentDict))
        self.assertEqual(len(newdata), len(data))

        self.assertTrue(isinstance(newdata["abc"], utilities.PersistentList))
        self.assertTrue(isinstance(newdata["efg"], dummy))
        self.assertEqual(newdata["hij"], (1.0, 2)) # immutable sequences not touched !

        self.assertEqual(len(newdata["efg"].__dict__), 2)
        self.assertTrue(isinstance(newdata["efg"].attr1, utilities.PersistentList))
        self.assertTrue(isinstance(newdata["efg"].attr2, (int, long)))

        self.assertEqual(newdata["klm"], set([8, ()]))

        # back-conversion
        newnewdata = utilities.convert_object_tree(newdata, utilities.zodb_to_python_types)
        self.assertEqual(data, newnewdata)


        # test 2 #

        data = utilities.PersistentDict(abc=utilities.PersistentList([1, 2, 3]))

        newdata = utilities.convert_object_tree(data, utilities.zodb_to_python_types)

        self.assertTrue(isinstance(newdata, dict))

        self.assertTrue(isinstance(newdata["abc"], list))

        newnewdata = utilities.convert_object_tree(newdata, utilities.python_to_zodb_types)

        self.assertEqual(data, newnewdata)



    def test_datetime_manipulations(self):

        self.assertRaises(Exception, utilities.compute_remote_datetime, (3, 2))

        for value in [0.025, (0.02, 0.03)]: # beware of the rounding to integer seconds...

            dt = utilities.compute_remote_datetime(value)

            self.assertEqual(utilities.is_past_datetime(dt), False)
            time.sleep(2)
            self.assertEqual(utilities.is_past_datetime(dt), True)

            utc = datetime.utcnow()
            now = datetime.now()
            now2 = utilities.utc_to_local(utc)

            self.assertTrue(now - timedelta(seconds=1) < now2 < now + timedelta(seconds=1))



TEST_ZODB_FILE = config.ZODB_FILE+".test" # let's not conflict with handle already open in middlewares, on config.ZODB_FILE



class AutoCheckingDM(object):
    """
    Dirty hack to automatically abort the ZODB transaction after each primary call to a datamanager method.

    This helps us ensure that we haven't forgotten the transaction watcher for any modifying operation.
    """

    def __init__(self, dm):
        object.__setattr__(self, "_real_dm", dm) # bypass overriding of __setattr__ below

    def __getattribute__(self, name):
        real_dm = object.__getattribute__(self, "_real_dm")
        attr = getattr(real_dm, name)
        if name.startswith("_") or not isinstance(attr, types.MethodType):
            return attr # data attribute
        else:
            # we wrap on the fly
            def _checked_method(*args, **kwargs):
                real_dm.commit() # we commit patches made from test suite...
                assert not real_dm.connection._registered_objects, real_dm.connection._registered_objects # BEFORE
                try:
                    res = attr(*args, **kwargs)
                finally:
                    assert not real_dm.connection._registered_objects, real_dm.connection._registered_objects # AFTER
                return res

            return _checked_method

    def __setattr__(self, name, value):
        return object.__getattribute__(self, "_real_dm").__setattr__(name, value)
            


class TestGame(TestCase):
    # WARNING - when directly modifying "self.dm.data" sub-objects, don't forget to commit() after !!

    # Also, test launching always sets "DEBUG" to False !!

    def setUp(self):
        django.utils.translation.activate("en") # to test for error messages, just in case...

        logging.basicConfig() # in case ZODB or others have things to say...
    
        self.db = utilities.open_zodb_file(TEST_ZODB_FILE)

        rpgweb.middlewares.ZODB_TEST_DB = self.db # to allow testing views via normal request dispatching

        self.connection = self.db.open()

        try:
            self.dm = dm_module.GameDataManager(game_instance_id=TEST_GAME_INSTANCE_ID,
                                                game_root=self.connection.root())

            self.dm.reset_game_data()

            self._inject_test_domain()
            self._inject_test_user()

            self.dm.check_database_coherency() # important

            self.dm.set_game_state(True)

            self.dm.clear_all_event_stats()

            #self.default_player = self.dm.get_character_usernames()[0]
            self._set_user(self.TEST_LOGIN)

            self.initial_msg_sent_length = len(self.dm.get_all_sent_messages())
            self.initial_msg_queue_length = len(self.dm.get_all_queued_messages())


            # comment this to have eclipse's autocompletion to work for datamanager anyway
            self.dm = AutoCheckingDM(self.dm) # protection against uncommitted, pending changes


            logging.disable(logging.CRITICAL) # to be commented if more output is wanted !!!

            self.client = Client()

        except:
            self.tearDown(check=False) # cleanup of db and connection in any case
            raise


    TEST_DOMAIN = "dummy_domain"
    def _inject_test_domain(self, name=TEST_DOMAIN, **overrides):
        return # TODO FIXME
        properties = dict(
                        show_official_identities=False,
                        victory="victory_masslavia",
                        defeat="defeat_masslavia",
                        prologue_music="prologue_masslavia.mp3",
                        instructions="blablablabla",
                        permissions=[]
                        )
        assert not (set(overrides.keys()) - set(properties.keys())) # don't inject unwanted params
        properties.update(overrides)

        properties = utilities.convert_object_tree(properties, utilities.python_to_zodb_types)
        self.dm.data["domains"][name] = properties
        self.dm.commit()


    TEST_LOGIN = "guy1" # because special private folders etc must exist. 
    def _inject_test_user(self, name=TEST_LOGIN, **overrides):
        return # TODO FIXME
        properties = dict(
                        password=name.upper(),
                        secret_question="What's the ultimate step of consciousness ?",
                        secret_answer="unguessableanswer",

                        domains=[self.TEST_DOMAIN],
                        permissions=[],

                        external_contacts=[],
                        new_messages_notification="new_messages_guy1",

                        account=1000,
                        initial_cold_cash=100,
                        gems=[],

                        official_name="Strange Character",
                        real_life_identity="John Doe",
                        real_life_email="john@doe.com",
                        description="Dummy test account",

                        last_online_time=None,
                        last_chatting_time=None
                       )

        assert not (set(overrides.keys()) - set(properties.keys())) # don't inject unwanted params
        properties.update(overrides)

        properties = utilities.convert_object_tree(properties, utilities.python_to_zodb_types)
        self.dm.data["character_properties"][name] = properties
        self.dm.commit()


    def tearDown(self, check=True):

        if hasattr(self, "dm") and check:
            self.dm.check_database_coherency()

        self.dm = None

        try: # FIXEME REMOVE
            self.connection.close()
        except:
            pass

        try: # FIXEME REMOVE
            self.db.close()
        except:
            pass

        rpgweb.middlewares.ZODB_TEST_DB = None

        ''' useless since we use a specific test DB
        # we empty the DB, so that at next restart the server resets its DBs automatically !
        for key in self.dm.data.keys():
            del self.dm.data[key]
        self.dm.commit()
        '''


    def _set_user(self, username):
        """
        *username* might be master or None, too. 
        """
        self.dm._set_user(username)


    def _reset_messages(self):
        self.dm.data["messages_sent"] = PersistentList()
        self.dm.data["messages_queued"] = PersistentList()
        self.dm.commit()


    @for_datamanager_base
    def test_modular_architecture(self):
        
        assert len(MODULES_REGISTRY) > 4
        
        for core_module in MODULES_REGISTRY:
            
            # we ensure every module calls super() properly
             
            CastratedDataManager = type(str('Dummy'+core_module.__name__), (core_module,), {})
            castrated_dm = CastratedDataManager.__new__(CastratedDataManager) # we bypass __init__() call there
            
            try:
                castrated_dm.__init__(game_instance_id=TEST_GAME_INSTANCE_ID,
                                      game_root=self.connection.root())
            except:
                pass
            assert castrated_dm.get_event_count("BASE_DATA_MANAGER_INIT_CALLED") == 1

            try:
                castrated_dm._load_initial_data()
            except:
                pass
            assert castrated_dm.get_event_count("BASE_LOAD_INITIAL_DATA_CALLED") == 1
                
            try:
                castrated_dm._check_database_coherency()
            except:
                pass
            assert castrated_dm.get_event_count("BASE_CHECK_DB_COHERENCY_CALLED") == 1

            try:
                report = PersistentList()
                castrated_dm._process_periodic_tasks(report)
            except:
                pass
            assert castrated_dm.get_event_count("BASE_PROCESS_PERIODIC_TASK_CALLED") == 1
                                       
             
            
            
    @for_core_module(CharacterHandling)
    def test_character_handling(self):
        
        assert self.dm.update_real_life_data("guy1", real_life_identity="jjjj") 
        assert self.dm.update_real_life_data("guy1", real_life_email="ss@pangea.com") 
        
        data = self.dm.get_character_properties("guy1")
        assert data["real_life_identity"] == "jjjj"
        assert data["real_life_email"] == "ss@pangea.com"
        
        assert self.dm.update_real_life_data("guy1", real_life_identity="kkkk", real_life_email="kkkk@pangea.com") 
        assert data["real_life_identity"] == "kkkk"
        assert data["real_life_email"] == "kkkk@pangea.com"    
    
        assert not self.dm.update_real_life_data("guy1", real_life_identity="", real_life_email=None)
        assert data["real_life_identity"] == "kkkk"
        assert data["real_life_email"] == "kkkk@pangea.com"          

        with pytest.raises(UsageError):
            self.dm.update_real_life_data("unexistinguy", real_life_identity="John")
            
        with pytest.raises(UsageError):
            self.dm.update_real_life_data("guy1", real_life_email="bad_email")


    @for_core_module(DomainHandling)
    def test_domain_handling(self):
        
        self.dm.update_allegiances("guy1", [])
        
        assert self.dm.update_allegiances("guy1", ["sciences"]) == (["sciences"], [])
        assert self.dm.update_allegiances("guy1", []) == ([], ["sciences"])
        assert self.dm.update_allegiances("guy1", ["sciences", "acharis"]) == (["acharis", "sciences"], []) # sorted
        assert self.dm.update_allegiances("guy1", ["sciences", "acharis"]) == ([], []) # no changes
             
        with pytest.raises(UsageError):
            self.dm.update_allegiances("guy1", ["dummydomain"])
            
        with pytest.raises(UsageError):
            self.dm.update_real_life_data("unexistinguy", real_life_identity=["sciences"])
            
            
    @for_core_module(OnlinePresence)
    def test_online_presence(self):

        self.dm.data["global_parameters"]["online_presence_timeout_s"] = 1
        self.dm.data["global_parameters"]["chatroom_presence_timeout_s"] = 1
        self.dm.commit()

        time.sleep(1.2)

        self.assertFalse(self.dm.get_online_status("guy1"))
        self.assertFalse(self.dm.get_online_status("guy2"))
        self.assertFalse(self.dm.get_chatting_status("guy1"))
        self.assertFalse(self.dm.get_chatting_status("guy2"))
        self.assertEqual(self.dm.get_online_users(), [])
        self.assertEqual(self.dm.get_chatting_users(), [])

        self.dm.set_online_status("guy1")

        self.assertTrue(self.dm.get_online_status("guy1"))
        self.assertFalse(self.dm.get_online_status("guy2"))
        self.assertFalse(self.dm.get_chatting_status("guy1"))
        self.assertFalse(self.dm.get_chatting_status("guy2"))
        self.assertEqual(self.dm.get_online_users(), ["guy1"])
        self.assertEqual(self.dm.get_chatting_users(), [])

        time.sleep(1.2)

        self.dm._set_chatting_status("guy2")
        self.dm.commit()

        self.assertFalse(self.dm.get_online_status("guy1"))
        self.assertFalse(self.dm.get_online_status("guy2"))
        self.assertFalse(self.dm.get_chatting_status("guy1"))
        self.assertTrue(self.dm.get_chatting_status("guy2"))
        self.assertEqual(self.dm.get_online_users(), [])
        self.assertEqual(self.dm.get_chatting_users(), ["guy2"])

        time.sleep(1.2)

        self.assertFalse(self.dm.get_online_status("guy1"))
        self.assertFalse(self.dm.get_online_status("guy2"))
        self.assertFalse(self.dm.get_chatting_status("guy1"))
        self.assertFalse(self.dm.get_chatting_status("guy2"))
        self.assertEqual(self.dm.get_online_users(), [])
        self.assertEqual(self.dm.get_chatting_users(), [])


    # todo - refactor this ?
    def test_getters_setters(self):
        self._reset_messages()

        self.assertEqual(self.dm.get_username_from_official_name(self.dm.get_official_name_from_username("guy2")), "guy2")

        # DEPRECATED self.assertEqual(self.dm.get_fellow_usernames("guy2"), ["guy1"])

        self.assertEqual(len(self.dm.get_game_instructions("guy2")), 3)

        self.dm.set_game_state(started=False)
        self.assertEqual(self.dm.is_game_started(), False)
        self.dm.set_game_state(started=True)
        self.assertEqual(self.dm.is_game_started(), True)

        self.assertEqual(self.dm.get_username_from_email("qdqsdqd@dqsd.fr"), self.dm.get_global_parameter("master_login"))
        self.assertEqual(self.dm.get_username_from_email("guy1@pangea.com"), "guy1")







    @for_core_module(MoneyItemsOwnership)
    def test_item_transfers(self):
        self._reset_messages()

        lg_old = copy.deepcopy(self.dm.get_character_properties("guy3"))
        nw_old = copy.deepcopy(self.dm.get_character_properties("guy1"))
        items_old = copy.deepcopy(self.dm.get_items_for_sale())
        bank_old = self.dm.get_global_parameter("bank_account")

        gem_names = [key for key, value in items_old.items() if value["is_gem"] and value["num_items"] >= 3] # we only take numerous groups
        object_names = [key for key, value in items_old.items() if not value["is_gem"]]

        gem_name1 = gem_names[0]
        gem_name2 = gem_names[1] # wont be sold
        object_name = object_names[0]
        bank_name = self.dm.get_global_parameter("bank_name")

        self.assertRaises(Exception, self.dm.transfer_money_between_characters, bank_name, "guy1", 10000000)
        self.assertRaises(Exception, self.dm.transfer_money_between_characters, "guy3", "guy1", -100)
        self.assertRaises(Exception, self.dm.transfer_money_between_characters, "guy3", "guy1", lg_old["account"] + 1)
        self.assertRaises(Exception, self.dm.transfer_money_between_characters, "guy3", "guy3", 1)
        self.assertRaises(Exception, self.dm.transfer_object_to_character, "dummy_name", "guy3")
        self.assertRaises(Exception, self.dm.transfer_object_to_character, object_name, "dummy_name")


        # data mustn't have changed when raising exceptions
        self.assertEqual(self.dm.get_character_properties("guy3"), lg_old)
        self.assertEqual(self.dm.get_character_properties("guy1"), nw_old)
        self.assertEqual(self.dm.get_items_for_sale(), items_old)
        self.assertEqual(self.dm.get_global_parameter("bank_account"), bank_old)

        # we check that real operations work OK
        self.dm.transfer_object_to_character(gem_name1, "guy3")
        self.dm.transfer_object_to_character(object_name, "guy3")
        self.dm.transfer_money_between_characters("guy3", "guy1", 100)

        self.dm.transfer_money_between_characters("guy3", "bank", 100)
        self.assertEqual(self.dm.get_global_parameter("bank_account"), bank_old + 100)
        self.assertEqual(self.dm.get_character_properties("guy3")["account"], lg_old["account"] - 200) # 100 to guy1 + 100 to bank
        self.dm.transfer_money_between_characters("bank", "guy3", 100)
        self.assertEqual(self.dm.get_global_parameter("bank_account"), bank_old)

        # we test gems transfers
        gems_given = self.dm.get_character_properties("guy3")["gems"][0:3]
        self.dm.transfer_gems_between_characters("guy3", "guy1", gems_given)
        self.dm.transfer_gems_between_characters("guy1", "guy3", gems_given)
        self.assertRaises(Exception, self.dm.transfer_gems_between_characters, "guy3", "guy1", gems_given + [27, 32])
        self.assertRaises(Exception, self.dm.transfer_gems_between_characters, "guy3", "guy1", [])

        items_new = copy.deepcopy(self.dm.get_items_for_sale())
        lg_new = self.dm.get_character_properties("guy3")
        nw_new = self.dm.get_character_properties("guy1")
        self.assertEqual(lg_new["items"], [gem_name1, object_name])
        self.assertEqual(lg_new["gems"], [items_new[gem_name1]["unit_cost"]] * items_new[gem_name1]["num_items"])
        self.assertEqual(items_new[gem_name1]["owner"], "guy3")
        self.assertEqual(items_new[object_name]["owner"], "guy3")
        self.assertEqual(lg_new["account"], lg_old["account"] - 100)
        self.assertEqual(nw_new["account"], nw_old["account"] + 100)


        # we test possible and impossible undo operations

        self.assertRaises(Exception, self.dm.undo_object_transfer, gem_name1, "network") # bad owner
        self.assertRaises(Exception, self.dm.undo_object_transfer, gem_name2, "guy3") # unsold item

        # check no changes occured
        self.assertEqual(self.dm.get_character_properties("guy3"), self.dm.get_character_properties("guy3"))
        self.assertEqual(self.dm.get_character_properties("guy1"), self.dm.get_character_properties("guy1"))
        self.assertEqual(self.dm.get_items_for_sale(), items_new)

        # undoing item sales
        self.dm.undo_object_transfer(gem_name1, "guy3")
        self.dm.undo_object_transfer(object_name, "guy3")
        self.dm.transfer_money_between_characters("guy1", "guy3", 100)

        # we're back to initial state
        self.assertEqual(self.dm.get_character_properties("guy3"), lg_old)
        self.assertEqual(self.dm.get_character_properties("guy1"), nw_old)
        self.assertEqual(self.dm.get_items_for_sale(), items_old)

        # undo failure
        self.dm.transfer_object_to_character(gem_name1, "guy3")
        gem = self.dm.get_character_properties("guy3")["gems"].pop()
        self.dm.commit()
        self.assertRaises(Exception, self.dm.undo_object_transfer, gem_name1, "guy3") # one gem is lacking, so...
        self.dm.get_character_properties("guy3")["gems"].append(gem)
        self.dm.commit()
        self.dm.undo_object_transfer(gem_name1, "guy3")

        self.assertEqual(self.dm.get_character_properties("guy3"), lg_old)
        self.assertEqual(self.dm.get_character_properties("guy1"), nw_old)
        self.assertEqual(self.dm.get_items_for_sale(), items_old)


    @for_core_module(MoneyItemsOwnership)
    def test_available_items_listing(self):
        self._reset_messages()

        items_old = copy.deepcopy(self.dm.get_items_for_sale())
        gem_names = [key for key, value in items_old.items() if value["is_gem"] and value["num_items"] >= 3] # we only take numerous groups
        object_names = [key for key, value in items_old.items() if not value["is_gem"]]

        gem_name1 = gem_names[0]
        gem_name2 = gem_names[1]
        object_name = object_names[0]

        self.dm.transfer_object_to_character(gem_name1, "guy2")
        self.dm.transfer_object_to_character(gem_name2, "guy2")
        self.dm.transfer_object_to_character(object_name, "guy3")

        self.assertEqual(self.dm.get_available_items_for_user("master"), self.dm.get_items_for_sale())
        self.assertEqual(set(self.dm.get_available_items_for_user("guy1").keys()), set([]))
        self.assertNotEqual(self.dm.get_available_items_for_user("guy2"), self.dm.get_available_items_for_user("guy1")) # no sharing of objects, even shared allegiance
        self.assertEqual(set(self.dm.get_available_items_for_user("guy2").keys()), set([gem_name1, gem_name2]))
        self.assertEqual(set(self.dm.get_available_items_for_user("guy3").keys()), set([object_name]))


    @for_ability(RunicTranslationAbility)
    def test_runic_translation(self):
        runic_translations = self.dm.abilities.runic_translations

        assert runic_translations.ability_data

        self._reset_messages()

        message = """ hi |there,   | how  are \t you # today,\n| buddy, # are you  \t\n okay ? """

        phrases = runic_translations._tokenize_rune_message(message)
        self.assertEqual(phrases, ['hi', 'there,', 'how are you', 'today,', 'buddy,', 'are you okay ?'])

        self.assertEqual(runic_translations._tokenize_rune_message(""), [])

        """ Too wrong and complicated...
        phrases = self.dm._tokenize_rune_message(message, left_to_right=True, top_to_bottom=False)
        self.assertEqual(phrases, ['are you okay ?', 'today,', 'buddy,', 'hi', 'there,', 'how are you'])

        phrases = self.dm._tokenize_rune_message(message, left_to_right=False, top_to_bottom=True)
        self.assertEqual(phrases, ['how are you', 'there,', 'hi' , 'buddy,', 'today,', 'are you okay ?'])

        phrases = self.dm._tokenize_rune_message(message, left_to_right=False, top_to_bottom=False)
        self.assertEqual(phrases, ['are you okay ?', 'buddy,', 'today,', 'how are you', 'there,', 'hi'])
        """

        translator = runic_translations._build_translation_dictionary("na | tsu | me",
                                                                      "yowh | man | cool")
        self.assertEqual(translator, dict(na="yowh", tsu="man", me="cool"))

        self.assertRaises(Exception, runic_translations._build_translation_dictionary, "na | tsu | me | no",
                          "yowh | man | cool")

        self.assertRaises(Exception, runic_translations._build_translation_dictionary, "me | tsu | me",
                          "yowh | man | cool")

        assert runic_translations.ability_data

        decoded_rune_string = "na  hu,  \t yo la\ttsu ri !\n go"
        translator = {"na hu": "welcome",
                      "yo la tsu": "people"}
        random_words = "hoy ma mi mo mu me".split()
        translated_tokens = runic_translations._try_translating_runes(decoded_rune_string, translator=translator, random_words=random_words)

        self.assertEqual(len(translated_tokens), 4, translated_tokens)
        self.assertEqual(translated_tokens[0:2], ["welcome", "people"])
        for translated_token in translated_tokens[2:4]:
            self.assertTrue(translated_token in random_words)

        # temporary solution to deal with currently untranslated runes... #FIXME
        available_translations = [(item_name, settings) for (item_name, settings) in runic_translations.get_ability_parameter("references").items() if settings["decoding"].strip()]
        (rune_item, translation_settings) = available_translations[0]

        transcription_attempt = translation_settings["decoding"] # '|' and '#'symbols are automatically cleaned
        expected_result = runic_translations._normalize_string(translation_settings["translation"].replace("#", " ").replace("|", " "))
        translation_result = runic_translations._translate_rune_message(rune_item, transcription_attempt)
        self.assertEqual(translation_result, expected_result)

        runic_translations._process_translation_submission("guy1", rune_item, transcription_attempt)

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["recipient_emails"], ["guy1@pangea.com"])
        self.assertTrue("translation" in msg["body"].lower())

        msgs = self.dm.get_all_sent_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["sender_email"], "guy1@pangea.com")
        self.assertTrue(transcription_attempt.strip() in msg["body"], (transcription_attempt, msg["body"]))
        self.assertTrue(self.dm.get_global_parameter("master_login") in msg["has_read"])



    @for_core_module(PersonalFiles)
    def test_personal_files(self):
        self._reset_messages()

        files1 = self.dm.get_personal_files("guy2", absolute_urls=True)
        self.assertTrue(len(files1))
        self.assertTrue(files1[0].startswith("http"))

        files1bis = self.dm.get_personal_files("guy2")
        self.assertEqual(len(files1), len(files1bis))
        self.assertTrue(files1bis[0].startswith("/"))

        files2 = self.dm.get_personal_files(None) # private game master files
        self.assertTrue(files2)

        c = Client() # file retrievals
        response = c.get(files1[0])
        self.assertEqual(response.status_code, 200)
        response = c.get(files1bis[0])
        self.assertEqual(response.status_code, 200)
        response = c.get(files1bis[0] + ".dummy")
        self.assertEqual(response.status_code, 404)

        for username in self.dm.get_character_usernames():
            self.dm.get_personal_files(username, absolute_urls=random.choice([True, False]))


    @for_core_module(PersonalFiles)
    def test_encrypted_folders(self):
        self._reset_messages()

        self.assertTrue(self.dm.encrypted_folder_exists("guy2_report"))
        self.assertFalse(self.dm.encrypted_folder_exists("dummyarchive"))

        self.assertRaises(dm_module.UsageError, self.dm.get_encrypted_files, "hacker", "dummyarchive", "bagheera")
        self.assertRaises(dm_module.UsageError, self.dm.get_encrypted_files, "hacker", "guy2_report", "badpassword")

        files = self.dm.get_encrypted_files("badusername", "guy2_report", "schamaalamoktuhg", absolute_urls=True) # no error raised for bad username !
        self.assertTrue(files, files)

        files1 = self.dm.get_encrypted_files("hacker", "guy2_report", "evans", absolute_urls=True)
        self.assertTrue(files1, files1)
        files2 = self.dm.get_encrypted_files("hacker", "guy2_report", "evans", absolute_urls=False)
        self.assertEqual(len(files1), len(files2))

        c = Client() # file retrievals
        response = c.get(files1[0])
        self.assertEqual(response.status_code, 200, (response.status_code, files1[0]))
        response = c.get(files2[0])
        self.assertEqual(response.status_code, 200)
        response = c.get(files2[0] + ".dummy")
        self.assertEqual(response.status_code, 404)


    def test_message_automated_state_changes(self):
        self._reset_messages()
        
        email = self.dm.get_character_email # function
        
        msg_id = self.dm.post_message(email("guy1"), email("guy2"), subject="ssd", body="qsdqsd")

        msg = self.dm.get_sent_message_by_id(msg_id)
        self.assertFalse(msg["has_replied"])
        self.assertFalse(msg["has_read"])
        
        # no strict checks on sender/recipient of original message, when using reply_to feature
        msg_id2 = self.dm.post_message(email("guy2"), email("guy1"), subject="ssd", body="qsdqsd", reply_to=msg_id)
        msg_id3 = self.dm.post_message(email("guy3"), email("guy2"), subject="ssd", body="qsdqsd", reply_to=msg_id)

        msg = self.dm.get_sent_message_by_id(msg_id2) # new message isn't impacted by reply_to
        self.assertFalse(msg["has_replied"])
        self.assertFalse(msg["has_read"])

        msg = self.dm.get_sent_message_by_id(msg_id) # replied-to message impacted
        self.assertEqual(len(msg["has_replied"]), 2)
        self.assertTrue("guy2" in msg["has_replied"])
        self.assertTrue("guy3" in msg["has_replied"])
        self.assertEqual(len(msg["has_read"]), 2)
        self.assertTrue("guy2" in msg["has_read"])
        self.assertTrue("guy3" in msg["has_read"])

        # -----

        (tpl_id, tpl) = self.dm.get_messages_templates().items()[0]
        self.assertEqual(tpl["is_used"], False)

        msg_id4 = self.dm.post_message(email("guy3"), email("guy1"), subject="ssd", body="qsdqsd", use_template=tpl_id)

        msg = self.dm.get_sent_message_by_id(msg_id4) # new message isn't impacted
        self.assertFalse(msg["has_replied"])
        self.assertFalse(msg["has_read"])

        tpl = self.dm.get_message_template(tpl_id)
        self.assertEqual(tpl["is_used"], True) # template properly marked as used

   
    @for_core_module(TextMessaging)
    def test_email_recipients_parsing(self):
        input1 = "guy1 , ; ; guy2@acharis.com , master, ; everyone ,master"
        input2 = ["everyone", "guy1@pangea.com", "guy2@acharis.com", "master@administration.com"]

        # unknown user login added
        self.assertRaises(dm_module.UsageError, self.dm._normalize_recipient_emails, input1 + " ; dummy value")

        recipients = self.dm._normalize_recipient_emails(input1)
        self.assertEqual(len(recipients), len(input2))
        self.assertEqual(set(recipients), set(input2))

        recipients = self.dm._normalize_recipient_emails(input2)
        self.assertEqual(len(recipients), len(input2))
        self.assertEqual(set(recipients), set(input2))



    @for_core_module(Chatroom)
    def test_chatroom_operations(self):

        self.assertEqual(self.dm.get_chatroom_messages(0), (0, None, []))

        self._set_user(None)
        self.assertRaises(dm_module.UsageError, self.dm.send_chatroom_message, " hello ")

        self._set_user("guy1")
        self.assertRaises(dm_module.UsageError, self.dm.send_chatroom_message, " ")

        self.assertEqual(self.dm.get_chatroom_messages(0), (0, None, []))

        self.dm.send_chatroom_message(" hello ! ")
        self.dm.send_chatroom_message(" re ")

        self._set_user("guy2")
        self.dm.send_chatroom_message("back")

        (slice_end, previous_msg_timestamp, msgs) = self.dm.get_chatroom_messages(0)
        self.assertEqual(slice_end, 3)
        self.assertEqual(previous_msg_timestamp, None)
        self.assertEqual(len(msgs), 3)

        self.assertEqual(sorted(msgs, key=lambda x: x["time"]), msgs)

        data = [(msg["username"], msg["message"]) for msg in msgs]
        self.assertEqual(data, [("guy1", "hello !"), ("guy1", "re"), ("guy2", "back")])

        (slice_end, previous_msg_timestamp, nextmsgs) = self.dm.get_chatroom_messages(3)
        self.assertEqual(slice_end, 3)
        self.assertEqual(previous_msg_timestamp, msgs[-1]["time"])
        self.assertEqual(len(nextmsgs), 0)

        (slice_end, previous_msg_timestamp, renextmsgs) = self.dm.get_chatroom_messages(2)
        self.assertEqual(slice_end, 3)
        self.assertEqual(previous_msg_timestamp, msgs[-2]["time"])
        self.assertEqual(len(renextmsgs), 1)
        data = [(msg["username"], msg["message"]) for msg in renextmsgs]
        self.assertEqual(data, [("guy2", "back")])



    def test_external_contacts(self):

        emails = self.dm.get_user_contacts(self.dm.get_global_parameter("master_login"))

        # guy1 and guy2 have 3 external contacts altogether, + 2 judicators @ implied by original sent msgs
        self.assertEqual(len(emails), len(self.dm.get_character_usernames()) + 5)  

        emails = self.dm.get_user_contacts("guy2")
        self.assertEqual(len(emails), len(self.dm.get_character_usernames()) + 2, emails) # himself & fellows, + 1 external contact + 1 implied by original msgs
        self.assertTrue("guy3@pangea.com" in emails) # proper domain name...

        emails = self.dm.get_user_contacts("guy3")
        self.assertEqual(len(emails), len(self.dm.get_character_usernames()), emails)
        emails = self.dm.get_external_emails("guy3")
        self.assertEqual(len(emails), 0, emails)
                

    def test_text_messaging(self):
        
        self._reset_messages()
        
        email = self.dm.get_character_email # function
        
        MASTER = self.dm.get_global_parameter("master_login")
        
        self.assertEqual(email("guy3"), "guy3@pangea.com")
        with pytest.raises(AssertionError):
            email("master") # not OK with get_character_email!


        record1 = {
            "sender_email": "guy2@pangea.com",
            "recipient_emails": ["guy3@pangea.com"],
            "subject": "hello everybody 1",
            "body": "Here is the body of this message lalalal...",
            "date_or_delay_mn":-1
        }

        record2 = {
            "sender_email": "guy4@pangea.com",
            "recipient_emails": ["secret-services@masslavia.com"],
            "subject": "hello everybody 2",
            "body": "Here is the body of this message lililili...",
            "attachment": "http://yowdlayhio",
            "date_or_delay_mn": 0
        }

        record3 = {
            "sender_email": "guy1@pangea.com",
            "recipient_emails": ["guy3@pangea.com"],
            "subject": "hello everybody 3",
            "body": "Here is the body of this message lulululu...",
            "date_or_delay_mn": None
            # "origin": "dummy-msg-id"  # shouldn't raise error - the problem is just logged
        }

        record4 = {
            "sender_email": "dummy-robot@masslavia.com",
            "recipient_emails": ["guy2@pangea.com"],
            "subject": "hello everybody 4",
            "body": "Here is the body of this message lililili...",
            }

        self.dm.post_message("guy1@masslavia.com", "netsdfworkerds@masslavia.com", subject="ssd", body="qsdqsd") # this works too !
        self.assertEqual(len(self.dm.get_game_master_messages()), 1)
        self.dm.get_game_master_messages()[0]["has_read"] = utilities.PersistentList(
            self.dm.get_character_usernames() + [self.dm.get_global_parameter("master_login")]) # we hack this message not to break following assertions

        self.dm.post_message(**record1)
        time.sleep(0.2)

        self.dm.set_wiretapping_targets("guy1", ["guy2"])
        self.dm.set_wiretapping_targets("guy2", ["guy4"])
        
        self.dm.post_message(**record2)
        time.sleep(0.2)
        self.dm.post_message(**record3)
        time.sleep(0.2)
        self.dm.post_message(**record4)
        time.sleep(0.2)
        self.dm.post_message(**record1) # this message will get back to the 2nd place of list !

        self.assertEqual(self.dm.get_unread_messages_count("guy3"), 3)

        self.assertEqual(self.dm.get_unread_messages_count(self.dm.get_global_parameter("master_login")), 1)

        self.assertEqual(len(self.dm.get_all_sent_messages()), 6)

        self.assertEqual(len(self.dm.get_game_master_messages()), 2) # secret services + wrong email address

        expected_notifications = {'guy2': "new_messages_2", 'guy3': "new_messages_1"}
        self.assertEqual(self.dm.get_pending_new_message_notifications(), expected_notifications)

        self.assertEqual(self.dm.get_pending_new_message_notifications(), expected_notifications) # no disappearance

        self.assertTrue(self.dm.has_new_message_notification("guy3"))
        self.assertEqual(len(self.dm.get_received_messages("guy3@pangea.com", reset_notification=True)), 3)
        self.assertFalse(self.dm.has_new_message_notification("guy3"))

        # here we can't do check messages of secret-services@masslavia.com since it's not a normal character

        self.assertTrue(self.dm.has_new_message_notification("guy2"))
        self.assertEqual(len(self.dm.get_received_messages("guy2@pangea.com", reset_notification=False)), 1)
        self.assertTrue(self.dm.has_new_message_notification("guy2"))
        self.dm.set_new_message_notification(utilities.PersistentList(["guy2@pangea.com"]), new_status=False)
        self.assertFalse(self.dm.has_new_message_notification("guy2"))

        self.assertEqual(self.dm.get_pending_new_message_notifications(), {}) # all have been reset

        self.assertEqual(len(self.dm.get_received_messages(self.dm.get_character_email("guy1"))), 0)

        self.assertEqual(len(self.dm.get_sent_messages("guy2@pangea.com")), 2)
        self.assertEqual(len(self.dm.get_sent_messages("guy1@pangea.com")), 1)
        self.assertEqual(len(self.dm.get_sent_messages("guy3@pangea.com")), 0)

        assert not self.dm.get_intercepted_messages("guy3")
        
        res = self.dm.get_intercepted_messages("guy1")
        self.assertEqual(len(res), 2)
        self.assertEqual(set([msg["subject"] for msg in res]), set(["hello everybody 1", "hello everybody 4"]))
        assert all(["guy1" in msg["intercepted_by"] for msg in res])
        
        res = self.dm.get_intercepted_messages()
        self.assertEqual(len(res), 3)
        self.assertEqual(set([msg["subject"] for msg in res]), set(["hello everybody 1", "hello everybody 2", "hello everybody 4"]))
        assert all([msg["intercepted_by"] for msg in res])     
           
        # NO - we dont notify interceptions - self.assertTrue(self.dm.get_global_parameter("message_intercepted_audio_id") in self.dm.get_all_next_audio_messages(), self.dm.get_all_next_audio_messages())

        # msg has_read state changes
        msg_id1 = self.dm.get_all_sent_messages()[0]["id"] # sent to guy3
        msg_id2 = self.dm.get_all_sent_messages()[3]["id"] # sent to external contact

        """ # NO PROBLEM with wrong msg owner
        self.assertRaises(Exception, self.dm.set_message_read_state, MASTER, msg_id1, True)
        self.assertRaises(Exception, self.dm.set_message_read_state, "guy2", msg_id1, True)
        self.assertRaises(Exception, self.dm.set_message_read_state, "guy1", msg_id2, True)
        """
        
        # wrong msg id
        self.assertRaises(Exception, self.dm.set_message_read_state, "dummyid", False)
   

        #self.assertEqual(self.dm.get_all_sent_messages()[0]["no_reply"], False)
        #self.assertEqual(self.dm.get_all_sent_messages()[4]["no_reply"], True)# msg from robot

        self.assertEqual(self.dm.get_all_sent_messages()[0]["is_certified"], False)
        self.assertFalse(self.dm.get_all_sent_messages()[0]["has_read"])
        self.dm.set_message_read_state("guy3", msg_id1, True)
        self.dm.set_message_read_state("guy2", msg_id1, True)

        self.assertEqual(len(self.dm.get_all_sent_messages()[0]["has_read"]), 2)
        self.assertTrue("guy2" in self.dm.get_all_sent_messages()[0]["has_read"])
        self.assertTrue("guy3" in self.dm.get_all_sent_messages()[0]["has_read"])

        self.assertEqual(self.dm.get_unread_messages_count("guy3"), 2)
        self.dm.set_message_read_state("guy3", msg_id1, False)
        self.assertEqual(self.dm.get_all_sent_messages()[0]["has_read"], ["guy2"])
        self.assertEqual(self.dm.get_unread_messages_count("guy3"), 3)

        self.assertFalse(self.dm.get_all_sent_messages()[3]["has_read"])
        self.dm.set_message_read_state(MASTER, msg_id2, True)
        self.assertTrue(MASTER in self.dm.get_all_sent_messages()[3]["has_read"])
        self.assertEqual(self.dm.get_unread_messages_count(self.dm.get_global_parameter("master_login")), 0)
        self.dm.set_message_read_state(MASTER, msg_id2, False)
        self.assertFalse(self.dm.get_all_sent_messages()[3]["has_read"])
        self.assertEqual(self.dm.get_unread_messages_count(self.dm.get_global_parameter("master_login")), 1)




    def test_audio_messages_management(self):
        self._reset_messages()
        
        email = self.dm.get_character_email # function
        
        self.assertRaises(dm_module.UsageError, self.dm.check_radio_frequency, "dummyfrequency")
        self.assertEqual(self.dm.check_radio_frequency(self.dm.get_global_parameter("pangea_radio_frequency")), None) # no exception nor return value

        self.dm.set_radio_state(is_on=True)
        self.assertEqual(self.dm.get_global_parameter("radio_is_on"), True)
        self.dm.set_radio_state(is_on=False)
        self.assertEqual(self.dm.get_global_parameter("radio_is_on"), False)
        self.dm.set_radio_state(is_on=True)
        self.assertEqual(self.dm.get_global_parameter("radio_is_on"), True)

        record1 = {
            "sender_email": email("guy2"),
            "recipient_emails": [email("guy3")],
            "subject": "hello everybody 1",
            "body": "Here is the body of this message lalalal...",
            "date_or_delay_mn":-1
        }

        self.dm.post_message(**record1)

        res = self.dm.get_pending_new_message_notifications()
        self.assertEqual(len(res), 1)
        (username, audio_id) = res.items()[0]
        self.assertEqual(username, "guy3")

        properties = self.dm.get_audio_message_properties(audio_id)
        self.assertEqual(set(properties.keys()), set(["text", "file", "url"]))

        #self.assertEqual(properties["new_messages_notification_for_user"], "guy3")
        #self.assertEqual(self.dm.get_audio_message_properties("request_for_report_teldorium")["new_messages_notification_for_user"], None)

        self.assertEqual(len(self.dm.get_all_next_audio_messages()), 0)

        self.dm.add_radio_message(audio_id)
        self.assertEqual(self.dm.get_next_audio_message(), audio_id)
        self.assertEqual(self.dm.get_next_audio_message(), audio_id) # no disappearance

        self.assertEqual(len(self.dm.get_all_next_audio_messages()), 1)

        self.dm.reset_audio_messages()
        self.assertEqual(self.dm.get_next_audio_message(), None)

        self.assertEqual(len(self.dm.get_all_next_audio_messages()), 0)

        audio_id_bis = self.dm.get_character_properties("guy2")["new_messages_notification"]
        audio_id_ter = self.dm.get_character_properties("guy1")["new_messages_notification"]

        self.assertRaises(dm_module.UsageError, self.dm.add_radio_message, "bad_audio_id")
        self.dm.add_radio_message(audio_id)
        self.dm.add_radio_message(audio_id) # double adding == NO OP
        self.dm.add_radio_message(audio_id_bis)
        self.dm.add_radio_message(audio_id_ter)

        self.assertEqual(len(self.dm.get_all_next_audio_messages()), 3)

        self.assertEqual(self.dm.get_next_audio_message(), audio_id)

        self.dm.notify_audio_message_termination("bad_audio_id") # no error, we just ignore it

        self.dm.notify_audio_message_termination(audio_id_ter)# removing trailing one works

        self.dm.notify_audio_message_termination(audio_id)

        self.assertEqual(self.dm.get_global_parameter("radio_is_on"), True)

        self.assertEqual(self.dm.get_next_audio_message(), audio_id_bis)
        self.dm.notify_audio_message_termination(audio_id_bis)

        self.assertEqual(self.dm.get_global_parameter("radio_is_on"), False) # auto extinction of radio

        self.assertEqual(self.dm.get_next_audio_message(), None)
        self.assertEqual(len(self.dm.get_all_next_audio_messages()), 0)

        
    def test_delayed_message_processing(self):
        self._reset_messages()

        email = self.dm.get_character_email # function
        
        # delayed message sending

        self.dm.post_message(email("guy3"), email("guy2"), "yowh1", "qhsdhqsdh", attachment=None, date_or_delay_mn=0.03)
        self.assertEqual(len(self.dm.get_all_sent_messages()), 0)
        queued_msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(queued_msgs), 1)
        #print datetime.utcnow(), " << ", queued_msgs[0]["sent_at"]
        self.assertTrue(datetime.utcnow() < queued_msgs[0]["sent_at"] < datetime.utcnow() + timedelta(minutes=0.22))

        self.dm.post_message(email("guy3"), email("guy2"), "yowh2", "qhsdhqsdh", attachment=None, date_or_delay_mn=(0.04, 0.05)) # 3s delay range
        self.assertEqual(len(self.dm.get_all_sent_messages()), 0)
        queued_msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(queued_msgs), 2)
        self.assertEqual(queued_msgs[1]["subject"], "yowh2", queued_msgs)
        #print datetime.utcnow(), " >> ", queued_msgs[1]["sent_at"]
        self.assertTrue(datetime.utcnow() < queued_msgs[1]["sent_at"] < datetime.utcnow() + timedelta(minutes=0.06))

        # delayed message processing

        self.dm.post_message(email("guy3"), email("guy2"), "yowh3", "qhsdhqsdh", attachment=None, date_or_delay_mn=0.01) # 0.6s
        self.assertEqual(len(self.dm.get_all_queued_messages()), 3)
        self.assertEqual(len(self.dm.get_all_sent_messages()), 0)
        res = self.dm.process_periodic_tasks()
        self.assertEqual(res["messages_sent"], 0)
        self.assertEqual(res["actions_executed"], 0)
        self.assertEqual(len(self.dm.get_all_sent_messages()), 0)

        time.sleep(0.8) # one message OK

        res = self.dm.process_periodic_tasks()
        #print self.dm.get_all_sent_messages(), datetime.utcnow()
        self.assertEqual(res["messages_sent"], 1)
        self.assertEqual(res["actions_executed"], 0)
        self.assertEqual(len(self.dm.get_all_sent_messages()), 1)
        self.assertEqual(len(self.dm.get_all_queued_messages()), 2)

        time.sleep(2.5) # last messages OK

        res = self.dm.process_periodic_tasks()
        self.assertEqual(res["messages_sent"], 2)
        self.assertEqual(res["actions_executed"], 0)
        self.assertEqual(len(self.dm.get_all_sent_messages()), 3)
        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        # due to the strength of coherency checks, it's about impossible to enforce a sending here here...
        self.assertEqual(self.dm.get_event_count("DELAYED_MESSAGE_ERROR"), 0)



        # forced sending of queued messages
        myid1 = self.dm.post_message(email("guy3"), email("guy2"), "yowh2", "qhsdhqsdh", attachment=None, date_or_delay_mn=(1, 2)) # 3s delay range
        myid2 = self.dm.post_message(email("guy3"), email("guy2"), "yowh2", "qhsdhqsdh", attachment=None, date_or_delay_mn=(1, 2)) # 3s delay range
        self.assertEqual(len(self.dm.get_all_queued_messages()), 2)

        self.assertFalse(self.dm.force_message_sending("dummyid"))
        self.assertTrue(self.dm.force_message_sending(myid1))
        self.assertEqual(len(self.dm.get_all_queued_messages()), 1)
        self.assertFalse(self.dm.force_message_sending(myid1)) # already sent now
        self.assertEqual(self.dm.get_all_queued_messages()[0]["id"], myid2)
        self.assertTrue(self.dm.get_sent_message_by_id(myid1))

        
     
        
    def test_delayed_action_processing(self):

        def _dm_delayed_action(arg1):
            self.dm.data["global_parameters"]["stuff"] = 23
            self.dm.commit()
        self.dm._dm_delayed_action = _dm_delayed_action # attribute of that precise instane, not class!
        
        self.dm.schedule_delayed_action(0.01, dummyfunc, 12, item=24)
        self.dm.schedule_delayed_action((0.04, 0.05), dummyfunc) # will raise error
        self.dm.schedule_delayed_action((0.035, 0.05), "_dm_delayed_action", "hello")
 
        res = self.dm.process_periodic_tasks()
        self.assertEqual(res["actions_executed"], 0)

        time.sleep(0.7)

        res = self.dm.process_periodic_tasks()
        self.assertEqual(res["actions_executed"], 1)

        self.assertEqual(self.dm.get_event_count("DELAYED_ACTION_ERROR"), 0)
        assert self.dm.data["global_parameters"].get("stuff") is None
        
        time.sleep(2.5)

        res = self.dm.process_periodic_tasks()
        self.assertEqual(res["actions_executed"], 2)

        self.assertEqual(len(self.dm.data["scheduled_actions"]), 0)

        self.assertEqual(self.dm.get_event_count("DELAYED_ACTION_ERROR"), 1) # error raised but swallowed
        assert self.dm.data["global_parameters"]["stuff"] == 23
 
 

    @for_core_module(PlayerAuthentication)
    def test_password_recovery(self):
        self._reset_messages()

        res = self.dm.get_secret_question("guy3")
        self.assertTrue("pet" in res)

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)
        res = self.dm.process_secret_answer_attempt("guy3", "FluFFy", "guy3@pangea.com")
        self.assertEqual(res, "awesome") # password

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertTrue("password" in msg["body"].lower())

        self.assertRaises(dm_module.UsageError, self.dm.process_secret_answer_attempt, "badusername", "badanswer", "guy3@sciences.com")
        self.assertRaises(dm_module.UsageError, self.dm.process_secret_answer_attempt, "guy3", "badanswer", "guy3@sciences.com")
        self.assertRaises(dm_module.UsageError, self.dm.process_secret_answer_attempt, "guy3", "MiLoU", "bademail@sciences.com")
        self.assertEqual(len(self.dm.get_all_queued_messages()), 1) # untouched


    @for_core_module(GameEvents)
    def test_event_logging(self):
        self._reset_messages()
        
        self._set_user("guy1")
        self.assertEqual(self.dm.get_game_events(), [])
        self.dm.log_game_event("hello there 1")
        self._set_user("master")
        self.dm.log_game_event("hello there 2", url="/my/url/")
        self.dm.commit()
        events = self.dm.get_game_events()
        self.assertEqual(len(events), 2)

        self.assertEqual(events[0]["message"], "hello there 1")
        self.assertEqual(events[0]["username"], "guy1")
        self.assertEqual(events[0]["url"], None)
        self.assertEqual(events[1]["message"], "hello there 2")
        self.assertEqual(events[1]["username"], "master")
        self.assertEqual(events[1]["url"], "/my/url/")

        utcnow = datetime.utcnow()
        for event in events:
            self.assertTrue(utcnow - timedelta(seconds=2) < event["time"] <= utcnow)


    @for_ability(HouseLockingAbility)
    def test_house_locking(self):

        house_locking = self.dm.abilities.house_locking
        expected_password = house_locking.get_ability_parameter("house_doors_password")

        self.assertEqual(house_locking.are_house_doors_open(), True) # initial state

        self.assertTrue(house_locking.lock_house_doors())
        self.assertEqual(house_locking.are_house_doors_open(), False)

        self.assertFalse(house_locking.lock_house_doors()) # already locked
        self.assertEqual(house_locking.are_house_doors_open(), False)

        self.assertFalse(house_locking.try_unlocking_house_doors(password="blablabla"))
        self.assertEqual(house_locking.are_house_doors_open(), False)

        self.assertTrue(house_locking.try_unlocking_house_doors(password=expected_password))
        self.assertEqual(house_locking.are_house_doors_open(), True)




    @for_datamanager_base
    def test_database_management(self):
        self._reset_messages()

        # test "reset databases" too, in the future
        res = self.dm.dump_zope_database()
        assert isinstance(res, basestring) and len(res) > 1000


    def _master_logging(self):
        login_page = reverse("rpgweb.views.login", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        response = self.client.get(login_page) # to set preliminary cookies
        self.assertEqual(response.status_code, 200)

        response = self.client.post(login_page, data=dict(secret_username=self.dm.get_global_parameter("master_login"), secret_password=self.dm.get_global_parameter("master_password")))

        self.assertEqual(response.status_code, 302)

        if self.dm.is_game_started():
            self.assertRedirects(response, ROOT_GAME_URL + "/")
        else:
            self.assertRedirects(response, ROOT_GAME_URL + "/opening/") # beautiful intro for days before the game starts

        self.assertTrue(self.client.cookies["sessionid"])


    def _player_logging(self, username):
        login_page = reverse("rpgweb.views.login", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        response = self.client.get(login_page) # to set preliminary cookies
        self.assertEqual(response.status_code, 200)

        response = self.client.post(login_page, data=dict(secret_username=username, secret_password=self.dm.get_character_properties(username)["password"]))

        self.assertEqual(response.status_code, 302)
        if self.dm.is_game_started():
            self.assertRedirects(response, ROOT_GAME_URL + "/")
        else:
            self.assertRedirects(response, ROOT_GAME_URL + "/opening/") # beautiful intro for days before the game starts

        self.assertTrue(self.client.cookies["sessionid"])


    def _unlog(self):
        login_page = reverse("rpgweb.views.login", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        logout_page = reverse("rpgweb.views.logout", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        response = self.client.get(logout_page) # to set preliminary cookies

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, login_page)

        self.assertEqual(self.client.session.keys(), ["testcookie"]) # we get it once more


    def _simple_master_get_requests(self):
        self.dm.data["global_parameters"]["online_presence_timeout_s"] = 1
        self.dm.data["global_parameters"]["chatroom_presence_timeout_s"] = 1
        self.dm.commit()
        time.sleep(1.2) # online/chatting users list gets emptied

        self._master_logging()

        from django.core.urlresolvers import RegexURLResolver
        from urls import final_urlpatterns

        skipped_patterns = "DATABASE_OPERATIONS FAIL_TEST ajax item_3d_view chat_with_djinn static.serve encrypted_folder view_single_message logout login secret_question".split()
        views = [url._callback_str for url in final_urlpatterns if not isinstance(url, RegexURLResolver) and not [veto for veto in skipped_patterns if veto in url._callback_str]]
        #print views

        for view in views:
            url = reverse(view, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
            #print " ====> ", url
            response = self.client.get(url)
            #print response.content
            self.assertEqual(response.status_code, 200, view + " | " + url + " | " + str(response.status_code))


        # these urls and their post data might easily change, beware !
        special_urls = {ROOT_GAME_URL + "/item3dview/sacred_book/": None,
                        ROOT_GAME_URL + "/djinn/": {"djinn": "Pay Rhuss"},
                        config.MEDIA_URL + "Burned/default_styles.css": None,
                        config.GAME_FILES_URL + "attachments/antic_runes.gif": None,
                        config.GAME_FILES_URL + "encrypted/guy2_report/evans/report.rtf": None,
                        ROOT_GAME_URL + "/messages/view_single_message/instructions_listener/": None,
                        ROOT_GAME_URL + "/secret_question/": dict(secret_answer="Milou", target_email="listener@teldorium.com", secret_username="guy3"),
                        ROOT_GAME_URL + "/webradio_applet/": dict(frequency=self.dm.get_global_parameter("pangea_radio_frequency"))
        }
        for url, value in special_urls.items():
            #print ">>>>>>", url

            if value:
                response = self.client.post(url, data=value)
            else:
                response = self.client.get(url)

            # print "WE TRY TO LOAD ", url
            self.assertNotContains(response, 'class="error_notifications"', msg_prefix=response.content)
            self.assertEqual(response.status_code, 200, url + " | " + str(response.status_code))


        # no directory index !
        response = self.client.get("/media/")
        self.assertEqual(response.status_code, 404)
        response = self.client.get("/files/")
        self.assertEqual(response.status_code, 404)

        self.assertEqual(self.dm.get_online_users(), [])
        self.assertEqual(self.dm.get_chatting_users(), [])

        self._unlog()


    def ___test_master_game_started_page_displays(self):
        self.dm.set_game_state(True)
        self._simple_master_get_requests()

    def ___test_master_game_paused_page_displays(self):
        self.dm.set_game_state(False)
        self._simple_master_get_requests()


    def _test_player_get_requests(self):
        #def get_allowed_user(permission):
        #    return [name for name, value in self.dm.get_character_sets().items() if permission in value["permissions"]][0]

        self.dm.data["global_parameters"]["online_presence_timeout_s"] = 1
        self.dm.data["global_parameters"]["chatroom_presence_timeout_s"] = 1
        self.dm.commit()
        time.sleep(1.2) # online/chatting users list gets emptied

        # PLAYER SETUP
        old_state = self.dm.is_game_started()
        self.dm.set_game_state(True)
        username = "guy2"
        user_money = self.dm.get_character_properties(username)["account"]
        if user_money:
            self.dm.transfer_money_between_characters(username, self.dm.get_global_parameter("bank_name"), user_money) # we empty money
        self.dm.data["character_properties"][username]["permissions"] = PersistentList(["contact_djinns", "manage_agents", "manage_wiretaps"]) # we grant all necessary permissions
        self.dm.commit()
        self.dm.set_game_state(old_state)
        self._player_logging(username)


        # VIEWS SELECTION
        from django.core.urlresolvers import RegexURLResolver
        from urls import final_urlpatterns
        # we test views for which there is a distinction between master and player
        selected_patterns = "inbox outbox compose_message intercepted_messages view_sales items_slideshow network_management personal_radio_messages_listing contact_djinns".split()
        views = [url._callback_str for url in final_urlpatterns if not isinstance(url, RegexURLResolver) and [match for match in selected_patterns if match in url._callback_str]]

        def test_views(views):
            for view in views:
                url = reverse(view, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
                response = self.client.get(url)
                #print response.content
                self.assertEqual(response.status_code, 200, view + " | " + url + " | " + str(response.status_code))

        test_views(views)

        old_state = self.dm.is_game_started()
        self.dm.set_game_state(True)
        self.dm.transfer_money_between_characters(self.dm.get_global_parameter("bank_name"), username, 1000)
        self.dm.set_game_state(old_state)

        test_views(views)

        old_state = self.dm.is_game_started()
        self.dm.set_game_state(True)
        gem_name = [key for key, value in self.dm.get_items_for_sale().items() if value["is_gem"] and value["num_items"] >= 6][0] # we only take numerous groups
        self.dm.transfer_object_to_character(gem_name, username)
        self.dm.set_game_state(old_state)

        test_views(views)

        self.assertEqual(self.dm.get_online_users(), [username])
        self.assertEqual(self.dm.get_chatting_users(), [])

        self._unlog()


    def __test_player_game_started_page_displays(self):
        self.dm.set_game_state(True)
        #print "STARTING"
        #import timeit
        #timeit.Timer(self._test_player_get_requests).timeit()
        self._test_player_get_requests()
        #print "OVER"

    def __test_player_game_paused_page_displays(self):
        self.dm.set_game_state(False)
        self._test_player_get_requests()



















class SpecialAbilityTests(object):




    def __test_telecom_investigations(self):
        # no reset of initial messages


        initial_length_queued_msgs = len(self.dm.get_all_queued_messages())
        initial_length_sent_msgs = len(self.dm.get_all_sent_messages())


        # text processing #

        res = self.dm._corrupt_text_parts("hello ca va bien coco?", (1, 1), "")
        self.assertEqual(res, "hello ... va ... coco?")

        msg = "hello ca va bien coco? Quoi de neuf ici ? Tout est OK ?"
        res = self.dm._corrupt_text_parts(msg, (2, 4), "de neuf ici")
        self.assertTrue("de neuf ici" in res, res)
        self.assertTrue(14 < len(res) < len(msg), len(res))


        # corruption of team intro + personal instructions
        text = self.dm._get_corrupted_introduction("guy2", "SiMoN  BladstaFfulOvza")

        dump = set(text.split())
        parts1 = set(u"Depuis , notre Ordre Acharite fouille Ciel Terre retrouver Trois Orbes".split())
        parts2 = set(u"votre drogues sera aide inestimable cette mission".split())

        self.assertTrue(len(dump ^ parts1) > 2)
        self.assertTrue(len(dump ^ parts2) > 2)

        self.assertTrue("Simon Bladstaffulovza" in text, repr(text))



        # whole inquiry requests

        telecom_investigations_done = self.dm.get_global_parameter("telecom_investigations_done")
        self.assertEqual(telecom_investigations_done, 0)
        max_telecom_investigations = self.dm.get_global_parameter("max_telecom_investigations")

        self.assertRaises(dm_module.UsageError, self.dm.launch_telecom_investigation, "guy2", "guy2")

        self.assertEqual(len(self.dm.get_all_queued_messages()), initial_length_queued_msgs + 0)

        self.dm.launch_telecom_investigation("guy2", "guy2")

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), initial_length_queued_msgs + 1)
        msg = msgs[-1]
        self.assertEqual(msg["recipient_emails"], ["guy2@sciences.com"])

        msgs = self.dm.get_all_sent_messages()
        self.assertEqual(len(msgs), initial_length_sent_msgs + 1)
        msg = msgs[-1]
        self.assertEqual(msg["sender_email"], "guy2@sciences.com")
        self.assertTrue("discover" in msg["body"])
        self.assertTrue(self.dm.get_global_parameter("master_login") in msg["has_read"])

        for i in range(max_telecom_investigations - 1):
            self.dm.launch_telecom_investigation("guy2", "guy3")
        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), initial_length_queued_msgs + max_telecom_investigations)

        self.assertRaises(dm_module.UsageError, self.dm.launch_telecom_investigation, "guy2", "guy3") # max count exceeded


    def ___test_agent_hiring(self):
        self._reset_messages()

        spy_cost_money = self.dm.get_global_parameter("spy_cost_money")
        spy_cost_gems = self.dm.get_global_parameter("spy_cost_gems")
        mercenary_cost_money = self.dm.get_global_parameter("mercenary_cost_money")
        mercenary_cost_gems = self.dm.get_global_parameter("mercenary_cost_gems")

        self.dm.get_character_properties("guy1")["gems"] = PersistentList([spy_cost_gems, spy_cost_gems, spy_cost_gems, mercenary_cost_gems])
        self.dm.commit()

        cities = self.dm.get_locations().keys()[0:5]


        # hiring with gems #


        self.assertRaises(Exception, self.dm.hire_remote_agent, "guy1",
                          cities[0], mercenary=False, pay_with_gems=True)

        self.assertRaises(Exception, self.dm.hire_remote_agent, "guy1",
                          cities[0], mercenary=True, pay_with_gems=True, gems_list=[spy_cost_gems]) # mercenary more expensive than spy
        self.assertRaises(Exception, self.dm.hire_remote_agent, "guy1",
                          cities[0], mercenary=False, pay_with_gems=True, gems_list=[mercenary_cost_gems, mercenary_cost_gems])

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        self.dm.hire_remote_agent("guy1", cities[0], mercenary=False, pay_with_gems=True, gems_list=[spy_cost_gems])
        self.assertRaises(Exception, self.dm.hire_remote_agent, "guy1", cities[0],
                          mercenary=False, pay_with_gems=True, gems_list=[spy_cost_gems])

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["recipient_emails"], ["guy1@masslavia.com"])
        self.assertTrue("report" in msg["body"].lower())

        self.dm.hire_remote_agent("guy1", cities[1], mercenary=True, pay_with_gems=True, gems_list=[spy_cost_gems, spy_cost_gems, mercenary_cost_gems])
        self.assertEqual(self.dm.get_character_properties("guy1")["gems"], [])

        self.assertEqual(len(self.dm.get_all_queued_messages()), 1)

        # hiring with money #
        old_nw_account = self.dm.get_character_properties("guy1")["account"]
        self.dm.transfer_money_between_characters("guy3", "guy1", 2 * mercenary_cost_money) # loyd must have at least that on his account

        self.assertRaises(Exception, self.dm.hire_remote_agent, "guy1",
                          cities[0], mercenary=True, pay_with_gems=False, gems_list=[mercenary_cost_gems])

        self.dm.hire_remote_agent("guy1", cities[2], mercenary=False, pay_with_gems=False)
        self.dm.hire_remote_agent("guy1", cities[2], mercenary=True, pay_with_gems=False)
        self.assertEqual(self.dm.get_locations()[cities[2]]["has_mercenary"], True)
        self.assertEqual(self.dm.get_locations()[cities[2]]["has_spy"], True)

        self.assertEqual(self.dm.get_character_properties("guy1")["account"], old_nw_account + mercenary_cost_money - spy_cost_money)

        self.dm.transfer_money_between_characters("guy1", "guy3", self.dm.get_character_properties("guy1")["account"]) # we empty the account

        self.assertRaises(Exception, self.dm.hire_remote_agent, "guy1",
                          cities[3], mercenary=False, pay_with_gems=False)
        self.assertEqual(self.dm.get_locations()[cities[3]]["has_spy"], False)

        # game master case
        self.dm.hire_remote_agent("master", cities[3], mercenary=True, pay_with_gems=False, gems_list=[])
        self.assertEqual(self.dm.get_locations()[cities[3]]["has_mercenary"], True)
        self.assertEqual(self.dm.get_locations()[cities[3]]["has_spy"], False)


    def ___test_mercenary_intervention(self):
        self._reset_messages()

        cities = self.dm.get_locations().keys()[0:5]
        self.dm.hire_remote_agent("guy1", cities[3], mercenary=True, pay_with_gems=False) # no message queued, since it's not a spy

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        self.assertRaises(dm_module.UsageError, self.dm.trigger_masslavian_mercenary_intervention, "guy1", cities[4], "Please attack this city.") # no mercenary ready

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        self.dm.trigger_masslavian_mercenary_intervention("guy1", cities[3], "Please attack this city.")

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        new_queue = self.dm.get_all_sent_messages()
        self.assertEqual(len(new_queue), 1)

        msg = new_queue[0]
        self.assertEqual(msg["sender_email"], "guy1@masslavia.com", msg) # we MUST use a dummy email to prevent forgery here
        self.assertEqual(msg["recipient_emails"], ["masslavian-army@special.com"], msg)
        self.assertTrue(msg["is_certified"], msg)
        self.assertTrue("attack" in msg["body"].lower())
        self.assertTrue("***" in msg["body"].lower())


    def ___test_teldorian_teleportation(self):
        self._reset_messages()

        cities = self.dm.get_locations().keys()[0:6]
        max_actions = self.dm.get_global_parameter("max_teldorian_teleportations")
        self.assertTrue(max_actions >= 2)

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        for i in range(max_actions):
            if i == (max_actions - 1):
                self.dm._add_to_scanned_locations([cities[3]]) # the last attack will be on scanned location !
            self.dm.trigger_teldorian_teleportation("scanner", cities[3], "Please destroy this city.")

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0) # immediate sending performed

        new_queue = self.dm.get_all_sent_messages()
        self.assertEqual(len(new_queue), max_actions)

        self.assertTrue("on unscanned" in new_queue[0]["subject"])

        msg = new_queue[-1]
        self.assertEqual(msg["sender_email"], "scanner@teldorium.com", msg) # we MUST use a dummy email to prevent forgery here
        self.assertEqual(msg["recipient_emails"], ["teldorian-army@special.com"], msg)
        self.assertTrue("on scanned" in msg["subject"])
        self.assertTrue(msg["is_certified"], msg)
        self.assertTrue("destroy" in msg["body"].lower())
        self.assertTrue("***" in msg["body"].lower())

        msg = new_queue[-2]
        self.assertTrue("on unscanned" in msg["subject"])

        self.assertEqual(self.dm.get_global_parameter("teldorian_teleportations_done"), self.dm.get_global_parameter("max_teldorian_teleportations"))
        self.assertRaises(dm_module.UsageError, self.dm.trigger_teldorian_teleportation, "scanner", cities[3], "Please destroy this city.") # too many teleportations


    def ___test_acharith_attack(self):
        self._reset_messages()

        cities = self.dm.get_locations().keys()[0:5]

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        self.dm.trigger_acharith_attack("guy2", cities[3], "Please annihilate this city.")

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        new_queue = self.dm.get_all_sent_messages()
        self.assertEqual(len(new_queue), 1)

        msg = new_queue[0]
        self.assertEqual(msg["sender_email"], "guy2@acharis.com", msg) # we MUST use a dummy email to prevent forgery here
        self.assertEqual(msg["recipient_emails"], ["acharis-army@special.com"], msg)
        self.assertTrue(msg["is_certified"], msg)
        self.assertTrue("annihilate" in msg["body"].lower())
        self.assertTrue("***" in msg["body"].lower())


    def ___test_wiretapping_management(self):
        self._reset_messages()

        char_names = self.dm.get_character_usernames()

        wiretapping = self.dm.abilities.wiretapping

        wiretapping.change_wiretapping_targets(PersistentList())
        self.assertEqual(wiretapping.get_current_targets(), [])

        wiretapping.change_wiretapping_targets([char_names[0], char_names[0], char_names[1]])

        self.assertEqual(set(wiretapping.get_current_targets()), set([char_names[0], char_names[1]]))
        self.assertEqual(wiretapping.get_listeners_for(char_names[1]), [self.TEST_LOGIN])

        self.assertRaises(UsageError, wiretapping.change_wiretapping_targets, ["dummy_name"])
        self.assertRaises(UsageError, wiretapping.change_wiretapping_targets, [char_names[i] for i in range(wiretapping.get_ability_parameter("max_wiretapping_targets") + 1)])

        self.assertEqual(set(wiretapping.get_current_targets()), set([char_names[0], char_names[1]])) # didn't change
        self.assertEqual(wiretapping.get_listeners_for(char_names[1]), [self.TEST_LOGIN])


    def ____test_scanning_management(self):
        self._reset_messages()

        self.dm.data["global_parameters"]["scanning_delays"] = 0.03
        self.dm.commit()

        res = self.dm._compute_scanning_result("sacred_chest")
        self.assertEqual(res, "Alifir Endara Denkos Mastden Aklarvik Kosalam Nelm".split())

        self.assertEqual(self.dm.get_global_parameter("scanned_locations"), [])

        self.assertEqual(len(self.dm.get_all_sent_messages()), 0)
        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        self.assertRaises(dm_module.UsageError, self.dm.process_scanning_submission, "scanner", "", None)

        # AUTOMATED SCAN #
        self.dm.process_scanning_submission("scanner", "sacred_chest", "dummydescription1")
        #print datetime.utcnow(), "----", self.dm.data["scheduled_actions"]


        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["recipient_emails"], ["scanner@teldorium.com"])
        self.assertTrue("scanning" in msg["body"].lower())

        msgs = self.dm.get_all_sent_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["sender_email"], "scanner@teldorium.com")
        self.assertTrue("scan" in msg["body"])
        self.assertTrue("dummydescription1" in msg["body"])
        self.assertTrue(self.dm.get_global_parameter("master_login") in msg["has_read"])

        self.dm.process_periodic_tasks()
        self.assertEqual(self.dm.get_global_parameter("scanned_locations"), []) # still delayed action

        time.sleep(3)

        self.assertEqual(self.dm.process_periodic_tasks(), {"messages_sent": 1, "actions_executed": 1})

        self.assertEqual(self.dm.get_event_count("DELAYED_ACTION_ERROR"), 0)
        self.assertEqual(self.dm.get_event_count("DELAYED_MESSAGE_ERROR"), 0)

        scanned_locations = self.dm.get_global_parameter("scanned_locations")
        self.assertTrue("Alifir" in scanned_locations, scanned_locations)


        # MANUAL SCAN #

        self.dm.process_scanning_submission("scanner", "", "dummydescription2")

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 0) # still empty

        msgs = self.dm.get_all_sent_messages()
        self.assertEqual(len(msgs), 3) # 2 messages from previous operation, + new one
        msg = msgs[2]
        self.assertEqual(msg["sender_email"], "scanner@teldorium.com")
        self.assertTrue("scan" in msg["body"])
        self.assertTrue("dummydescription2" in msg["body"])
        self.assertFalse(self.dm.get_global_parameter("master_login") in msg["has_read"])




    def ____test_bots(self):  # TODO PAKAL PUT BOTS BACK!!!

        bot_name = "Pay Rhuss" #self.dm.data["AI_bots"]["Pay Rhuss"].keys()[0]
        #print bot_name, " --- ",self.dm.data["AI_bots"]["bot_properties"]

        self._reset_messages()

        username = "guy1"

        res = self.dm.get_bot_response(username, bot_name, "hello")
        self.assertTrue("hi" in res.lower())

        res = self.dm.get_bot_response(username, bot_name, "What's your name ?")
        self.assertTrue(bot_name.lower() in res.lower())

        res = self.dm.get_bot_response(username, bot_name, "What's my name ?")
        self.assertTrue(username in res.lower())

        res = self.dm.get_bot_history(bot_name)
        self.assertEqual(len(res), 2)
        self.assertEqual(len(res[0]), 3)
        self.assertEqual(len(res[0]), len(res[1]))

        res = self.dm.get_bot_response(username, bot_name, "do you know where the orbs are ?").lower()
        self.assertTrue("celestial tears" in res, res)

        res = self.dm.get_bot_response(username, bot_name, "Where is loyd georges' orb ?").lower()
        self.assertTrue("father and his future son-in-law" in res, res)

        res = self.dm.get_bot_response(username, bot_name, "who owns the beta orb ?").lower()
        self.assertTrue("underground temple" in res, res)

        res = self.dm.get_bot_response(username, bot_name, "where is the gamma orb ?").lower()
        self.assertTrue("last treasure" in res, res)

        res = self.dm.get_bot_response(username, bot_name, "where is the wife of the guy2 ?").lower()
        self.assertTrue("young reporter" in res, res)

        res = self.dm.get_bot_response(username, bot_name, "who is cynthia ?").lower()
        self.assertTrue("future wife" in res, res)



















'''
      # Mega patching, to test that all what has to persist has been committed
        # properly before returning from datamanager

        for name in dir(self.dm):
            if "transaction" in name or name.startswith("_"):
                continue
            attr = getattr(self.dm, name)
            if isinstance(attr, types.MethodType):
                def container(attr):
                    # we need a container to freeze the free variable "attr"
                    def aborter(*args, **kwargs):
                        res = attr(*args, **kwargs)
                        dm_module.transaction.abort() # we ensure all non-transaction-watched data gets lost !
                        print "Forcing abort"
                        return res
                    return aborter
                setattr(self.dm, name, container(attr))
                print "MONKEY PATCHING ", name

'''


""" DEPRECATED
    def __test_message_template_formatting(self):

        self._reset_messages()

        (subject, body, attachment) = self.dm._build_robot_message_content("translation_result", subject_dict=dict(item="myitem"),
                                                               body_dict=dict(original="lalalall", translation="sqsdqsd", exceeding="qsqsdqsd"))
        self.assertTrue(subject)
        self.assertTrue(body)
        self.assertTrue(attachment is None or isinstance(attachment, basestring))

        self.assertEqual(self.dm.get_event_count("MSG_TEMPLATE_FORMATTING_ERROR_1"), 0)
        self.assertEqual(self.dm.get_event_count("MSG_TEMPLATE_FORMATTING_ERROR_2"), 0)

        (subject, body, attachment) = self.dm._build_robot_message_content("translation_result", subject_dict=dict(item="myitem"),
                                                               body_dict=dict(original="lalalall")) # translation missing

        self.assertEqual(self.dm.get_event_count("MSG_TEMPLATE_FORMATTING_ERROR_1"), 1)
        self.assertEqual(self.dm.get_event_count("MSG_TEMPLATE_FORMATTING_ERROR_2"), 0)

        # we won't test the MSG_TEMPLATE_FORMATTING_ERROR_2, as it'd complicate code uselessly
"""
