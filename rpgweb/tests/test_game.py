# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import random
from textwrap import dedent
import tempfile
import shutil

from ._test_tools import *
from rpgweb.abilities._abstract_ability import AbstractAbility
from rpgweb.common import _undefined, config, AbnormalUsageError
from rpgweb.views._abstract_game_view import ClassInstantiationProxy
from rpgweb.templatetags.helpers import _generate_encyclopedia_links
from rpgweb import views
from rpgweb.utilities import fileservers, autolinker
from django.test.client import RequestFactory
import pprint
from rpgweb.datamanager.datamanager_administrator import retrieve_game_instance,\
    _get_zodb_connection
from rpgweb.tests._test_tools import temp_datamanager











class TestUtilities(TestCase):

    def __call__(self, *args, **kwds):
        return unittest.TestCase.run(self, *args, **kwds) # we bypass test setups from django's TestCase, to use py.test instead
    
    def test_restructuredtext_handling(self):
        from docutils.utils import SystemMessage
        from django.contrib.markup.templatetags.markup import restructuredtext

        assert restructuredtext("""aaaa*aaa""") # star is ignored

        # outputs stuffs on stderr, but doesn't break
        restructuredtext("""aaaaaaa*zezez
                              mytitle :xyz:`qqq`
                            ===
                        """) # too short underline

        assert "title1" in restructuredtext("""title1\n=======\n\naaa""") # thx to our conf, title1 stays in html fragment
        
        html = restructuredtext(dedent("""
                    title1
                    -------
                    
                    aaa   
                      
                    title2
                    -------
                    
                    bbbbb
                    """))
        assert "title1" in html and "title2" in html
      
        
    def test_sphinx_publisher_settings(self) :   
        from django.utils.encoding import smart_str, force_unicode
        from docutils.core import publish_parts
        docutils_settings = {"initial_header_level": 3, 
                             "doctitle_xform": False, 
                             "sectsubtitle_xform": False}
        parts = publish_parts(source=smart_str("""title\n=======\n\naaa\n"""), # lone title would become document title by default - we prevent it
                              writer_name="html4css1", settings_overrides=docutils_settings)
        assert parts["fragment"] == '<div class="section" id="title">\n<h3>title</h3>\n<p>aaa</p>\n</div>\n'
        #pprint.pprint(parts)
        
        
    def test_html_autolinker(self):
        
        regex = autolinker.join_regular_expressions_as_disjunction(("[123]", "(k*H?)"), as_words=False)
        assert regex == r"(?:[123])|(?:(k*H?))"
        assert re.compile(regex).match("2joll")

        regex = autolinker.join_regular_expressions_as_disjunction(("[123]", "(k*H)"), as_words=True)
        assert regex == r"(?:\b[123]\b)|(?:\b(k*H)\b)"
        assert re.compile(regex).match("kkH")          
          
          
        input0 = '''one<a>ones</a>'''
        res = autolinker.generate_links(input0, "ones?", lambda x: dict(href="TARGET_"+x.group(0), title="mytitle"))
        assert res == '''<a href="TARGET_one" title="mytitle">one</a><a>ones</a>'''
        
                  
        input = dedent('''
        <html>
        <head><title>Page title one</title></head>
        <body>
        <div>Hi</div>
        <p id="firstpara" class="one red" align="center">This is one paragraph <b>ones</b>.</a>
        <a href="http://aaa">This is one paragraph <b>one</b>.</a>
        </html>''') 
        
        res = autolinker.generate_links(input, "ones?", lambda x: dict(href="TARGET_"+x.group(0), title="mytitle"))

        assert res == dedent('''
        <html>
        <head><title>Page title one</title></head>
        <body>
        <div>Hi</div>
        <p align="center" class="one red" id="firstpara">This is <a href="TARGET_one" title="mytitle">one</a> paragraph <b><a href="TARGET_ones" title="mytitle">ones</a></b>.
        <a href="http://aaa">This is one paragraph <b>one</b>.</a>
        </p></body></html>''')



                   
          
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


    def test_yaml_fixture_loading(self):
        
        data = {"file1.yml": dedent("""
                                    characters:
                                        parent: "No data"
                                     """),
                "file2.yaml": dedent("""
                                     wap: 32
                                     """), 
                "ignored.yl": "hello: 'hi'"}        
        

        def _load_data(mydict):
            
            my_dir = tempfile.mkdtemp() 
            print(">> temp dir", my_dir)
        
            for filename, file_data in mydict.items():
                with open(os.path.join(my_dir, filename), "w") as fd:
                    fd.write(file_data)
            
            return my_dir      
        
        tmp_dir = _load_data(data)
        
        with pytest.raises(ValueError):
            utilities.load_yaml_fixture("/badpath")
            
        res = utilities.load_yaml_fixture(tmp_dir)
        assert res == {'characters': {'parent': 'No data'}, 'wap': 32}
               
        res = utilities.load_yaml_fixture(os.path.join(tmp_dir, "file1.yml"))
        assert res == {'characters': {'parent': 'No data'}}
        shutil.rmtree(tmp_dir)
        
        data.update({"file3.yml": "characters: 99"}) # collision
        tmp_dir = _load_data(data)
        with pytest.raises(ValueError):
            utilities.load_yaml_fixture("/badpath")        
        shutil.rmtree(tmp_dir)

    
    def test_file_server_backends(self):
        
        path = os.path.join(config.GAME_FILES_ROOT, "README.txt")
        request = RequestFactory().get("/path/to/file.zip")
    
        kwargs = dict(save_as=random.choice((None, "othername.zip")),
                      size=random.choice((None, 1625726)),)                                         
        
        def _check_standard_headers(response):
            if kwargs["save_as"]:
                assert kwargs["save_as"] in response["Content-Disposition"]
            if kwargs["size"]:
                assert response["Content-Length"] == str(kwargs["size"])
                                      
        response = fileservers.serve_file(request, path, **kwargs)
        assert response.content
        _check_standard_headers(response)
        
        response = fileservers.serve_file(request, path, backend_name="nginx", **kwargs)
        print (response._headers)
        assert response['X-Accel-Redirect'] == path
        assert not response.content        
        _check_standard_headers(response)
        
        response = fileservers.serve_file(request, path, backend_name="xsendfile", **kwargs)
        assert not response.content        
        assert response['X-Sendfile'] == path
        _check_standard_headers(response)
        
        
    def test_url_hashing_func(self):

        hash = hash_url_path("whatever/shtiff/kk.mp3?sssj=33")
        
        assert len(hash) == 8
        for c in hash:
            assert c in "abcdefghijklmnopqrstuvwxyz01234567"
            
        
# TODO - test that messages are well propagated through session
# TODO - test interception of "POST" when impersonating user


class TestDatamanager(BaseGameTestCase):


    @for_datamanager_base
    def test_requestless_datamanager(self):
        
        assert self.dm.request
        self.dm._request = None
        assert self.dm.request is None # property
        
        # user notifications get swallowed
        user = self.dm.user
        user.add_message("sqdqsd sss")
        user.add_error("fsdfsdf")
        assert user.get_notifications() == []
        assert not user.has_notifications()
        user.discard_notifications()

        

    @for_datamanager_base
    def test_modular_architecture(self):
        
        assert len(MODULES_REGISTRY) > 4
        
        for core_module in MODULES_REGISTRY:
            
            # we ensure every module calls super() properly
             
            CastratedDataManager = type(str('Dummy'+core_module.__name__), (core_module,), {})
            castrated_dm = CastratedDataManager.__new__(CastratedDataManager) # we bypass __init__() call there
            utilities.TechnicalEventsMixin.__init__(castrated_dm) # only that mixing gets initizalized
                                                    
            try:
                root = _get_zodb_connection().root()
                my_id = str(random.randint(1, 10000))
                root[my_id] = PersistentDict()
                castrated_dm.__init__(game_instance_id=my_id,
                                      game_root=root[my_id],
                                      request=self.request)
            except Exception, e:
                transaction.abort()
                print("AAA", e)
            assert castrated_dm.get_event_count("BASE_DATA_MANAGER_INIT_CALLED") == 1

            try:
                castrated_dm._load_initial_data()
            except Exception, e:
                transaction.abort()
                print("BBB", e)
            assert castrated_dm.get_event_count("BASE_LOAD_INITIAL_DATA_CALLED") == 1
                
            try:
                castrated_dm._check_database_coherency()
            except Exception, e:
                transaction.abort()
                print("CCC", e)
            assert castrated_dm.get_event_count("BASE_CHECK_DB_COHERENCY_PRIVATE_CALLED") == 1

            try:
                report = PersistentList()
                castrated_dm._process_periodic_tasks(report)
            except Exception, e:
                transaction.abort()
                print("DDD", e)
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
        assert self.dm.get_character_color_or_none("guy1") == "#0033CC"
        assert self.dm.get_character_color_or_none("unexistinguy") is None
        assert self.dm.get_character_color_or_none("") is None
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


    @for_core_module(FriendshipHandling)
    def test_friendship_handling(self):           
        
        dm = self.dm
        proposal_date = datetime.utcnow() - timedelta(hours=3)
        
        dm.reset_friendship_data()
        
        assert not dm.data["friendships"]["proposed"]
        assert not dm.data["friendships"]["sealed"]
        
        with pytest.raises(AbnormalUsageError):
            dm.propose_friendship("guy1", "guy1") # auto-friendship impossible
            
        dm.propose_friendship("guy2", "guy1")
        assert not dm.are_friends("guy1", "guy2")
        assert not dm.are_friends("guy2", "guy1")
        assert not dm.are_friends("guy1", "guy3")

        with pytest.raises(AbnormalUsageError):
            dm.propose_friendship("guy2", "guy1") # friendship already requested
            
        assert dm.data["friendships"]["proposed"]
        assert not dm.data["friendships"]["sealed"]
              
        with pytest.raises(AbnormalUsageError):
            dm.propose_friendship("guy2", "guy1") # duplicate proposal
            
        assert dm.get_friendship_requests("guy3") == dict(proposed_to=[],
                                                          requested_by=[])    
        assert dm.get_friendship_requests("guy1") == dict(proposed_to=[],
                                                          requested_by=["guy2"])
        assert dm.get_friendship_requests("guy2") == dict(proposed_to=["guy1"],
                                                          requested_by=[])
        time.sleep(0.5)
        dm.propose_friendship("guy1", "guy2") # we seal friendship, here       

        with pytest.raises(AbnormalUsageError):
            dm.propose_friendship("guy2", "guy1") # already friends
        with pytest.raises(AbnormalUsageError):
            dm.propose_friendship("guy1", "guy2") # already friends
                   
        assert not dm.data["friendships"]["proposed"]
        assert dm.data["friendships"]["sealed"].keys() == [("guy2", "guy1")] # order is "first proposer first"

        key, params = dm.get_friendship_params("guy1", "guy2")
        key_bis, params_bis = dm.get_friendship_params("guy2", "guy1")
        assert key == key_bis == ("guy2", "guy1") # order OK
        assert params == params_bis
        assert datetime.utcnow() - timedelta(seconds=5) <= params["proposal_date"] <= datetime.utcnow()  
        assert datetime.utcnow() - timedelta(seconds=5) <= params["acceptance_date"] <= datetime.utcnow()  
        assert params["proposal_date"] < params["acceptance_date"]
        
        with pytest.raises(AbnormalUsageError):
            dm.get_friendship_params("guy1", "guy3")
        with pytest.raises(AbnormalUsageError):
            dm.get_friendship_params("guy3", "guy1")            
        with pytest.raises(AbnormalUsageError):
            dm.get_friendship_params("guy3", "guy4")              
            
        assert dm.are_friends("guy2", "guy1") == dm.are_friends("guy1", "guy2") == True
        assert dm.are_friends("guy2", "guy3") == dm.are_friends("guy3", "guy4") == False
        
        dm.propose_friendship("guy2", "guy3") # proposed
        dm.propose_friendship("guy3", "guy2") # accepted
        assert dm.get_friends("guy1") == dm.get_friends("guy3") == ["guy2"]
        assert dm.get_friends("guy2") in (["guy1", "guy3"], ["guy3", "guy1"]) # order not enforced
        assert dm.get_friends("guy4") == []
        
        with pytest.raises(AbnormalUsageError):
            dm.terminate_friendship("guy3", "guy4") # unexisting friendship
        with pytest.raises(NormalUsageError):
            dm.terminate_friendship("guy1", "guy2") # too young   
                         
        for params in dm.data["friendships"]["sealed"].values():
            params["acceptance_date"] -= timedelta(hours=30) # delay must be 24h in dev
            dm.commit()         
                  
        dm.terminate_friendship("guy1", "guy2") # success 
        assert not dm.are_friends("guy2", "guy1") 
        with pytest.raises(UsageError):
            dm.get_friendship_params("guy1", "guy2")
        assert dm.are_friends("guy2", "guy3") # untouched   
                                                    
        dm.reset_friendship_data()
        assert not dm.data["friendships"]["proposed"]  
        assert not dm.data["friendships"]["sealed"]  
        assert not dm.get_friends("guy1")
        assert not dm.get_friends("guy2")
        assert not dm.get_friends("guy3")
        assert not dm.are_friends("guy2", "guy1")
        assert not dm.are_friends("guy3", "guy2")
        assert not dm.are_friends("guy3", "guy4")
        
        
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

    
    @for_core_module(Encyclopedia)
    def test_encyclopedia(self):
        
        utilities.check_is_restructuredtext(self.dm.get_encyclopedia_entry(" gerbiL_speCies ")) # tolerant fetching
        assert self.dm.get_encyclopedia_entry("qskiqsjdqsid") is None
        assert "gerbil_species" in self.dm.get_encyclopedia_article_ids()
        
        assert ("animals?", ["lokon", "gerbil_species"]) in self.dm.get_encyclopedia_keywords_mapping().items()
        for entry in self.dm.get_encyclopedia_keywords_mapping().keys():
            utilities.check_is_slug(entry)
            assert entry.lower() == entry
        
        # best matches
        assert self.dm.get_encyclopedia_matches("qssqs") == []
        assert self.dm.get_encyclopedia_matches("hiqqsd bAdgerbilZ") == ["gerbil_species"] # we're VERY tolerant
        assert self.dm.get_encyclopedia_matches("rodEnt") == ["gerbil_species"]
        assert self.dm.get_encyclopedia_matches("hi gerbils animaL") == ["gerbil_species", "lokon"]
        assert self.dm.get_encyclopedia_matches("animal loKon") == ["lokon", "gerbil_species"]
        assert self.dm.get_encyclopedia_matches(u"animéàk") == [u"wu\\gly_é"]
        
        
        # index available or not ?
        assert not self.dm.is_encyclopedia_index_visible()
        not self.dm.set_encyclopedia_index_visibility(True)
        assert self.dm.is_encyclopedia_index_visible()
        not self.dm.set_encyclopedia_index_visibility(False)
        assert not self.dm.is_encyclopedia_index_visible()
        
        # generation of entry links 
        res = _generate_encyclopedia_links("lokon lokons lokonsu", self.dm)
        expected = """<a href="@@@?search=lokon">lokon</a> <a href="@@@?search=lokons">lokons</a> lokonsu"""
        expected = expected.replace("@@@", reverse(views.view_encyclopedia, kwargs=dict(game_instance_id=self.dm.game_instance_id)))
        assert res == expected
        
        res = _generate_encyclopedia_links(u"""wu\\gly_é gerbil \n lokongerbil dummy gerb\nil <a href="#">lokon\n</a> lokons""", self.dm)                         
        print (repr(res))
        expected = u'wu\\gly_é <a href="@@@?search=gerbil">gerbil</a> \n lokongerbil dummy gerb\nil <a href="#">lokon\n</a> <a href="@@@?search=lokons">lokons</a>'
        expected = expected.replace("@@@", reverse(views.view_encyclopedia, kwargs=dict(game_instance_id=self.dm.game_instance_id)))
        assert res == expected
        
        res = _generate_encyclopedia_links(u"""i<à hi""", self.dm)                         
        print (repr(res))
        expected = u'<a href="/TeStiNg/encyclopedia/?search=i%3C%C3%A0">i&lt;\xe0</a> hi'
        expected = expected.replace("@@@", reverse(views.view_encyclopedia, kwargs=dict(game_instance_id=self.dm.game_instance_id)))
        assert res == expected        
        

        # knowledge of article ids #
        
        for unauthorized in ("master", None):
            self._set_user(unauthorized)
            with pytest.raises(UsageError):
                self.dm.get_character_known_article_ids()
            with pytest.raises(UsageError):
                self.dm.update_character_known_article_ids(["lokon"])
            with pytest.raises(UsageError):
                self.dm.reset_character_known_article_ids()
        
        self._set_user("guy1")
        assert self.dm.get_character_known_article_ids() == []
        self.dm.update_character_known_article_ids(["lokon"])
        assert self.dm.get_character_known_article_ids() == ["lokon"]
        self.dm.update_character_known_article_ids(["gerbil_species", "unexisting", "lokon", "gerbil_species"])
        assert self.dm.get_character_known_article_ids() == ["lokon", "gerbil_species", "unexisting"]
        self.dm.reset_character_known_article_ids()
        assert self.dm.get_character_known_article_ids() == []
        
        
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

        ######

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
        self.assertEqual(set(properties.keys()), set(["text", "file", "url", "title"]))

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
    def test_standard_player_authentication(self):
        """
        Here we use frontend methods from authentication.py instead of
        directly datamanager methods.
        """
        self._reset_django_db()
        
        from rpgweb.authentication import (authenticate_with_credentials, try_authenticating_with_ticket, logout_session,
                                           SESSION_TICKET_KEY)
        from django.contrib.sessions.middleware import SessionMiddleware
        
        home_url = reverse(views.homepage, kwargs={"game_instance_id": TEST_GAME_INSTANCE_ID})
        
        master_login = self.dm.get_global_parameter("master_login")
        master_password = self.dm.get_global_parameter("master_password")
        player_login = "guy1"
        player_password = "elixir"
        anonymous_login = self.dm.get_global_parameter("anonymous_login")
        
 
        # build complete request
        request = self.factory.post(home_url)
        request.datamanager = self.dm
        
        # we let different states of the session ticket be there, at the beginning
        if random.choice((0, 1)):
            request.session[SESSION_TICKET_KEY] = random.choice((None, {}))
        
        # anonymous case
        assert request.datamanager.user.username == anonymous_login
        assert not self.dm.get_impersonation_targets(anonymous_login)
        
        
        def _standard_authenticated_checks():
            
            original_ticket = request.session[SESSION_TICKET_KEY].copy()
            original_username = request.datamanager.user.username
            
            assert request.datamanager == self.dm 
            self._set_user(None)
            assert request.datamanager.user.username == anonymous_login
            
            res = try_authenticating_with_ticket(request)
            assert res is None
            
            assert request.session[SESSION_TICKET_KEY] == original_ticket
            assert request.datamanager.user.username == original_username
            
            self._set_user(None) 
            
            # failure case: wrong ticket type
            request.session[SESSION_TICKET_KEY] = ["dqsdqs"]
            try_authenticating_with_ticket(request) # exception gets swallowed
            assert request.session[SESSION_TICKET_KEY] is None
             
            self._set_user(None) 
            
            # failure case: wrong instance id
            request.session[SESSION_TICKET_KEY] = original_ticket.copy()
            request.session[SESSION_TICKET_KEY]["game_instance_id"] = "qsdjqsidub"
            _temp = request.session[SESSION_TICKET_KEY].copy()
            try_authenticating_with_ticket(request) # exception gets swallowed
            assert request.session[SESSION_TICKET_KEY] == _temp
            
            self._set_user(None) 
            
            request.session[SESSION_TICKET_KEY] = original_ticket.copy()
            request.session[SESSION_TICKET_KEY]["username"] = "qsdqsdqsd"
            try_authenticating_with_ticket(request) # exception gets swallowed
            assert request.session[SESSION_TICKET_KEY] == None # but ticket gets reset
            
            self._set_user(None) 
            
            request.session[SESSION_TICKET_KEY] = original_ticket.copy()
            try_authenticating_with_ticket(request)
            assert request.datamanager.user.username == original_username
            
            logout_session(request)
            assert SESSION_TICKET_KEY not in request.session
            assert request.datamanager.user.username == anonymous_login

        
        # simple player case
        
        res = authenticate_with_credentials(request, player_login, player_password)
        assert res is None # no result expected
        ticket = request.session[SESSION_TICKET_KEY]
        assert ticket == {'game_instance_id': u'TeStiNg', 'impersonation': None, 'username': player_login} 
        
        assert request.datamanager.user.username == player_login
        assert not self.dm.get_impersonation_targets(player_login)
        
        _standard_authenticated_checks()
         
         
        # game master case
        
        res = authenticate_with_credentials(request, master_login, master_password)
        assert res is None # no result expected
        ticket = request.session[SESSION_TICKET_KEY]
        assert ticket == {'game_instance_id': u'TeStiNg', 'impersonation': None, 'username': master_login}
        
        _standard_authenticated_checks()
        
        
    
    
        
        
    @for_core_module(PlayerAuthentication)
    def test_impersonation(self):
        
        self._reset_django_db()
        
        from rpgweb.authentication import (authenticate_with_credentials, try_authenticating_with_ticket, logout_session,
                                           SESSION_TICKET_KEY, IMPERSONATION_POST_VARIABLE)

        
        master_login = self.dm.get_global_parameter("master_login")
        master_password = self.dm.get_global_parameter("master_password")
        player_login = "guy1"
        player_password = "elixir"
        player_login_bis = "guy2"
        anonymous_login = self.dm.get_global_parameter("anonymous_login")
        
        
        # build complete request
        
        # Impersonation control with can_impersonate()
        assert not self.dm.can_impersonate(master_login, master_login)
        assert self.dm.can_impersonate(master_login, player_login)
        assert self.dm.can_impersonate(master_login, anonymous_login)
        
        assert not self.dm.can_impersonate(player_login, master_login)
        assert not self.dm.can_impersonate(player_login, player_login)
        assert not self.dm.can_impersonate(player_login, player_login_bis)        
        assert not self.dm.can_impersonate(player_login, anonymous_login)  
 
        assert not self.dm.can_impersonate(anonymous_login, master_login)
        assert not self.dm.can_impersonate(anonymous_login, player_login)        
        assert not self.dm.can_impersonate(anonymous_login, anonymous_login) 
               
        
        # impersonation cases #
        
        self.dm.user.discard_notifications()
        
        request = self.request
        authenticate_with_credentials(request, master_login, master_password)
        session_ticket = request.session[SESSION_TICKET_KEY]
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': None, 'username': master_login}
        assert self.dm.user.username == master_login
        assert self.dm.user.has_write_access
        assert not self.dm.user.is_impersonation
        assert self.dm.user.real_username == master_login
        assert not self.dm.user.has_notifications()        
        
        
        # Impersonate player
        res = self.dm.authenticate_with_ticket(session_ticket, 
                                               requested_impersonation=player_login)
        assert res is session_ticket
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': player_login, 'username': master_login}
        assert self.dm.user.username == player_login
        assert not self.dm.user.has_write_access
        assert self.dm.user.is_impersonation
        assert self.dm.user.real_username == master_login
        assert not self.dm.user.has_notifications()
        
        # Impersonated player renewed just with ticket
        self._set_user(None)
        assert self.dm.user.username == anonymous_login
        self.dm.authenticate_with_ticket(session_ticket, 
                                         requested_impersonation=None)
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': player_login, 'username': master_login}
        assert self.dm.user.username == player_login
        assert not self.dm.user.has_notifications() 
        
        # Impersonation stops because of unexisting username
        self.dm.authenticate_with_ticket(session_ticket, 
                                         requested_impersonation="dsfsdfkjsqodsd")
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': None, 'username': master_login}
        assert self.dm.user.username == master_login
        assert self.dm.user.has_write_access
        assert not self.dm.user.is_impersonation
        assert self.dm.user.real_username == master_login
        assert self.dm.user.has_notifications()        
        self.dm.user.discard_notifications()
                
        # Impersonate anonymous
        self.dm.authenticate_with_ticket(session_ticket, 
                                         requested_impersonation=anonymous_login)
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': anonymous_login, 'username': master_login}
        assert self.dm.user.username == anonymous_login
        assert not self.dm.user.has_write_access
        assert self.dm.user.is_impersonation
        assert self.dm.user.real_username == master_login
        assert not self.dm.user.has_notifications()        
        _copy = session_ticket.copy()
        
        # Impersonation stops completely because of unauthorized impersonation attempt
        self.dm.authenticate_with_ticket(session_ticket, 
                                         requested_impersonation=master_login)
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': None, 'username': master_login}
        assert self.dm.user.username == master_login
        assert self.dm.user.has_write_access
        assert not self.dm.user.is_impersonation
        assert self.dm.user.real_username == master_login
        assert self.dm.user.has_notifications()        
        self.dm.user.discard_notifications()                
        
        # Back as anonymous
        self.dm.authenticate_with_ticket(session_ticket, 
                                         requested_impersonation=anonymous_login)                    
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': anonymous_login, 'username': master_login}
        assert self.dm.user.username == anonymous_login
        assert not self.dm.user.has_write_access
        assert self.dm.user.is_impersonation
        assert self.dm.user.real_username == master_login
        assert not self.dm.user.has_notifications()        
   
        # Standard stopping of impersonation 
        self.dm.authenticate_with_ticket(session_ticket, 
                                         requested_impersonation="")                    
        assert session_ticket == {'game_instance_id': u'TeStiNg', 'impersonation': None, 'username': master_login}
        assert self.dm.user.username == master_login
        assert self.dm.user.has_write_access
        assert not self.dm.user.is_impersonation
        assert self.dm.user.real_username == master_login
        assert not self.dm.user.has_notifications() # IMPORTANT - no error message    
    
    
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

    
    
    @for_core_module(GameViews)
    def test_game_view_registries(self):
        
        assert self.dm.get_event_count("SYNC_GAME_VIEW_DATA_CALLED") == 0 # event stats have been cleared above
        
        views_dict = self.dm.get_game_views()
        assert views_dict is not self.dm.GAME_VIEWS_REGISTRY # copy
        
        activable_views_dict = self.dm.get_activable_views()
        assert activable_views_dict is not self.dm.ACTIVABLE_VIEWS_REGISTRY # copy
        assert set(activable_views_dict.keys()) < set(self.dm.get_game_views().keys())
        
        random_view, random_klass = activable_views_dict.items()[0]
        
        # instantiation works for both names and classes
        view = self.dm.instantiate_game_view(random_view)
        assert isinstance(view, AbstractGameView)
        view = self.dm.instantiate_game_view(activable_views_dict[random_view])
        assert isinstance(view, AbstractGameView)        

        with pytest.raises(AbnormalUsageError):
            self.dm.set_activated_game_views(["aaa", random_view])
        
        self.dm.set_activated_game_views([])      
        assert not self.dm.is_game_view_activated(random_view)
        self.dm.set_activated_game_views([random_view])
        assert self.dm.is_game_view_activated(random_view)
        
        
        # access-token retriever shortcut works OK
        assert self.dm.user.is_anonymous
        token = self.dm.get_game_view_access_token(views.homepage.NAME)
        assert token == AccessResult.available
        token = self.dm.get_game_view_access_token(views.view_sales._klass)
        assert token == AccessResult.authentication_required        
                
        
        # test registry resync
        del self.dm.ACTIVABLE_VIEWS_REGISTRY[random_view] # class-level registry
        self.dm.sync_game_view_data()
        assert not self.dm.is_game_view_activated(random_view) # cleanup occurred
        assert self.dm.get_event_count("SYNC_GAME_VIEW_DATA_CALLED") == 1
        
        with temp_datamanager(TEST_GAME_INSTANCE_ID, self.request) as _dm2:
            assert _dm2.get_event_count("SYNC_GAME_VIEW_DATA_CALLED") == 1 # sync well called at init!!

        self.dm.ACTIVABLE_VIEWS_REGISTRY[random_view] = random_klass # test cleanup
        
        
        # test admin form tokens
        assert "runic_translation.translation_form" in self.dm.get_admin_widget_identifiers()
        
        assert self.dm.resolve_admin_widget_identifier("") is None
        assert self.dm.resolve_admin_widget_identifier("qsdqsd") is None
        assert self.dm.resolve_admin_widget_identifier("qsdqsd.translation_form") is None
        assert self.dm.resolve_admin_widget_identifier("runic_translation.") is None
        assert self.dm.resolve_admin_widget_identifier("runic_translation.qsdqsd") is None
        
        from rpgweb.abilities import runic_translation_view
        components = self.dm.resolve_admin_widget_identifier("runic_translation.translation_form")
        assert len(components) == 2
        assert isinstance(components[0], runic_translation_view._klass)
        assert components[1] == "translation_form"
        
        
    @for_core_module(SpecialAbilities)
    def test_special_abilities_registry(self):
        
        abilities = self.dm.get_abilities()
        assert abilities is not self.dm.ABILITIES_REGISTRY # copy
        assert "runic_translation" in abilities
        
        
        @register_view
        class TesterAbility(AbstractAbility):

            NAME = "dummy_ability"
            GAME_FORMS = {}
            ACTIONS = dict()
            TEMPLATE = "base_main.html" # must exist
            ACCESS = UserAccess.anonymous
            PERMISSIONS = [] 
            ALWAYS_AVAILABLE = False 
        
        
            def get_template_vars(self, previous_form_data=None):
                return {'page_title': "hello",}
                
            @classmethod
            def _setup_ability_settings(cls, settings):
                settings.setdefault("myvalue", "True")
                self.dm.notify_event("LATE_ABILITY_SETUP_DONE") # BEWARE - event registry of OTHER DM instance!
                
            def _setup_private_ability_data(self, private_data):
                pass
        
            def _check_data_sanity(self, strict=False):
                settings = self.settings
                assert settings["myvalue"] == "True"
        

        assert "dummy_ability" in self.dm.get_abilities() # auto-registration
        self.dm.rollback()
        with pytest.raises(KeyError):        
            self.dm.get_ability_data("dummy_ability") # not yet setup in ZODB
        
        with temp_datamanager(TEST_GAME_INSTANCE_ID, self.request) as _dm:
            assert "dummy_ability" in _dm.get_abilities()
            assert _dm.get_ability_data("dummy_ability") # ability now setup in ZODB
            assert self.dm.get_event_count("LATE_ABILITY_SETUP_DONE") == 1 # parasite event - autosync well called at init!!
            del self.dm.ABILITIES_REGISTRY["dummy_ability"] # important cleanup!!!
             


    @for_core_module(HelpPages)
    def test_help_pages(self):
        
        utilities.check_is_restructuredtext(self.dm.get_help_page(" view_EncyClopedia ")) # tolerant fetching
        
        assert self.dm.get_help_page("qskiqsjdqsid") is None
        
        assert "homepage" in self.dm.get_help_page_names()
        for entry in self.dm.get_help_page_names():
            utilities.check_is_slug(entry)
            assert entry.lower() == entry
        
            
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



    @for_datamanager_base
    def test_database_management(self):
        self._reset_messages()

        # test "reset databases" too, in the future
        res = self.dm.dump_zope_database()
        assert isinstance(res, basestring) and len(res) > 1000

    

    @for_core_module(NightmareCaptchas)
    def test_nightmare_captchas(self):
        
        captcha_ids = self.dm.get_available_captchas()
        assert captcha_ids
        
        captcha1 = self.dm.get_selected_captcha(captcha_ids[0])
        captcha2 = self.dm.get_selected_captcha(captcha_ids[-1])
        assert captcha1 != captcha2
        
        random_captchas = [self.dm.get_random_captcha() for i in range(30)]
        assert set(v["id"] for v in random_captchas) == set(captcha_ids) # unless very bad luck...
        
        with pytest.raises(AbnormalUsageError):
            self.dm.check_captcha_answer_attempt(captcha_id="unexisting_id", attempt="whatever")
            
        for captcha in (random_captchas + [captcha1, captcha2]):
            assert set(captcha.keys()) == set("id text image".split()) # no spoiler of answer elements here
            assert self.dm.get_selected_captcha(captcha["id"]) == captcha
            with pytest.raises(NormalUsageError):
                self.dm.check_captcha_answer_attempt(captcha["id"], "")
            with pytest.raises(NormalUsageError):
                self.dm.check_captcha_answer_attempt(captcha["id"], "random stuff ")
            
            _full_captch_data = self.dm.data["nightmare_captchas"][captcha["id"]]
            answer = "  " + _full_captch_data["answer"].upper() + " " # case and spaces are not important
            res = self.dm.check_captcha_answer_attempt(captcha["id"], answer)
            assert res == _full_captch_data["explanation"] # sucess
            
            
            
class TestHttpRequests(BaseGameTestCase):

    def _master_auth(self):
        master_login = self.dm.get_global_parameter("master_login")
        login_page = reverse("rpgweb.views.login", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        response = self.client.get(login_page) # to set preliminary cookies
        self.assertEqual(response.status_code, 200)

        response = self.client.post(login_page, data=dict(secret_username=master_login, secret_password=self.dm.get_global_parameter("master_password")))

        self.assertEqual(response.status_code, 302)

        if self.dm.is_game_started():
            self.assertRedirects(response, ROOT_GAME_URL + "/")
        else:
            self.assertRedirects(response, ROOT_GAME_URL + "/opening/") # beautiful intro for days before the game starts
        
        assert self.client.session["rpgweb_session_ticket"] == dict(game_instance_id=TEST_GAME_INSTANCE_ID, 
                                                                    username=master_login,
                                                                    impersonation=None)
        self.assertTrue(self.client.cookies["sessionid"])


    def _player_auth(self, username):
        login_page = reverse("rpgweb.views.login", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        response = self.client.get(login_page) # to set preliminary cookies
        self.assertEqual(response.status_code, 200)

        response = self.client.post(login_page, data=dict(secret_username=username, secret_password=self.dm.get_character_properties(username)["password"]))

        self.assertEqual(response.status_code, 302)
        if self.dm.is_game_started():
            self.assertRedirects(response, ROOT_GAME_URL + "/")
        else:
            self.assertRedirects(response, ROOT_GAME_URL + "/opening/") # beautiful intro for days before the game starts
            
        assert self.client.session["rpgweb_session_ticket"] == dict(game_instance_id=TEST_GAME_INSTANCE_ID, 
                                                                    username=username,
                                                                    impersonation=None)
        self.assertTrue(self.client.cookies["sessionid"])


    def _logout(self):
        login_page = reverse("rpgweb.views.login", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        logout_page = reverse("rpgweb.views.logout", kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
        response = self.client.get(logout_page) # to set preliminary cookies

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, login_page)

        assert not self.client.session.has_key("rpgweb_session_ticket")
        self.assertEqual(self.client.session.keys(), ["testcookie"]) # we get it once more


    def _simple_master_get_requests(self):
        # FIXME - currently not testing abilities
        self._reset_django_db()
        
        self.dm.data["global_parameters"]["online_presence_timeout_s"] = 1
        self.dm.data["global_parameters"]["chatroom_presence_timeout_s"] = 1
        self.dm.commit()
        time.sleep(1.2) # online/chatting users list gets emptied

        self._master_auth() # equivalent to self._set_user(self.dm.get_global_parameter("master_login"))
        
        from django.core.urlresolvers import RegexURLResolver
        from rpgweb.urls import final_urlpatterns

        skipped_patterns = """ability instructions view_help_page
                              DATABASE_OPERATIONS FAIL_TEST ajax item_3d_view chat_with_djinn static.serve encrypted_folder view_single_message logout login secret_question""".split()
        views_names = [url._callback_str for url in final_urlpatterns 
                                   if not isinstance(url, RegexURLResolver) and 
                                      not [veto for veto in skipped_patterns if veto in url._callback_str]
                                      and "__" not in url._callback_str] # skip disabled views
        #print views_names
        
        for view in views_names:
            url = reverse(view, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
            #print(" ====> ", url)
            response = self.client.get(url)
            #print(response._headers) #repr(response.content))
            self.assertEqual(response.status_code, 200, view + " | " + url + " | " + str(response.status_code))
 
   
        # these urls and their post data might easily change, beware !
        special_urls = {ROOT_GAME_URL + "/item3dview/sacred_chest/": None,
                        # FIXME NOT YET READYROOT_GAME_URL + "/djinn/": {"djinn": "Pay Rhuss"},
                        config.MEDIA_URL + "Burned/default_styles.css": None,
                        game_file_url("attachments/image1.png"): None,
                        game_file_url("encrypted/guy2_report/evans/orb.jpg"): None,
                        ROOT_GAME_URL + "/messages/view_single_message/instructions_bewitcher/": None,
                        ROOT_GAME_URL + "/secret_question/": dict(secret_answer="Fluffy", target_email="guy3@pangea.com", secret_username="guy3"),
                        ROOT_GAME_URL + "/webradio_applet/": dict(frequency=self.dm.get_global_parameter("pangea_radio_frequency")),
                        reverse(views.view_help_page, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID, keyword="homepage")): None,                     
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
        
        # no direct file access, we need the hash tag
        response = self.client.get("/files/qsdqsdqs/README.txt")
        self.assertEqual(response.status_code, 404)
        response = self.client.get(game_file_url("README.txt"))
        self.assertEqual(response.status_code, 200)
        
        # user presence is not disrupted by game master
        self.assertEqual(self.dm.get_online_users(), [])
        self.assertEqual(self.dm.get_chatting_users(), [])

        self._logout()


    def test_master_game_started_page_displays(self):
        self.dm.set_game_state(True)
        self._simple_master_get_requests()

    def test_master_game_paused_page_displays(self):
        self.dm.set_game_state(False)
        self._simple_master_get_requests()


    def _test_player_get_requests(self):
        
        # FIXME - currently not testing abilities
        
        self._reset_django_db()
        
        self.dm.data["global_parameters"]["online_presence_timeout_s"] = 1
        self.dm.data["global_parameters"]["chatroom_presence_timeout_s"] = 1
        self.dm.commit()
        time.sleep(1.2) # online/chatting users list gets emptied
        
        old_state = self.dm.is_game_started()
        
        # PLAYER SETUP
        
        self.dm.set_game_state(True)
        username = "guy2"
        user_money = self.dm.get_character_properties(username)["account"]
        if user_money:
            self.dm.transfer_money_between_characters(username, self.dm.get_global_parameter("bank_name"), user_money) # we empty money
        self.dm.data["character_properties"][username]["permissions"] = PersistentList(["contact_djinns", "manage_agents", "manage_wiretaps"]) # we grant all necessary permissions
        self.dm.commit()
        self.dm.set_game_state(old_state)
        self._player_auth(username)


        # VIEWS SELECTION
        from django.core.urlresolvers import RegexURLResolver
        from rpgweb.urls import final_urlpatterns
        # we test views for which there is a distinction between master and player
        selected_patterns = """inbox outbox compose_message intercepted_messages view_sales items_slideshow""".split() # TODO LATER network_management contact_djinns 
        views = [url._callback_str for url in final_urlpatterns if not isinstance(url, RegexURLResolver) and [match for match in selected_patterns if match in url._callback_str]]
        assert len(views) == len(selected_patterns)
        
        def test_views(views):
            for view in views:
                url = reverse(view, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))
                response = self.client.get(url)
                #print response.content
                self.assertEqual(response.status_code, 200, view + " | " + url + " | " + str(response.status_code))

        test_views(views)

        self.dm.set_game_state(True)
        self.dm.transfer_money_between_characters(self.dm.get_global_parameter("bank_name"), username, 1000)
        self.dm.set_game_state(old_state)

        test_views(views)

        self.dm.set_game_state(True)
        gem_name = [key for key, value in self.dm.get_items_for_sale().items() if value["is_gem"] and value["num_items"] >= 6][0] # we only take numerous groups
        self.dm.transfer_object_to_character(gem_name, username)
        self.dm.set_game_state(old_state)

        test_views(views)

        self.assertEqual(self.dm.get_online_users(), [username])
        self.assertEqual(self.dm.get_chatting_users(), [])

        self._logout()
   

    def test_player_game_started_page_displays(self):
        self.dm.set_game_state(True)
        #print "STARTING"
        #import timeit
        #timeit.Timer(self._test_player_get_requests).timeit()
        self._test_player_get_requests()
        #print "OVER"

    def test_player_game_paused_page_displays(self):
        self.dm.set_game_state(False)
        self._test_player_get_requests()

    
    def test_specific_help_pages_behaviour(self):
        self.dm.set_game_state(True)
        
        # TODO FIXME - use Http403 exceptions instead, when new django version is out !!
        
        url = reverse(views.view_help_page, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID,
                                                        keyword=""))
        response = self.client.get(url)
        assert response.status_code == 404

        url = reverse(views.view_help_page, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID,
                                                        keyword="homepage"))
        response = self.client.get(url)
        assert response.status_code == 200
        
        url = reverse(views.view_help_page, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID,
                                                        keyword="runic_translation"))
        response = self.client.get(url)
        assert response.status_code == 404
        
        url = reverse(views.view_help_page, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID,
                                                        keyword="logo_animation"))
        response = self.client.get(url)
        assert response.status_code == 404 # view always available, but no help text available for it
    
    
    def test_encyclopedia_behaviour(self):
        
        url_base = reverse(views.view_encyclopedia, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))        
        
        for login in ("master", "guy1", None):
            
            self._set_user(login)
            
            self.dm.set_game_state(False)
            
            response = self.client.get(url_base+"?search=animal")
            assert response.status_code == 200
            assert "under repair" in response.content.decode("utf8") # no search results
                        
            self.dm.set_game_state(True)
            
            response = self.client.get(url_base)
            assert response.status_code == 200
                   
            url = reverse(views.view_encyclopedia, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID,
                                                               article_id="lokon"))        
            response = self.client.get(url)
            assert response.status_code == 200
            assert "animals" in response.content.decode("utf8")
            
            response = self.client.get(url_base+"?search=animal")
            assert response.status_code == 200
            #print(repr(response.content))
            assert "results" in response.content.decode("utf8") # several results displayed     
                            
            response = self.client.get(url_base+"?search=gerbil")
            assert response.status_code == 302
            assert reverse(views.view_encyclopedia, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID, article_id="gerbil_species")) in response['Location'] 
                                   
                        
class TestGameViewSystem(BaseGameTestCase):
    
    
    def test_mandatory_access_settings(self):
        
        # let's not block the home url...
        assert views.homepage.ACCESS == UserAccess.anonymous
        assert views.homepage.ALWAYS_AVAILABLE == True
        
    
    def test_access_parameters_normalization(self):
        
        from rpgweb.views._abstract_game_view import _normalize_view_access_parameters
        from rpgweb.common import _undefined
        
        res = _normalize_view_access_parameters()
        assert res == dict(access=UserAccess.master,
                            permissions=[],
                            always_available=True)

        res = _normalize_view_access_parameters(UserAccess.anonymous, ["hi"], False)
        assert res == dict(access=UserAccess.anonymous,
                            permissions=["hi"], # would raise an issue later, in metaclass, because we're in anonymous access
                            always_available=False)

        res = _normalize_view_access_parameters(UserAccess.anonymous)
        assert res == dict(access=UserAccess.anonymous,
                            permissions=[],
                            always_available=False) # even in anonymous access

        res = _normalize_view_access_parameters(UserAccess.character)
        assert res == dict(access=UserAccess.character,
                            permissions=[],
                            always_available=False)

        res = _normalize_view_access_parameters(UserAccess.authenticated)
        assert res == dict(access=UserAccess.authenticated,
                            permissions=[],
                            always_available=False)
        
        res = _normalize_view_access_parameters(UserAccess.master)
        assert res == dict(access=UserAccess.master,
                            permissions=[],
                            always_available=True) # logical
        
        res = _normalize_view_access_parameters(UserAccess.character, permissions="sss")
        assert res == dict(access=UserAccess.character,
                            permissions=["sss"], # proper autofix of basestring to list of single item
                            always_available=False)        
    
         
        class myview:
            ACCESS = UserAccess.authenticated
            PERMISSIONS = ["stuff"]
            ALWAYS_AVAILABLE = False
            
        res = _normalize_view_access_parameters(attach_to=myview)
        assert res == dict(access=UserAccess.authenticated,
                            permissions=["stuff"],
                            always_available=False)      
       
        with pytest.raises(AssertionError):
            while True:
                a, b, c = [random.choice([_undefined, False]) for i in range(3)]
                if not all((a, b, c)):
                    break # at leats one of them must NOT be _undefined
            _normalize_view_access_parameters(a, b, c, attach_to=myview)    
            
     
    def test_game_view_registration_decorator(self):
        
        # case of method registration #
        
        def my_little_view(request, *args, **kwargs):
            pass
        
        # stupid cases get rejected in debug mode
        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.master, permissions=["sss"])
        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.master, always_available=False) # master must always access his views!          
        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.anonymous, permissions=["sss"])         
   
        proxy = register_view(my_little_view, access=UserAccess.master, )     
        
        assert isinstance(proxy, ClassInstantiationProxy)
        assert proxy._klass.__name__ == "MyLittleView" # pascal case
        assert proxy._klass.NAME == "my_little_view" # snake case
        assert proxy._klass.NAME in self.dm.GAME_VIEWS_REGISTRY
        
        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.master)  # double registration impossible!
                 
        
        # case of class registration #
        class DummyView(object):
            ACCESS = "sqdqsjkdqskj"
        assert isinstance(DummyView, type)
        
        proxy = register_view(DummyView)     
        assert isinstance(proxy, ClassInstantiationProxy) 
        assert proxy.__dict__["_klass"] is DummyView # no changes to wrapped object!
        register_view(DummyView) # double registration possible, since it's class creation which actually registers it, not that decorator      
        
        
        class OtherDummyView(object):
            ACCESS = "sdqsd"         
        with pytest.raises(AssertionError): # when a klass is given, all other arguments become forbidden
            while True:
                a, b, c, d= [random.choice([_undefined, False]) for i in range(4)]
                if not all((a, b, c)):
                    break # at least one of them must NOT be _undefined
            register_view(DummyView, a, b, c, d)         
                
                
    def test_access_token_computation(self):
        

        datamanager = self.dm
        
        def dummy_view_anonymous(request):
            pass
        view_anonymous = register_view(dummy_view_anonymous, access=UserAccess.anonymous, always_available=False)
        
        def dummy_view_character(request):
            pass        
        view_character = register_view(dummy_view_character, access=UserAccess.character, always_available=False)

        def dummy_view_character_permission(request):
            pass               
        view_character_permission = register_view(dummy_view_character_permission, access=UserAccess.character, permissions=["runic_translation"], always_available=False)
        
        def dummy_view_authenticated(request):
            pass            
        view_authenticated = register_view(dummy_view_authenticated, access=UserAccess.authenticated, always_available=False)
        
        def dummy_view_master(request):
            pass         
        view_master = register_view(dummy_view_master, access=UserAccess.master, always_available=True) # always_available is enforced to True for master views, actually

 
        # check global disabling of views by game master #
        for username in (None, "guy1", "guy2", self.dm.get_global_parameter("master_login")):
            self._set_user(username)
            
            for my_view in (view_anonymous, view_character, view_character_permission, view_authenticated): # not view_master          
                
                my_view._klass.ALWAYS_AVAILABLE = False
                assert my_view.get_access_token(datamanager) == AccessResult.globally_forbidden
                self.dm.set_activated_game_views([my_view._klass.NAME]) # exists in ACTIVABLE_VIEWS_REGISTRY because we registered view with always_available=True
                assert my_view.get_access_token(datamanager) != AccessResult.globally_forbidden
                
                my_view._klass.ALWAYS_AVAILABLE = True
                assert my_view.get_access_token(datamanager) != AccessResult.globally_forbidden
                self.dm.set_activated_game_views([]) # RESET
                assert my_view.get_access_token(datamanager) != AccessResult.globally_forbidden
                                
    
        self._set_user(None)
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_permission.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required
        
        self._set_user("guy1") # has runic_translation permission
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.available
        assert view_character_permission.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required        
        
        self._set_user("guy2") # has NO runic_translation permission
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.available
        assert view_character_permission.get_access_token(datamanager) == AccessResult.permission_required # != authentication required 
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required        
                
        self._set_user(self.dm.get_global_parameter("master_login"))
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.authentication_required # master must downgrade to character!!
        assert view_character_permission.get_access_token(datamanager) == AccessResult.authentication_required # master must downgrade to character!!
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_master.get_access_token(datamanager) == AccessResult.available                        
                
        

                
        
class TestSpecialAbilities(BaseGameTestCase):

    def test_3D_items_display(self):
        
        for autoreverse in (True, False):
                
            viewer_settings = dict( levels=2,
                                    per_level=5, 
                                    index_steps=5,
                                    index_offset=3,
                                    start_level=1,
                                    file_template="openinglogo/crystal%04d.jpg",
                                    image_width=528,
                                    image_height=409,
                                    mode="object",
                                    x_coefficient=12,
                                    y_coefficient=160,
                                    autoreverse=autoreverse,
                                    rotomatic=150, 
                                    music="musics/mymusic.mp3")
            display_data = views._build_display_data_from_viewer_settings(viewer_settings)
    
    
            assert "musics/mymusic.mp3" in display_data["music_url"] # authenticated url
            del display_data["music_url"] 
            
            rel_expected_image_urls = [["openinglogo/crystal0003.jpg",
                                       "openinglogo/crystal0008.jpg",
                                       "openinglogo/crystal0013.jpg",
                                       "openinglogo/crystal0018.jpg",
                                       "openinglogo/crystal0023.jpg"],
                                      ["openinglogo/crystal0028.jpg",
                                       "openinglogo/crystal0033.jpg",
                                       "openinglogo/crystal0038.jpg",
                                       "openinglogo/crystal0043.jpg",
                                       "openinglogo/crystal0048.jpg"],]
            expected_image_urls = [[game_file_url(rel_path) for rel_path in level] for level in rel_expected_image_urls]  
            
            if autoreverse:
                for id, value in enumerate(expected_image_urls):
                    expected_image_urls[id] = value + list(reversed(value))
            
            
            #pprint.pprint(display_data["image_urls"])
            #pprint.pprint(expected_image_urls)    
                        
            assert display_data["image_urls"] == expected_image_urls
            
            del display_data["image_urls"] 
            
            assert display_data == dict(levels=2,
                                        per_level=5 if not autoreverse else 10,
                                        x_coefficient=12,
                                        y_coefficient=160,
                                        rotomatic=150,
                                        image_width=528,
                                        image_height=409,
                                        start_level=1,
                                        mode="object")


    @for_ability(runic_translation_view)
    def test_runic_translation(self):
        runic_translation = self.dm.instantiate_ability("runic_translation")

        assert runic_translation.ability_data

        self._reset_messages()

        message = """ hi |there,   | how  are \t you # today,\n| buddy, # are you  \t\n okay ? """

        phrases = runic_translation._tokenize_rune_message(message)
        self.assertEqual(phrases, ['hi', 'there,', 'how are you', 'today,', 'buddy,', 'are you okay ?'])

        self.assertEqual(runic_translation._tokenize_rune_message(""), [])

        """ Too wrong and complicated...
        phrases = self.dm._tokenize_rune_message(message, left_to_right=True, top_to_bottom=False)
        self.assertEqual(phrases, ['are you okay ?', 'today,', 'buddy,', 'hi', 'there,', 'how are you'])

        phrases = self.dm._tokenize_rune_message(message, left_to_right=False, top_to_bottom=True)
        self.assertEqual(phrases, ['how are you', 'there,', 'hi' , 'buddy,', 'today,', 'are you okay ?'])

        phrases = self.dm._tokenize_rune_message(message, left_to_right=False, top_to_bottom=False)
        self.assertEqual(phrases, ['are you okay ?', 'buddy,', 'today,', 'how are you', 'there,', 'hi'])
        """

        translator = runic_translation._build_translation_dictionary("na | tsu | me",
                                                                      "yowh | man | cool")
        self.assertEqual(translator, dict(na="yowh", tsu="man", me="cool"))

        self.assertRaises(Exception, runic_translation._build_translation_dictionary, "na | tsu | me | no",
                          "yowh | man | cool")

        self.assertRaises(Exception, runic_translation._build_translation_dictionary, "me | tsu | me",
                          "yowh | man | cool")

        assert runic_translation.ability_data

        decoded_rune_string = "na  hu,  \t yo la\ttsu ri !\n go"
        translator = {"na hu": "welcome",
                      "yo la tsu": "people"}
        random_words = "hoy ma mi mo mu me".split()
        translated_tokens = runic_translation._try_translating_runes(decoded_rune_string, translator=translator, random_words=random_words)

        self.assertEqual(len(translated_tokens), 4, translated_tokens)
        self.assertEqual(translated_tokens[0:2], ["welcome", "people"])
        for translated_token in translated_tokens[2:4]:
            self.assertTrue(translated_token in random_words)

        # temporary solution to deal with currently untranslated runes... #FIXME
        available_translations = [(item_name, settings) for (item_name, settings) in runic_translation.get_ability_parameter("references").items() 
                                    if settings["decoding"].strip()]
        (rune_item, translation_settings) = available_translations[0]

        transcription_attempt = translation_settings["decoding"] # '|' and '#'symbols are automatically cleaned
        expected_result = runic_translation._normalize_string(translation_settings["translation"].replace("#", " ").replace("|", " "))
        translation_result = runic_translation._translate_rune_message(rune_item, transcription_attempt)
        self.assertEqual(translation_result, expected_result)

        runic_translation._process_translation_submission("guy1", rune_item, transcription_attempt)

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


    @for_ability(house_locking_view)
    def test_house_locking(self):

        house_locking = self.dm.instantiate_ability("house_locking")
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


    @for_ability(wiretapping_management_view)
    def test_wiretapping_management(self):
        
        self._reset_messages()
        
        self._set_user("guy1") # has all permissions
        
        char_names = self.dm.get_character_usernames()

        wiretapping = self.dm.instantiate_ability("wiretapping")
        
        wiretapping._perform_lazy_initializations() # normally done during request processing
        
        wiretapping.change_wiretapping_targets(PersistentList())
        self.assertEqual(wiretapping.get_current_targets(), [])

        wiretapping.change_wiretapping_targets([char_names[0], char_names[0], char_names[1]])

        self.assertEqual(set(wiretapping.get_current_targets()), set([char_names[0], char_names[1]]))
        self.assertEqual(wiretapping.get_listeners_for(char_names[1]), ["guy1"])

        self.assertRaises(UsageError, wiretapping.change_wiretapping_targets, ["dummy_name"])
        self.assertRaises(UsageError, wiretapping.change_wiretapping_targets, [char_names[i] for i in range(wiretapping.get_ability_parameter("max_wiretapping_targets") + 1)])

        self.assertEqual(set(wiretapping.get_current_targets()), set([char_names[0], char_names[1]])) # didn't change
        self.assertEqual(wiretapping.get_listeners_for(char_names[1]), ["guy1"])


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



"""
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
    """
    
