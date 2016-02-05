# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import random
from textwrap import dedent
import tempfile
import shutil
import inspect
from pprint import pprint

from ._test_tools import *
from ._dummy_abilities import *

import fileservers
from django.utils.functional import Promise # used eg. for lazy-translated strings
from django.utils import timezone

from pychronia_game.datamanager.abstract_ability import AbstractAbility
from pychronia_game.datamanager.action_middlewares import CostlyActionMiddleware, \
    CountLimitedActionMiddleware, TimeLimitedActionMiddleware
from pychronia_game.common import _undefined, config, AbnormalUsageError, reverse, \
    UsageError, checked_game_file_path, NormalUsageError, determine_asset_url
from pychronia_game.templatetags.helpers import _generate_encyclopedia_links, \
    advanced_restructuredtext, _generate_messaging_links, _generate_site_links, \
    format_enriched_text, _generate_game_file_links, _generate_game_image_thumbnails
from pychronia_game import views, utilities, authentication
from pychronia_game.utilities import autolinker
from django.test.client import RequestFactory
from pychronia_game.datamanager.datamanager_administrator import retrieve_game_instance, \
    _get_zodb_connection, GameDataManager, get_all_instances_metadata, \
    delete_game_instance, check_zodb_structure, change_game_instance_status, \
    GAME_STATUSES, list_backups_for_game_instance, backup_game_instance_data, \
    _get_backup_folder
from pychronia_game.tests._test_tools import temp_datamanager
from django.forms.fields import Field
from django.core.urlresolvers import resolve, NoReverseMatch
from pychronia_game.views import friendship_management
from pychronia_game.views.abilities import house_locking, \
    wiretapping_management, runic_translation, artificial_intelligence_mod, telecom_investigation_mod
from django.contrib.auth.models import User
from pychronia_game.authentication import clear_all_sessions
from pychronia_game.utilities.mediaplayers import generate_image_viewer
from django.core.urlresolvers import RegexURLResolver
from pychronia_game.datamanager.abstract_form import AbstractGameForm, GemPayementFormMixin
from ZODB.POSException import POSError
from pychronia_game.meta_administration_views import compute_game_activation_token, \
    decode_game_activation_token
from types import *






class TestUtilities(BaseGameTestCase):
    '''
    def __call__(self, *args, **kwds):
        return unittest.TestCase.run(self, *args, **kwds) # we bypass test setups from django's TestCase, to use py.test instead
        '''
    def test_restructuredtext_handling(self):
        from docutils.utils import SystemMessage

        restructuredtext = advanced_restructuredtext # we use our own version

        assert restructuredtext("""aaaa*aaa""") # star is ignored

        # outputs errors on stderr, but doesn't break
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
                    
                    .. embed_audio:: http://mydomain.com/myfile<ABC
                    
                    .. embed_video:: https://hi.com/a&b.flv
                        :width: 219px
                        :height: 121px
                        :image: /a<kl.jpg
               
                    .. embed_image:: https://hisss.com/a&b.jpg
                        :alias: default
                        :align: center

                    .. embed_video:: https://hi.com/cantwork.mp4
                    
                    .. embed_video:: https://cantwork.mp4/
                    """))

        assert "title1" in html and "title2" in html

        print("------>", html)

        for mystr in ("<object", "AudioPlayer.embed", "http://mydomain.com/myfile<ABC"): # IMPORTANT - url-escaping of file url
            assert mystr in html

        for mystr in ("<object", "mediaplayer", "https://hi.com/a&amp;b.flv"): # AT LEAST html-escaped, but urlescaping could be necessary for some media types
            assert mystr in html

        for mystr in ("<img class=\"imageviewer align-center\"", "https://hisss.com/a&amp;b.jpg", "500px"): # fallback to default width/height since image url is buggy (so easy-thumbnails fails)
            assert mystr in html

        assert 'href="https://cantwork.mp4/"' in html
        assert 'https://cantwork.mp4/' in html


        # IMPORTANT - security measures #

        html = restructuredtext(dedent("""
        
                    .. include:: manage.py
                    
                    """))
        assert "System Message" in html and "directive disabled" in html
        assert "django" not in html

        html = restructuredtext(dedent("""
        
                    .. raw:: python
                        :file: manage.py
                    
                    """))
        assert "System Message" in html and "directive disabled" in html
        assert "django" not in html


        html = restructuredtext(dedent("""
        
                    .. raw:: html
                    
                        <script></script>
                        
                    
                    """))
        assert "System Message" in html and "directive disabled" in html
        assert "<script" not in html



        # now our settings overrides, do they work ?
        buggy_rst = dedent("""
        
                    mytitle
                    ========
                    
                    bad *text `here
                    
                    :xyzizjzb:`qqq`
                    
                    """)


        html = restructuredtext(buggy_rst,
                    initial_header_level=2,
                    report_level=1)
        ## print (">>>>>>>>>>", html)
        assert "<h2" in html
        assert "System Message" in html # specific error divs
        assert 'class="problematic"' in html # spans around faulty strings


        html = restructuredtext(buggy_rst,
                    initial_header_level=2,
                    report_level=4)
        ## print (">>>>>>>>>>", html)
        assert "<h2" in html
        assert "System Message" not in html # no additional error divs
        assert 'class="problematic"' in html # spans remain though




    def test_sphinx_publisher_settings(self) :
        from django.utils.encoding import smart_str, force_unicode
        from docutils.core import publish_parts
        docutils_settings = {"initial_header_level": 3,
                             "doctitle_xform": False,
                             "sectsubtitle_xform": False}
        parts = publish_parts(source=smart_str("""title\n=======\n\naaa\n"""), # lone title would become document title by default - we prevent it
                              writer_name="html4css1", settings_overrides=docutils_settings)
        assert parts["fragment"] == '<div class="section" id="title">\n<h3>title</h3>\n<p>aaa</p>\n</div>\n'
        # pprint.pprint(parts)


    def test_html_autolinker(self):

        regex = autolinker.join_regular_expressions_as_disjunction(("[123]", "(k*H?)"), as_words=False)
        assert regex == r"(?:[123])|(?:(k*H?))"
        assert re.compile(regex).match("2joll")

        regex = autolinker.join_regular_expressions_as_disjunction(("[123]", "(k*H)"), as_words=True)
        assert regex == r"(?:\b[123]\b)|(?:\b(k*H)\b)"
        assert re.compile(regex).match("kkH")


        input0 = '''one<a>ones</a>'''
        res = autolinker.generate_links(input0, "ones?", lambda x: dict(href="TARGET_" + x.group(0), title="mytitle"))
        assert res == '''<a href="TARGET_one" title="mytitle">one</a><a>ones</a>'''


        input = dedent('''
        <html>
        <head><title>Page title one</title></head>
        <body>
        <div>Hi</div>
        <p id="firstpara" class="one red" align="center">This is one paragraph <b>ones</b>.</a>
        <a href="http://aaa">This is one paragraph <b>one</b>.</a>
        </html>''')

        res = autolinker.generate_links(input, "ones?", lambda x: dict(href="TARGET_" + x.group(0), title="mytitle"))

        #print(">>>", res)

        assert res.strip() == dedent('''
        <html>
        <head><title>Page title one</title></head>
        <body>
        <div>Hi</div>
        <p align="center" class="one red" id="firstpara">This is <a href="TARGET_one" title="mytitle">one</a> paragraph <b><a href="TARGET_ones" title="mytitle">ones</a></b>.</p></body></html>
        <a href="http://aaa">This is one paragraph <b>one</b>.</a>''').strip()



    def test_generate_image_viewer(self):

        self._reset_django_db()

        code = generate_image_viewer("http://otherdomain/myimage.jpg")
        assert 'src="http://otherdomain/myimage.jpg"' in code # untouched

        local_img_url = game_file_url("unexisting/img.jpg")
        code = generate_image_viewer(local_img_url, preset=random.choice(("default", "badalias")))
        assert "unexisting/img.jpg" in code

        real_img = "personal_files/master/1236637123369.jpg"
        utilities.check_is_game_file(real_img)
        local_img_url = game_file_url(real_img)
        code = generate_image_viewer(local_img_url, preset=random.choice(("default", "badalias")))
        assert real_img in code # as target only
        assert "thumbs/" in code


    def test_type_conversions(self):

        # test 1 #

        class dummy(object):
            def __init__(self):
                self.attr1 = ["hello"]
                self.attr2 = 34

        data = dict(abc=[1, 2, 3], efg=dummy(), hij=(1.0, 2), klm=set([8, ()]))

        newdata = utilities.convert_object_tree(data, utilities.python_to_zodb_types)

        self.assertTrue(isinstance(newdata, utilities.PersistentMapping))
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

        data = utilities.PersistentMapping(abc=utilities.PersistentList([1, 2, 3]))

        newdata = utilities.convert_object_tree(data, utilities.zodb_to_python_types)

        self.assertTrue(isinstance(newdata, dict))

        self.assertTrue(isinstance(newdata["abc"], list))

        newnewdata = utilities.convert_object_tree(newdata, utilities.python_to_zodb_types)

        self.assertEqual(data, newnewdata)




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


    def test_media_url_determination(self):

        res = determine_asset_url(None)
        assert res == ""

        res = determine_asset_url("")
        assert res == ""

        res = determine_asset_url(dict(url=None))
        assert res == ""

        for val in ("http://mystuff",
                    dict(file="http://mystuff", url=None),
                    dict(file=None, url="http://mystuff")):
            res = determine_asset_url(val)
            assert res == "http://mystuff"

        for val in ("audio/musics/sample.mp3",
                    dict(file="audio/musics/sample.mp3", url=None),
                    dict(file=None, url="audio/musics/sample.mp3")):
            res = determine_asset_url(val)
            assert res == "http://localhost:8000/files/7211b1bf/audio/musics/sample.mp3"
            res = determine_asset_url(val, absolute=False)
            assert res == "/files/7211b1bf/audio/musics/sample.mp3"


    def test_url_protection_functions(self):

        hash = hash_url_path("whatever/shtiff/kk.mp3?sssj=33")
        assert len(hash) == 8
        for c in hash:
            assert c in "abcdefghijklmnopqrstuvwxyz0123456789"

        rel_path = checked_game_file_path(game_file_url("/my/file/path"))
        assert rel_path == "my/file/path"

        rel_path = checked_game_file_path("http://baddomain/files/%s/my_file/a.jpg" % hash_url_path("my_file/a.jpg")) # we only care about PATH component of url
        assert rel_path == "my_file/a.jpg"

        assert checked_game_file_path("/bad/stuffs.mpg") is None
        assert checked_game_file_path(config.GAME_FILES_URL + "bad/stuffs.mpg") is None



    def test_rst_game_file_url_tags_handling(self):

        self._reset_django_db() # for thumbnails

        rst = dedent(r"""
        
                    [   GAME_FILE_URL 'myfile.jpg'    ] here
                    
                    .. image:: picture.jpeg [GAME_FILE_URL /a/cat/image.png]
                
                        [GAME_FILE_URL 'aa bb/cc']
                        
                        [GAME_FILE_URL "bad
                        path.jpg]
                    """)

        res = _generate_game_file_links(rst, self.dm)
        #print("\n@@@@@@\n", res)

        # WILL BREAK IF settings.SECRET_KEY IS CHANGED #
        assert res.strip() == dedent("""
                                /files/dfb1c549/myfile.jpg here

                                .. image:: picture.jpeg /files/92572209/a/cat/image.png
                                
                                    /files/8112d6b3/aa bb/cc
                                
                                    [GAME_FILE_URL "bad
                                    path.jpg]
                                """).strip()

        # -----------------------------------

        rst = dedent(r"""
        
                    [   GAME_IMAGE_URL 'world_map.jpg'   'default' ] here
                    
                    .. image:: picture.jpeg [GAME_IMAGE_URL "world_map.jpg" 'badalias' ]
                
                        [GAME_IMAGE_URL 'aa bb/cc']
                        
                        [GAME_IMAGE_URL "bad
                        path.jpg]
                    """)

        res = _generate_game_image_thumbnails(rst, self.dm)

        print(res)

        assert res.strip() == dedent("""
                                    /files/3560c5f8/thumbs/world_map.jpg.300x300_q85_autocrop.jpg here
                                    
                                    .. image:: picture.jpeg /files/3ab7d512/world_map.jpg
                                    
                                        [GAME_IMAGE_URL 'aa bb/cc']
                                    
                                        [GAME_IMAGE_URL "bad
                                        path.jpg]
                                    """).strip()



    def test_rst_site_links_generation(self):

        # here we have: 1 bad view name, 2 good tags, and then an improperly formatted tag #
        rst = dedent(r"""
                    hi
                    
                    [ GAME_PAGE_LINK "hello" "kj.jjh" ]
                    
                    [GAME_PAGE_LINK'good1' "pychronia_game.views.homepage"]
                    
                    [GAME_PAGE_LINK "good2" "view_sales"]
                    
                    [ GAME_PAGE_LINK "bad\"string" "view_sales" ]
                    """)

        html = _generate_site_links(rst, self.dm)

        print("------->", html)
        assert html.strip() == dedent(r"""
                                hi

                                hello
                                
                                <a href="/TeStiNg/guest/">good1</a>
                                <a href="/TeStiNg/guest/view_sales/">good2</a>
                                
                                [ GAME_PAGE_LINK "bad\"string" "view_sales" ]
                                """).strip()


    def test_format_enriched_text_behaviour(self):
        """
        We only test here that dependencies are well triggered, we don't test them precisely.
        """

        assert not self.dm.get_event_count("GENERATE_MESSAGING_LINKS")
        assert not self.dm.get_event_count("GENERATE_ENCYCLOPEDIA_LINKS")
        assert not self.dm.get_event_count("GENERATE_SITE_LINKS")
        assert not self.dm.get_event_count("GENERATE_GAME_FILE_LINKS")
        assert not self.dm.get_event_count("GENERATE_GAME_IMAGE_THUMBNAILS")

        rst = dedent(r"""
                    hi
                    ---
                    
                    lokons
                    
                    rodents
                    
                    gerbils
                    
                    ugly
                    
                    [INSTANCE_ID]
                    
                    .. baddirective:: aaa
                    
                    hi[BR]you
                    """)
        html = format_enriched_text(self.dm, rst, initial_header_level=2, report_level=5, excluded_link=u"wu\\gly_é")

        assert self.dm.get_event_count("GENERATE_MESSAGING_LINKS") == 1
        assert self.dm.get_event_count("GENERATE_ENCYCLOPEDIA_LINKS") == 1
        assert self.dm.get_event_count("GENERATE_SITE_LINKS") == 1
        assert self.dm.get_event_count("GENERATE_GAME_FILE_LINKS") == 1
        assert self.dm.get_event_count("GENERATE_GAME_IMAGE_THUMBNAILS") == 1

        assert "hi<br />you" in html # handy


        #print("------->", html)
        assert html.strip() == dedent("""
                            <div class="section" id="hi">
                            <h2>hi</h2>
                            <p>lokons</p>
                            <p>rodents</p>
                            <p><a href="/TeStiNg/guest/encyclopedia/?search=gerbils">gerbils</a></p>
                            <p>ugly</p>
                            <p>TeStiNg</p>
                            <p>hi<br />you</p>
                            </div>""").strip()


        rst = dedent(r"""
                    hello
                    ======
                    
                    .. baddirective:: aaa
                    
                    """)
        html = format_enriched_text(self.dm, rst)  # we ensure NO PERSISTENCE of previously set options!!

        #print("------->", html)

        html = html.strip().replace("&quot;", '"') # not always entities, depending on software versions...

        # beware, there are smart quotes in the results!
        assert html == dedent("""
                                <div class="section" id="hello">
                                <h2>hello</h2>
                                <div class="system-message">
                                <p class="system-message-title">System Message: ERROR/3 (<tt class="docutils">&lt;string&gt;</tt>, line 5)</p>
                                <p>Unknown directive type \u201cbaddirective\u201d.</p>
                                <pre class="literal-block">
                                .. baddirective:: aaa
                                
                                </pre>
                                </div>
                                </div>
                                """).strip()



class TestMetaAdministration(unittest.TestCase): # no django setup required ATM

    def test_game_instance_backups(self):

        reset_zodb_structure()

        game_instance_id = "antropiatestgame"

        # cleanup before test
        backup_folder = _get_backup_folder(game_instance_id)
        if os.path.exists(backup_folder):
            for i in os.listdir(backup_folder):
                os.remove(os.path.join(backup_folder, i))

        res = list_backups_for_game_instance(game_instance_id)
        assert res == []

        with pytest.raises(UsageError):
            backup_game_instance_data(game_instance_id, comment="abc")

        res = list_backups_for_game_instance(game_instance_id)
        assert res == []

        skip_randomizations = random.choice((True, False))
        create_game_instance(game_instance_id, creator_login="ze_creator_test", skip_randomizations=skip_randomizations)

        backup_game_instance_data(game_instance_id, comment="important")

        res = list_backups_for_game_instance(game_instance_id)
        assert len(res) == 1
        assert "important" in res[0]

        backup_file_path = os.path.join(_get_backup_folder(game_instance_id), res[0])

        with open(backup_file_path, "U") as f:
            raw_yaml_data = f.read().decode("utf8")

        raw_yaml_data = raw_yaml_data.replace(u"pangea.com", u"planeta.fr") # MASS REPLACE in data

        dm = datamanager_administrator.retrieve_game_instance(game_instance_id=game_instance_id,
                                                              request=None,
                                                              metadata_checker=None)
        assert not dm.get_event_count("BASE_CHECK_DB_COHERENCE_PUBLIC_CALLED")
        data_tree = dm.load_zope_database_from_string(raw_yaml_data)
        assert dm.get_event_count("BASE_CHECK_DB_COHERENCE_PUBLIC_CALLED") == 1 # data well checked

        assert "metadata" not in data_tree # it's well ONLY the "data" part of the game instance tree
        assert "data" not in data_tree
        assert data_tree["global_parameters"]["pangea_network_domain"] == u"planeta.fr" # success!



    def test_game_instance_management_api(self):

        reset_zodb_structure()

        assert not get_all_instances_metadata()

        creator_email = random.choice((None, "aaa@sffr.com"))
        skip_randomizations = random.choice((True, False))

        game_instance_id = "mystuff"
        assert not game_instance_exists(game_instance_id)
        create_game_instance(game_instance_id, creator_login="ze_creator_test", creator_email=creator_email, skip_randomizations=skip_randomizations)
        assert game_instance_exists(game_instance_id)

        all_res = get_all_instances_metadata()
        assert len(all_res) == 1
        res = all_res[0]
        assert res["creator_login"] == "ze_creator_test"
        assert res["creator_email"] == creator_email
        assert res["creation_time"] == res["last_access_time"] == res["last_status_change_time"]
        assert res["accesses_count"] == 0
        assert res["status"] == GAME_STATUSES.active == "active"
        assert res["maintenance_until"] is None

        initial_last_access_time = res["last_access_time"]
        assert initial_last_access_time  # immediately set

        dm = retrieve_game_instance(game_instance_id, update_timestamp=False)

        time.sleep(1)

        dm = retrieve_game_instance(game_instance_id)
        assert dm.is_initialized
        assert dm.data

        assert bool(dm.get_character_properties("guy1")["password"] == u"elixir") == skip_randomizations # conditional reset of player passwords

        with pytest.raises(UsageError):
            retrieve_game_instance("sqdqsd")

        dm = retrieve_game_instance(game_instance_id)

        time.sleep(1)

        res = get_all_instances_metadata()[0]
        assert res["last_access_time"] == initial_last_access_time  # never updated so far

        dm = retrieve_game_instance(game_instance_id, update_timestamp=True)

        res = get_all_instances_metadata()[0]
        assert res["last_access_time"] > initial_last_access_time  # UPDATED

        time.sleep(1)

        with pytest.raises(UsageError):
            delete_game_instance("sqdqsd")
        with pytest.raises(UsageError):
            delete_game_instance(game_instance_id) # must be NOn-ACTIVE

        with pytest.raises(UsageError):
            change_game_instance_status("sqdqsd", GAME_STATUSES.aborted)

        change_game_instance_status(game_instance_id, GAME_STATUSES.aborted, maintenance_until=datetime.utcnow() + timedelta(seconds=1))
        with pytest.raises(GameMaintenanceError):
            retrieve_game_instance(game_instance_id)
        retrieve_game_instance(game_instance_id, metadata_checker=None) # disable maintenance check
        time.sleep(1)
        retrieve_game_instance(game_instance_id) # NOW works even without force=True

        change_game_instance_status(game_instance_id, GAME_STATUSES.active)
        change_game_instance_status(game_instance_id, GAME_STATUSES.terminated)
        change_game_instance_status(game_instance_id, random.choice((GAME_STATUSES.terminated, GAME_STATUSES.aborted)))

        all_res = get_all_instances_metadata()
        assert len(all_res) == 1
        res = all_res[0]
        assert res["creator_login"] == "ze_creator_test"
        assert res["creation_time"] < res["last_access_time"] < res["last_status_change_time"]
        assert res["accesses_count"] == 6
        assert res["status"] != GAME_STATUSES.active
        assert res["maintenance_until"] is not None # was left as is

        delete_game_instance(game_instance_id)

        assert not game_instance_exists(game_instance_id)
        assert not get_all_instances_metadata()
        with pytest.raises(UsageError):
            retrieve_game_instance(game_instance_id)


    def test_meta_admin_utilities(self):

        data = compute_game_activation_token(u"myinstànce", u"mylogïn", "my@email.fr")
        assert decode_game_activation_token(data) == (u"myinstànce", u"mylogïn", "my@email.fr")

        data = compute_game_activation_token(u"2myinstànce", u"amylogïn", None)
        assert decode_game_activation_token(data) == (u"2myinstànce", u"amylogïn", None)


    def test_admin_scripts(self):

        from pychronia_game.scripts import backup_all_games, check_global_sanity, notify_novelties_by_email, reset_demo_account

        reset_zodb_structure()

        assert reset_demo_account.execute() == None

        assert backup_all_games.execute() == 1

        assert check_global_sanity.execute() == (1, True)

        dm = retrieve_game_instance("DEMO")
        dm.post_message("guy2@pangea.com",
                         recipient_emails=["guy1@pangea.com"], # HAS NEWS
                         subject="subj22323", body="qsdqsd")

        (idx, successes, errors) = notify_novelties_by_email.execute()
        assert (idx, successes, errors) == (1, 0, 1) # no smtp server, so exception!




class TestDatamanager(BaseGameTestCase):


    def test_public_method_wrapping(self):

        # TODO FIXME - extend this check action methods of all ABILITIES !!! FIXME


        special_methods = """begin rollback commit close check_no_pending_transaction is_in_writing_transaction
                             begin_top_level_wrapping end_top_level_wrapping is_under_top_level_wrapping
                             sort_email_addresses_list""".split()

        for attr in dir(GameDataManager):
            if attr.startswith("_") or attr in special_methods:
                continue

            # we remove class/static methods, and some utilities that don't need decorators.
            if attr in ("""
                        notify_event get_event_count clear_event_stats clear_all_event_stats
                        
                        register_permissions register_ability register_game_view get_abilities 
                        get_activable_views get_game_views instantiate_ability instantiate_game_view
                        """.split()):
                continue

            obj = getattr(GameDataManager, attr)
            if not inspect.isroutine(obj):
                continue

            if not getattr(obj, "_is_under_transaction_watcher", None) \
                and not getattr(obj, "_is_under_readonly_method", None):
                raise AssertionError("Undecorated public datamanager method: %s" % obj)


        assert GameDataManager.process_secret_answer_attempt._is_always_writable == False # sensible DEFAULT
        assert GameDataManager.access_novelty._is_always_writable == False
        assert GameDataManager.mark_current_playlist_read._is_always_writable == False

        assert GameDataManager.set_game_state._is_always_writable == True # even if master bypasses constraints here
        assert GameDataManager.sync_game_view_data._is_always_writable == True
        assert GameDataManager.set_dispatched_message_state_flags._is_always_writable == True


    def test_zodb_conflict_retrier(self):
        """
        We ensure ZODB conflict errors lead to a retry.
        """
        ERROR_TYPE = ConflictError

        def broken(*args, **kwargs):
            self.dm.notify_event("BROKEN_DUMMY_FUNC_CALLED")
            raise ERROR_TYPE("dummy error")

        self.dm.get_character_properties = broken # INSTANCE attribute, no problem

        for func in (self.dm.get_wiretapping_targets, # READONLY
                     self.dm.set_confidentiality_protection_status): # WRITABLE
            self.dm.clear_all_event_stats()
            with pytest.raises(AbnormalUsageError) as exc_info:
                func()
            assert "Concurrent access" in str(exc_info.value)
            assert self.dm.get_event_count("BROKEN_DUMMY_FUNC_CALLED") == 3 # 3 attempts max

        del self.dm.get_character_properties
        self.dm.check_database_coherence()
        self.dm.get_character_properties = broken # INSTANCE attribute, no problem

        for ERROR_TYPE in (UsageError, EnvironmentError, TypeError):
            for func in (self.dm.get_wiretapping_targets, self.dm.set_confidentiality_protection_status):
                self.dm.clear_all_event_stats()
                with pytest.raises(ERROR_TYPE):
                    func()
                assert self.dm.get_event_count("BROKEN_DUMMY_FUNC_CALLED") == 1 # no retries in these cases

        del self.dm.get_character_properties
        self.dm.check_database_coherence()



    @for_datamanager_base
    def test_requestless_datamanager(self):

        assert self.dm.request
        assert not self.dm.request.is_ajax()

        user = self.dm.user
        assert user._is_user_messaging_possible()

        self.dm.request.is_ajax = lambda: True
        assert self.dm.request.is_ajax()

        # user notifications get swallowed because AJAX MODE

        assert not user._is_user_messaging_possible()
        user.add_message("sqdqsd sss")
        user.add_error("fsdfsdf")
        assert user.get_notifications() == []
        assert not user.has_notifications()
        user.discard_notifications()

        del self.dm.request.is_ajax
        assert not self.dm.request.is_ajax()

        self.dm._request = None
        assert self.dm.request is None # property

        # user notifications get swallowed because NO REQUEST
        user = self.dm.user
        assert not user._is_user_messaging_possible()
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

            CastratedDataManager = type(str('Dummy' + core_module.__name__), (core_module,), {})
            castrated_dm = CastratedDataManager.__new__(CastratedDataManager) # we bypass __init__() call there
            utilities.TechnicalEventsMixin.__init__(castrated_dm) # only that mixing gets initizalized

            try:
                root = _get_zodb_connection().root()
                my_id = str(random.randint(1, 10000))
                root[my_id] = PersistentMapping()
                castrated_dm.__init__(game_instance_id=my_id,
                                      game_root=root[my_id],
                                      request=self.request)
            except Exception, e:
                transaction.abort()
            assert castrated_dm.get_event_count("BASE_DATA_MANAGER_INIT_CALLED") == 1

            try:
                castrated_dm._init_from_db()
            except Exception, e:
                transaction.abort()
            assert castrated_dm.get_event_count("BASE_DATA_MANAGER_INIT_FROM_DB_CALLED") == 1

            try:
                castrated_dm._load_initial_data()
            except Exception, e:
                transaction.abort()
            assert castrated_dm.get_event_count("BASE_LOAD_INITIAL_DATA_CALLED") == 1

            try:
                castrated_dm._check_database_coherence()
            except Exception, e:
                transaction.abort()
            assert castrated_dm.get_event_count("BASE_CHECK_DB_COHERENCE_PRIVATE_CALLED") == 1

            try:
                report = PersistentList()
                castrated_dm._process_periodic_tasks(report)
            except Exception, e:
                transaction.abort()
            assert castrated_dm.get_event_count("BASE_PROCESS_PERIODIC_TASK_CALLED") == 1


    @for_core_module(FlexibleTime)
    def test_permission_handling(self):

        assert self.dm.build_permission_select_choices()
        assert "purchase_confidentiality_protection" in self.dm.PERMISSIONS_REGISTRY # EXTRA_PERMISSIONS system

        permission = "access_world_scan" # exists because REQUIRES_CHARACTER_PERMISSION=True
        assert permission in self.dm.PERMISSIONS_REGISTRY

        self._set_user("guy1")
        assert not self.dm.has_permission(permission=permission)
        self.dm.update_permissions(permissions=[permission])
        assert self.dm.has_permission(permission=permission)
        assert self.dm.user.has_permission(permission)
        self.dm.update_permissions(permissions=[])
        assert not self.dm.has_permission(username="guy1", permission=permission)
        assert not self.dm.user.has_permission(permission)

        self._set_user("guy3")
        assert not self.dm.has_permission(permission=permission)
        self.dm.update_allegiances(allegiances=["sciences"]) # has that "permission"
        assert self.dm.has_permission(permission=permission)
        self.dm.update_permissions(permissions=[permission])
        assert self.dm.has_permission(permission=permission) # permission both personally and via allegiance
        assert self.dm.user.has_permission(permission)
        self.dm.update_allegiances(allegiances=[])
        assert self.dm.has_permission(permission=permission) # still personally
        self.dm.update_permissions(permissions=[])
        assert not self.dm.has_permission(permission=permission)
        assert not self.dm.user.has_permission(permission)

        permission_other = "view_others_belongings"
        self.dm.set_permission("guy3", permission, is_present=True)
        self.dm.set_permission("guy3", permission, is_present=True)
        assert self.dm.user.has_permission(permission)
        assert not self.dm.user.has_permission(permission_other)

        self.dm.set_permission("guy3", permission_other, is_present=True)
        self.dm.set_permission("guy3", permission, is_present=False)
        self.dm.set_permission("guy3", permission, is_present=False)
        assert not self.dm.user.has_permission(permission)
        assert self.dm.user.has_permission(permission_other)


    @for_core_module(FlexibleTime)
    def test_flexible_time_module(self):

        game_length = 45.3 # test fixture
        assert self.dm.get_global_parameter("game_theoretical_length_days") == game_length

        self.assertRaises(Exception, self.dm.compute_effective_remote_datetime, (3, 2))

        for value in [0.025 / game_length, (0.02 / game_length, 0.03 / game_length)]: # beware of the rounding to integer seconds...

            now = datetime.utcnow()
            dt = self.dm.compute_effective_remote_datetime(value)
            assert now + timedelta(seconds=1) <= dt <= now + timedelta(seconds=2), (now, dt)

            self.assertEqual(utilities.is_past_datetime(dt), False)
            time.sleep(0.5)
            self.assertEqual(utilities.is_past_datetime(dt), False)
            time.sleep(2)
            self.assertEqual(utilities.is_past_datetime(dt), True)

            utc = datetime.utcnow()
            now = datetime.now()
            now2 = utilities.utc_to_local(utc)
            self.assertTrue(now - timedelta(seconds=1) < now2 < now + timedelta(seconds=1))

        dt = self.dm.compute_effective_remote_datetime(delay_mn=(-10, 10))
        dt2 = self.dm.compute_effective_remote_datetime(delay_mn=(12, 20))
        dt3 = self.dm.compute_effective_remote_datetime(delay_mn= -12)
        assert dt3 < dt < dt2


    @for_core_module(CurrentUserHandling)
    def test_game_writability_summarizer(self):

        self._set_user("guy1")
        res = self.dm.determine_actual_game_writability()
        assert res["writable"]
        assert not res["reason"]


        self.dm.propose_friendship("guy1", "guy2")
        self.dm.propose_friendship("guy2", "guy1")

        self._set_user(random.choice(("master", "guy2")), impersonation_target="guy1", impersonation_writability=False)
        res = self.dm.determine_actual_game_writability()
        assert not res["writable"]
        assert res["reason"] # IMPERSONATION
        assert not self.dm.is_game_writable()

        self._set_user(None, impersonation_target="master", impersonation_writability=False, is_superuser=True)
        res = self.dm.determine_actual_game_writability()
        assert not res["writable"]
        assert res["reason"] # IMPERSONATION
        assert not self.dm.is_game_writable()

        self._set_user("master", impersonation_target="guy1", impersonation_writability=True)
        res = self.dm.determine_actual_game_writability()
        assert res["writable"]
        assert res["reason"] # IMPERSONATION
        assert self.dm.is_game_writable()

        self._set_user(None, impersonation_target="master", impersonation_writability=True, is_superuser=True)
        res = self.dm.determine_actual_game_writability()
        assert res["writable"]
        assert res["reason"] # IMPERSONATION
        assert self.dm.is_game_writable()


        self.dm.set_game_state(False) # PAUSE GAME #

        self._set_user("master")
        res = self.dm.determine_actual_game_writability()
        assert res["writable"]
        assert not res["reason"] # no impersonation, and we don't care about game pause because we're master
        assert self.dm.is_game_writable()

        self._set_user("guy1")
        res = self.dm.determine_actual_game_writability()
        assert not res["writable"]
        assert res["reason"] # game is paused
        assert not self.dm.is_game_writable()




    @for_core_module(CharacterHandling)
    def test_character_handling(self):

        self._set_user("guy1")

        assert self.dm.update_official_character_data("guy1", official_name="Simon ", official_role="A killer ", gamemaster_hints="ABCD", is_npc=True, extra_goods="hi\nall")
        data = self.dm.get_character_properties("guy1")
        assert data["official_name"] == "Simon "
        assert data["official_role"] == "A killer "
        assert data["gamemaster_hints"] == "ABCD"
        assert data["is_npc"] == True
        assert data["extra_goods"] == "hi\nall"
        assert not self.dm.update_official_character_data("guy1", official_name=None, is_npc=None)
        data = self.dm.get_character_properties("guy1")
        assert data["official_name"] == "Simon "
        assert data["official_role"] == "A killer "
        assert data["gamemaster_hints"] == "ABCD"
        assert data["is_npc"] == True
        assert data["extra_goods"] == "hi\nall"
        assert not self.dm.update_official_character_data("guy1", official_name="", official_role="", # THESE can't be empty, so update is ignored
                                                          gamemaster_hints=None, is_npc=None, extra_goods=None) # would override if was ""
        data = self.dm.get_character_properties("guy1")
        assert data["official_name"] == "Simon "
        assert data["official_role"] == "A killer "
        assert data["gamemaster_hints"] == "ABCD"
        assert data["is_npc"] == True
        assert data["extra_goods"] == "hi\nall"
        assert self.dm.update_official_character_data("guy1", gamemaster_hints="", is_npc=False, extra_goods="") # overrides
        data = self.dm.get_character_properties("guy1")
        assert data["official_name"] == "Simon "
        assert data["official_role"] == "A killer "
        assert data["gamemaster_hints"] == ""
        assert data["is_npc"] == False
        assert data["extra_goods"] == ""

        assert self.dm.update_real_life_data("guy1", real_life_identity="jjjj")
        assert self.dm.update_real_life_data("guy1", real_life_email="ss@pangea.com")
        data = self.dm.get_character_properties("guy1")
        assert data["real_life_identity"] == "jjjj"
        assert data["real_life_email"] == "ss@pangea.com"
        assert self.dm.update_real_life_data("guy1", real_life_identity="kkkk", real_life_email="kkkk@pangea.com")
        assert data["real_life_identity"] == "kkkk"
        assert data["real_life_email"] == "kkkk@pangea.com"
        assert not self.dm.update_real_life_data("guy1", real_life_identity=None, real_life_email=None)
        assert data["real_life_identity"] == "kkkk"
        assert data["real_life_email"] == "kkkk@pangea.com"
        with pytest.raises(UsageError):
            self.dm.update_real_life_data("unexistinguy", real_life_identity="John")
        with pytest.raises(UsageError):
            self.dm.update_real_life_data("guy1", real_life_email="bad_email")
        assert self.dm.update_real_life_data("guy1", real_life_email="", real_life_identity="") # erasing, these CAN be empty
        data = self.dm.get_character_properties("guy1")
        assert data["real_life_email"] == ""
        assert data["real_life_identity"] == ""

        assert self.dm.get_character_color_or_none("guy1") == "#0033CC"
        assert self.dm.get_character_color_or_none("unexistinguy") is None
        assert self.dm.get_character_color_or_none("") is None


        self._set_user("guy1")
        res1 = self.dm.get_character_usernames()
        assert "guy1" in res1
        assert "my_npc" in res1
        res2 = self.dm.get_character_usernames(exclude_current=True)
        assert "guy1" not in res2
        assert "my_npc" in res2
        assert len(res2) == len(res1) - 1

        res1 = self.dm.get_character_usernames(is_npc=True)
        assert "guy1" not in res1
        assert "guy2" not in res1
        assert "my_npc" in res1

        res2 = self.dm.get_character_usernames(is_npc=False)
        assert "guy1" in res2
        assert "guy2" in res2
        assert "my_npc" not in res2

        assert self.dm.get_character_usernames(is_npc=None) == self.dm.get_character_usernames(is_npc=False) + self.dm.get_character_usernames(is_npc=True)

        self._set_user("master")
        assert self.dm.get_character_usernames(exclude_current=True) == self.dm.get_character_usernames() # no crash if not a proper character currently set
        self._set_user(None)
        assert self.dm.get_character_usernames(exclude_current=True) == self.dm.get_character_usernames() # no crash if not a proper character currently set






    @for_core_module(DomainHandling)
    def test_domain_handling(self):

        self.dm.update_allegiances("guy1", [])

        assert self.dm.update_allegiances("guy1", ["sciences"]) == (["sciences"], [])
        assert self.dm.update_allegiances("guy1", []) == ([], ["sciences"])
        assert self.dm.update_allegiances("guy1", ["sciences", "akaris"]) == (["akaris", "sciences"], []) # sorted
        assert self.dm.update_allegiances("guy1", ["sciences", "akaris"]) == ([], []) # no changes

        with pytest.raises(UsageError):
            self.dm.update_allegiances("guy1", ["dummydomain"])

        with pytest.raises(UsageError):
            self.dm.update_real_life_data("unexistinguy", real_life_identity=["sciences"])


    @for_core_module(FriendshipHandling)
    def test_friendship_handling(self):

        dm = self.dm

        dm.reset_friendship_data()

        full = self.dm.get_full_friendship_data()
        assert isinstance(full, (dict, PersistentMapping))
        assert "sealed" in full and "proposed" in full


        assert self.dm.get_other_characters_friendship_statuses("guy1") == {u'guy2': None, 'guy3': None, 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy2") == {u'guy1': None, 'guy3': None, 'guy4': None, 'my_npc': None}

        assert not dm.data["friendships"]["proposed"]
        assert not dm.data["friendships"]["sealed"]

        with pytest.raises(UsageError):
            dm.propose_friendship(dm.anonymous_login, "guy1")
        with pytest.raises(UsageError):
            dm.propose_friendship("guy1", dm.anonymous_login)
        with pytest.raises(UsageError):
            dm.propose_friendship("guy1", "guy1") # auto-friendship impossible

        assert not dm.propose_friendship("guy2", "guy1") # proposes
        assert not dm.are_friends("guy1", "guy2")
        assert not dm.are_friends("guy2", "guy1")
        assert not dm.are_friends("guy1", "guy3")

        assert self.dm.get_other_characters_friendship_statuses("guy1") == {u'guy2': 'requested_by', 'guy3': None, 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy2") == {u'guy1': 'proposed_to', 'guy3': None, 'guy4': None, 'my_npc': None}

        # friendship proposals don't impact impersonation
        assert not self.dm.can_impersonate("guy1", "guy3")
        assert not self.dm.can_impersonate("guy1", "guy2")
        assert not self.dm.can_impersonate("guy2", "guy1")

        with pytest.raises(UsageError):
            dm.propose_friendship("guy2", "guy1") # friendship already requested

        assert dm.data["friendships"]["proposed"]
        assert not dm.data["friendships"]["sealed"]

        with pytest.raises(UsageError):
            dm.propose_friendship("guy2", "guy1") # duplicate proposal

        assert dm.get_friendship_requests_for_character("guy3") == dict(proposed_to=[],
                                                          requested_by=[])
        assert dm.get_friendship_requests_for_character("guy1") == dict(proposed_to=[],
                                                          requested_by=["guy2"])
        assert dm.get_friendship_requests_for_character("guy2") == dict(proposed_to=["guy1"],
                                                          requested_by=[])
        time.sleep(0.5)
        assert dm.propose_friendship("guy1", "guy2") # we seal friendship, here

        # friends can impersonate each other!
        assert not self.dm.can_impersonate("guy1", "guy3")
        assert self.dm.can_impersonate("guy1", "guy2")
        assert self.dm.can_impersonate("guy2", "guy1")

        assert self.dm.get_other_characters_friendship_statuses("guy1") == {u'guy2': 'recent_friend', 'guy3': None, 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy2") == {u'guy1': 'recent_friend', 'guy3': None, 'guy4': None, 'my_npc': None}

        with pytest.raises(UsageError):
            dm.propose_friendship("guy2", "guy1") # already friends
        with pytest.raises(UsageError):
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

        with pytest.raises(UsageError):
            dm.get_friendship_params("guy1", "guy3")
        with pytest.raises(UsageError):
            dm.get_friendship_params("guy3", "guy1")
        with pytest.raises(UsageError):
            dm.get_friendship_params("guy3", "guy4")

        assert dm.are_friends("guy2", "guy1") == dm.are_friends("guy1", "guy2") == True
        assert dm.are_friends("guy2", "guy3") == dm.are_friends("guy3", "guy4") == False

        assert not dm.propose_friendship("guy2", "guy3") # proposed
        with pytest.raises(UsageError):
            dm.terminate_friendship("guy3", "guy2") # wrong direction
        assert not dm.terminate_friendship("guy2", "guy3") # abort proposal, actually

        assert not dm.propose_friendship("guy2", "guy3") # proposed
        assert dm.propose_friendship("guy3", "guy2") # accepted
        assert dm.get_friends_for_character("guy1") == dm.get_friends_for_character("guy3") == ["guy2"]
        assert dm.get_friends_for_character("guy2") in (["guy1", "guy3"], ["guy3", "guy1"]) # order not enforced
        assert dm.get_friends_for_character("guy4") == []

        assert self.dm.get_other_characters_friendship_statuses("guy1") == {u'guy2': 'recent_friend', 'guy3': None, 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy2") == {u'guy1': 'recent_friend', 'guy3': 'recent_friend', 'guy4': None, 'my_npc': None}

        with pytest.raises(UsageError):
            dm.terminate_friendship("guy3", "guy4") # unexisting friendship
        with pytest.raises(UsageError):
            dm.terminate_friendship("guy1", "guy2") # too young friendship

        # old friendship still makes impersonation possible of course
        assert not self.dm.can_impersonate("guy1", "guy3")
        assert self.dm.can_impersonate("guy1", "guy2")
        assert self.dm.can_impersonate("guy2", "guy1")

        for pair, params in dm.data["friendships"]["sealed"].items():
            if "guy1" in pair:
                params["acceptance_date"] -= timedelta(hours=30) # delay should be 24h in dev
                dm.commit()

        assert self.dm.get_other_characters_friendship_statuses("guy1") == {u'guy2': 'old_friend', 'guy3': None, 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy2") == {u'guy1': 'old_friend', 'guy3': 'recent_friend', 'guy4': None, 'my_npc': None}

        assert dm.terminate_friendship("guy1", "guy2") # success

        # no more friends -> no more impersonation
        assert not self.dm.can_impersonate("guy1", "guy3")
        assert not self.dm.can_impersonate("guy1", "guy2")
        assert not self.dm.can_impersonate("guy2", "guy1")

        assert not dm.are_friends("guy2", "guy1")
        with pytest.raises(UsageError):
            dm.get_friendship_params("guy1", "guy2")
        assert dm.are_friends("guy2", "guy3") # untouched

        assert self.dm.get_other_characters_friendship_statuses("guy1") == {u'guy2': None, 'guy3': None, 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy2") == {u'guy1': None, 'guy3': 'recent_friend', 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy3") == {u'guy1': None, 'guy2': 'recent_friend', 'guy4': None, 'my_npc': None}
        assert self.dm.get_other_characters_friendship_statuses("guy4") == {u'guy1': None, 'guy2': None, 'guy3': None, 'my_npc': None}

        dm.reset_friendship_data()
        assert not dm.data["friendships"]["proposed"]
        assert not dm.data["friendships"]["sealed"]
        assert not dm.get_friends_for_character("guy1")
        assert not dm.get_friends_for_character("guy2")
        assert not dm.get_friends_for_character("guy3")
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
        self.assertTrue(self.dm.get_online_status("guy2")) # propagated too
        self.assertFalse(self.dm.get_chatting_status("guy1"))
        self.assertTrue(self.dm.get_chatting_status("guy2"))
        self.assertEqual(self.dm.get_online_users(), ["guy2"])
        self.assertEqual(self.dm.get_chatting_users(), ["guy2"])
        self.assertEqual(self.dm.get_chatting_users(exclude_current=True), ["guy2"])

        self._set_user("guy2")
        self.assertEqual(self.dm.get_chatting_users(), ["guy2"])
        self.assertEqual(self.dm.get_chatting_users(exclude_current=True), [])

        time.sleep(1.2)

        self.dm.get_chatroom_messages(from_slice_index=0)
        self.assertFalse(self.dm.get_online_status("guy1"))
        self.assertTrue(self.dm.get_online_status("guy2")) # UP for online presence
        self.assertFalse(self.dm.get_chatting_status("guy1"))
        self.assertTrue(self.dm.get_chatting_status("guy2")) # just fetching msgs does update chatting presence
        self.assertEqual(self.dm.get_online_users(), ["guy2"])
        self.assertEqual(self.dm.get_chatting_users(), ["guy2"])


        time.sleep(1.2)

        self.assertFalse(self.dm.get_online_status("guy1"))
        self.assertFalse(self.dm.get_online_status("guy2"))
        self.assertFalse(self.dm.get_chatting_status("guy1"))
        self.assertFalse(self.dm.get_chatting_status("guy2"))
        self.assertEqual(self.dm.get_online_users(), [])
        self.assertEqual(self.dm.get_chatting_users(), [])


    # todo - refactor this ?
    def test_misc_getters_setters(self):
        self._reset_messages()

        self.assertEqual(self.dm.get_username_from_official_name(self.dm.get_official_name("guy2")), "guy2")

        # DEPRECATED self.assertEqual(self.dm.get_fellow_usernames("guy2"), ["guy1"])
        ## self.assertEqual(len(self.dm.get_game_instructions("guy2")), 3)

        self.dm.set_game_state(started=False)
        self.assertEqual(self.dm.is_game_started(), False)
        self.dm.set_game_state(started=True)
        self.assertEqual(self.dm.is_game_started(), True)

        self.assertEqual(self.dm.get_username_from_email("qdqsdqd@dqsd.fr"), self.dm.get_global_parameter("master_login"))
        self.assertEqual(self.dm.get_username_from_email("guy1@pangea.com"), "guy1")


        self._set_user("master")


        # we test global parameter handling here...
        self.dm.set_global_parameter("game_theoretical_length_days", 22)
        assert self.dm.get_global_parameter("game_theoretical_length_days") == 22

        with pytest.raises(AbnormalUsageError):
            self.dm.set_global_parameter("unexisting_param", 33)




    @for_core_module(MoneyItemsOwnership)
    def test_item_transfers(self):
        self._reset_messages()

        # small check - NULL PRICE IS NOT A PROBLEM
        chest = self.dm.get_item_properties("sacred_chest")
        assert chest["unit_cost"] == chest["total_price"] == 0  # NOT A PROBLEM

        lg_old = copy.deepcopy(self.dm.get_character_properties("guy3"))
        nw_old = copy.deepcopy(self.dm.get_character_properties("guy1"))
        items_old = copy.deepcopy(self.dm.get_all_items())
        bank_old = self.dm.get_global_parameter("bank_account")

        gem_names = [key for key, value in items_old.items() if value["is_gem"] and value["num_items"] >= 3] # we only take numerous groups
        object_names = [key for key, value in items_old.items() if not value["is_gem"]]

        gem_name1 = gem_names[0]
        gem_name2 = gem_names[1] # wont be sold
        object_name = object_names[0]
        bank_name = self.dm.get_global_parameter("bank_name")

        self.assertRaises(UsageError, self.dm.transfer_money_between_characters, bank_name, "guy1", 10000000, reason="because!")
        self.assertRaises(UsageError, self.dm.transfer_money_between_characters, "guy3", "guy1", -100)
        self.assertRaises(UsageError, self.dm.transfer_money_between_characters, "guy3", "guy1", 0)
        self.assertRaises(UsageError, self.dm.transfer_money_between_characters, "guy3", "guy1", lg_old["account"] + 1) # too much
        self.assertRaises(UsageError, self.dm.transfer_money_between_characters, "guy3", "guy3", 1, reason="lalalall") # same ids
        self.assertRaises(UsageError, self.dm.transfer_object_to_character, "dummy_name", "guy3") # shall NOT happen
        self.assertRaises(UsageError, self.dm.transfer_object_to_character, object_name, "dummy_name")


        # data mustn't have changed when raising exceptions
        self.assertEqual(self.dm.get_character_properties("guy3"), lg_old)
        self.assertEqual(self.dm.get_character_properties("guy1"), nw_old)
        self.assertEqual(self.dm.get_all_items(), items_old)
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

        # we fully test gems transfers
        guy3_bkp = copy.deepcopy(self.dm.get_character_properties("guy3"))
        guy1_bkp = copy.deepcopy(self.dm.get_character_properties("guy1"))
        gems_given = self.dm.get_character_properties("guy3")["gems"][0:3]
        self.dm.transfer_gems_between_characters("guy3", "guy1", gems_given)
        assert self.dm.get_character_properties("guy3") != guy3_bkp
        assert self.dm.get_character_properties("guy1") != guy1_bkp
        self.dm.transfer_gems_between_characters("guy1", "guy3", gems_given)
        assert self.dm.get_character_properties("guy3") == guy3_bkp
        assert self.dm.get_character_properties("guy1") == guy1_bkp
        self.assertRaises(UsageError, self.dm.transfer_gems_between_characters, "guy3", "guy3", gems_given) # same ids
        self.assertRaises(UsageError, self.dm.transfer_gems_between_characters, "guy3", "guy1", gems_given + [27, 32]) # not possessed
        self.assertRaises(UsageError, self.dm.transfer_gems_between_characters, "guy3", "guy1", []) # at least 1 gem needed

        items_new = copy.deepcopy(self.dm.get_all_items())
        lg_new = self.dm.get_character_properties("guy3")
        nw_new = self.dm.get_character_properties("guy1")
        assert set(self.dm.get_available_items_for_user("guy3").keys()) == set([gem_name1, object_name])
        self.assertEqual(lg_new["gems"], [(items_new[gem_name1]["unit_cost"], gem_name1)] * items_new[gem_name1]["num_items"])
        self.assertEqual(items_new[gem_name1]["owner"], "guy3")
        self.assertEqual(items_new[object_name]["owner"], "guy3")
        self.assertEqual(lg_new["account"], lg_old["account"] - 100)
        self.assertEqual(nw_new["account"], nw_old["account"] + 100)


        # PREVIOUS OWNER CHECKING (it's currently guy3)
        for previous_owner in (self.dm.master_login, self.dm.anonymous_login, "guy1", "guy2"):
            with pytest.raises(UsageError):
                self.dm.transfer_object_to_character(object_name, "guy2", previous_owner=previous_owner)
        self.dm.transfer_object_to_character(object_name, "guy2", previous_owner="guy3")
        assert self.dm.get_user_artefacts("guy2").keys() == [object_name]
        assert self.dm.get_user_artefacts("guy3") == {}
        self.dm.transfer_object_to_character(object_name, "guy3", previous_owner="guy2") # we undo just this


        # we test possible and impossible undo operations

        self.assertRaises(Exception, self.dm.transfer_object_to_character, gem_name2, None) # same ids - already free item

        # check no changes occured
        self.assertEqual(self.dm.get_character_properties("guy3"), self.dm.get_character_properties("guy3"))
        self.assertEqual(self.dm.get_character_properties("guy1"), self.dm.get_character_properties("guy1"))
        self.assertEqual(self.dm.get_all_items(), items_new)

        # undoing item sales
        self.assertRaises(Exception, self.dm.transfer_object_to_character, gem_name1, "guy3") # same ids - same current owner and target
        self.dm.transfer_object_to_character(gem_name1, None)
        self.dm.transfer_object_to_character(object_name, None)
        items_new = copy.deepcopy(self.dm.get_all_items())
        self.assertEqual(items_new[gem_name1]["owner"], None)
        self.assertEqual(items_new[object_name]["owner"], None)
        self.dm.transfer_money_between_characters("guy1", "guy3", 100)

        # we're back to initial state
        self.assertEqual(self.dm.get_character_properties("guy3"), lg_old)
        self.assertEqual(self.dm.get_character_properties("guy1"), nw_old)
        self.assertEqual(self.dm.get_all_items(), items_old)

        # undo failure
        self.dm.transfer_object_to_character(gem_name1, "guy3")
        gem = self.dm.get_character_properties("guy3")["gems"].pop()
        self.dm.commit()
        with pytest.raises(UsageError) as exc_info:
            self.dm.transfer_object_to_character(gem_name1, random.choice(("guy1", None))) # one gem is lacking, so...
        assert "already been used" in str(exc_info.value)

        self.dm.get_character_properties("guy3")["gems"].append(gem)
        self.dm.commit()
        self.dm.transfer_object_to_character(gem_name1, None)

        self.assertEqual(self.dm.get_character_properties("guy3"), lg_old)
        self.assertEqual(self.dm.get_character_properties("guy1"), nw_old)
        self.assertEqual(self.dm.get_all_items(), items_old)


        # test PURE DEBIT of gems

        self.dm.transfer_object_to_character(gem_name2, "guy3")
        gems_given = self.dm.get_character_properties("guy3")["gems"][0:2]
        guy3_previous = copy.deepcopy(self.dm.get_character_properties("guy3"))

        with pytest.raises(UsageError):
            self.dm.debit_character_gems("guy3", gems_choices=[(gems_given[0][0], "weird_origin")])
        with pytest.raises(UsageError):
            self.dm.debit_character_gems("guy3", gems_choices=[(345, gems_given[0][1])])
        assert self.dm.get_character_properties("guy3") == guy3_previous

        self.dm.debit_character_gems("guy3", gems_choices=gems_given)
        assert self.dm.get_character_properties("guy3") != guy3_previous
        assert len(self.dm.get_character_properties("guy3")["gems"]) == len(guy3_previous["gems"]) - 2


        # test PURE CREDIT of gems

        guy3_previous2 = copy.deepcopy(self.dm.get_character_properties("guy3"))

        with pytest.raises(UsageError):
            self.dm.credit_character_gems("guy3", gems_choices=[(gems_given[0][0], "weird_origin")])
        with pytest.raises(UsageError):
            self.dm.credit_character_gems("guy3", gems_choices=[(345, gems_given[0][1])])
        assert self.dm.get_character_properties("guy3") == guy3_previous2

        self.dm.credit_character_gems("guy3", gems_choices=gems_given)
        assert self.dm.get_character_properties("guy3") != guy3_previous2
        assert self.dm.get_character_properties("guy3") == guy3_previous  # back to previous state
        assert len(self.dm.get_character_properties("guy3")["gems"]) == len(guy3_previous2["gems"]) + 2

        with pytest.raises(UsageError):  # can't do it a second time, no more of these gems in "spent_gems"!
            self.dm.credit_character_gems("guy3", gems_choices=gems_given)


    @for_core_module(MoneyItemsOwnership)
    def test_available_items_listing(self):
        self._reset_messages()

        self._set_user("guy1")

        # print (">>>", self.dm.__class__.__mro__)
        all_items = self.dm.get_all_items()
        gems = self.dm.get_gem_items()
        artefacts = self.dm.get_non_gem_items()

        assert set(all_items.keys()) == set(gems.keys()) | set(artefacts.keys())
        assert not (set(gems.keys()) & set(artefacts.keys()))

        auctions = self.dm.get_auction_items()
        assert auctions
        for it in auctions.values():
            assert it["auction"]

        items_old = copy.deepcopy(self.dm.get_all_items())
        gem_names = sorted([key for key, value in items_old.items() if value["is_gem"] and value["num_items"] >= 3]) # we only take numerous groups
        auction_object_names = sorted([key for key, value in items_old.items() if not value["is_gem"] and value["auction"]])
        no_auction_object_names = sorted([key for key, value in items_old.items() if not value["is_gem"] and not value["auction"]])

        gem_name1 = gem_names[0]
        gem_name2 = gem_names[1]
        object_name_auction = auction_object_names[0]
        object_name_no_auction = no_auction_object_names[0]
        object_name_free = no_auction_object_names[1]

        self.dm.transfer_object_to_character(gem_name1, "guy2")
        self.dm.transfer_object_to_character(gem_name2, "guy2")
        self.dm.transfer_object_to_character(object_name_auction, "guy3")
        self.dm.transfer_object_to_character(object_name_no_auction, "guy4")

        self.assertEqual(self.dm.get_available_items_for_user("master"), self.dm.get_all_items())
        self.assertEqual(self.dm.get_available_items_for_user("master", auction_only=False), self.dm.get_all_items())
        self.assertEqual(self.dm.get_available_items_for_user("master", auction_only=True), self.dm.get_auction_items())

        self.assertEqual(set(self.dm.get_available_items_for_user("guy1").keys()), set([]))
        self.assertNotEqual(self.dm.get_available_items_for_user("guy2", auction_only=False), self.dm.get_available_items_for_user("guy1")) # no sharing of objects, even shared allegiance
        self.assertEqual(set(self.dm.get_available_items_for_user("guy2").keys()), set([gem_name1, gem_name2]))
        self.assertEqual(set(self.dm.get_available_items_for_user("guy3").keys()), set([object_name_auction]))
        self.assertEqual(set(self.dm.get_available_items_for_user("guy3", auction_only=True).keys()), set([object_name_auction]))
        self.assertEqual(set(self.dm.get_available_items_for_user("guy4", auction_only=False).keys()), set([object_name_no_auction]))
        self.assertEqual(set(self.dm.get_available_items_for_user("guy4", auction_only=True).keys()), set([])) # filtered out

        assert self.dm.get_user_artefacts() == {} # guy1
        assert self.dm.get_user_artefacts("guy1") == {}
        assert self.dm.get_user_artefacts("guy2") == {} # gems NOT included
        assert self.dm.get_user_artefacts("guy3").keys() == [object_name_auction]
        assert self.dm.get_user_artefacts("guy4").keys() == [object_name_no_auction]


        # mutability control #
        # NOTE that currently ALL ITEMS are MUTABLE iff they are not OWNED (and initial ones are undeletable) #

        container = self.dm.game_items

        unmodifiable_entry = object_name_auction  # OWNED by guy3
        assert unmodifiable_entry in container.get_all_data()
        assert unmodifiable_entry in container.get_all_data(mutability=False)
        assert unmodifiable_entry not in container.get_all_data(mutability=True)
        assert unmodifiable_entry in [k for k, v in container.get_all_data(as_sorted_list=True)]
        assert unmodifiable_entry in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=False)]
        assert unmodifiable_entry not in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=True)]
        assert unmodifiable_entry in container.get_undeletable_identifiers()  # ALSO not deletable of course

        mutable_entry = object_name_free
        assert mutable_entry in container.get_all_data()
        assert mutable_entry in container.get_all_data(mutability=True)
        assert mutable_entry not in container.get_all_data(mutability=False)
        assert mutable_entry in [k for k, v in container.get_all_data(as_sorted_list=True)]
        assert mutable_entry not in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=False)]
        assert mutable_entry in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=True)]
        assert mutable_entry not in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=False)]
        assert mutable_entry in container.get_undeletable_identifiers()  # undeletable because initial

        assert len(container.get_all_data()) == len(container.get_undeletable_identifiers())  # ALL undeletable initially

        new_id = "newid"
        new_item = utilities.safe_copy(container[mutable_entry])
        del new_item["initial"]
        container[new_id] = new_item
        self.dm.commit()
        assert new_id not in container.get_undeletable_identifiers()
        assert new_id in container.get_all_data(mutability=True)
        assert new_id not in container.get_all_data(mutability=False)

        assert mutable_entry in container.get_undeletable_identifiers()
        new_item = utilities.safe_copy(container[mutable_entry])
        del new_item["initial"]
        container[mutable_entry] = utilities.safe_copy(new_item)
        self.dm.commit()
        assert mutable_entry in container.get_undeletable_identifiers()  # unchanged deletability for existing entry




    @for_core_module(PersonalFiles)
    def test_personal_files(self):
        self._reset_django_db()
        self._reset_messages()

        files1 = self.dm.get_personal_files("guy2", absolute_urls=True)
        self.assertTrue(len(files1))
        self.assertTrue(files1[0].startswith("http"))

        files1bis = self.dm.get_personal_files("guy2")
        self.assertEqual(len(files1), len(files1bis))
        self.assertTrue(files1bis[0].startswith("/"))

        files2 = self.dm.get_personal_files(self.dm.master_login) # private game master files
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


        files = self.dm.get_personal_files("guy1")
        print(">>>>files>>>>", files)
        assert len(files) == 5
        assert os.path.basename(files[0]) == "111first.jpg" # sorted by basename



    @for_core_module(PersonalFiles)
    def test_encrypted_folders(self):
        self._reset_django_db()
        self._reset_messages()

        assert self.dm.get_all_encrypted_folders_info() == dict(guy2_report=["evans", "schamaalamoktuhg"])

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
    def test_encyclopedia_api_and_keywords(self):

        utilities.check_is_restructuredtext(self.dm.get_encyclopedia_entry(" gerbiL_speCies ")["content"])# tolerant fetching
        assert self.dm.get_encyclopedia_entry("qskiqsjdqsid") is None
        assert "gerbil_species" in self.dm.get_encyclopedia_article_ids()

        assert ("animals?", ["lokon", "gerbil_species"]) in self.dm.get_encyclopedia_keywords_mapping().items()
        assert ("animals?", ["lokon"]) in self.dm.get_encyclopedia_keywords_mapping(excluded_link="gerbil_species").items() # no links to currently viewed article

        regexes = self.dm.get_encyclopedia_keywords_mapping(only_primary_keywords=False)
        assert regexes == self.dm.get_encyclopedia_keywords_mapping()  # default value
        assert "animals?" in regexes
        assert "lokons?" in regexes
        regexes = self.dm.get_encyclopedia_keywords_mapping(only_primary_keywords=True)
        assert "animals?" in regexes
        assert "lokons?" not in regexes  # secondary keyword

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
        res = _generate_encyclopedia_links("animals lokons lokonsu", self.dm)
        expected = """<a href="@@@?search=animals">animals</a> lokons lokonsu"""
        expected = expected.replace("@@@", game_view_url(views.view_encyclopedia, datamanager=self.dm))
        assert res == expected

        res = _generate_encyclopedia_links(u"""wu\\gly_é gerbil \n lokongerbil dummy gerb\nil <a href="#">lokon\n</a> lokons""", self.dm)
        print (repr(res))
        expected = u'wu\\gly_é <a href="@@@?search=gerbil">gerbil</a> \n lokongerbil dummy gerb\nil <a href="#">lokon\n</a> lokons'
        expected = expected.replace("@@@", game_view_url(views.view_encyclopedia, datamanager=self.dm))
        assert res == expected

        res = _generate_encyclopedia_links(u"""i<à hi""", self.dm)
        print (repr(res))
        expected = u'<a href="/TeStiNg/guest/encyclopedia/?search=i%3C%C3%A0">i&lt;\xe0</a> hi'
        expected = expected.replace("@@@", game_view_url(views.view_encyclopedia, datamanager=self.dm))
        assert res == expected


        # knowledge of article ids #

        for unauthorized in ("master", None):
            self._set_user(unauthorized)
            with pytest.raises(UsageError):
                self.dm.get_character_known_article_ids()
            with pytest.raises(UsageError):
                self.dm.update_character_known_article_ids(article_ids=["lokon"])
            with pytest.raises(UsageError):
                self.dm.reset_character_known_article_ids()

        self._set_user("guy1")
        assert self.dm.get_character_known_article_ids() == []
        self.dm.update_character_known_article_ids(article_ids=["lokon"])
        assert self.dm.get_character_known_article_ids() == ["lokon"]
        self.dm.update_character_known_article_ids(article_ids=["gerbil_species", "unexisting", "lokon", "gerbil_species"])
        assert self.dm.get_character_known_article_ids() == ["lokon", "gerbil_species", "unexisting"]
        self.dm.reset_character_known_article_ids()
        assert self.dm.get_character_known_article_ids() == []


    def test_message_automated_state_changes(self):
        self._reset_messages()

        email = self.dm.get_character_email # function

        msg_id = self.dm.post_message(email("guy1"), email("guy2"), subject="ssd", body="qsdqsd")

        msg = self.dm.get_dispatched_message_by_id(msg_id)
        self.assertFalse(msg["has_replied"])
        self.assertEqual(msg["has_read"], ["guy1"]) # SENDER auto registered

        # no strict checks on sender/recipient of original message, when using parent_id feature
        msg_id2 = self.dm.post_message(email("guy2"), email("guy1"), subject="ssd", body="qsdqsd", parent_id=msg_id, delay_mn= -2)
        msg_id3 = self.dm.post_message(email("guy3"), email("guy2"), subject="ssd", body="qsdqsd", parent_id=msg_id)

        msg = self.dm.get_dispatched_message_by_id(msg_id2) # new message isn't impacted by parent_id
        self.assertFalse(msg["has_replied"])
        self.assertEqual(msg["has_read"], ["guy2"]) # SENDER auto registered

        msg = self.dm.get_dispatched_message_by_id(msg_id) # replied-to message impacted
        self.assertEqual(len(msg["has_replied"]), 2)
        self.assertTrue("guy2" in msg["has_replied"])
        self.assertTrue("guy3" in msg["has_replied"])
        self.assertEqual(msg["has_read"], ["guy1"]) # read state of parent messages do NOT autochange, still only sender is in here

        ######

        (tpl_id, tpl) = self.dm.get_messages_templates().items()[0]
        self.assertEqual(tpl["is_used"], False)
        self.assertEqual(tpl["is_ignored"], False)

        msg_id4 = self.dm.post_message(email("guy3"), email("guy1"), subject="ssd", body="qsdqsd",
                                       use_template=tpl_id, mask_recipients=True, transferred_msg=msg_id2,
                                       attachment="/urlbidon")

        msg = self.dm.get_dispatched_message_by_id(msg_id4)
        self.assertFalse(msg["has_replied"])  # new message isn't impacted
        self.assertEqual(msg["has_read"], ["guy3"])

        tpl = self.dm.get_message_template(tpl_id)
        self.assertEqual(tpl["is_used"], True) # template properly marked as used (even if message sending - when delay>0 - is eventually canceled)

        self.dm.set_template_state_flags(tpl_id=tpl_id, is_ignored=True)
        tpl = self.dm.get_message_template(tpl_id)
        self.assertEqual(tpl["is_ignored"], True)
        self.dm.set_template_state_flags(tpl_id=tpl_id, is_ignored=False)
        tpl = self.dm.get_message_template(tpl_id)
        self.assertEqual(tpl["is_ignored"], False)

        new_tpl = self.dm.convert_msg_to_template(msg)

        print (new_tpl)
        assert new_tpl == {u'body': u'qsdqsd', 'gamemaster_hints': u'',
                           u'mask_recipients': True, u'recipient_emails': [u'guy1@pangea.com'],
                           u'transferred_msg': u'1_1ef3', u'attachment': None, u'sender_email': u'guy3@pangea.com',
                           u'categories': [u'unsorted'], u'subject': u'ssd', u'attachment': u'/urlbidon'}




    @for_core_module(Chatroom)
    def test_chatroom_operations(self):

        self.assertEqual(self.dm.get_chatroom_messages(0), (0, None, []))

        self._set_user(None)
        self.assertRaises(dm_module.UsageError, self.dm.send_chatroom_message, " hello ")

        self._set_user("guy1")
        self.assertRaises(dm_module.UsageError, self.dm.send_chatroom_message, " ")

        self.assertEqual(self.dm.get_chatroom_messages(0), (0, None, []))

        self.dm.send_chatroom_message(u" héllo <tag> ! ")
        self.dm.send_chatroom_message(" re ")

        self._set_user("guy2")
        self.dm.send_chatroom_message("back")

        (slice_end, previous_msg_timestamp, msgs) = self.dm.get_chatroom_messages(0)
        self.assertEqual(slice_end, 3)
        self.assertEqual(previous_msg_timestamp, None)
        self.assertEqual(len(msgs), 3)

        self.assertEqual(sorted(msgs, key=lambda x: x["time"]), msgs)

        data = [(msg["username"], msg["message"]) for msg in msgs]
        self.assertEqual(data, [("guy1", u"héllo &lt;tag&gt; !"), ("guy1", "re"), ("guy2", "back")]) # MESSAGES ARE ESCAPED IN ZODB, for safety

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



    def test_address_book(self):

        emails = self.dm.get_character_address_book("my_npc")
        assert not emails
        usernames = self.dm.get_other_known_characters("my_npc")
        assert not usernames
        usernames = self.dm.get_other_known_characters("guy2")
        assert not usernames

        self.dm.post_message("guy2@pangea.com",
                             recipient_emails=["guy1@pangea.com"],
                             subject="subj22323", body="qsdqsd")

        ml = self.dm.get_global_parameter("all_players_mailing_list")

        master_contacts = self.dm.get_sorted_user_contacts(self.dm.master_login)
        assert sorted(master_contacts) == sorted(self.dm.get_all_existing_emails())
        assert master_contacts[0] == ml
        master_contacts = set(master_contacts)
        assert master_contacts == set(self.dm.get_all_contacts_unsorted()) # get_all_contacts_unsorted is just an optimized method

        char_emails = set(self.dm.get_character_emails())
        assert master_contacts & char_emails == char_emails # all chars are in
        assert len(master_contacts) > len(char_emails) + 4
        assert "judicators2@akaris.com" in master_contacts

        emails = self.dm.get_sorted_user_contacts("guy2")
        assert sorted(emails) != sorted(self.dm.get_all_existing_emails())
        emails = set(emails)
        assert ml not in emails # not ALWAYS
        assert (char_emails - emails) # guy2 has not ALL character emails
        assert (char_emails & emails) # has SOME character emails
        assert self.dm.get_character_email("guy2") in emails # has self as contact due to any dispatched email
        assert "guy1@pangea.com" in emails
        assert "judicators2@akaris.com" in emails

        emails = self.dm.get_character_address_book("guy2")
        assert "guy1@pangea.com" in emails
        assert "judicators2@akaris.com" in emails
        assert ml not in emails # not yet concerned by this one yet
        usernames = self.dm.get_other_known_characters("guy2")
        assert usernames == ["guy1"]

        emails = self.dm.get_sorted_user_contacts("guy3")
        assert emails == [] # not even ml
        emails = self.dm.get_character_address_book("guy3")
        assert emails == [] # not even ml
        usernames = self.dm.get_other_known_characters("guy3")
        assert not usernames

        self.dm.post_message("guy3@pangea.com",
                             recipient_emails=[ml, "judicators2@akaris.com"],
                             subject="fffff", body="ffff")

        emails = self.dm.get_sorted_user_contacts("guy3")
        assert emails[0] == ml
        assert set(emails) == set([ml, "judicators2@akaris.com", "guy3@pangea.com"])
        emails = self.dm.get_character_address_book("guy3")
        assert set(emails) == set([ml, "judicators2@akaris.com", "guy3@pangea.com"])
        usernames = self.dm.get_other_known_characters("guy3")
        assert not usernames # guy3


    @for_core_module(TextMessagingCore)
    def test_globally_registered_contacts(self):

        contact1 = "SOME_EMAILS"
        contact2 = "phoenix@stash.com"
        contact_bad = "qsd qsdqsd"
        good_content = dict(avatar="images/avatars/question_mark.png", description="here a description", access_tokens=None,
                            gamemaster_hints=random.choice(("", "here some hint")))

        container = self.dm.global_contacts

        # preexisting, immutable entry
        fixture_key = "everyone@chars.com" # test fixture
        assert fixture_key in container
        assert fixture_key in sorted(container.keys())
        assert fixture_key in container.get_all_data()
        assert sorted(container.keys()) == sorted(container.get_all_data().keys())
        assert fixture_key in [i[0] for i in container.get_all_data(as_sorted_list=True)]

        assert container[fixture_key]["initial"]

        _tmp = utilities.safe_copy(container[fixture_key])
        del _tmp["initial"]

        assert container[fixture_key]["initial"]
        container[fixture_key] = _tmp # key already existing, but modifying in-place is OK
        self.dm.commit()

        assert container[fixture_key]["initial"]  # remains undeletable
        with pytest.raises(UsageError):
            del container[fixture_key] # key can't be DELETED/MOVED
        assert fixture_key in container


        with pytest.raises(UsageError):
            container[contact_bad] = good_content.copy() # bad key


        # dealing with new entry (mutable)
        for contact in (contact1, contact2):

            # not yet present
            assert contact not in container
            assert contact not in container.get_all_data()
            assert contact not in sorted(container.keys())

            with pytest.raises(UsageError):
                container[contact]
            with pytest.raises(UsageError):
                del container[contact]


            with pytest.raises(UsageError):
                container[contact] = {"avatar": 11} # bad content
            with pytest.raises(UsageError):
                container[contact] = {"description": False} # bad content


            container[contact] = good_content.copy()

            assert contact in container
            res = utilities.safe_copy(container[contact])
            assert res["initial"] == False
            del res["initial"]
            assert res == good_content

            with pytest.raises(UsageError):
                container[contact] = {"avatar": 11} # bad content
            container[contact] = {"avatar": None, "description": None}

            res = utilities.safe_copy(container[contact])
            assert res["initial"] == False
            del res["initial"]
            assert res == {"avatar": None, "description": None, "access_tokens": None, "gamemaster_hints": ""}

            assert contact in container

            del container[contact]
            with pytest.raises(UsageError):
                del container[contact]
            assert contact not in container

            assert contact not in container.get_all_data()
            with pytest.raises(UsageError):
                container[contact]


            # mutability control #
            # NOTE that currently ALL CONTACTS are MUTABLE (but some are undeletable) #

            assert not container.get_all_data(mutability=False)

            undeletable_entry = "[auction-list]@pangea.com"
            assert undeletable_entry in container.get_all_data()
            assert undeletable_entry not in container.get_all_data(mutability=False)
            assert undeletable_entry in container.get_all_data(mutability=True)
            assert undeletable_entry in [k for k, v in container.get_all_data(as_sorted_list=True)]
            assert undeletable_entry not in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=False)]
            assert undeletable_entry in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=True)]
            assert undeletable_entry in container.get_undeletable_identifiers()

            new_id = "newid"
            new_entry = utilities.safe_copy(container["[auction-list]@pangea.com"])
            del new_entry["initial"]
            container[new_id] = new_entry
            self.dm.commit()

            assert new_id in container.get_all_data(mutability=True)
            assert new_id not in container.get_all_data(mutability=False)
            assert new_id not in container.get_undeletable_identifiers()

            assert undeletable_entry in container.get_undeletable_identifiers()
            new_item = utilities.safe_copy(container[undeletable_entry])
            del new_item["initial"]
            container[undeletable_entry] = utilities.safe_copy(new_item)
            self.dm.commit()
            assert undeletable_entry in container.get_undeletable_identifiers()  # unchanged deletability for existing entry





    '''        
    @for_core_module(TextMessagingCore)
    def __test_globally_registered_contacts_old(self):
        
        contact1 = "ALL_EMAILS"
        contact2 = "phoenix@stash.com"
        contact_bad = "qsd qsdqsd"
        
        res = self.dm.get_globally_registered_contact_info("ALL_CONTACTS") # test fixture
        self.dm.add_globally_registered_contact("ALL_CONTACTS") # no error
        assert self.dm.get_globally_registered_contact_info("ALL_CONTACTS") == res # untouched if existing
        
        with pytest.raises(AssertionError):
            self.dm.add_globally_registered_contact(contact_bad)
        assert not self.dm.is_globally_registered_contact(contact_bad)
        
        for contact in (contact1, contact2):
            
            assert contact not in self.dm.get_globally_registered_contacts()
            with pytest.raises(AbnormalUsageError):
                self.dm.get_globally_registered_contact_info(contact)   
            with pytest.raises(AbnormalUsageError):
                self.dm.remove_globally_registered_contact(contact)   
                                     
            assert not self.dm.is_globally_registered_contact(contact)
            self.dm.add_globally_registered_contact(contact)
            assert self.dm.is_globally_registered_contact(contact)
            self.dm.add_globally_registered_contact(contact)
            assert self.dm.is_globally_registered_contact(contact)
            
            assert self.dm.get_globally_registered_contact_info(contact) is None
            assert contact in self.dm.get_globally_registered_contacts()
            
            self.dm.remove_globally_registered_contact(contact)
            with pytest.raises(AbnormalUsageError):
                self.dm.get_globally_registered_contact_info(contact)  
            with pytest.raises(AbnormalUsageError):
                self.dm.remove_globally_registered_contact(contact)          
            assert not self.dm.is_globally_registered_contact(contact)
            assert contact not in self.dm.get_globally_registered_contacts()
    '''

    @for_core_module(TextMessagingForCharacters)
    def test_messaging_utilities(self):

        input1 = "guy1 , ; ; guy2@akaris.com , master, ; everyone@lg-auction.com ,master, stuff@micro.fr"
        input2 = ["everyone@lg-auction.com", "guy1@pangea.com", "guy2@akaris.com", "master@pangea.com", "stuff@micro.fr"]


        sender, recipients = self.dm._normalize_message_addresses("  guy1   ", input1)
        assert sender == "guy1@pangea.com"
        self.assertEqual(len(recipients), len(input2))
        self.assertEqual(set(recipients), set(input2))

        sender, recipients = self.dm._normalize_message_addresses(" gu222@microkosm.com", input2)
        assert sender == "gu222@microkosm.com"
        self.assertEqual(len(recipients), len(input2))
        self.assertEqual(set(recipients), set(input2))

        assert self.dm.get_character_or_none_from_email("guy1@pangea.com") == "guy1"
        assert self.dm.get_character_or_none_from_email("guy1@wrongdomain.com") is None
        assert self.dm.get_character_or_none_from_email("master@pangea.com") is None


        sample = u""" Hello hélloaaxsjjs@gmaïl.fr. please write to hérbèrt@hélénia."""
        res = _generate_messaging_links(sample, self.dm)

        # the full email is well linked, not the incomplete one
        assert res == u' Hello <a href="/TeStiNg/guest/messages/compose/?recipient=h%C3%A9lloaaxsjjs%40gma%C3%AFl.fr">h\xe9lloaaxsjjs@gma\xefl.fr</a>. please write to h\xe9rb\xe8rt@h\xe9l\xe9nia.'


        expected_res = [{'description': 'Simon Bladstaffulovza - whatever', 'avatar': os.path.normpath('images/avatars/guy1.png'), 'address': u'guy1@pangea.com', 'color': '#0033CC', 'gamemaster_hints': 'This is guy1, actually agent SHA1.'},
                       {'description': 'the terrible judicators', 'avatar': os.path.normpath('images/avatars/here.png'), 'address': u'judicators@akaris.com', 'color': None, 'gamemaster_hints': ''},
                       {'description': u'Unidentified contact', 'avatar': os.path.normpath('images/avatars/question_mark.png'), 'address': u'unknown@mydomain.com', 'color': None, 'gamemaster_hints': None}]

        assert self.dm.get_contacts_display_properties([]) == []
        res = self.dm.get_contacts_display_properties(["guy1@pangea.com", "judicators@akaris.com", "unknown@mydomain.com"])
        #print(">>", res)
        assert res == expected_res

        res = self.dm.get_contacts_display_properties(["guy1@pangea.com", "judicators@akaris.com", "unknown@mydomain.com"], as_dict=True)
        assert set(res.keys()) == set(["guy1@pangea.com", "judicators@akaris.com", "unknown@mydomain.com"])
        assert sorted(res.values(), key=lambda x: x["address"]) == expected_res # values are the same as above...


    def test_message_archiving(self):

        self._reset_messages()

        msg_id_1 = self.dm.post_message("guy2@pangea.com",
                             recipient_emails=["secret-services@masslavia.com", "guy1@pangea.com"],
                             subject="subj", body="INITIAL MESSAGE 1")

        # SIMPLE REPLY
        msg_id_2 = self.dm.post_message("guy1@pangea.com",
                             recipient_emails=["secret-services@heliossar.com", "guy2@pangea.com"],
                             subject="subj", body="MESSAGE WITH PARENT", parent_id=msg_id_1)

        self.dm.set_dispatched_message_state_flags("guy1", msg_id=msg_id_2, has_archived=True)
        msg2 = self.dm.get_dispatched_message_by_id(msg_id_2)
        print("-------------------->", msg2)


        res = self.dm.get_user_related_messages("guy1")
        assert len(res) == 2

        res = self.dm.get_user_related_messages("guy1", archived=None)
        assert len(res) == 2

        res1 = self.dm.get_user_related_messages("guy1", archived=True)
        assert len(res1) == 1
        assert res1[0]["id"] == msg_id_2

        res2 = self.dm.get_user_related_messages("guy1", archived=False)
        assert len(res2) == 1
        assert res2[0]["id"] == msg_id_1


        res = self.dm.get_user_related_messages("guy2")
        assert len(res) == 2

        res = self.dm.get_user_related_messages("guy2", archived=None)
        assert len(res) == 2

        res1 = self.dm.get_user_related_messages("guy2", archived=True)
        assert len(res1) == 0

        res2 = self.dm.get_user_related_messages("guy2", archived=False)
        assert len(res2) == 2  # only "guy1" has archived the msg2


        archived = random.choice((None, True, False))
        res = self.dm.get_user_related_messages("guy3", archived=archived)
        assert len(res) == 0



    def test_deletion_of_transferred_message(self):

        msg_id_1 = self.dm.post_message("guy2@pangea.com",
                             recipient_emails=["secret-services@masslavia.com", "guy1@pangea.com"],
                             subject="subj", body="INITIAL MESSAGE 1")

        # SIMPLE REPLY
        msg_id_2 = self.dm.post_message("guy3@pangea.com",
                             recipient_emails=["secret-services@heliossar.com"],
                             subject="subj", body="MESSAGE WITH PARENT", parent_id=msg_id_1)

        # TRANSFER
        msg_id_3 = self.dm.post_message("guy4@pangea.com",
                             recipient_emails=["guy1@pangea.com"],
                             subject="subj", body="MESSAGE WITH TRANSFER", transferred_msg=msg_id_1)

        self.dm.get_dispatched_message_by_id(msg_id_1)
        self.dm.permanently_delete_message(msg_id_1)
        with pytest.raises(UsageError):
            self.dm.get_dispatched_message_by_id(msg_id_1)  # will cause trouble in global coherence check, if handling is buggy

        msg2 = self.dm.get_dispatched_message_by_id(msg_id_2)
        assert not msg2["transferred_msg"]

        msg3 = self.dm.get_dispatched_message_by_id(msg_id_3)
        assert msg3["transferred_msg"] == msg_id_1  # STILL present


    def test_mailing_list_special_case(self):

        ml = self.dm.get_global_parameter("all_players_mailing_list")

        self.dm.post_message("guy2@pangea.com",
                             recipient_emails=["secret-services@masslavia.com", "guy1@pangea.com", ml],
                             subject="subj", body="qsdqsd") # this works too !

        msg = self.dm.get_all_dispatched_messages()[-1]

        assert msg["subject"] == "subj"
        assert msg["visible_by"] == {'guy3': 'recipient',
                                     'guy4': 'recipient',
                                     'master': 'recipient',
                                     'guy2': 'sender', # well set
                                     'guy1': 'recipient'}
        assert self.dm.get_character_properties("my_npc") # EXISTS, but not included since it's not a player

        self.dm.post_message("secret-services@masslavia.com",
                             recipient_emails=["guy1@pangea.com", ml],
                             subject="subj2", body="qsdqsd") # this works too !

        msg = self.dm.get_all_dispatched_messages()[-1]

        assert msg["subject"] == "subj2"
        assert msg["visible_by"] == {'guy3': 'recipient',
                                     'guy4': 'recipient',
                                     'master': 'sender',
                                     'guy2': 'recipient',
                                     'guy1': 'recipient'}

        self.dm.post_message("guy2@pangea.com",
                             recipient_emails=[ml],
                             subject="subj2", body="qsdqsd") # this works too !

        msg = self.dm.get_all_dispatched_messages()[-1]

        assert msg["subject"] == "subj2"
        assert msg["visible_by"] == {'guy3': 'recipient',
                                     'guy4': 'recipient',
                                     'guy2': 'sender', # "sender" STRONGER than "recipient" status
                                     'guy1': 'recipient'}


    def test_text_messaging_workflow(self):

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
            "recipient_emails": ["secret-services@masslavia.com", "guy2@pangea.com"], # guy2 will both wiretap and receive here
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

        self.dm.post_message("guy1@masslavia.com", # NOT recognised as guy1, because wrong domain
                             "netsdfworkerds@masslavia.com", subject="ssd", body="qsdqsd") # this works too !

        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        assert not msg["mask_recipients"]  # default value
        # we now check that MATSER doesn't appear in get_characters_for_visibility_reason() output
        assert self.dm.get_characters_for_visibility_reason(msg, visibility_reason=VISIBILITY_REASONS.interceptor) == []
        assert self.dm.get_characters_for_visibility_reason(msg, visibility_reason=VISIBILITY_REASONS.sender) == []
        assert self.dm.get_characters_for_visibility_reason(msg, visibility_reason=VISIBILITY_REASONS.recipient) == []

        self.assertEqual(len(self.dm.get_user_related_messages(self.dm.master_login)), 1)
        self.dm.get_user_related_messages(self.dm.master_login)[0]["has_read"] = utilities.PersistentList(
            self.dm.get_character_usernames() + [self.dm.get_global_parameter("master_login")]) # we hack this message not to break following assertions

        id_msg_back = self.dm.post_message(**record1)
        time.sleep(0.2)

        self.dm.set_wiretapping_targets("guy4", ["guy4"]) # stupid but possible, and harmless actually

        self.dm.set_wiretapping_targets("guy1", ["guy2"])
        self.dm.set_wiretapping_targets("guy2", ["guy4"])

        self.dm.set_wiretapping_targets("guy3", ["guy1"]) # USELESS wiretapping, thanks to SSL/TLS
        self.dm.set_confidentiality_protection_status("guy3", True)

        self.dm.post_message(transferred_mdg=id_msg_back, **record2)
        time.sleep(0.2)
        self.dm.post_message(**record3)
        time.sleep(0.2)
        self.dm.post_message(**record4)
        time.sleep(0.2)
        self.dm.post_message(**record1) # this message will get back to the 2nd place of list !

        #print ("@>@>@>@>", self.dm.get_all_dispatched_messages())
        self.assertEqual(self.dm.get_unread_messages_count("guy3"), 3)

        self.assertEqual(self.dm.get_unread_messages_count(self.dm.get_global_parameter("master_login")), 1) # message sent BY master is already marked as read

        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 6)

        res = self.dm.get_user_related_messages(self.dm.master_login)
        #pprint.pprint(res)
        self.assertEqual(len(res), 3) # secret services masslavia + wrong networker email address + dummy-robot

        visibility_reasons = random.sample(list(VISIBILITY_REASONS), random.randint(1, 3))
        res = self.dm.get_user_related_messages(self.dm.master_login, visibility_reasons=visibility_reasons)
        assert len(res) <= 3
        assert all(msg["visible_by"][self.dm.master_login] in visibility_reasons for msg in res)

        self.assertEqual(len(self.dm.get_user_related_messages("guy3")), 3)  # duplicate sending of msg1
        self.assertEqual(len(self.dm.get_user_related_messages("guy3", visibility_reasons=(VISIBILITY_REASONS.sender,))), 0)
        self.assertEqual(len(self.dm.get_user_related_messages("guy3", visibility_reasons=(VISIBILITY_REASONS.interceptor,))), 0)
        self.assertEqual(len(self.dm.get_user_related_messages("guy3", visibility_reasons=(VISIBILITY_REASONS.recipient,))), 3)

        expected_notifications = {'guy2': "new_messages_2", 'guy3': "new_messages_1", 'guy1': 'info_spots_1'} # guy1 because of wiretapping, not guy4 because was only a sender
        self.assertEqual(self.dm.get_pending_new_message_notifications(), expected_notifications)
        self.assertEqual(self.dm.get_pending_new_message_notifications(), expected_notifications) # no disappearance

        self.assertEqual(self.dm.has_new_message_notification("guy3"), 3)
        self.assertEqual(len(self.dm.pop_received_messages("guy3")), 3)
        self.assertFalse(self.dm.has_new_message_notification("guy3"))

        # here we can't do check messages of secret-services@masslavia.com since it's not a normal character

        self.assertEqual(self.dm.has_new_message_notification("guy2"), 2) # 2 messages where he's TARGET
        self.assertEqual(len(self.dm.get_received_messages("guy2")), 2)
        assert not self.dm.get_intercepted_messages("guy2") # wiretapping is overridden by other visibility reasons

        self.assertTrue(self.dm.has_new_message_notification("guy2"))
        self.dm.set_new_message_notification(utilities.PersistentList(["guy1", "guy2"]), increment=0)
        self.assertFalse(self.dm.has_new_message_notification("guy1"))
        self.assertFalse(self.dm.has_new_message_notification("guy2"))

        self.assertEqual(self.dm.get_pending_new_message_notifications(), {}) # all have been reset

        self.assertEqual(len(self.dm.get_received_messages("guy1")), 0)

        self.assertEqual(len(self.dm.get_sent_messages("guy2")), 2)
        self.assertEqual(len(self.dm.get_sent_messages("guy1")), 1)
        self.assertEqual(len(self.dm.get_sent_messages("guy3")), 0)

        assert not self.dm.get_intercepted_messages("guy3") # ineffective wiretapping

        res = self.dm.get_intercepted_messages("guy1")
        self.assertEqual(len(res), 3) # wiretapping of user as sender AND recipient
        self.assertEqual(set([msg["subject"] for msg in res]), set(["hello everybody 1", "hello everybody 2", "hello everybody 4"]))
        assert all([msg["visible_by"]["guy1"] == VISIBILITY_REASONS.interceptor for msg in res])

        msg = res[0] # first of these messages intercepted by guy1
        assert msg["subject"] == "hello everybody 1"
        assert self.dm.get_characters_for_visibility_reason(msg, visibility_reason=VISIBILITY_REASONS.interceptor) == ["guy1"]
        assert self.dm.get_characters_for_visibility_reason(msg, visibility_reason=VISIBILITY_REASONS.sender) == ["guy2"]
        assert self.dm.get_characters_for_visibility_reason(msg, visibility_reason=VISIBILITY_REASONS.recipient) == ["guy3"]



        res = self.dm.get_intercepted_messages(self.dm.master_login)
        self.assertEqual(len(res), 0)

        # game master doesn't need these...
        #self.assertEqual(set([msg["subject"] for msg in res]), set(["hello everybody 1", "hello everybody 2", "hello everybody 4"]))
        #assert all([msg["intercepted_by"] for msg in res])
        # NO - we dont notify interceptions - self.assertTrue(self.dm.get_global_parameter("message_intercepted_audio_id") in self.dm.get_all_next_audio_messages(), self.dm.get_all_next_audio_messages())

        # msg has_read state changes
        msg_id1 = self.dm.get_all_dispatched_messages()[0]["id"] # sent to guy3
        msg_id2 = self.dm.get_all_dispatched_messages()[3]["id"] # sent to external contact

        """ # NO PROBLEM with wrong msg owner
        self.assertRaises(Exception, self.dm.set_dispatched_message_state_flags, MASTER, msg_id1, has_read=True)
        self.assertRaises(Exception, self.dm.set_dispatched_message_state_flags, "guy2", msg_id1, has_read=True)
        self.assertRaises(Exception, self.dm.set_dispatched_message_state_flags, "guy1", msg_id2, has_read=True)
        """

        # wrong msg id
        self.assertRaises(Exception, self.dm.set_dispatched_message_state_flags, "dummyid", has_read=False)


        # self.assertEqual(self.dm.get_all_dispatched_messages()[0]["no_reply"], False)
        # self.assertEqual(self.dm.get_all_dispatched_messages()[4]["no_reply"], True)# msg from robot

        _get_first_dispatched_msg = lambda: self.dm.get_all_dispatched_messages()[0]

        self.assertEqual(_get_first_dispatched_msg()["is_certified"], False)
        self.assertEqual(_get_first_dispatched_msg()["has_read"], ["guy2"])
        self.dm.set_dispatched_message_state_flags("guy3", msg_id1, has_read=True)
        self.dm.set_dispatched_message_state_flags("guy2", msg_id1, has_read=True)

        self.assertEqual(len(_get_first_dispatched_msg()["has_read"]), 2)
        self.assertTrue("guy2" in _get_first_dispatched_msg()["has_read"])
        self.assertTrue("guy3" in _get_first_dispatched_msg()["has_read"])

        self.assertEqual(self.dm.get_unread_messages_count("guy3"), 2)
        self.dm.set_dispatched_message_state_flags("guy3", msg_id1, has_read=False)
        self.assertEqual(_get_first_dispatched_msg()["has_read"], ["guy2"])
        self.assertEqual(self.dm.get_unread_messages_count("guy3"), 3)

        self.assertEqual(self.dm.get_all_dispatched_messages()[3]["has_read"], ["guy4"])
        self.dm.set_dispatched_message_state_flags(MASTER, msg_id2, has_read=True)
        self.assertTrue(MASTER in self.dm.get_all_dispatched_messages()[3]["has_read"])
        self.assertEqual(self.dm.get_unread_messages_count(self.dm.get_global_parameter("master_login")), 0)
        self.dm.set_dispatched_message_state_flags(MASTER, msg_id2, has_read=False)
        self.assertEqual(self.dm.get_all_dispatched_messages()[3]["has_read"], ["guy4"])
        self.assertEqual(self.dm.get_unread_messages_count(self.dm.get_global_parameter("master_login")), 1)


        # for now we just check email address format, not its existence in our registries #
        with pytest.raises(NormalUsageError):
            self.dm.post_message("anything@masssslavia.com",
                                 "net@sdfworkerds@massla@via.com;aaa@fff.fr", subject="ssd", body="qsdqsd") # wrong recipient format
        with pytest.raises(NormalUsageError):
            self.dm.post_message("anything@mas@sss@lavia.com",
                                 "net@via.com;aaa@fff.fr", subject="ssd", body="qsdqsd") # wrong sender format
        self.dm.post_message("anything@lavia.com",
                             "net@via.com;aaa@fff.fr", subject="ssd", body="qsdqsd") # no problem, even if email addresses are unknown


        # special case : visibility reason for game master

        contact_for_master = random.choice(("anything@masssslavia.com", self.dm.get_character_email("my_npc")))
        contact_for_master2 = random.choice(("anythdfsdfing@mas.com", self.dm.get_character_email("my_npc")))

        self.dm.post_message(contact_for_master, "guy2@pangea.com", subject="AAA1", body="BBBBB") # master is SENDER
        self.dm.post_message("guy2@pangea.com", contact_for_master, subject="AAA2", body="BBBBB") # master is RECIPIENT
        self.dm.post_message("guy2@pangea.com", "guy4@pangea.com", subject="AAA3", body="BBBBB") # master is NOTHING
        self.dm.post_message(contact_for_master, contact_for_master2, subject="AAA4", body="BBBBB")

        a, b, c, d = self.dm.get_all_dispatched_messages()[-4:]

        assert a["visible_by"][MASTER] == VISIBILITY_REASONS.sender
        assert b["visible_by"][MASTER] == VISIBILITY_REASONS.recipient
        assert MASTER not in c["visible_by"]
        assert d["visible_by"][MASTER] == VISIBILITY_REASONS.sender # takes precedence!

        assert all(not x["mask_recipients"] for x in self.dm.get_all_dispatched_messages())


        # test that we can initialize boolean fields as we wish
        self.dm.post_message(**{
            "sender_email": "guy4@pangea.com",
            "recipient_emails": ["guy4@pangea.com"],
            "subject": "BOOLEAN_FIELDS",
            "body": "Here is the body of this message lalalal...",
            "date_or_delay_mn":0,
            "has_read": ["guy1"],
            "has_replied": ["guy2"],
            "has_starred": ["guy3"],
            "has_archived": ["guy4"]
            })
        msg = self.dm.get_all_dispatched_messages()[-1]
        assert msg["subject"] == "BOOLEAN_FIELDS"
        assert msg["has_read"] == ["guy1", "guy4"]  # sender is auto-added
        assert msg["has_replied"] == ["guy2"]
        assert msg["has_starred"] == ["guy3"]
        assert msg["has_archived"] == ["guy4"]


    def test_message_recipients_masking(self):

        self._reset_messages()

        self.dm.post_message("guy2@pangea.com", "guy1@pangea.com", subject="AAA", body="BBBBB", mask_recipients=True)

        (msg,) = self.dm.get_all_dispatched_messages()

        assert msg["mask_recipients"]  # important

        assert msg["visible_by"]["guy2"] == VISIBILITY_REASONS.sender
        assert msg["visible_by"]["guy1"] == VISIBILITY_REASONS.recipient


    def test_time_shifts_on_message_posting(self):

        self._reset_messages()

        game_length_days = self.dm.get_global_parameter("game_theoretical_length_days")
        assert game_length_days == 45.3

        utcnow = datetime.utcnow()

        fixed_dt_past = utcnow.replace(microsecond=0) + timedelta(hours=random.randint(-1000, -100))
        fixed_dt_future = utcnow.replace(microsecond=0) + timedelta(hours=random.randint(100, 1000))

        record = {
            "sender_email": "guy4@pangea.com",
            "recipient_emails": ["secret-services@masslavia.com", "guy2@pangea.com"],
            "subject": "hello everybody 1",
            "body": "Here is the body of this message lililili...",
            "attachment": "http://yowdlayhio",
            "date_or_delay_mn": 0
        }
        self.dm.post_message(**record) # IMMEDIATE

        record["date_or_delay_mn"] = -29.8 # will be interpreted as a flexible time delay
        self.dm.post_message(**record)

        record["date_or_delay_mn"] = fixed_dt_past
        self.dm.post_message(**record)

        record["date_or_delay_mn"] = (10, 30) # will be interpreted as a flexible time delay
        self.dm.post_message(**record)

        record["date_or_delay_mn"] = fixed_dt_future
        self.dm.post_message(**record)

        # DISPATCHED MESSAGES
        dispatched = self.dm.get_all_dispatched_messages()
        assert len(dispatched) == 3 # only 3 of the 5 where set in the past
        assert dispatched[0]["sent_at"] == fixed_dt_past # NO FLEXIBLE TIME HERE
        assert utcnow - timedelta(minutes=1450) < dispatched[1]["sent_at"] < utcnow - timedelta(minutes=1250)
        assert utcnow - timedelta(seconds=10) < dispatched[2]["sent_at"] <= utcnow + timedelta(seconds=10)
        del dispatched

        # QUEUED MESSAGES
        queued = self.dm.get_all_queued_messages()
        assert len(queued) == 2 # only 2 of the 5 where set in the future
        assert utcnow + timedelta(minutes=450) < queued[0]["sent_at"] < utcnow + timedelta(minutes=1600)
        assert queued[1]["sent_at"] == fixed_dt_future # NO FLEXIBLE TIME HERE
        del queued


    def test_messaging_address_restrictions(self):

        target = "judicators@akaris.com"
        assert self.dm.global_contacts[target]["access_tokens"] == ["guy1", "guy2"]

        if random.choice((True, False)):
            self._set_user("guy1") # WITHOUT IMPACT HERE

        self.dm.post_message("guy1@pangea.com", [target], "hhh", "hello") # allowed
        self.dm.post_message("othercontact@anything.fr", [target], "hhh", "hello") # allowed
        self.dm.post_message(target, [target], "hhh", "hello") # allowed

        with pytest.raises(UsageError):
            self.dm.post_message("guy3@pangea.com", [target], "hhaah", "hssello") # NOT allowed, because sender is character AND not in access tokens



    def test_wiretapping_methods(self):


        my_user1 = "guy2"
        my_user2 = "guy3"
        my_user3 = "guy4"
        self._set_user(my_user1)

        # standard target setup

        self.dm.set_wiretapping_targets(my_user1, [my_user2])

        assert self.dm.get_wiretapping_targets(my_user1) == [my_user2]
        assert self.dm.get_wiretapping_targets(my_user2) == []
        assert self.dm.get_wiretapping_targets(my_user3) == []

        assert self.dm.get_listeners_for(my_user1) == []
        assert self.dm.get_listeners_for(my_user2) == [my_user1]
        assert self.dm.get_listeners_for(my_user3) == []

        assert self.dm.determine_effective_wiretapping_traps(my_user1) == [my_user2]
        assert self.dm.determine_effective_wiretapping_traps(my_user2) == []
        assert self.dm.determine_effective_wiretapping_traps(my_user3) == []

        assert self.dm.determine_broken_wiretapping_data(my_user1) == {}
        assert self.dm.determine_broken_wiretapping_data(my_user2) == {}
        assert self.dm.determine_broken_wiretapping_data(my_user3) == {}


        # SSL/TLS protection enabled

        self.dm.set_wiretapping_targets(my_user2, [my_user1])  # back link

        assert not self.dm.get_confidentiality_protection_status(my_user1)
        assert not self.dm.get_confidentiality_protection_status(my_user2)

        start = datetime.utcnow()
        self.dm.set_confidentiality_protection_status(my_user1, has_confidentiality=True) # my_user1 is PROTECTED against interceptions!!
        end = datetime.utcnow()

        activation_date = self.dm.get_confidentiality_protection_status(my_user1)
        assert activation_date and (start <= activation_date <= end)
        assert not self.dm.get_confidentiality_protection_status(my_user2)

        assert self.dm.get_wiretapping_targets(my_user1) == [my_user2]
        assert self.dm.get_wiretapping_targets(my_user2) == [my_user1] # well listed, even if ineffective
        assert self.dm.get_wiretapping_targets(my_user3) == []

        assert self.dm.get_listeners_for(my_user1) == [my_user2] # well listed, even if ineffective
        assert self.dm.get_listeners_for(my_user2) == [my_user1]
        assert self.dm.get_listeners_for(my_user3) == []

        assert self.dm.determine_effective_wiretapping_traps(my_user1) == [my_user2]
        assert self.dm.determine_effective_wiretapping_traps(my_user2) == [] # NOT EFFECTIVE
        assert self.dm.determine_effective_wiretapping_traps(my_user3) == []

        assert self.dm.determine_broken_wiretapping_data(my_user1) == {}
        assert self.dm.determine_broken_wiretapping_data(my_user2) == {my_user1: activation_date}
        assert self.dm.determine_broken_wiretapping_data(my_user3) == {}


        # SSL/TLS protection disabled

        self.dm.set_confidentiality_protection_status(has_confidentiality=False) # fallback to current user

        assert not self.dm.get_confidentiality_protection_status(my_user1)
        assert not self.dm.get_confidentiality_protection_status(my_user2)

        assert self.dm.determine_effective_wiretapping_traps(my_user1) == [my_user2]
        assert self.dm.determine_effective_wiretapping_traps(my_user2) == [my_user1]
        assert self.dm.determine_effective_wiretapping_traps(my_user3) == []

        assert self.dm.determine_broken_wiretapping_data(my_user1) == {}
        assert self.dm.determine_broken_wiretapping_data(my_user2) == {}
        assert self.dm.determine_broken_wiretapping_data(my_user3) == {}



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
        self.assertEqual(set(properties.keys()), set(["title", "text", "file", "initial", "gamemaster_hints"]))

        # self.assertEqual(properties["new_messages_notification_for_user"], "guy3")
        # self.assertEqual(self.dm.get_audio_message_properties("request_for_report_teldorium")["new_messages_notification_for_user"], None)

        self.assertEqual(len(self.dm.get_all_next_audio_messages()), 0)

        assert self.dm.has_read_current_playlist("guy4") # empty playlist ALWAYS read
        assert self.dm.has_read_current_playlist("guy3")

        self.dm.add_radio_message(audio_id)
        self.assertEqual(self.dm.get_next_audio_message(), audio_id)
        self.assertEqual(self.dm.get_next_audio_message(), audio_id) # no disappearance
        assert not self.dm.has_read_current_playlist("guy4")

        assert not self.dm.has_read_current_playlist("guy4") # RESET
        self.dm.mark_current_playlist_read("guy4")
        assert self.dm.has_read_current_playlist("guy4")
        assert not self.dm.has_read_current_playlist("guy3")

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
        assert self.dm.get_all_next_audio_messages() == [audio_id, audio_id_bis, audio_id_ter]

        self.assertEqual(self.dm.get_next_audio_message(), audio_id)

        self.dm.notify_audio_message_termination("bad_audio_id") # no error, we just ignore it

        self.dm.notify_audio_message_termination(audio_id_ter) # removing trailing one works

        self.dm.notify_audio_message_termination(audio_id)

        self.assertEqual(self.dm.get_global_parameter("radio_is_on"), True)

        self.assertEqual(self.dm.get_next_audio_message(), audio_id_bis)
        self.dm.notify_audio_message_termination(audio_id_bis)

        self.assertEqual(self.dm.get_global_parameter("radio_is_on"), False) # auto extinction of radio

        self.assertEqual(self.dm.get_next_audio_message(), None)
        self.assertEqual(len(self.dm.get_all_next_audio_messages()), 0)

        self.dm.set_radio_messages([audio_id_bis, audio_id_ter])

        self.dm.mark_current_playlist_read("guy2")
        assert self.dm.has_read_current_playlist("guy2")
        assert not self.dm.has_read_current_playlist("guy3")

        self.dm.set_radio_messages([audio_id_bis, audio_id_ter]) # UNCHANGED

        assert self.dm.has_read_current_playlist("guy2") # UNCHANGED
        assert not self.dm.has_read_current_playlist("guy3")

        self.dm.add_radio_message(audio_id_ter) # UNCHANGED

        assert self.dm.has_read_current_playlist("guy2") # UNCHANGED
        assert not self.dm.has_read_current_playlist("guy3")

        self.dm.set_radio_messages([audio_id_bis, audio_id_ter, audio_id_ter]) # finally changed
        assert self.dm.get_all_next_audio_messages() == [audio_id_bis, audio_id_ter, audio_id_ter]
        self.assertEqual(self.dm.get_next_audio_message(), audio_id_bis)

        assert not self.dm.has_read_current_playlist("guy2") # RESET
        assert not self.dm.has_read_current_playlist("guy3")


    def test_radio_spots_referential_integrity(self):

        with pytest.raises(AbnormalUsageError):
            del self.dm.radio_spots["info_spots_1"]  # initial spots are, by default, immutable

        audio_id = "erasable_spots"   # this one IS mutable
        self.dm.set_radio_messages([audio_id])
        assert self.dm.get_all_next_audio_messages() == [audio_id]
        del self.dm.radio_spots[audio_id]  # triggers pruning of radio playlist
        assert self.dm.get_all_next_audio_messages() == []



        # mutability control #
        # NOTE that currently ALL radio spots are MUTABLE (but initial ones are undeletable)#

        container = self.dm.radio_spots

        assert not container.get_all_data(mutability=False)

        mutable_entry = "intro_audio_messages"
        assert mutable_entry in container.get_all_data()
        assert mutable_entry in container.get_all_data(mutability=True)
        assert mutable_entry not in container.get_all_data(mutability=False)
        assert mutable_entry in [k for k, v in container.get_all_data(as_sorted_list=True)]
        assert mutable_entry not in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=False)]
        assert mutable_entry in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=True)]
        assert mutable_entry not in [k for k, v in container.get_all_data(as_sorted_list=True, mutability=False)]
        assert mutable_entry in container.get_undeletable_identifiers()
        assert len(container.get_all_data()) == len(container.get_undeletable_identifiers())  # ALL undeletable initially

        new_id = "newid"
        new_item = utilities.safe_copy(container[mutable_entry])
        del new_item["initial"]
        container[new_id] = new_item
        self.dm.commit()

        assert new_id not in container.get_undeletable_identifiers()
        assert new_id in container.get_all_data(mutability=True)
        assert new_id not in container.get_all_data(mutability=False)

        new_item = utilities.safe_copy(container[mutable_entry])
        del new_item["initial"]
        container[mutable_entry] = utilities.safe_copy(new_item)
        self.dm.commit()
        assert mutable_entry in container.get_undeletable_identifiers()  # unchanged deletability for existing entry



    def test_delayed_message_processing_and_basic_message_deletion(self):

        WANTED_FACTOR = 2 # we only double durations below
        params = self.dm.get_global_parameters()
        assert params["game_theoretical_length_days"]
        params["game_theoretical_length_days"] = WANTED_FACTOR


        self._reset_messages()

        email = self.dm.get_character_email # function

        # delayed message sending

        self.dm.post_message(email("guy3"), email("guy2"), "yowh1", "qhsdhqsdh", attachment=None, date_or_delay_mn=0.03 / WANTED_FACTOR)
        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 0)
        queued_msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(queued_msgs), 1)
        # print datetime.utcnow(), " << ", queued_msgs[0]["sent_at"]
        self.assertTrue(datetime.utcnow() < queued_msgs[0]["sent_at"] < datetime.utcnow() + timedelta(minutes=0.22))

        self.dm.post_message(email("guy3"), email("guy2"), "yowh2", "qhsdhqsdh", attachment="/my/dummy/url", transferred_msg=queued_msgs[0]["id"],
                             date_or_delay_mn=(0.04 / WANTED_FACTOR, 0.05 / WANTED_FACTOR)) # 3s delay range
        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 0)
        queued_msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(queued_msgs), 2)
        self.assertEqual(queued_msgs[1]["subject"], "yowh2", queued_msgs)
        # print datetime.utcnow(), " >> ", queued_msgs[1]["sent_at"]
        self.assertTrue(datetime.utcnow() < queued_msgs[1]["sent_at"] < datetime.utcnow() + timedelta(minutes=0.06))

        # delayed message processing

        self.dm.post_message(email("guy3"), email("guy2"), "yowh3", "qhsdhqsdh", attachment=None, date_or_delay_mn=0.01 / WANTED_FACTOR) # 0.6s
        self.assertEqual(len(self.dm.get_all_queued_messages()), 3)
        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 0)
        res = self.dm.process_periodic_tasks()
        self.assertEqual(res["messages_dispatched"], 0)
        self.assertEqual(res["actions_executed"], 0)
        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 0)

        time.sleep(0.8) # one message OK

        res = self.dm.process_periodic_tasks()
        # print self.dm.get_all_dispatched_messages(), datetime.utcnow()
        self.assertEqual(res["messages_dispatched"], 1)
        self.assertEqual(res["actions_executed"], 0)
        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 1)
        # print(">>>>>>>>>>>>>>>>>>>>>>##", self.dm.get_all_queued_messages())
        self.assertEqual(len(self.dm.get_all_queued_messages()), 2)

        time.sleep(2.5) # last messages OK

        res = self.dm.process_periodic_tasks()
        self.assertEqual(res["messages_dispatched"], 2)
        self.assertEqual(res["actions_executed"], 0)
        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 3)
        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        # due to the strength of coherence checks, it's about impossible to enforce a sending here here...
        self.assertEqual(self.dm.get_event_count("DELAYED_MESSAGE_ERROR"), 0)


        # forced sending of queued messages
        myid1 = self.dm.post_message(email("guy3"), email("guy2"), "yowh2", "qhsdhqsdh", attachment=None, date_or_delay_mn=(1.0 / WANTED_FACTOR, 2.0 / WANTED_FACTOR)) # 3s delay range
        myid2 = self.dm.post_message(email("guy3"), email("guy2"), "yowh2", "qhsdhqsdh", attachment=None, date_or_delay_mn=(1.0 / WANTED_FACTOR, 2.0 / WANTED_FACTOR)) # 3s delay range
        assert myid1 != myid2
        self.assertEqual(len(self.dm.get_all_queued_messages()), 2)

        self.assertFalse(self.dm.force_message_sending("dummyid"))
        self.assertTrue(self.dm.force_message_sending(myid1))
        self.assertEqual(len(self.dm.get_all_queued_messages()), 1)
        self.assertFalse(self.dm.force_message_sending(myid1)) # already sent now
        self.assertEqual(self.dm.get_all_queued_messages()[0]["id"], myid2)
        self.assertTrue(self.dm.get_dispatched_message_by_id(myid1))


        # basic message deletion #
        assert not self.dm.permanently_delete_message("badid")

        assert self.dm.permanently_delete_message(myid1) # DISPATCHED MESSAGE DELETED
        assert not self.dm.permanently_delete_message(myid1)
        with pytest.raises(UsageError):
            self.dm.get_dispatched_message_by_id(myid1) # already deleted

        assert self.dm.permanently_delete_message(myid2) # QUEUED MESSAGE DELETED
        assert not self.dm.permanently_delete_message(myid2)
        assert not self.dm.get_all_queued_messages()



    def test_delayed_action_processing(self):

        WANTED_FACTOR = 2 # we only double durations below
        params = self.dm.get_global_parameters()
        assert params["game_theoretical_length_days"]
        params["game_theoretical_length_days"] = WANTED_FACTOR


        def _dm_delayed_action(arg1):
            self.dm.data["global_parameters"]["stuff"] = 23
            self.dm.commit()
        self.dm._dm_delayed_action = _dm_delayed_action # now an attribute of that speific instance, not class!

        self.dm.schedule_delayed_action(0.01 / WANTED_FACTOR, dummyfunc, 12, item=24)
        self.dm.schedule_delayed_action((0.04 / WANTED_FACTOR, 0.05 / WANTED_FACTOR), dummyfunc) # will raise error
        self.dm.schedule_delayed_action((0.035 / WANTED_FACTOR, 0.05 / WANTED_FACTOR), "_dm_delayed_action", "hello")

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
    def test_standard_user_authentication(self):
        """
        Here we use frontend methods from authentication.py instead of
        directly datamanager methods.
        """
        self._reset_django_db()

        OTHER_SESSION_TICKET_KEY = SESSION_TICKET_KEY_TEMPLATE % "my_other_test_game_id"

        home_url = neutral_url_reverse(views.homepage)

        master_login = self.dm.get_global_parameter("master_login")
        master_password = self.dm.get_global_parameter("master_password")
        player_login = "guy1"
        player_password = "elixir"
        anonymous_login = self.dm.get_global_parameter("anonymous_login")


        # build complete request (without auto-checking DM)
        request = self.factory.post(home_url)
        request.datamanager = self.dm
        # we let different states of the session ticket be there, at the beginning
        if random.choice((0, 1)):
            request.session[SESSION_TICKET_KEY] = random.choice((None, {}))

        # anonymous case
        assert request.datamanager.user.username == anonymous_login
        assert not self.dm.get_impersonation_targets(anonymous_login)


        def _standard_authenticated_checks():

            # we set a ticket for another game instance, different
            other_session_ticket = random.choice((None, True, {'a': 'b'}, [1, 2]))
            request.session[OTHER_SESSION_TICKET_KEY] = copy.copy(other_session_ticket)


            original_ticket = request.session[SESSION_TICKET_KEY].copy()
            original_username = request.datamanager.user.username

            assert request.datamanager == self.dm
            self._set_user(None)
            assert request.datamanager.user.username == anonymous_login
            assert request.datamanager.user.real_username == anonymous_login
            assert request.datamanager.user.has_write_access
            assert not request.datamanager.user.is_impersonation
            assert not request.datamanager.user.impersonation_target
            assert not request.datamanager.user.impersonation_writability
            assert not request.datamanager.user.is_superuser
            assert not request.datamanager.user.is_observer
            assert not self.dm.should_display_admin_tips()

            res = try_authenticating_with_session(request)
            assert res is None

            assert request.session[SESSION_TICKET_KEY] == original_ticket
            assert request.datamanager.user.username == original_username
            assert request.datamanager.user.real_username == original_username
            assert request.datamanager.user.has_write_access
            assert not request.datamanager.user.is_impersonation
            assert not request.datamanager.user.impersonation_target
            assert not request.datamanager.user.impersonation_writability
            assert not request.datamanager.user.is_superuser
            assert not request.datamanager.user.is_observer
            assert self.dm.should_display_admin_tips() == (original_username == master_login)

            self._set_user(None)

            # failure case: wrong ticket type
            request.session[SESSION_TICKET_KEY] = ["dqsdqs"]
            try_authenticating_with_session(request) # exception gets swallowed
            assert request.session[SESSION_TICKET_KEY] is None

            self._set_user(None)

            # failure case: wrong instance id
            request.session[SESSION_TICKET_KEY] = original_ticket.copy()
            request.session[SESSION_TICKET_KEY]["game_instance_id"] = "qsdjqsidub"
            _temp = request.session[SESSION_TICKET_KEY].copy()
            try_authenticating_with_session(request)
            assert request.session[SESSION_TICKET_KEY] == None # removed

            self._set_user(None)

            request.session[SESSION_TICKET_KEY] = original_ticket.copy()
            request.session[SESSION_TICKET_KEY]["game_username"] = "qsdqsdqsd"
            try_authenticating_with_session(request) # exception gets swallowed
            assert request.session[SESSION_TICKET_KEY] == None # but ticket gets reset

            self._set_user(None)

            request.session[SESSION_TICKET_KEY] = original_ticket.copy()
            try_authenticating_with_session(request)
            assert request.datamanager.user.username == original_username

            logout_session(request)
            assert SESSION_TICKET_KEY not in request.session
            assert request.datamanager.user.username == anonymous_login # reset
            assert request.session[OTHER_SESSION_TICKET_KEY] == other_session_ticket # other session ticket UNTOUCHED by logout

            request.session[SESSION_TICKET_KEY] = original_ticket.copy()
            try_authenticating_with_session(request)
            assert request.datamanager.user.username == original_username

            clear_all_sessions(request) # FULL reset, including django user data
            assert SESSION_TICKET_KEY not in request.session
            assert request.datamanager.user.username == anonymous_login # reset
            assert OTHER_SESSION_TICKET_KEY not in request.session


        # simple player case

        res = try_authenticating_with_credentials(request, player_login, player_password)
        assert res is None # no result expected
        ticket = request.session[SESSION_TICKET_KEY]
        # NOTE that "is_observer" is NOT added by default
        assert ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                          'impersonation_writability': None, 'game_username': player_login}

        assert request.datamanager.user.username == player_login
        assert not self.dm.get_impersonation_targets(player_login)

        _standard_authenticated_checks()


        # game master case

        res = try_authenticating_with_credentials(request, master_login, master_password)
        assert res is None # no result expected
        ticket = request.session[SESSION_TICKET_KEY]
        # NOTE that "is_observer" is NOT added by default
        assert ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                          'impersonation_writability': None, 'game_username': master_login}

        _standard_authenticated_checks()


    @for_core_module(PlayerAuthentication)
    def test_enforced_session_ticket(self):

        assert config.GAME_ALLOW_ENFORCED_LOGIN
        request_var = "session_ticket"

        username = random.choice(("guy3", "master"))
        home_url = neutral_url_reverse(views.homepage)

        token = authentication.compute_enforced_login_token(self.dm.game_instance_id, username)
        request = self.factory.post(home_url, data={request_var : token})
        request.datamanager = self.dm

        try_authenticating_with_session(request)
        assert request.datamanager.user.username == username # well auto-signed-in
        assert not request.datamanager.user.is_observer

        request._request = {"sdsds" : "sdsd"} # PATCH
        assert request.REQUEST["sdsds"]

        try_authenticating_with_session(request)
        assert request.datamanager.user.username == username # remains


        token = random.choice(("", u"ahduiAy@", u"a è"))
        request._request = {request_var : token} # PATCH

        try_authenticating_with_session(request)
        assert request.datamanager.user.username == username # wrong session ticket given by REQUEST, so we remain as usual
        assert not request.datamanager.user.is_observer


        token = authentication.compute_enforced_login_token("badinstanceid", "guy1", is_observer=False)
        request._request = {request_var : token} # PATCH

        try_authenticating_with_session(request)
        assert request.datamanager.user.username == username # wrong game id given by REQUEST, so we remain as usual


        token = authentication.compute_enforced_login_token(self.dm.game_instance_id, "guy2323")
        request._request = {request_var : token} # PATCH
        assert request.REQUEST[request_var] == token

        try_authenticating_with_session(request)
        assert request.datamanager.user.username == username # wrong user name id given by REQUEST, so we remain as usual


        token = authentication.compute_enforced_login_token(self.dm.game_instance_id, "my_npc")
        request._request = {request_var : token} # PATCH

        try_authenticating_with_session(request)
        assert request.datamanager.user.username == "my_npc"
        assert not request.datamanager.user.is_observer

        logout_session(request)
        assert request.datamanager.user.username == "guest"
        assert not request.datamanager.user.is_observer

        try_authenticating_with_session(request)
        assert request.datamanager.user.username == "my_npc"
        assert not request.datamanager.user.is_observer



        # SPECIAL OBSERVER MODE #

        username = "master"
        token = authentication.compute_enforced_login_token(self.dm.game_instance_id, username, is_observer=True)

        request = self.factory.post(home_url, data={request_var : token})
        request.datamanager = self.dm
        try_authenticating_with_session(request)
        assert request.datamanager.user.username == username # well auto-signed-in
        assert request.datamanager.user.is_observer
        assert not request.datamanager.user.has_write_access # NO write, even for non-impersonated username


        request = self.factory.post(home_url, data={request_var: token, # note that django session tracking via cookie doesn't work here
                                                    IMPERSONATION_TARGET_POST_VARIABLE: "guy1",
                                                    IMPERSONATION_WRITABILITY_POST_VARIABLE: True})
        request.datamanager = self.dm
        try_authenticating_with_session(request)
        assert request.datamanager.user.username == "guy1" # impersonation
        assert request.datamanager.user.real_username == "master"
        assert request.datamanager.user.is_observer
        assert not request.datamanager.user.has_write_access # NO write, especially for impersonated username


        request = self.factory.post(home_url, data={request_var: "",  # quitting authenticated mode
                                                    IMPERSONATION_TARGET_POST_VARIABLE: "guy1",
                                                    IMPERSONATION_WRITABILITY_POST_VARIABLE: True})
        request.datamanager = self.dm
        try_authenticating_with_session(request)
        assert request.datamanager.user.username == "guest" # impersonation
        assert request.datamanager.user.real_username == "guest"
        assert not request.datamanager.user.is_observer
        assert request.datamanager.user.has_write_access



    @for_core_module(PlayerAuthentication)
    def test_observer_authentication(self):

        master_login = self.dm.get_global_parameter("master_login")
        player_login = "guy1"
        anonymous_login = self.dm.get_global_parameter("anonymous_login")

        session_ticket = {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                           'impersonation_writability': None, 'game_username': master_login,
                           'is_observer': True}

        if random.choice((True, False)):
            now = timezone.now()
            is_superuser = random.choice((True, False))
            django_user = User(username='fakename', email='my@email.fr',
                              is_staff=is_superuser, is_active=True, is_superuser=is_superuser,
                              last_login=now, date_joined=now)
        else:
            is_superuser = False
            django_user = None

        requested_impersonation_target = random.choice((None, player_login, anonymous_login))
        requested_impersonation_writability = random.choice((True, False, None)) # IGNORED!
        res = self.dm.authenticate_with_session_data(session_ticket.copy(),
                                                   requested_impersonation_target=requested_impersonation_target,
                                                   requested_impersonation_writability=requested_impersonation_writability,
                                                   django_user=django_user)

        assert res == {u'game_username': master_login,
                       u'impersonation_target': requested_impersonation_target,
                       u'impersonation_writability': None, # blocked because OBSERVER
                       u'game_instance_id': TEST_GAME_INSTANCE_ID,
                       u'is_observer': True}
        assert self.dm.user.is_observer
        assert self.dm.user.username == requested_impersonation_target if requested_impersonation_target else master_login
        assert not self.dm.user.has_write_access
        assert not self.dm.user.is_superuser # hidden by game_username==master_login

        expected_capabilities = dict(display_impersonation_target_shortcut=True,
                                     display_impersonation_writability_shortcut=False, # Special
                                     # impersonation_targets - DELETED
                                     has_writability_control=False, # Special
                                     current_impersonation_target=requested_impersonation_target,
                                     current_impersonation_writability=False)

        res = self.dm.get_current_user_impersonation_capabilities()
        del res["impersonation_targets"]

        assert res == expected_capabilities



    @for_core_module(PlayerAuthentication)
    def test_impersonation_by_superuser(self):

        # TODO check that staff django_user doesn't mess with friendship impersonations either!!!!!!!!

        master_login = self.dm.get_global_parameter("master_login")
        master_password = self.dm.get_global_parameter("master_password")
        player_login = "guy1"
        player_password = "elixir"
        player_login_bis = "guy2"
        anonymous_login = self.dm.get_global_parameter("anonymous_login")


        # use django user, without privileges or inactive #

        now = timezone.now()
        django_user = User(username='fakename', email='my@email.fr',
                      is_staff=False, is_active=True, is_superuser=False,
                      last_login=now, date_joined=now)


        session_ticket = {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                           'impersonation_writability': None, 'game_username': None}

        for i in range(6):

            if random.choice((True, False)):
                django_user.is_active = True
                django_user.is_staff = django_user.is_superuser = False
            else:
                django_user.is_active = False
                django_user.is_staff = random.choice((True, False))
                if django_user.is_staff:
                    django_user.is_superuser = random.choice((True, False))
                else:
                    django_user.is_superuser = False

            requested_impersonation_target = random.choice((None, master_login, player_login, anonymous_login))
            requested_impersonation_writability = random.choice((True, False, None))
            res = self.dm.authenticate_with_session_data(session_ticket.copy(), # COPY
                                                   requested_impersonation_target=requested_impersonation_target,
                                                   requested_impersonation_writability=requested_impersonation_writability,
                                                   django_user=django_user)

            # NOTE that "is_observer" is NOT added to session by default
            assert res == {u'game_username': None,
                           u'impersonation_target': None, # we can't impersonate because inactive or not staff user
                           u'impersonation_writability': None, # blocked because non-privileged user
                           u'game_instance_id': TEST_GAME_INSTANCE_ID}
            assert not self.dm.user.is_observer
            assert self.dm.user.username == anonymous_login
            assert self.dm.user.has_write_access
            assert not self.dm.user.is_superuser
            assert not self.dm.should_display_admin_tips()
            assert not self.dm.user.is_impersonation
            assert self.dm.user.real_username == anonymous_login

            must_have_notifications = bool(requested_impersonation_target and requested_impersonation_target != anonymous_login)
            assert self.dm.user.has_notifications() == must_have_notifications
            self.dm.user.discard_notifications()

            # ANONYMOUS CASE
            expected_capabilities = dict(display_impersonation_target_shortcut=False,
                                         display_impersonation_writability_shortcut=False,
                                         impersonation_targets=[],
                                         has_writability_control=False,
                                         current_impersonation_target=None,
                                         current_impersonation_writability=False)
            assert self.dm.get_current_user_impersonation_capabilities() == expected_capabilities

            # then we look at impersonation by django super user #

            django_user.is_active = True
            django_user.is_staff = True
            django_user.is_superuser = random.choice((True, False))

            requested_impersonation_target = random.choice((None, master_login, player_login, anonymous_login))
            requested_impersonation_writability = random.choice((True, False, None))
            res = self.dm.authenticate_with_session_data(session_ticket.copy(), # COPY
                                                   requested_impersonation_target=requested_impersonation_target,
                                                   requested_impersonation_writability=requested_impersonation_writability,
                                                   django_user=django_user)
            assert res == {u'game_username': None, # left as None!
                           u'impersonation_target': requested_impersonation_target, # no saving of fallback impersonation into session
                           u'impersonation_writability': requested_impersonation_writability,
                           u'game_instance_id': TEST_GAME_INSTANCE_ID}
            assert self.dm.user.username == requested_impersonation_target if requested_impersonation_target else anonymous_login # AUTO FALLBACK

            _expected_writability = True if not requested_impersonation_target else bool(requested_impersonation_writability)
            assert self.dm.user.has_write_access == _expected_writability
            assert self.dm.user.is_superuser
            assert self.dm.should_display_admin_tips()
            assert self.dm.user.is_impersonation == bool(requested_impersonation_target)
            assert self.dm.user.impersonation_target == requested_impersonation_target
            assert self.dm.user.impersonation_writability == bool(requested_impersonation_writability)
            assert self.dm.user.real_username == anonymous_login # LEFT ANONYMOUS, superuser status does it all
            assert not self.dm.user.has_notifications()
            self.dm.user.discard_notifications()

            # SUPERUSER CASE
            expected_capabilities = dict(display_impersonation_target_shortcut=True,
                                         display_impersonation_writability_shortcut=True,
                                        impersonation_targets=self.dm.get_available_logins(),
                                        has_writability_control=True,
                                        current_impersonation_target=requested_impersonation_target,
                                        current_impersonation_writability=bool(requested_impersonation_writability))
            assert self.dm.get_current_user_impersonation_capabilities() == expected_capabilities




    @for_core_module(PlayerAuthentication)
    def test_impersonation_by_master(self):

        # FIXME - test for django super user, for friendship................

        self._reset_django_db()

        master_login = self.dm.get_global_parameter("master_login")
        master_password = self.dm.get_global_parameter("master_password")
        player_login = "guy1"
        player_password = "elixir"
        player_login_bis = "guy2"
        anonymous_login = self.dm.get_global_parameter("anonymous_login")

        if random.choice((True, False)):
            # django superuser has no effect on authentications, as long as a game user is provided
            now = timezone.now()
            django_user = User(username='fakename', email='my@email.fr',
                              is_staff=True, is_active=True, is_superuser=True,
                              last_login=now, date_joined=now)
        else:
            django_user = None

        # build complete request


        # Impersonation control with can_impersonate() - THAT TEST COULD BE MOVED SOMEWHERE ELSE
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


        # Impersonation cases #

        self.dm.user.discard_notifications()

        request = self.request
        try_authenticating_with_credentials(request, master_login, master_password)
        base_session_ticket = request.session[SESSION_TICKET_KEY]
        assert base_session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                                       'impersonation_writability': None, 'game_username': master_login}
        assert self.dm.user.username == master_login
        assert self.dm.user.has_write_access
        assert not self.dm.user.is_superuser # reserved to staff django users
        assert not self.dm.user.is_impersonation
        assert not self.dm.user.impersonation_target
        assert not self.dm.user.impersonation_writability
        assert self.dm.user.real_username == master_login
        assert not self.dm.user.has_notifications()


        # Impersonate player
        for writability in (None, True, False):

            session_ticket = base_session_ticket.copy()

            res = self.dm.authenticate_with_session_data(session_ticket,
                                                   requested_impersonation_target=player_login,
                                                   requested_impersonation_writability=writability,
                                                   django_user=django_user)
            assert res is session_ticket
            assert session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': player_login,
                                      'impersonation_writability': writability, 'game_username': master_login}

            assert self.dm.user.username == player_login
            assert self.dm.user.has_write_access == bool(writability) # no write access by default, if requested_impersonation_writability is None
            assert not self.dm.user.is_superuser
            assert self.dm.user.is_impersonation
            assert self.dm.user.impersonation_target == player_login
            assert self.dm.user.impersonation_writability == bool(writability)
            assert self.dm.user.real_username == master_login
            assert self.dm.should_display_admin_tips()
            assert not self.dm.user.has_notifications()

            # Impersonated player renewed just with ticket
            self._set_user(None)
            assert self.dm.user.username == anonymous_login
            self.dm.authenticate_with_session_data(session_ticket,
                                             requested_impersonation_target=None,
                                             requested_impersonation_writability=None,
                                             django_user=django_user)
            assert session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': player_login,
                                      'impersonation_writability': writability, 'game_username': master_login}

            assert self.dm.user.username == player_login
            assert not self.dm.user.has_notifications()

            # Unexisting impersonation target leads to bad exception (should never happen)
            with pytest.raises(AbnormalUsageError):
                self.dm.authenticate_with_session_data(session_ticket,
                                                 requested_impersonation_target="dsfsdfkjsqodsd",
                                                 requested_impersonation_writability=not writability,
                                                 django_user=django_user)
            # untouched - upper layers must reset that ticket in session
            assert session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': player_login,
                                      'impersonation_writability': writability, 'game_username': master_login}



            # Impersonate anonymous
            self.dm.authenticate_with_session_data(session_ticket,
                                             requested_impersonation_target=anonymous_login,
                                             requested_impersonation_writability=writability,
                                             django_user=django_user)
            assert session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': anonymous_login,
                                      'impersonation_writability': writability, 'game_username': master_login}

            assert self.dm.user.username == anonymous_login
            assert self.dm.user.has_write_access == bool(writability)
            assert not self.dm.user.is_superuser
            assert self.dm.user.is_impersonation
            assert self.dm.user.impersonation_target == anonymous_login
            assert self.dm.user.impersonation_writability == bool(writability)
            assert self.dm.user.real_username == master_login
            assert self.dm.should_display_admin_tips()
            assert not self.dm.user.has_notifications()

            # MASTER CASE
            expected_capabilities = dict(display_impersonation_target_shortcut=True,
                                         display_impersonation_writability_shortcut=True,
                                         impersonation_targets=[self.dm.anonymous_login] + self.dm.get_character_usernames(),
                                         has_writability_control=True,
                                         current_impersonation_target=anonymous_login,
                                         current_impersonation_writability=bool(writability))
            assert self.dm.get_current_user_impersonation_capabilities() == expected_capabilities


            assert self.dm.user.real_username == master_login

            # By "impersonating current game user", we actually just stop impersonation
            self.dm.authenticate_with_session_data(session_ticket,
                                             requested_impersonation_target=master_login,
                                             requested_impersonation_writability=writability,
                                             django_user=None) # no django staff user here
            assert session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID,
                                      'impersonation_target': None,
                                      'impersonation_writability': writability,  # NOT RESET
                                      'game_username': master_login}
            assert self.dm.user.username == master_login
            assert self.dm.user.has_write_access # always if not impersonation
            assert not self.dm.user.is_superuser
            assert not self.dm.user.is_impersonation
            assert not self.dm.user.impersonation_target
            assert self.dm.user.impersonation_writability == bool(writability)
            assert self.dm.user.real_username == master_login
            assert self.dm.should_display_admin_tips()
            assert not self.dm.user.has_notifications()  # no errors, it's a standard case when using "usernames in URLs"
            self.dm.user.discard_notifications()


            # Back as anonymous
            self.dm.authenticate_with_session_data(session_ticket,
                                                     requested_impersonation_target=anonymous_login,
                                                     requested_impersonation_writability=writability,
                                                     django_user=django_user)
            assert session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': anonymous_login,
                                      'impersonation_writability': writability if writability is not None else None,  # if None, we remember previous value
                                      'game_username': master_login}

            assert self.dm.user.username == anonymous_login
            assert self.dm.user.has_write_access == bool(writability)
            assert not self.dm.user.is_superuser
            assert self.dm.user.is_impersonation
            assert self.dm.user.impersonation_target == anonymous_login
            assert self.dm.user.impersonation_writability == bool(writability)
            assert self.dm.user.real_username == master_login
            assert self.dm.should_display_admin_tips()
            assert not self.dm.user.has_notifications()


            # Standard stopping of impersonation
            self.dm.authenticate_with_session_data(session_ticket,
                                             requested_impersonation_target="",
                                             requested_impersonation_writability=writability,
                                             django_user=django_user)
            assert session_ticket == {'game_instance_id': TEST_GAME_INSTANCE_ID,
                                      'impersonation_target': None,
                                      'impersonation_writability': writability, # NOT RESET
                                      'game_username': master_login}

            assert self.dm.user.username == master_login
            assert self.dm.user.has_write_access # always
            assert not self.dm.user.is_superuser
            assert not self.dm.user.is_impersonation
            assert not self.dm.user.impersonation_target
            assert self.dm.user.impersonation_writability == bool(writability) # NOT RESET
            assert self.dm.user.real_username == master_login
            assert self.dm.should_display_admin_tips()
            assert not self.dm.user.has_notifications() # IMPORTANT - no error message


    @for_core_module(PlayerAuthentication)
    def test_impersonation_by_character(self):

        django_user = None
        if random.choice((True, False)):
            now = timezone.now()
            django_user = User(username='fakename', email='my@email.fr',
                          is_staff=random.choice((True, False)), is_active=random.choice((True, False)),
                          is_superuser=random.choice((True, False)), last_login=now, date_joined=now)

        player_name = "guy1"
        other_player = "guy2"
        session_ticket = {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                            'impersonation_writability': None, 'game_username': player_name}

        if random.choice((True, False)):
            if random.choice((True, False)):
                self.dm.propose_friendship(player_name, other_player)
            else:
                self.dm.propose_friendship(other_player, player_name)

        self.dm.authenticate_with_session_data(session_ticket,
                                                 requested_impersonation_target=other_player,
                                                 requested_impersonation_writability=random.choice((True, False)),
                                                 django_user=django_user)
        session_ticket = {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                            'impersonation_writability': None, 'game_username': player_name} # writability change rejected as well
        assert self.dm.username == player_name # no impersonation, even if friendship proposals
        assert self.dm.user.has_write_access
        assert not self.dm.user.is_superuser
        assert not self.dm.user.is_impersonation
        assert not self.dm.user.impersonation_target
        assert not self.dm.user.impersonation_writability
        assert self.dm.user.real_username == player_name
        assert not self.dm.should_display_admin_tips()

        expected_capabilities = dict(display_impersonation_target_shortcut=False,
                                     display_impersonation_writability_shortcut=False,
                                    impersonation_targets=[], # needs frienships
                                    has_writability_control=False,
                                    current_impersonation_target=None,
                                    current_impersonation_writability=False)
        assert self.dm.get_current_user_impersonation_capabilities() == expected_capabilities



        # we finish the friendship
        try:
            self.dm.propose_friendship(player_name, other_player)
        except UsageError:
            pass
        try:
            self.dm.propose_friendship(other_player, player_name)
        except UsageError:
            pass
        assert self.dm.are_friends(player_name, other_player)

        self.dm.authenticate_with_session_data(session_ticket,
                                                 requested_impersonation_target=other_player,
                                                 requested_impersonation_writability=random.choice((True, False)),
                                                 django_user=django_user)
        session_ticket = {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                            'impersonation_writability': None, 'game_username': player_name} # writability change rejected in ANY CASE
        assert self.dm.username == other_player # no impersonation, even if friendship proposals
        assert not self.dm.user.has_write_access
        assert not self.dm.user.is_superuser
        assert self.dm.user.is_impersonation
        assert self.dm.user.impersonation_target == other_player
        assert not self.dm.user.impersonation_writability
        assert self.dm.user.real_username == player_name # well kept
        assert not self.dm.should_display_admin_tips()

        expected_capabilities = dict(display_impersonation_target_shortcut=True, # NOW we display shortcut
                                     display_impersonation_writability_shortcut=False, # NEVER
                                    impersonation_targets=[other_player],
                                    has_writability_control=False,
                                    current_impersonation_target=other_player,
                                    current_impersonation_writability=False)
        assert self.dm.get_current_user_impersonation_capabilities() == expected_capabilities



    @for_core_module(PlayerAuthentication)
    def test_impersonation_by_anonymous(self):

        if random.choice((True, False)):
            now = timezone.now()
            is_superuser = True
            django_user = User(username='fakename', email='my@email.fr',
                              is_staff=True, is_active=True, is_superuser=is_superuser,
                              last_login=now, date_joined=now)
        else:
            is_superuser = False
            django_user = None


        player_login = "guy1"
        anonymous_login = self.dm.get_global_parameter("anonymous_login")


        # ensure that empty "game_username" in session is not a problem when resetting impersonation
        is_observer = random.choice((True, False))
        _special_session_ticket = {'game_instance_id': TEST_GAME_INSTANCE_ID,
                                 'impersonation_target': random.choice((player_login, anonymous_login, None)),
                                 'is_superuser': False,
                                 'impersonation_writability': None,
                                 'game_username': None,  # ANONYMOUS
                                 'is_observer': is_observer}

        writability = random.choice((True, False, None))
        self.dm.authenticate_with_session_data(_special_session_ticket,
                                             requested_impersonation_target="",  # THIS sometimes crashed
                                             requested_impersonation_writability=writability,
                                             django_user=django_user)
        assert not _special_session_ticket["impersonation_target"]
        assert _special_session_ticket["impersonation_writability"] == (writability if (is_superuser and not is_observer) else None)  # reset IFF non-privileged user
        assert not self.dm.user.has_notifications()


        # ensure that the side-effect "anonymous impersonating anonymous" is well dealt with
        _special_session_ticket = {'game_instance_id': TEST_GAME_INSTANCE_ID,
                                 'impersonation_target': random.choice((player_login, anonymous_login, None)),
                                 'is_superuser': False,
                                 'impersonation_writability': random.choice((True, False, None)),
                                 'game_username': None,  # ANONYMOUS
                                 'is_observer': random.choice((True, False))}
        self.dm.authenticate_with_session_data(_special_session_ticket,
                                             requested_impersonation_target=anonymous_login,  # THIS crashed before
                                             requested_impersonation_writability=random.choice((True, False, None)),
                                             django_user=django_user)
        if django_user:
            assert django_user.is_superuser
            assert _special_session_ticket["impersonation_target"] == anonymous_login
            # then "impersonation_writability" might be ANYTHING here
        else:
            assert not _special_session_ticket["impersonation_target"]
            assert not _special_session_ticket["impersonation_writability"]


    @for_core_module(PlayerAuthentication)
    def test_master_credentials_reset(self):

        self.dm.authenticate_with_credentials("master", "ultimate")
        self._set_user(None)
        assert not self.dm.user.is_master

        self.dm.override_master_credentials(master_password=None, master_real_email=None)

        master_real_email = random.choice(("abc@mail.com", None))
        self.dm.override_master_credentials(master_password="mypsgh", master_real_email=master_real_email)

        with pytest.raises(UsageError): # "unrecognized character name" error
            self.dm.authenticate_with_credentials("master", "ultimate")

        assert not self.dm.user.is_master

        self.dm.authenticate_with_credentials("MaSter", "mypsgh")  # it works

        assert self.dm.user.is_master

        assert self.dm.get_global_parameter("master_real_email") == master_real_email


    @for_core_module(PlayerAuthentication)
    def test_players_passwords_randomization(self):

        old_master_pwd = self.dm.get_global_parameter("master_password")

        assert self.dm.get_character_properties("my_npc")["is_npc"]
        old_npc_password = self.dm.get_character_properties("my_npc")["password"]
        assert old_npc_password

        assert not self.dm.get_character_properties("guy4")["is_npc"]
        old_empty_password = self.dm.get_character_properties("guy4")["password"]
        assert not old_empty_password

        for data in self.dm.get_character_sets().values():
            assert data["password"] not in config.PASSWORDS_POOL # initial passwords come from yaml fixtures

        self.dm.randomize_passwords_for_players() # RANDOMIZE

        assert self.dm.get_global_parameter("master_password") == old_master_pwd # untouched

        for username, data in self.dm.get_character_sets().items():
            if username not in ("guy4", "my_npc"):
                assert data["password"] in config.PASSWORDS_POOL # well changed
        assert self.dm.get_character_properties("my_npc")["password"] == old_npc_password
        assert self.dm.get_character_properties("guy4")["password"] == old_empty_password



    @for_core_module(PlayerAuthentication)
    def test_password_operations(self):
        self._reset_messages()

        # "secret question" system

        with raises_with_content(NormalUsageError, "master"):
            self.dm.get_secret_question(self.dm.get_global_parameter("master_login"))
        with raises_with_content(NormalUsageError, "master"):
            self.dm.process_secret_answer_attempt(self.dm.get_global_parameter("master_login"), "FluFFy", "guy3@pangea.com")

        with raises_with_content(NormalUsageError, "invalid"):
            self.dm.get_secret_question("sdqqsd")
        with raises_with_content(NormalUsageError, "invalid"):
            self.dm.process_secret_answer_attempt("sdqqsd", "FluFFy", "guy3@pangea.com")

        with raises_with_content(NormalUsageError, "no secret question"):
            self.dm.get_secret_question("guy1")
        with raises_with_content(NormalUsageError, "no secret question"):
            self.dm.process_secret_answer_attempt("guy1", "FluFFy", "guy3@pangea.com")

        res = self.dm.get_secret_question("guY3")  # case-insensitive
        self.assertTrue("pet" in res)

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)
        res = self.dm.process_secret_answer_attempt("gUy3", "FluFFy", "guy3@pangea.com")  # case-insensitive
        self.assertEqual(res, "awesome2") # password

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertTrue("password" in msg["body"].lower())

        self.assertRaises(dm_module.UsageError, self.dm.process_secret_answer_attempt, "badusername", "badanswer", "guy3@sciences.com")
        self.assertRaises(dm_module.UsageError, self.dm.process_secret_answer_attempt, "guy3", "badanswer", "guy3@sciences.com")
        self.assertRaises(dm_module.UsageError, self.dm.process_secret_answer_attempt, "guy3", "MiLoU", "bademail@sciences.com")
        self.assertEqual(len(self.dm.get_all_queued_messages()), 1) # untouched


        # password change

        with pytest.raises(NormalUsageError):
            self.dm.process_password_change_attempt("guy1", "badpwd", "newpwd")
        with pytest.raises(AbnormalUsageError):
            self.dm.process_password_change_attempt("guy1", "badpwd", "new pwd") # wrong new pwd
        with pytest.raises(AbnormalUsageError):
            self.dm.process_password_change_attempt("guy1", "elixir", "newpwd\n") # wrong new pwd
        with pytest.raises(AbnormalUsageError):
            self.dm.process_password_change_attempt("guy1", "elixir", "") # wrong new pwd
        with pytest.raises(AbnormalUsageError):
            self.dm.process_password_change_attempt("guy1", "elixir", None) # wrong new pwd

        self.dm.process_password_change_attempt("guy1", "elixir", "newpwd")

        with pytest.raises(NormalUsageError):
            self.dm.process_password_change_attempt("guy1", "elixir", "newpwd")  # old-password not OK

        with pytest.raises(NormalUsageError):
            self.dm.authenticate_with_credentials("guy1", "elixir")

        self._set_user("guy3")
        assert self.dm.username == "guy3"

        self.dm.authenticate_with_credentials("GuY1", "newpwd")  # case-insensitive is OK
        assert self.dm.username == "guy1"

        assert self.dm.get_character_properties("guy4")["password"] is None
        with pytest.raises(AttributeError):
            self.dm.authenticate_with_credentials("guy4", None) # value can't be "stripped"
        with pytest.raises(NormalUsageError):
            self.dm.authenticate_with_credentials("guy4", "")



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
        token = self.dm.get_game_view_access_token(views.view_characters)
        assert token == AccessResult.authentication_required


        # test registry resync
        del self.dm.ACTIVABLE_VIEWS_REGISTRY[random_view] # class-level registry
        self.dm.sync_game_view_data()
        assert not self.dm.is_game_view_activated(random_view) # cleanup occurred
        assert self.dm.get_event_count("SYNC_GAME_VIEW_DATA_CALLED") == 1

        with temp_datamanager(TEST_GAME_INSTANCE_ID, self.request) as _dm2:
            assert _dm2.get_event_count("SYNC_GAME_VIEW_DATA_CALLED") == 1 # sync well called at init!!

        self.dm.ACTIVABLE_VIEWS_REGISTRY[random_view] = random_klass # test cleanup


        self._set_user("master")

        # test admin form tokens
        assert "admin_dashboard.choose_activated_views" in self.dm.get_admin_widget_identifiers()

        assert self.dm.resolve_admin_widget_identifier("") is None
        assert self.dm.resolve_admin_widget_identifier("qsdqsd") is None
        assert self.dm.resolve_admin_widget_identifier("qsdqsd.choose_activated_views") is None
        assert self.dm.resolve_admin_widget_identifier("admin_dashboard.") is None
        assert self.dm.resolve_admin_widget_identifier("admin_dashboard.qsdqsd") is None

        from pychronia_game.views import admin_dashboard
        components = self.dm.resolve_admin_widget_identifier("admin_dashboard.choose_activated_views")
        assert len(components) == 2
        assert isinstance(components[0], admin_dashboard.klass)
        assert components[1] == "choose_activated_views"


        # test HTML admin summaries of each view
        res = self.dm.get_game_view_admin_summaries()
        assert isinstance(res, dict) and res, res
        for k, v in res.items():
            assert isinstance(v["title"], Promise) and len(v["title"])
            assert "<p>" in v["html_chunk"] or "dd" in v["html_chunk"]



    @for_core_module(SpecialAbilities)
    def test_special_abilities_registry(self):

        abilities = self.dm.get_abilities()
        assert abilities is not self.dm.ABILITIES_REGISTRY # copy
        assert "runic_translation" in abilities

        @register_view
        class PrivateTestAbility(AbstractAbility):

            TITLE = ugettext_lazy("Private dummy ability")
            NAME = "_private_dummy_ability"
            GAME_ACTIONS = {}
            TEMPLATE = "base_main.html" # must exist
            ACCESS = UserAccess.anonymous
            REQUIRES_CHARACTER_PERMISSION = False
            REQUIRES_GLOBAL_PERMISSION = True


            def get_template_vars(self, previous_form_data=None):
                return {'page_title': "hello", }

            @classmethod
            def _setup_ability_settings(cls, settings):
                settings.setdefault("myvalue", "True")
                cls._LATE_ABILITY_SETUP_DONE = 65

            def _setup_private_ability_data(self, private_data):
                pass

            def _check_data_sanity(self, strict=False):
                settings = self.settings
                assert settings["myvalue"] == "True"


        assert "_private_dummy_ability" in self.dm.get_abilities() # auto-registration of dummy test ability
        self.dm.rollback()
        with pytest.raises(KeyError):
            self.dm.get_ability_data("_private_dummy_ability") # ability not yet setup in ZODB


        with temp_datamanager(TEST_GAME_INSTANCE_ID, self.request) as _dm:
            assert "_private_dummy_ability" in _dm.get_abilities()
            with pytest.raises(KeyError):
                assert _dm.get_ability_data("_private_dummy_ability") # no hotplug synchronization for abilities ATM
            assert not hasattr(PrivateTestAbility, "_LATE_ABILITY_SETUP_DONE")

        del GameDataManager.ABILITIES_REGISTRY["_private_dummy_ability"] # important cleanup!!!
        del GameDataManager.GAME_VIEWS_REGISTRY["_private_dummy_ability"] # important cleanup!!!



    @for_core_module(StaticPages)
    def test_static_pages(self):

        EXISTING_HELP_PAGE = "help-homepage"

        block = self.dm.get_categorized_static_page(category="content", name="help-view_encyclopedia")
        utilities.check_is_restructuredtext(block["content"])

        assert self.dm.get_categorized_static_page(category="content", name="qskiqsjdqsid") is None
        assert self.dm.get_categorized_static_page(category="badcategory", name="help-view_encyclopedia") is None

        assert EXISTING_HELP_PAGE in self.dm.get_static_page_names_for_category("content")

        assert "lokon" not in self.dm.get_static_page_names_for_category("content")
        assert "lokon" in self.dm.get_static_page_names_for_category("encyclopedia")

        assert sorted(self.dm.get_static_pages_for_category("content").keys()) == sorted(self.dm.get_static_page_names_for_category("content")) # same "random" sorting

        for key, value in self.dm.get_static_pages_for_category("content").items():
            assert "content" in value["categories"]
            utilities.check_is_slug(key)
            assert key.lower() == key

        self._set_user("guy1")
        assert not self.dm.has_user_accessed_static_page(EXISTING_HELP_PAGE)
        self.dm.mark_static_page_as_accessed(EXISTING_HELP_PAGE)
        assert self.dm.has_user_accessed_static_page(EXISTING_HELP_PAGE)
        self.dm.mark_static_page_as_accessed(EXISTING_HELP_PAGE)
        assert self.dm.has_user_accessed_static_page(EXISTING_HELP_PAGE)



        # mutability control #
        # NOTE that ALL static pages are currently modifiable and deletable #

        container = self.dm.static_pages

        mutable_entry = "top-homepage"

        new_id = "newid"  # create a new page
        new_item = utilities.safe_copy(container[mutable_entry])
        del new_item["initial"]
        container[new_id] = new_item
        self.dm.commit()

        assert mutable_entry in container.get_all_data()
        assert mutable_entry in container.get_all_data(mutability=True)

        assert not container.get_all_data(mutability=False)
        assert not container.get_undeletable_identifiers()



    @for_core_module(GameEvents)
    def test_event_logging(self):
        self._reset_messages()

        self._set_user("guy1")
        events = self.dm.get_game_events() # for guy1
        assert not events

        events = self.dm.get_game_events("master")
        self.assertEqual(len(events), 1) # fixture for master

        self.dm.log_game_event("hello there 1", visible_by=None)
        self._set_user("master")
        self.dm.log_game_event("hello there 2", url="/my/url/", visible_by=["guy1", "guy2"])
        self.dm.commit()

        events = self.dm.get_game_events("master")[1:] # skip fixture
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

        self._set_user("guy1")
        events = self.dm.get_game_events() # for guy1
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["message"], "hello there 2") # only one authorized

        self._set_user("guy4")
        events = self.dm.get_game_events() # for guy4
        self.assertEqual(len(events), 0)


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

        real_test_done = False

        for captcha in (random_captchas + [captcha1, captcha2]):
            assert set(captcha.keys()) == set("id text image".split()) # no spoiler of answer elements here
            assert self.dm.get_selected_captcha(captcha["id"]) == captcha
            with pytest.raises(NormalUsageError):
                self.dm.check_captcha_answer_attempt(captcha["id"], "")
            with pytest.raises(NormalUsageError):
                self.dm.check_captcha_answer_attempt(captcha["id"], "random stuff ")

            _full_captch_data = self.dm.data["nightmare_captchas"][captcha["id"]]
            if _full_captch_data["answer"] is None:
                continue

            answer = "  " + _full_captch_data["answer"].upper() + " " # case and spaces are not important
            res = self.dm.check_captcha_answer_attempt(captcha["id"], answer)
            assert res == _full_captch_data["explanation"] # success
            real_test_done = True

        assert real_test_done # we must test "normal" case too

        impossible_catcha = "enigma2"
        assert self.dm.data["nightmare_captchas"][impossible_catcha]["answer"] is None
        for answer_attempt in ("None", "whatever"):
            with pytest.raises(NormalUsageError):
                self.dm.check_captcha_answer_attempt(impossible_catcha, answer_attempt)
        with pytest.raises(AssertionError):
            self.dm.check_captcha_answer_attempt(impossible_catcha, None) # can't happen


    @for_core_module(NovaltyTracker)
    def test_novelty_tracker(self):

        assert self.dm.get_novelty_registry() == {}

        assert self.dm.access_novelty("guest", "qdq|sd") is None

        assert self.dm.access_novelty("master", "qdq|sd")
        assert self.dm.access_novelty("guy1", "qdq|sd")

        assert self.dm.access_novelty("guy1", "qsdffsdf")
        assert not self.dm.access_novelty("guy1", "qsdffsdf") # duplicate OK
        assert self.dm.access_novelty("guy3", "qsdffsdf")
        assert self.dm.access_novelty("guy2", "qsdffsdf")

        assert self.dm.access_novelty("guy4", "dllll", category="mycat")

        #print (self.dm.get_novelty_registry())

        assert self.dm.has_accessed_novelty("guest", "qdq|sd")
        assert self.dm.has_accessed_novelty("guest", "OAUIATAUATUY") # ALWAYS for anonymous, no novelty display

        assert self.dm.has_accessed_novelty("master", "qdq|sd")
        assert self.dm.has_accessed_novelty("guy1", "qdq|sd")
        assert self.dm.has_accessed_novelty("guy1", "qsdffsdf")
        assert not self.dm.has_accessed_novelty("guy1", "qsdffsdf", category="whatever_else")

        assert not self.dm.has_accessed_novelty("guy1", "sdfdfsdkksdfksdkf")
        assert not self.dm.has_accessed_novelty("guy1", "dllll", category="mycat")
        assert self.dm.has_accessed_novelty("guy4", "dllll", category="mycat")
        assert not self.dm.has_accessed_novelty("guy4", "dllll", category="myCat") # case sensitive category
        assert not self.dm.has_accessed_novelty("guy4", "dlllL", category="mycat") # case sensitive key

        # this method's input is not checked by coherence routines, so let's ensure it's protected...
        with pytest.raises(AssertionError):
            self.dm.has_accessed_novelty("badusername", "qsdffsdf")
        with pytest.raises(AssertionError):
            self.dm.has_accessed_novelty("guy1", "qsdf fsdf")

        #print (self.dm.get_novelty_registry())

        assert self.dm.get_novelty_registry() == {("default", u'qsdffsdf'): [u'guy1', u'guy3', u'guy2'], # NO guest (anonymous) HERE (ignored)
                                                  ("default", u'qdq|sd'): [u'master', u'guy1'],
                                                  ("mycat", u'dllll'): [u'guy4']}

        self.dm.reset_novelty_accesses('qdq|sd')
        self.dm.reset_novelty_accesses('unexistingname') # ignored

        assert self.dm.get_novelty_registry() == {("default", u'qsdffsdf'): [u'guy1', u'guy3', u'guy2'],
                                                  ("mycat", u'dllll'): [u'guy4']}
        assert not self.dm.has_accessed_novelty("guy1", 'qdq|sd')
        assert self.dm.has_accessed_novelty("guy1", 'qsdffsdf')



    @for_core_module(NoveltyNotifications)
    def test_novelty_notifications(self):

        assert not self.dm.get_global_parameter("disable_real_email_notifications")

        res = self.dm.get_characters_external_notifications()
        assert res == [{'username': 'guy1', 'real_email': 'dummy@hotmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': False},
                       {'username': 'guy2', 'real_email': 'shalk@gmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': False},
                       {'username': 'my_npc', 'real_email': 'xcvxcv@gmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': False}]

        assert self.dm.get_single_character_external_notifications("guy1") == {'signal_new_radio_messages': False, 'signal_new_text_messages': False}
        assert self.dm.get_single_character_external_notifications("guy2") == {'signal_new_radio_messages': False, 'signal_new_text_messages': False}

        audio_id = self.dm.get_character_properties("guy2")["new_messages_notification"]
        self.dm.add_radio_message(audio_id)

        assert self.dm.get_single_character_external_notifications("guy1") == {'signal_new_radio_messages': True, 'signal_new_text_messages': False}
        assert self.dm.get_single_character_external_notifications("guy2") == {'signal_new_radio_messages': True, 'signal_new_text_messages': False}

        for i in range(3):
            self.dm.post_message("guy1@pangea.com", "guy2@pangea.com", "yowh1", "qhsdhqsdh")

        assert self.dm.get_single_character_external_notifications("guy1") == {'signal_new_radio_messages': True, 'signal_new_text_messages': False} # sender NOT notified
        assert self.dm.get_single_character_external_notifications("guy2") == {'signal_new_radio_messages': True, 'signal_new_text_messages': 3}

        res = self.dm.get_characters_external_notifications()
        #print(res)
        assert res == [{'username': 'guy1', 'real_email': 'dummy@hotmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': True},
                       {'username': 'guy2', 'real_email': 'shalk@gmail.com', u'signal_new_text_messages': 3, u'signal_new_radio_messages': True},
                       {'username': 'my_npc', 'real_email': 'xcvxcv@gmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': True}]
        self.dm.reset_audio_messages()

        assert self.dm.get_single_character_external_notifications("guy1") == {'signal_new_radio_messages': False, 'signal_new_text_messages': False} # sender NOT notified
        assert self.dm.get_single_character_external_notifications("guy2") == {'signal_new_radio_messages': False, 'signal_new_text_messages': 3}

        self.dm.set_new_message_notification(["guy2"], increment=0)

        assert self.dm.get_single_character_external_notifications("guy1") == {'signal_new_radio_messages': False, 'signal_new_text_messages': False}
        assert self.dm.get_single_character_external_notifications("guy2") == {'signal_new_radio_messages': False, 'signal_new_text_messages': False}

        res = old_res = self.dm.get_characters_external_notifications()
        #print(res)
        assert res == [{'username': 'guy1', 'real_email': 'dummy@hotmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': False},
                       {'username': 'guy2', 'real_email': 'shalk@gmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': False},
                       {'username': 'my_npc', 'real_email': 'xcvxcv@gmail.com', u'signal_new_text_messages': False, u'signal_new_radio_messages': False}]

        self.dm.set_global_parameter("disable_real_email_notifications", True)
        assert self.dm.get_global_parameter("disable_real_email_notifications")

        res = self.dm.get_characters_external_notifications()
        assert res == [] # completely disabled

        self.dm.set_global_parameter("disable_real_email_notifications", False)
        assert not self.dm.get_global_parameter("disable_real_email_notifications")

        res = self.dm.get_characters_external_notifications()
        assert res == old_res


class TestHttpRequests(BaseGameTestCase):

    def _master_auth(self):

        master_login = self.dm.get_global_parameter("master_login")
        login_page = neutral_url_reverse("pychronia_game.views.login")
        response = self.client.get(login_page) # to set preliminary cookies
        self.assertEqual(response.status_code, 200)

        response = self.client.post(login_page, data=dict(secret_username=master_login, secret_password=self.dm.get_global_parameter("master_password")))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, ROOT_GAME_URL + "/master/")

        assert self.client.session[SESSION_TICKET_KEY] == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                                                                'impersonation_writability': None, 'game_username': master_login}

        self.assertTrue(self.client.cookies["sessionid"])


    def _player_auth(self, username):

        login_page = neutral_url_reverse("pychronia_game.views.login")
        response = self.client.get(login_page) # to set preliminary cookies
        self.assertEqual(response.status_code, 200)

        response = self.client.post(login_page, data=dict(secret_username=username, secret_password=self.dm.get_character_properties(username)["password"]))

        #html = response.content.decode("utf8")
        #print("-------------->", html)

        # if HTTP 200 is received here (with error notifications), note that users like guy4 are DISABLED!
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, ROOT_GAME_URL + "/" + username + "/")

        assert self.client.session[SESSION_TICKET_KEY] == {'game_instance_id': TEST_GAME_INSTANCE_ID, 'impersonation_target': None,
                                                                'impersonation_writability': None, 'game_username': username}
        self.assertTrue(self.client.cookies["sessionid"])


    def _logout(self):

        login_page = neutral_url_reverse("pychronia_game.views.login", game_username="guest")
        logout_page = neutral_url_reverse("pychronia_game.views.logout")
        response = self.client.get(logout_page, follow=False)

        self.assertEqual(response.status_code, 302)
        #print("LOGOUT SESSION -> ", self.client.session.items())
        assert not self.client.session.has_key(SESSION_TICKET_KEY)  # if this fails, maybe use was not authenticated (thus logout fails)

        self.assertRedirects(response, login_page)  # beware - LOADS TARGET LOGIN PAGE, so MODIFIES session!

        assert self.client.session.has_key("testcookie")  # we get it once more thanks to the assertRedirects() above
        assert self.client.session.has_key(SESSION_TICKET_KEY)


    def _test_special_pages(self):
        self._reset_django_db()

        self.dm.data["global_parameters"]["online_presence_timeout_s"] = 1
        self.dm.data["global_parameters"]["chatroom_presence_timeout_s"] = 1
        self.dm.commit()
        time.sleep(1.2) # online/chatting users list gets emptied

        self._master_auth() # equivalent to self._set_user(self.dm.get_global_parameter("master_login"))

        initial_msg_id = "instructions_bewitcher"
        msg_id = self.dm._obfuscate_initial_id(initial_msg_id)
        assert msg_id != initial_msg_id
        assert len(msg_id) == len(initial_msg_id) # simple translation

        root_game_url_with_username = ROOT_GAME_URL + "/" + self.dm.master_login

        # these urls and their post data might easily change, beware !
        special_urls = {
                        root_game_url_with_username + "/item3dview/sacred_chest/": None,
                        neutral_url_reverse(views.view_static_page, page_id="lokon"): None,
                        # FIXME NOT YET READYROOT_GAME_URL + "/djinn/": {"djinn": "Pay Rhuss"},
                        ##### FIXME LATER config.MEDIA_URL + "Burned/default_styles.css": None,
                        game_file_url("images/attachments/image1.png"): None,
                        game_file_url("encrypted/guy2_report/evans/orb.jpg"): None,
                        root_game_url_with_username + "/bug_report/": None,
                        root_game_url_with_username + "/bug_report/": dict(location="http://mondomaine", report_data="ceci est un message"),
                        root_game_url_with_username + "/messages/view_single_message/%s/" % msg_id: None,
                        root_game_url_with_username + "/messages/view_single_message/UNEXISTING_MSG/": None,
                        root_game_url_with_username + "/messages/view_single_message/%s/?popup=1" % msg_id: None,
                        root_game_url_with_username + "/messages/view_single_message/UNEXISTING_MSG/?popup=1": None,
                        root_game_url_with_username + "/secret_question/guy3/": dict(secret_answer="Fluffy", target_email="guy3@pangea.com"),
                        root_game_url_with_username + "/public_webradio/": dict(frequency=self.dm.get_global_parameter("pangea_radio_frequency")),
                        neutral_url_reverse(views.view_help_page, keyword="help-homepage"): None,
                        root_game_url_with_username + "/view_media/?autostart=true&url=%2Ffiles%2Fe65701d5%2Fpersonal_files%2F_common_files_%2Fgraphs.gif": None,
                        }

        for url, value in special_urls.items():
            # print ">>>>>>", url

            if value:
                response = self.client.post(url, data=value)
            else:
                response = self.client.get(url)

            ##print ("WE TRY TO LOAD ", url, response.__dict__)
            try:
                msg_prefix = response.content[0:300].decode("utf8")
            except UnicodeError:
                pass # must be a binary file
            else:
                self.assertNotContains(response, 'class="error_notifications"', msg_prefix=msg_prefix)
            self.assertEqual(response.status_code, 200, url + " | " + str(response.status_code))


        # no directory index, especially because of hash-protected file serving
        response = self.client.get("/files/") # because ValueError: Unexisting instance u'files'
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


    def test_game_started_special_pages(self):
        self.dm.set_game_state(True)
        self._test_special_pages()

    def test_game_paused_special_pages(self):
        self.dm.set_game_state(False)
        self._test_special_pages()




    UNGETTABLE_SPECIAL_VIEWS = ("""CHARACTERS_IDENTITIES DATABASE_OPERATIONS FAIL_TEST MEDIA_TEST  logout ___instructions ___logo_animation ___opening
                        """.split() + # BROKEN VIEWS
                     ["view_single_message", "item_3d_view", "encrypted_folder", "view_help_page", "secret_question", "view_static_page", ])  # NEEDS PARAMETERS


    def _test_all_views_http_get(self):

        skipped_views_lowercase = [n.lower() for n in self.UNGETTABLE_SPECIAL_VIEWS]

        def test_views(view_classes):
            results = []
            for view_class in view_classes:
                name = view_class.NAME.lower()
                if name in skipped_views_lowercase or "ajax" in name or "dummy" in name:
                    results.append(0)
                    continue
                url = neutral_url_reverse(view_class.as_view)
                response = self.client.get(url)
                # print response.content
                self.assertEqual(response.status_code, 200, name + " | " + url + " | " + str(response.status_code))
                results.append(1)
            return results

        self._reset_django_db()

        # we activate ALL views
        old_state = self.dm.is_game_started()
        self.dm.set_game_state(True)
        activable_views = self.dm.ACTIVABLE_VIEWS_REGISTRY.keys()
        self.dm.set_activated_game_views(activable_views)
        # we give guy1 access to everything
        self.dm.update_permissions("guy1", PersistentList(self.dm.PERMISSIONS_REGISTRY))
        self.dm.set_game_state(old_state)

        all_views = self.dm.get_game_views().values() # these are actually view CLASSES

        master_views = [v for v in all_views if v.ACCESS == UserAccess.master]
        authenticated_views = [v for v in all_views if v.ACCESS == UserAccess.authenticated]
        character_views = [v for v in all_views if v.ACCESS == UserAccess.character]
        anonymous_views = [v for v in all_views if v.ACCESS == UserAccess.anonymous]

        assert len(all_views) == len(master_views) + len(authenticated_views) + len(character_views) + len(anonymous_views)

        self._master_auth()

        res = test_views(view_classes=master_views)
        assert sum(res) > 7

        if random.choice((True, False)):
            self._player_auth("guy1") # either master or guy1

        res = test_views(view_classes=authenticated_views)
        assert sum(res) > 7

        self._player_auth("guy1") # has all permissions

        res = test_views(view_classes=character_views)
        assert sum(res) > 7

        if random.choice((True, False)):
            if random.choice((True, False)):
                self._master_auth()
            else:
                self._logout()

        res = test_views(view_classes=anonymous_views)
        assert sum(res) > 7


    def test_game_started_all_get_pages(self):
        self.dm.set_game_state(True)
        self._test_all_views_http_get()

    def test_game_paused_all_get_pages(self):
        self.dm.set_game_state(False)
        self._test_all_views_http_get()



    def _test_player_multistate_get_requests(self):

        # FIXME - currently not testing abilities

        self._reset_django_db()

        self.dm.data["global_parameters"]["online_presence_timeout_s"] = 1
        self.dm.data["global_parameters"]["chatroom_presence_timeout_s"] = 1
        self.dm.commit()
        time.sleep(1.2) # online/chatting users list gets emptied

        old_state = self.dm.is_game_started()

        self.dm.set_game_state(True)
        self._set_user(None)


        # PLAYER SETUP
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
        from pychronia_game.urls import inner_game_urlpatterns
        # we test some views for which there is a distinction between master and player
        selected_patterns = """ compose_message view_sales personal_items_slideshow character_profile friendship_management""".split()
        views = [url._callback_str for url in inner_game_urlpatterns if not isinstance(url, RegexURLResolver) and [match for match in selected_patterns if match in url._callback_str]]
        assert len(views) == len(selected_patterns)

        def test_views(views):
            for view in views:
                url = neutral_url_reverse(view)
                response = self.client.get(url)
                # print response.content
                self.assertEqual(response.status_code, 200, view + " | " + url + " | " + str(response.status_code))

        test_views(views)

        self.dm.set_game_state(True)
        self.dm.transfer_money_between_characters(self.dm.get_global_parameter("bank_name"), username, 1000)
        self.dm.set_game_state(old_state)

        test_views(views)

        self.dm.set_game_state(True)
        gem_name = [key for key, value in self.dm.get_all_items().items() if value["is_gem"] and value["num_items"] >= 6][0] # we only take numerous groups
        self.dm.transfer_object_to_character(gem_name, username)
        self.dm.set_game_state(old_state)

        test_views(views)

        self.assertEqual(self.dm.get_online_users(), [username] if old_state else []) # in paused game, even online users are not updated
        self.assertEqual(self.dm.get_chatting_users(), [])

        self._logout()


    def test_player_game_started_multistate_pages(self):
        self.dm.set_game_state(True)
        self._test_player_multistate_get_requests()

    def test_player_game_paused_multistate_pages(self):
        self.dm.set_game_state(False)
        self._test_player_multistate_get_requests()


    def test_specific_help_pages_behaviour(self):

        self._reset_django_db()
        self.dm.set_game_state(True)

        # TODO FIXME - use Http403 exceptions instead, when new django version is out !!

        url = neutral_url_reverse(views.view_help_page, keyword="")
        response = self.client.get(url)
        assert response.status_code == 404

        url = neutral_url_reverse(views.view_help_page, keyword="qsd8778GAVVV")
        response = self.client.get(url)
        assert response.status_code == 404

        url = neutral_url_reverse(views.view_help_page, keyword="help-homepage")
        response = self.client.get(url)
        assert response.status_code == 200

        assert self.dm.get_categorized_static_page(self.dm.HELP_CATEGORY, "help-runic_translation")
        url = neutral_url_reverse(views.view_help_page, keyword="help-runic_translation")
        response = self.client.get(url)
        assert response.status_code == 404 # ACCESS FORBIDDEN

        url = neutral_url_reverse(views.view_help_page, keyword="help-chatroom")
        response = self.client.get(url)
        assert response.status_code == 404 # view always available, but no help text available for it


    def test_encyclopedia_index_knowledge(self):

        ok = 0

        self._reset_django_db()

        url_base = neutral_url_reverse(views.view_encyclopedia)

        for login in ("master", "guy1", None):

            game_state = random.choice((True, False))
            self.dm.set_game_state(game_state)

            self._set_user(login) # auth for local DM
            if login == "guy1":
                self._player_auth(login)
            elif login == "master":
                self._master_auth()
            else:
                self._logout()  # get back to GUEST

            response = self.client.get(url_base)
            assert response.status_code == 200

            url = neutral_url_reverse(views.view_encyclopedia, current_article_id="lokon")
            response = self.client.get(url)
            assert response.status_code == 200
            assert "animals" in response.content.decode("utf8")

            if login == "guy1":
                assert "gerbil_species" not in self.dm.get_character_known_article_ids()
                ok += 1

            response = self.client.get(url_base + "?search=badkeyword")
            assert response.status_code == 200
            # print(repr(response.content))
            assert "Please use the side controls" in response.content.decode("utf8") # homepage of encylopedia

            response = self.client.get(url_base + "?search=animal")
            assert response.status_code == 200
            # print(repr(response.content))
            assert "results" in response.content.decode("utf8") # several results displayed

            response = self.client.get(url_base + "?search=gerbil")
            assert response.status_code == 302
            assert game_view_url(views.view_encyclopedia,
                                 datamanager=self.dm,
                                 current_article_id="gerbil_species") in response['Location']

            if login == "guy1":
                assert ("gerbil_species" in self.dm.get_character_known_article_ids()) == game_state
                ok += 1

        assert ok == 2 # coherence of test method


    def test_usage_error_transformation(self):

        self._reset_django_db()

        # user is initially anonymous, we have a special redirection for access denials in this case
        response = self.client.get(neutral_url_reverse(views.view_sales, game_username="guest"))  # we target "anyuser" url
        expected_url = "http://testserver/TeStiNg/guest/login/?next=http%3A%2F%2Ftestserver%2FTeStiNg%2Fredirect%2Fview_sales%2F"
        self.assertRedirects(response, expected_url=expected_url)

        # we ensure that the "next" argument works fine through all redirections
        response = self.client.post(expected_url, data=dict(secret_username="guy1", secret_password=self.dm.get_character_properties("guy1")["password"]), follow=True)
        assert response.status_code == 200  # all went fine
        self.assertRedirects(response, expected_url="http://testserver/TeStiNg/guy1/view_sales/")  # redirection chain went up to there

        self._logout()

        #---

        self._player_auth("guy1")
        self.dm.set_permission("guy1", views.wiretapping_management.get_access_permission_name(), is_present=False)  # else, would override is_game_view_activated()!

        url_home = neutral_url_reverse("pychronia_game-homepage")  # for ANY game-username

        url = neutral_url_reverse(views.wiretapping_management)

        self.dm.set_activated_game_views([])  # for wiretapping, character permissions are the most important anyway
        assert not self.dm.is_game_view_activated("wiretapping")

        # AJAX ACCESS DENIED #
        response = self.client.post(url, data=dict(_action_="purchase_wiretapping_slot"), **AJAX_HEADERS)
        assert response.status_code == 403

        # HTML ACCESS DENIED #
        response = self.client.get(url)
        self.assertRedirects(response, expected_url=neutral_url_reverse("pychronia_game-homepage", game_username="guy1"))  # HOME of guy1!

        # ACCESS OK, in ajax or not #
        self.dm.set_permission("guy1", views.wiretapping_management.get_access_permission_name(), is_present=True)
        response = self.client.get(url)
        assert response.status_code == 200
        response = self.client.post(url, data=dict(_action_="purchase_wiretapping_slot"), **AJAX_HEADERS)
        assert response.status_code == 200


        self.dm.set_activated_game_views([])
        assert not self.dm.is_game_view_activated("wiretapping")
        self.dm.set_permission("guy1", views.wiretapping_management.get_access_permission_name(), is_present=False)

        # impersonate guy1 while being logged as master #
        self._master_auth()
        response = self.client.post(url_home, data={IMPERSONATION_TARGET_POST_VARIABLE: "guy1", IMPERSONATION_WRITABILITY_POST_VARIABLE: "true"})
        #print(response.content)
        assert "Guy1" in response.content.decode("utf8")
        assert response.status_code == 200


        # AJAX ACCESS DENIED #
        response = self.client.post(url, data=dict(_action_="purchase_wiretapping_slot"), **AJAX_HEADERS)
        #print("@@@@@@", response.content)
        assert response.status_code == 403 # still FORBIDDEN code

        # HTML ACCESS DENIED #
        response = self.client.get(url)
        self.assertRedirects(response, expected_url=neutral_url_reverse("pychronia_game-homepage", game_username="guy1"))


        # impersonate anonymous while being logged as master #
        response = self.client.post(url_home, data={IMPERSONATION_TARGET_POST_VARIABLE: "guest", IMPERSONATION_WRITABILITY_POST_VARIABLE: "false"})
        #print(response.content)
        assert "Guest" in response.content.decode("utf8")
        assert response.status_code == 200

        response = self.client.get(neutral_url_reverse(views.view_sales))
        # NOT redirected to login page, since it's an impersonation
        self.assertRedirects(response, expected_url=neutral_url_reverse("pychronia_game-homepage", game_username="guest"))


        self._player_auth("guy1")
        self.dm.set_permission("guy1", views.wiretapping_management.get_access_permission_name(), is_present=True)  # else, would override is_game_view_activated()!

        def _broken_func(*args, **kwargs):
            raise EXCEPTION("TESTINNNG")

        oldie = AbstractGameView._process_standard_request
        AbstractGameView._process_standard_request = _broken_func
        try:

            EXCEPTION = random.choice((AbnormalUsageError, POSError))

            response = self.client.post(url, data=dict(_action_="purchase_wiretapping_slot"), **AJAX_HEADERS)
            #print("@@@@@@", response.content)
            assert response.status_code == 400 # HttpResponseBadRequest

            response = self.client.get(url)
            self.assertRedirects(response, expected_url=neutral_url_reverse("pychronia_game-homepage", game_username="guy1")) # redirect with user error message


            EXCEPTION = random.choice((ValueError, RuntimeError))

            with pytest.raises(EXCEPTION): # would become http 500 error
                self.client.post(url, data=dict(_action_="purchase_wiretapping_slot"), **AJAX_HEADERS)

            with pytest.raises(EXCEPTION): # would become http 500 error
                response = self.client.get(url)

        finally:
            AbstractGameView._process_standard_request = oldie


    def test_message_composition(self):

        self._reset_django_db()

        self._player_auth("guy1")

        url = neutral_url_reverse(views.compose_message)

        params = dict(_ability_form="pychronia_game.views.messaging_views.MessageComposeForm",
                      body="Ceci est le body!",
                      delay_h=0,
                      recipients=["guy2@pangea.com", "guy3@pangea.com"],
                      sender="guy1@pangea.com",
                      subject="Sujet de test")

        response = self.client.post(url, data=params, follow=True)
        #print("@@@@@@", response.content)
        assert response.status_code == 200

        html = response.content.decode("utf8")

        assert "conversation" in html  # we got redirected
        assert "clear_saved_content();  // we do cleanup localstorage, since email was sent" in html


    def test_game_homepage_without_username(self):

        self._reset_django_db()
        url = ROOT_GAME_URL + "/"  # homepage without game username in it

        response = self.client.get(url, follow=False)
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guest/")  # this auto-checks the target URL for us!

        self._player_auth("guy1")

        response = self.client.get(url, follow=False)
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guy1/")

        self._master_auth()

        response = self.client.get(url, follow=False)
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/master/")


    def test_game_username_embedded_in_url(self):

        self._reset_django_db()

        self._player_auth("guy3")

        weird_url = reverse(views.login, kwargs=dict(game_instance_id="moN_in-stance.&moi", game_username="loyd.-george_s"))
        assert weird_url == "/moN_in-stance.%26moi/loyd.-george_s/login/"  # special characters well accepted

        response = self.client.get(ROOT_GAME_URL + "/anyuser/", follow=False)  # SPECIAL token
        assert response.status_code == 200  # no redirection, the site keeps the fake username "any" in navigation
        html = response.content.decode("utf8")
        assert "CURRENT_USERNAME=guy3" in html  # authentication OK
        assert "CURRENT_REAL_USERNAME=guy3" in html

        response = self.client.get(ROOT_GAME_URL + "/guy1/", follow=False)
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guy3/")  # impersonation refused

        response = self.client.get(ROOT_GAME_URL + "/redirect/", follow=False)
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guy3/")  # standard redirection system

        msg_id = self.dm.post_message("guy2@pangea.com",
                                         recipient_emails=["guy1@pangea.com"],
                                         subject="subj22323", body="qsdqsd")
        response = self.client.get(ROOT_GAME_URL + "/redirect/messages/view_single_message/%s/" % msg_id, follow=False)
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guy3/messages/view_single_message/%s/" % msg_id)  # works also with url-keywords

        response = self.client.get(ROOT_GAME_URL + "/badusername/", follow=False)
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guest/")  # error - unrecognized username leads to ession reset (anti-cheat)

        self._player_auth("guy3")
        self.dm.propose_friendship("guy1", "guy3")
        self.dm.propose_friendship("guy3", "guy1")  # sealed!
        response = self.client.get(ROOT_GAME_URL + "/guy1/", follow=False)
        assert response.status_code == 200  # no redirection
        html = response.content.decode("utf8")
        assert "CURRENT_USERNAME=guy1" in html  # NOW impersonation is OK
        assert "CURRENT_REAL_USERNAME=guy3" in html

        data = {IMPERSONATION_TARGET_POST_VARIABLE: "", IMPERSONATION_WRITABILITY_POST_VARIABLE: random.choice(("true", "false", "", "None"))}
        response = self.client.post(ROOT_GAME_URL + "/guy1/", data=data, follow=False)  # we target impersonated URL
        assert response.status_code == 302  # logged out
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guy3/")

        # let's test concurrent redirections, to check that nothing breaks
        self._player_auth("guy3")
        data = None
        if random.choice((True, False)):  # whatever this data
            data = {IMPERSONATION_TARGET_POST_VARIABLE: "", IMPERSONATION_WRITABILITY_POST_VARIABLE: random.choice(("true", "false", "", "None"))}
        response = self.client.post(ROOT_GAME_URL + "/guy2/logout/", data=data, follow=False)  # forbidden url
        assert response.status_code == 302  # game_username was corrected in URL
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guy3/logout/", fetch_redirect_response=False)
        response = self.client.post(ROOT_GAME_URL + "/guy3/logout/", data=data, follow=False)  # forbidden url
        assert response.status_code == 302  # NOW we really logout
        self.assertRedirects(response, expected_url=ROOT_GAME_URL + "/guest/login/", fetch_redirect_response=True)



    def test_http_complex_message_posting(self):

        self._reset_django_db()

        self._set_user(self.dm.master_login)  # for local DM
        self._master_auth() # for client cookies

        parent_msg_id = self.dm.post_message("guy2@pangea.com",
                                             recipient_emails=["guy1@pangea.com"],
                                             subject="PARENT", body="qsdqsd")
        transferred_msg_id = self.dm.post_message("guy3@pangea.com",
                                             recipient_emails=["guy2@pangea.com"],
                                             subject="TRANSFERRED", body="qsdqsd")

        base_parameters = dict(
                            _ability_form="pychronia_game.views.messaging_views.MessageComposeForm",
                            attachment="/files/e797ff6b/personal_files/_common_files_/Ninja-cat.mp4",
                            body="sdfsdfsdfsdf",
                            delay_h="-1",
                            mask_recipients="on",
                            parent_id=str(parent_msg_id),
                            recipients="emilos.loakim@anthropia.pg",
                            sender="contact@akaris.pg",
                            subject="test message complex",
                            transferred_msg=str(transferred_msg_id),
                            use_template="mind_opening_instructions_oracle",  # from test fixtures
                         )

        url = game_view_url("pychronia_game.views.compose_message", datamanager=self.dm)

        parameters = base_parameters.copy()
        response = self.client.post(url, data=parameters, follow=False)
        #print("@@@@@@", response.content)
        assert response.status_code == 302  # redirect
        self.assertRedirects(response, expected_url=game_view_url("pychronia_game.views.all_dispatched_messages", datamanager=self.dm) + "?message_sent=1")

        parameters = base_parameters.copy()
        parameters["delay_h"] = "1.2"
        response = self.client.post(url, data=parameters, follow=False)
        #print("@@@@@@", response.content)
        assert response.status_code == 302  # redirect
        self.assertRedirects(response, expected_url=game_view_url("pychronia_game.views.all_queued_messages", datamanager=self.dm) + "?message_sent=1")


        self._set_user("guy2")
        self._player_auth("guy2")
        url = game_view_url("pychronia_game.views.compose_message", datamanager=self.dm) # now with player username

        parameters = base_parameters.copy()  # too many parameters for a player, but they'll just be ignored without errors
        parameters["delay_h"] = "1.2"  # will be ignored too
        response = self.client.post(url, data=parameters, follow=False)
        #print("@@@@@@", response.content)
        assert response.status_code == 302  # redirect
        self.assertRedirects(response, expected_url=game_view_url("pychronia_game.views.standard_conversations", datamanager=self.dm) + "?message_sent=1")




class TestGameViewSystem(BaseGameTestCase):


    def test_instantiation_proxy_singleton(self):

        import pychronia_game.views.info_views
        A = pychronia_game.views.view_encyclopedia
        B = pychronia_game.views.info_views.EncyclopediaView.as_view
        C = pychronia_game.views.info_views.EncyclopediaView._instantiation_proxy
        assert A == B == C # SINGLETON system, else reverse() won't work


    def test_relevant_title(self):

        dm = self.dm

        same_titles = self.dm.instantiate_game_view("view_encyclopedia")
        different_titles = self.dm.instantiate_game_view("view_sales")

        self._set_user(random.choice(("guy1", None)))

        assert same_titles.relevant_title(dm) == same_titles.TITLE and same_titles.TITLE
        assert different_titles.relevant_title(dm) == different_titles.TITLE and different_titles.TITLE

        self._set_user("master")

        assert same_titles.relevant_title(dm) == same_titles.TITLE and same_titles.TITLE
        assert different_titles.relevant_title(dm) == different_titles.TITLE_FOR_MASTER and different_titles.TITLE_FOR_MASTER


    def test_game_forms_payment_fields_setup(self):

        class MyGameDummyForm(AbstractGameForm):
            pass

        character = random.choice(("guy1", "guy4"))
        self._set_user(character) # one has gems, the other not, but in any case we put a (hidden or not) form field
        assert bool(self.dm.get_character_properties()["gems"]) == bool(character == "guy1")

        form = MyGameDummyForm(self.dm)
        assert form.fields.keys() == ["_ability_form"]

        form = MyGameDummyForm(self.dm, payment_by_money=True)
        assert form.fields.keys() == ["_ability_form", "pay_with_money"]

        form = MyGameDummyForm(self.dm, payment_by_gems=True)
        assert form.fields.keys() == ["_ability_form", "gems_list"]

        form = MyGameDummyForm(self.dm, payment_by_gems=True)
        assert form.fields.keys() == ["_ability_form", "gems_list"]

        form = MyGameDummyForm(self.dm, payment_by_gems=True, payment_by_money=True)
        assert form.fields.keys() == ["_ability_form", "pay_with_money", "gems_list"]

        for username in (None, "master"):
            self._set_user(username)
            form = MyGameDummyForm(self.dm, payment_by_gems=random.choice((True, False)), payment_by_money=random.choice((True, False)))
            assert form.fields.keys() == ["_ability_form"] # never add payment controls, for master or guests



        # Now check that we get cleaned data properly #

        self._set_user("guy1")
        gems_list = self.dm.get_character_properties()["gems"][0:1]
        gems_list_serialized = GemPayementFormMixin._encode_gems(gems_list)

        # here with useless exceeding data fields, IGNORED
        form = MyGameDummyForm(self.dm, data=dict(_ability_form=form._get_dotted_class_name(), pay_with_money=True, gems_list=gems_list_serialized))
        assert form.is_valid()
        assert form.get_normalized_values() == {}
        #print (form.as_p())

        form = MyGameDummyForm(self.dm, data=dict(_ability_form=form._get_dotted_class_name(), pay_with_money=True, gems_list=gems_list_serialized),
                               payment_by_money=True, payment_by_gems=True)
        assert form.is_valid()
        with pytest.raises(NormalUsageError):
            form.get_normalized_values() # we must choose between money and gems (not BOTH)

        form = MyGameDummyForm(self.dm, data=dict(_ability_form=form._get_dotted_class_name(), pay_with_money=False, gems_list=()),
                               payment_by_money=True, payment_by_gems=True)
        assert form.is_valid()
        with pytest.raises(NormalUsageError):
            form.get_normalized_values() # we must choose between money and gems (not NONE)

        form = MyGameDummyForm(self.dm, data=dict(_ability_form=form._get_dotted_class_name(), pay_with_money=True, gems_list=()),
                               payment_by_money=True, payment_by_gems=True)
        assert form.is_valid()
        assert form.get_normalized_values() == dict(use_gems=[]) # we might actually remove pay_with_money from cleaned data...

        form = MyGameDummyForm(self.dm, data=dict(_ability_form=form._get_dotted_class_name(), pay_with_money=random.choice((False, None)), gems_list=gems_list_serialized),
                               payment_by_money=True, payment_by_gems=True)
        assert form.is_valid()
        assert form.get_normalized_values() == dict(use_gems=gems_list)


        for username in (None, "master"):
            self._set_user(username)
            form = MyGameDummyForm(self.dm, data=dict(_ability_form=form._get_dotted_class_name(),
                                                      pay_with_money=random.choice((True, False, None)),
                                                      gems_list=random.choice(([], gems_list_serialized))),
                                   payment_by_money=True, payment_by_gems=True)
            assert form.is_valid()
            assert form.get_normalized_values() == {} # no payment data at all



    def test_game_forms_to_action_signature_compatibility(self):
        """
        Forms attached to actions must define AT LEAST the fields mandatory in the action callback.
        """

        COMPUTED_VALUES = ["target_names"] # values that are injected in get_normalized_values(), and so invisible until actual processing

        self._set_user("guy1") # later, we'll need to change it depending on abilities instantiated below...
        # all forms must be instantiable, so provided items etc. !
        self.dm.transfer_object_to_character("statue", "guy1")
        wiretapping = self.dm.instantiate_ability("wiretapping")
        wiretapping.perform_lazy_initializations()
        wiretapping.purchase_wiretapping_slot()

        check_done = 0
        for game_view_class in self.dm.GAME_VIEWS_REGISTRY.values():

            game_view = self.dm.instantiate_game_view(game_view_class) # must work for abilities too!
            if hasattr(game_view, "perform_lazy_initializations"):
                game_view.perform_lazy_initializations() # ability object


            for action_name, action_properties in game_view.GAME_ACTIONS.items() + game_view.ADMIN_ACTIONS.items():

                FormClass = action_properties["form_class"]
                if not FormClass:
                    continue # action without predefined form class

                if action_name in game_view.GAME_ACTIONS:
                    form_inst = game_view._instantiate_game_form(action_name)
                else:
                    assert action_name in game_view.ADMIN_ACTIONS
                    form_inst = game_view._instantiate_admin_form(action_name)

                callback_name = action_properties["callback"]
                callback = getattr(game_view, callback_name)

                (args, varargs, varkw, defaults) = inspect.getargspec(callback) # will fail if keyword-only arguments are used, in the future

                if action_name in game_view.GAME_ACTIONS and game_view.ACCESS in (UserAccess.authenticated, UserAccess.character):
                    assert "use_gems" in args # IMPORTANT - all actions available to players MUST be potentially configurable for "gems payment"

                if args[0] == "self":
                    args = args[1:] # PB if instance is not called "self"...
                if varkw:
                    args = args[:-1]
                if varargs:
                    args = args[:-1]
                if defaults:
                    args = args[:-len(defaults)] # beware, wrong if defaults == ()

                for arg_name in args: # remaining ones are mandatory
                    if arg_name in COMPUTED_VALUES: # values not in form.fields, but created dynamically at instantiation
                        continue
                    fields = form_inst.fields
                    # print(fields)
                    assert arg_name in fields # IMPORTANT - mandatory arguments of action must exist in form fields (unless generated by form class)

                check_done += 1

        assert check_done > 3 # increase that in the future, for safety



    def test_mandatory_access_settings(self):

        # let's not block the home url...
        assert views.homepage.ACCESS == UserAccess.anonymous
        assert views.homepage.REQUIRES_GLOBAL_PERMISSION == False


    def test_access_parameters_normalization(self):

        from pychronia_game.datamanager.abstract_game_view import _normalize_view_access_parameters
        from pychronia_game.common import _undefined

        res = _normalize_view_access_parameters()
        assert res == dict(access=UserAccess.master,
                            requires_character_permission=False,
                            requires_global_permission=False)

        res = _normalize_view_access_parameters(UserAccess.anonymous, True, False)
        assert res == dict(access=UserAccess.anonymous,
                            requires_character_permission=True, # would raise an issue later, in metaclass, because we're in anonymous access
                            requires_global_permission=False)

        res = _normalize_view_access_parameters(UserAccess.anonymous, False, True)
        assert res == dict(access=UserAccess.anonymous,
                            requires_character_permission=False,
                            requires_global_permission=True)

        res = _normalize_view_access_parameters(UserAccess.anonymous)
        assert res == dict(access=UserAccess.anonymous,
                            requires_character_permission=False,
                            requires_global_permission=True) # even in anonymous access

        res = _normalize_view_access_parameters(UserAccess.character)
        assert res == dict(access=UserAccess.character,
                            requires_character_permission=False,
                            requires_global_permission=True)

        res = _normalize_view_access_parameters(UserAccess.authenticated)
        assert res == dict(access=UserAccess.authenticated,
                            requires_character_permission=False,
                            requires_global_permission=True)

        res = _normalize_view_access_parameters(UserAccess.master)
        assert res == dict(access=UserAccess.master,
                            requires_character_permission=False,
                            requires_global_permission=False) # logical

        res = _normalize_view_access_parameters(UserAccess.character, requires_character_permission=True)
        assert res == dict(access=UserAccess.character,
                            requires_character_permission=True,
                            requires_global_permission=True)


        class myview:
            ACCESS = UserAccess.authenticated
            REQUIRES_CHARACTER_PERMISSION = True
            REQUIRES_GLOBAL_PERMISSION = True

        res = _normalize_view_access_parameters(attach_to=myview)
        assert res == dict(access=UserAccess.authenticated,
                            requires_character_permission=True,
                            requires_global_permission=True)

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

        title = ugettext_lazy("test-title")

        # stupid cases get rejected in debug mode
        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.master, requires_character_permission=True, title=title)
        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.master, requires_global_permission=True, title=title) # master must always access his views!
        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.anonymous, requires_character_permission=True, title=title)

        klass = register_view(my_little_view, access=UserAccess.master, title=title, always_allow_post=True)

        assert issubclass(klass, AbstractGameView)
        assert klass.__name__ == "MyLittleView" # pascal case
        assert klass.NAME == "my_little_view" # snake case
        assert klass.NAME in self.dm.GAME_VIEWS_REGISTRY

        assert klass.ALWAYS_ALLOW_POST == True
        assert AbstractGameView.ALWAYS_ALLOW_POST == False

        with pytest.raises(AssertionError):
            register_view(my_little_view, access=UserAccess.master, title=ugettext_lazy("ssss")) # double registration impossible!


        # case of class registration #
        class DummyViewNonGameView(object):
            ACCESS = "sqdqsjkdqskj"
        with pytest.raises(AssertionError):
            register_view(DummyViewNonGameView, title=ugettext_lazy("SSS")) # must be a subclass of AbstractGameView


        class DummyView(AbstractGameView):
            TITLE = ugettext_lazy("DSDSF")
            NAME = "sdfsdf"
            ACCESS = UserAccess.anonymous
        klass = register_view(DummyView)
        assert isinstance(klass, type)
        register_view(DummyView, title=ugettext_lazy("DDD")) # double registration possible, since it's class creation which actually registers it, not that decorator


        class OtherDummyView(AbstractGameView):
            TITLE = ugettext_lazy("LJKSG")
            NAME = "sdfsdzadsfsdff"
            ACCESS = UserAccess.anonymous
        with pytest.raises(AssertionError): # when a klass is given, all other arguments become forbidden
            while True:
                a, b, c, d = [random.choice([_undefined, False]) for i in range(4)]
                if not all((a, b, c)):
                    break # at least one of them must NOT be _undefined
            register_view(OtherDummyView, a, b, c, d, title=ugettext_lazy("SSS"))



    def test_access_token_computation(self):

        datamanager = self.dm

        def dummy_view_callable(request):
            pass

        view_anonymous = register_view(dummy_view_callable, access=UserAccess.anonymous, requires_global_permission=False, title=ugettext_lazy("Hi"), view_name="view_anonymous")
        view_anonymous_gp = register_view(dummy_view_callable, access=UserAccess.anonymous, requires_global_permission=True, title=ugettext_lazy("Hi2"), view_name="view_anonymous_gp")
        assert view_anonymous_gp.klass.REQUIRES_GLOBAL_PERMISSION
        view_character = register_view(dummy_view_callable, access=UserAccess.character, requires_global_permission=False, title=ugettext_lazy("Yowh1"), view_name="view_character")
        view_character_gp = register_view(dummy_view_callable, access=UserAccess.character, requires_character_permission=False, requires_global_permission=True, title=ugettext_lazy("Yowh2"), view_name="view_character_gp")
        view_character_cp = register_view(dummy_view_callable, access=UserAccess.character, requires_character_permission=True, requires_global_permission=False, title=ugettext_lazy("Yowh3"), view_name="view_character_cp")
        view_character_gp_cp = register_view(dummy_view_callable, access=UserAccess.character, requires_character_permission=True, requires_global_permission=True, title=ugettext_lazy("Yowh4"), view_name="view_character_gp_cp")

        view_authenticated = register_view(dummy_view_callable, access=UserAccess.authenticated, requires_global_permission=False, title=ugettext_lazy("Yayh1"), view_name="view_authenticated")
        view_authenticated_gp = register_view(dummy_view_callable, access=UserAccess.authenticated, requires_character_permission=False, requires_global_permission=True, title=ugettext_lazy("Yayh2"), view_name="view_authenticated_gp")
        view_authenticated_cp = register_view(dummy_view_callable, access=UserAccess.authenticated, requires_character_permission=True, requires_global_permission=False, title=ugettext_lazy("Yayh3"), view_name="view_authenticated_cp")
        view_authenticated_gp_cp = register_view(dummy_view_callable, access=UserAccess.authenticated, requires_character_permission=True, requires_global_permission=True, title=ugettext_lazy("Yayh4"), view_name="view_authenticated_gp_cp")

        view_master = register_view(dummy_view_callable, access=UserAccess.master, title=ugettext_lazy("Maaaster"), view_name="view_master")  # requires_global_permission is enforced to False for master views, actually


        for perm in self.dm.PERMISSIONS_REGISTRY:
            self.dm.set_permission("guy1", permission=perm, is_present=True)
        for perm in self.dm.PERMISSIONS_REGISTRY:
            self.dm.set_permission("guy2", permission=perm, is_present=False)


        self.dm.set_activated_game_views([])  # NO VIEWS ARE ACTIVATED

        self._set_user(None)
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_character.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required

        self._set_user("guy1")  # has ALL CHARACTER PERMISSIONS
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_character.get_access_token(datamanager) == AccessResult.available
        assert view_character_gp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_character_cp.get_access_token(datamanager) == AccessResult.available
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.available  # character permission overrides global disabling of view
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.available
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required

        self._set_user("guy2")  # has NO CHARACTER PERMISSIONS
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_character.get_access_token(datamanager) == AccessResult.available
        assert view_character_gp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_character_cp.get_access_token(datamanager) == AccessResult.permission_required
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.permission_required
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.globally_forbidden
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required

        self._set_user(self.dm.get_global_parameter("master_login"))
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.available
        assert view_master.get_access_token(datamanager) == AccessResult.available



        self.dm.set_activated_game_views(self.dm.ACTIVABLE_VIEWS_REGISTRY.keys())  # NO VIEWS ARE ACTIVATED

        self._set_user(None)
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required

        self._set_user("guy1")  # has ALL CHARACTER PERMISSIONS
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.available
        assert view_character_gp.get_access_token(datamanager) == AccessResult.available
        assert view_character_cp.get_access_token(datamanager) == AccessResult.available
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.available
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required

        self._set_user("guy2")  # has NO CHARACTER PERMISSIONS
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.available
        assert view_character_gp.get_access_token(datamanager) == AccessResult.available
        assert view_character_cp.get_access_token(datamanager) == AccessResult.permission_required
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.permission_required
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.permission_required
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.permission_required
        assert view_master.get_access_token(datamanager) == AccessResult.authentication_required

        self._set_user(self.dm.get_global_parameter("master_login"))
        assert view_anonymous.get_access_token(datamanager) == AccessResult.available
        assert view_anonymous_gp.get_access_token(datamanager) == AccessResult.available
        assert view_character.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_character_gp_cp.get_access_token(datamanager) == AccessResult.authentication_required
        assert view_authenticated.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_cp.get_access_token(datamanager) == AccessResult.available
        assert view_authenticated_gp_cp.get_access_token(datamanager) == AccessResult.available
        assert view_master.get_access_token(datamanager) == AccessResult.available



    def test_per_action_user_permissions(self):

        view_url = neutral_url_reverse(views.wiretapping_management)

        # ACTIONS that require personal permissions
        request1 = self.factory.post(view_url, data=dict(_action_="purchase_confidentiality_protection")) # direct call
        request2 = self.factory.post(view_url, data=dict(_ability_form="pychronia_game.views.abilities.wiretapping_management_mod.WiretappingConfidentialityForm")) # form call

        for (username, request, error_msg) in [("guy1", request1, "by unauthorized user"),
                                               ("guy2", request2, "Submitted data is invalid")]:

            request.datamanager._set_user(username)

            wiretapping = request.datamanager.instantiate_ability("wiretapping")

            assert wiretapping.datamanager.user is request.datamanager.user
            wiretapping.datamanager.user.discard_notifications() # ugly stuffs might be left around
            assert not wiretapping._is_action_permitted_for_user("purchase_confidentiality_protection", wiretapping.GAME_ACTIONS, wiretapping.datamanager.user)
            assert wiretapping._instantiate_game_form(new_action_name="purchase_confidentiality_protection") is None

            self.dm.set_permission(username, wiretapping.get_access_permission_name(), True) # personal access permission

            # FAILURE #
            response = wiretapping(request)
            print(">>>>>>>>>", response.content)
            assert response.status_code == 200
            assert error_msg in response.content.decode("utf8")
            assert not wiretapping.datamanager.get_confidentiality_protection_status() # NOT ACQUIRED BY USER

            request.datamanager.set_permission(username, "purchase_confidentiality_protection", is_present=True)  # has same name as action, here
            assert wiretapping.datamanager.has_permission(permission="purchase_confidentiality_protection")
            assert wiretapping._is_action_permitted_for_user("purchase_confidentiality_protection", wiretapping.GAME_ACTIONS, wiretapping.datamanager.user)
            assert wiretapping._instantiate_game_form(new_action_name="purchase_confidentiality_protection")

            # SUCCESS #
            wiretapping.datamanager.user.discard_notifications() # ugly stuffs might be left around
            response = wiretapping(request)
            #print(response.content)
            assert response.status_code == 200
            assert error_msg not in response.content.decode("utf8")
            assert wiretapping.datamanager.get_confidentiality_protection_status() # ACQUIRED



    def test_action_processing_basics(self):

        bank_name = self.dm.get_global_parameter("bank_name")
        self.dm.transfer_money_between_characters(bank_name, "guy1", amount=1000)

        # BEWARE - below we use another datamanager !!
        view_url = neutral_url_reverse(views.wiretapping_management)

        # first a "direct action" html call
        request = self.factory.post(view_url, data=dict(_action_="purchase_wiretapping_slot", qsdhqsdh="33"))
        request.datamanager._set_user("guy1")
        request.datamanager.set_permission("guy1", views.wiretapping_management.get_access_permission_name(), is_present=True)

        wiretapping = request.datamanager.instantiate_ability("wiretapping")
        assert not request.datamanager.get_event_count("TRY_PROCESSING_FORMLESS_GAME_ACTION")
        assert not request.datamanager.get_event_count("PROCESS_HTML_REQUEST")
        response = wiretapping(request)
        assert response.status_code == 200
        assert wiretapping.get_wiretapping_slots_count() == 1
        assert request.datamanager.get_event_count("TRY_PROCESSING_FORMLESS_GAME_ACTION") == 1
        assert request.datamanager.get_event_count("PROCESS_HTML_REQUEST") == 1

        # now in ajax
        request = self.factory.post(view_url, data=dict(_action_="purchase_wiretapping_slot", vcv="33"), **AJAX_HEADERS)
        request.datamanager._set_user("guy1")
        wiretapping = request.datamanager.instantiate_ability("wiretapping")
        assert not request.datamanager.get_event_count("TRY_PROCESSING_FORMLESS_GAME_ACTION")
        assert not request.datamanager.get_event_count("PROCESS_AJAX_REQUEST")
        response = wiretapping(request)
        assert response.status_code == 200
        assert wiretapping.get_wiretapping_slots_count() == 2
        assert request.datamanager.get_event_count("TRY_PROCESSING_FORMLESS_GAME_ACTION") == 1
        assert request.datamanager.get_event_count("PROCESS_AJAX_REQUEST") == 1



        # now via the abstract form (+ middleware), failure because no payment means is chosen (CostlyActionMiddleware ON)
        request = self.factory.post(view_url, data=dict(_ability_form="pychronia_game.views.abilities.wiretapping_management_mod.WiretappingTargetsForm",
                                                        target_0="guy3",
                                                        fdfd="33"))
        request.datamanager._set_user("guy1")
        wiretapping = request.datamanager.instantiate_ability("wiretapping")
        assert not request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION")
        assert not request.datamanager.get_event_count("PROCESS_HTML_REQUEST")
        assert not request.datamanager.get_event_count("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES")
        assert request.datamanager.get_wiretapping_targets() == []
        response = wiretapping(request)
        assert response.status_code == 200
        assert wiretapping.get_wiretapping_slots_count() == 2 # unchanged
        assert request.datamanager.get_wiretapping_targets() == [] # unchanged
        assert request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION") == 1
        assert request.datamanager.get_event_count("PROCESS_HTML_REQUEST") == 1
        assert request.datamanager.get_event_count("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES") == 0 # NOPE

        request.datamanager.clear_all_event_stats()

        # now via the abstract form (+ middleware), now successful
        request = self.factory.post(view_url, data=dict(_ability_form="pychronia_game.views.abilities.wiretapping_management_mod.WiretappingTargetsForm",
                                                        target_0="guy3",
                                                        pay_with_money=True, # now we choose
                                                        fdfd="33"))
        request.datamanager._set_user("guy1")
        wiretapping = request.datamanager.instantiate_ability("wiretapping")
        assert not request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION")
        assert not request.datamanager.get_event_count("PROCESS_HTML_REQUEST")
        assert not request.datamanager.get_event_count("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES")
        assert request.datamanager.get_wiretapping_targets() == []
        response = wiretapping(request)
        assert response.status_code == 200
        assert wiretapping.get_wiretapping_slots_count() == 2 # unchanged
        assert request.datamanager.get_wiretapping_targets() == ["guy3"]
        assert request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION") == 1
        assert request.datamanager.get_event_count("PROCESS_HTML_REQUEST") == 1
        assert request.datamanager.get_event_count("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES") == 1



    def test_gameview_novelty_tracking(self):

        view_url = neutral_url_reverse(views.runic_translation)  # access == character only

        # first a "direct action" html call
        request = self.factory.post(view_url)

        request.datamanager._set_user("master")
        request.datamanager.set_permission("guy1", views.runic_translation.get_access_permission_name(), is_present=True)

        runic_translation = request.datamanager.instantiate_ability("runic_translation")

        res = runic_translation(request)
        assert res.status_code == 302 # access not allowed

        assert not runic_translation.has_user_accessed_view(runic_translation.datamanager)

        request.datamanager._set_user("guy1")
        request.datamanager.set_activated_game_views([runic_translation.NAME]) # else no access

        res = runic_translation(request)
        assert res.status_code == 200 # access allowed

        assert runic_translation.has_user_accessed_view(runic_translation.datamanager)



class TestActionMiddlewares(BaseGameTestCase):


    def _flatten_explanations(self, list_of_lists_of_strings):
        """
        Also checks for coherence of list_of_lists_of_strings.
        """
        assert isinstance(list_of_lists_of_strings, list) # may be empty
        for l in list_of_lists_of_strings:
            assert l # important -> if a middleware has nothing to say, he musn't include its sublist
            for s in l:
                assert s
                assert isinstance(s, basestring)
        return u"\n".join(u"".join(strs) for strs in list_of_lists_of_strings)


    def _check_full_action_explanations(self, full_list):
        for title, explanations in full_list:
            utilities.check_is_lazy_translation(title)
            assert unicode(title)
            assert explanations # NO empty lists here
            assert self._flatten_explanations(explanations)
        return full_list # if caller wants to check non-emptiness


    def test_basic_action_middleware_status(self):

        self._set_user("guy4")

        ability = self.dm.instantiate_ability("dummy_ability")
        ability.perform_lazy_initializations() # normally done while treating HTTP request...

        assert not ability.has_action_middlewares_configured(action_name="middleware_wrapped_test_action")
        assert not ability.is_action_middleware_activated(action_name="middleware_wrapped_test_action", middleware_class=CostlyActionMiddleware)

        ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(is_active=False, money_price=203, gems_price=123))

        assert ability.has_action_middlewares_configured(action_name="middleware_wrapped_test_action")
        assert not ability.is_action_middleware_activated(action_name="middleware_wrapped_test_action", middleware_class=CostlyActionMiddleware)
        self._set_user("master")
        assert not ability.is_action_middleware_activated(action_name="middleware_wrapped_test_action", middleware_class=CostlyActionMiddleware)
        self._set_user(None)
        assert not ability.is_action_middleware_activated(action_name="middleware_wrapped_test_action", middleware_class=CostlyActionMiddleware)

        self._set_user("guy4")

        with pytest.raises(RuntimeError):
            assert ability.get_middleware_settings("middleware_wrapped_test_action", CostlyActionMiddleware)
        with pytest.raises(RuntimeError):
            assert ability.get_middleware_settings("middleware_wrapped_test_action", CostlyActionMiddleware, ensure_active=True)
        assert ability.get_middleware_settings("middleware_wrapped_test_action", CostlyActionMiddleware, ensure_active=False)

        ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(is_active=True, money_price=203, gems_price=123))

        assert ability.has_action_middlewares_configured(action_name="middleware_wrapped_test_action")
        assert ability.is_action_middleware_activated(action_name="middleware_wrapped_test_action", middleware_class=CostlyActionMiddleware)
        self._set_user("master")
        assert not ability.is_action_middleware_activated(action_name="middleware_wrapped_test_action", middleware_class=CostlyActionMiddleware)
        self._set_user(None)
        assert not ability.is_action_middleware_activated(action_name="middleware_wrapped_test_action", middleware_class=CostlyActionMiddleware)

        self._set_user("guy4")

        assert ability.get_middleware_settings("middleware_wrapped_test_action", CostlyActionMiddleware)
        assert ability.get_middleware_settings("middleware_wrapped_test_action", CostlyActionMiddleware, ensure_active=True)
        assert ability.get_middleware_settings("middleware_wrapped_test_action", CostlyActionMiddleware, ensure_active=False)



    def test_all_get_middleware_data_explanations(self):

        self._set_user("guy4") # important
        bank_name = self.dm.get_global_parameter("bank_name")
        self.dm.transfer_money_between_characters(bank_name, "guy4", amount=1000)

        ability = self.dm.instantiate_ability("dummy_ability")
        ability.perform_lazy_initializations() # normally done while treating HTTP request...

        assert not ability.has_action_middlewares_configured(action_name="middleware_wrapped_test_action")
        ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(is_active=False, money_price=203, gems_price=123))

        explanations = ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action")
        assert explanations == [] # no middlewares ACTIVATED
        assert ability.get_game_form_extra_params(action_name="middleware_wrapped_test_action") == {}

        ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(is_active=True, money_price=203, gems_price=123))
        assert ability.has_action_middlewares_configured(action_name="middleware_wrapped_test_action")
        assert ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action") # no pb with non-activated ones
        assert ability.get_game_form_extra_params(action_name="middleware_wrapped_test_action") == dict(payment_by_money=True, payment_by_gems=True)

        ability.reset_test_settings("middleware_wrapped_test_action", CountLimitedActionMiddleware, dict(max_per_character=23, max_per_game=33))
        assert ability.has_action_middlewares_configured(action_name="middleware_wrapped_test_action")
        assert ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action") # no pb with non-activated ones
        assert ability.get_game_form_extra_params(action_name="middleware_wrapped_test_action") == dict(payment_by_money=True, payment_by_gems=True)

        ability.reset_test_settings("middleware_wrapped_test_action", TimeLimitedActionMiddleware, dict(waiting_period_mn=87, max_uses_per_period=12))
        assert ability.has_action_middlewares_configured(action_name="middleware_wrapped_test_action")
        assert ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action") # no pb with non-activated ones
        assert ability.get_game_form_extra_params(action_name="middleware_wrapped_test_action") == dict(payment_by_money=True, payment_by_gems=True)

        assert 18277 == ability.middleware_wrapped_callable1(use_gems=None) # we perform action ONCE

        explanations = ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action")
        explanations = self._flatten_explanations(explanations)
        assert "%s" not in explanations and "%r" not in explanations, explanations

        for stuff in (203, 123, 23, 33, 12, " 1 "):
            assert str(stuff) in explanations
        assert "3941" in explanations, explanations # floor of 45.3 days factor * 87 mn

        ##print(">>>>>|||>>>>>", explanations)


    def test_get_game_actions_explanations(self):

        self._set_user("guy4") # important
        bank_name = self.dm.get_global_parameter("bank_name")
        self.dm.transfer_money_between_characters(bank_name, "guy4", amount=1000)

        view = self.dm.instantiate_game_view("characters_view")
        assert view.get_game_actions_explanations() == [] # has game actions, but no middlewares, because not an ability
        del view

        ability = self.dm.instantiate_ability("dummy_ability")
        ability.perform_lazy_initializations() # normally done while treating HTTP request...


        ability.reset_test_settings("middleware_wrapped_other_test_action", CostlyActionMiddleware, dict(money_price=203, gems_price=123))
        assert self._check_full_action_explanations(ability.get_game_actions_explanations())

        ability.reset_test_settings("middleware_wrapped_other_test_action", CountLimitedActionMiddleware, dict(max_per_character=23, max_per_game=33))
        assert self._check_full_action_explanations(ability.get_game_actions_explanations())

        ability.reset_test_settings("middleware_wrapped_other_test_action", TimeLimitedActionMiddleware, dict(waiting_period_mn=87, max_uses_per_period=12))
        assert self._check_full_action_explanations(ability.get_game_actions_explanations())

        assert True == ability.middleware_wrapped_other_test_action(my_arg=None) # we perform action ONCE
        assert self._check_full_action_explanations(ability.get_game_actions_explanations())


    def test_action_middleware_bypassing(self):
        """
        Actions that have no entry of the ability's middleware settings shouldn't go through the middlewares chain
        """

        self._set_user("guy4") # important

        ability = self.dm.instantiate_ability("dummy_ability")
        ability.perform_lazy_initializations() # normally done while treating HTTP request...

        transactional_processor = ability.execute_game_action_callback # needs transaction watcher else test is buggy...

        assert not self.dm.get_event_count("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES")
        assert not self.dm.get_event_count("TOP_LEVEL_PROCESS_ACTION_THROUGH_MIDDLEWARES")

        res = transactional_processor("non_middleware_action_callable", unfiltered_params=dict(use_gems=True, aaa=33))
        assert res == 23

        assert not self.dm.get_event_count("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES") # BYPASSED
        assert not self.dm.get_event_count("TOP_LEVEL_PROCESS_ACTION_THROUGH_MIDDLEWARES")

        ability.reset_test_settings("non_middleware_action_callable", CountLimitedActionMiddleware, dict(max_per_character=1, max_per_game=12))

        res = transactional_processor("non_middleware_action_callable", unfiltered_params=dict(use_gems=True, aaa=33))
        assert res == 23

        assert self.dm.get_event_count("EXECUTE_GAME_ACTION_WITH_MIDDLEWARES") # NOT BYPASSED, because configured
        assert self.dm.get_event_count("TOP_LEVEL_PROCESS_ACTION_THROUGH_MIDDLEWARES")

        with raises_with_content(NormalUsageError, "exceeded your quota"):
            transactional_processor("non_middleware_action_callable", unfiltered_params=dict(use_gems=True, aaa=33))

        self.dm.rollback()


    def test_costly_action_middleware(self):

        gem_125 = (125, "several_misc_gems2")
        gem_200 = (200, "several_misc_gems")

        # setup
        bank_name = self.dm.get_global_parameter("bank_name")
        self.dm.transfer_money_between_characters(bank_name, "guy4", amount=1000)
        self.dm.transfer_object_to_character("several_misc_gems", "guy4") # 5 * 200 kashes
        self.dm.transfer_object_to_character("several_misc_gems2", "guy4") # 8 * 125 kashes

        props = self.dm.get_character_properties("guy4")
        assert props["account"] == 1000
        utilities.assert_counters_equal(props["gems"], ([gem_125] * 8 + [gem_200] * 5))

        self._set_user("guy4") # important

        ability = self.dm.instantiate_ability("dummy_ability")
        ability.perform_lazy_initializations() # normally done while treating HTTP request...

        assert isinstance(ability, DummyTestAbility)
        assert CostlyActionMiddleware
        self.dm.commit()

        self.dm.check_database_coherence() # SECURITY


        # misconfiguration case #

        ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(money_price=None, gems_price=None))

        assert ability.get_game_form_extra_params(action_name="middleware_wrapped_test_action") == dict()

        for value in (None, [], [gem_125], [gem_200, gem_125]):
            assert ability.middleware_wrapped_callable1(use_gems=value) # no limit is set at all
            assert ability.middleware_wrapped_callable2(value)
            assert ability.non_middleware_action_callable(use_gems=[gem_125])

        assert not self.dm.is_in_writing_transaction()
        self.dm.check_no_pending_transaction()

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 4
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 4
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 4

        self.dm.clear_all_event_stats()

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


        # payment with money #

        for gems_price in (None, 15, 100): # WHATEVER gems prices

            ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(money_price=15, gems_price=gems_price))
            ability.reset_test_data("middleware_wrapped_test_action", CostlyActionMiddleware, dict()) # useless actually for that middleware

            res = ability.get_game_form_extra_params(action_name="middleware_wrapped_test_action")
            assert res.get("payment_by_money") == True
            assert bool(res.get("payment_by_gems")) == bool(gems_price is not None)

            # payments OK
            assert 18277 == ability.middleware_wrapped_callable1(use_gems=random.choice((None, []))) # triggers payment by money
            assert True == ability.middleware_wrapped_callable2(34) # idem, points to the same conf

            # not taken into account - no middlewares here
            assert 23 == ability.non_middleware_action_callable(use_gems=[gem_125])

            # too expensive
            ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(money_price=999, gems_price=gems_price))
            with raises_with_content(NormalUsageError, "in money"):
                ability.middleware_wrapped_callable1(use_gems=random.choice((None, [])))
            with raises_with_content(NormalUsageError, "in money"):
                ability.middleware_wrapped_callable2("helly")

            # not taken into account - no middlewares here
            assert 23 == ability.non_middleware_action_callable(use_gems=[gem_125])

        ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(money_price=53, gems_price=None))
        assert 18277 == ability.middleware_wrapped_callable1(use_gems=[gem_125, gem_125]) # triggers payment by money ANYWAY!

        # we check data coherence
        props = self.dm.get_character_properties("guy4")
        new_money_value = 1000 - 2 * 3 * 15 - 53 # 2 callables * 3 use_gems values * money price, and special 53 kashes payment
        assert props["account"] == new_money_value
        utilities.assert_sets_equal(props["gems"], [gem_125] * 8 + [gem_200] * 5) # unchanged

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 4 # 3 + 1 extra call
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 3
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 6

        self.dm.clear_all_event_stats()

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


        self.dm.check_database_coherence() # SECURITY


        # payment with gems #

        for money_price in (None, 0, 15): # WHATEVER money prices

            ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(money_price=money_price, gems_price=150))
            ability.reset_test_data("middleware_wrapped_test_action", CostlyActionMiddleware, dict()) # useless actually for that middleware

            res = ability.get_game_form_extra_params(action_name="middleware_wrapped_test_action")
            assert res.get("payment_by_gems") == True
            assert bool(res.get("payment_by_money")) == bool(money_price is not None)

            # payments OK
            assert ability.middleware_wrapped_callable1(use_gems=[gem_200]) # triggers payment by gems

            # not taken into account - no middlewares here
            assert ability.non_middleware_action_callable(use_gems=[gem_125, (128, None), (129, None)])

            # too expensive for current gems given
            with raises_with_content(NormalUsageError, "kashes of gems"):
                ability.middleware_wrapped_callable1(use_gems=[gem_125])

            with raises_with_content(NormalUsageError, "top off"): # we're nice with people who give too much...
                ability.middleware_wrapped_callable1(use_gems=[gem_125, gem_200])

            with raises_with_content(NormalUsageError, "top off"): # that check is done before "whether or not they really own the games"
                ability.middleware_wrapped_callable1(use_gems=[(128, "several_misc_gems2"), (178, None)])

            # some wrong gems in input (even if a sufficient number  of them is OK)
            with raises_with_content(UsageError, "doesn't possess"):
                ability.middleware_wrapped_callable1(use_gems=[(111, None), (125, "stuffs")])

            if not money_price:
                # no fallback to money, when no gems at all in input
                with raises_with_content(NormalUsageError, "kashes of gems"):
                    ability.middleware_wrapped_callable1(use_gems=random.choice((None, [])))
                with raises_with_content(NormalUsageError, "kashes of gems"):
                    ability.middleware_wrapped_callable2([gem_125, gem_125]) # wrong param name

            assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))

        assert ability.middleware_wrapped_callable1(use_gems=[gem_200]) # OK
        assert ability.middleware_wrapped_callable1(use_gems=[gem_125, gem_125]) # OK as long as not too many gems for the asset value

        # we check data coherence
        props = self.dm.get_character_properties("guy4")
        assert props["account"] == new_money_value # unchanged
        utilities.assert_sets_equal(props["gems"], [gem_125] * 6 + [gem_200]) # 3 payments with 2 gems, + 2 separate payments

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 5 # 3 + 2 extra calls
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 0
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 3

        self.dm.clear_all_event_stats()


        self.dm.check_database_coherence() # SECURITY


        # payment with both is possible #

        ability.reset_test_settings("middleware_wrapped_test_action", CostlyActionMiddleware, dict(money_price=11, gems_price=33))
        ability.reset_test_data("middleware_wrapped_test_action", CostlyActionMiddleware, dict()) # useless actually for that middleware

        ability.middleware_wrapped_callable1(use_gems=[gem_200]) # by gems, works even if smaller gems of user would fit better (no paternalism)
        ability.middleware_wrapped_callable1(use_gems=None) # by money
        ability.middleware_wrapped_callable2("hi") # by money
        assert ability.non_middleware_action_callable(use_gems=[gem_125])
        assert ability.non_middleware_action_callable(use_gems=[])

        # we check data coherence
        props = self.dm.get_character_properties("guy4")
        assert props["account"] == new_money_value - 11 * 2
        utilities.assert_sets_equal(props["gems"], [gem_125] * 2) # "200 kashes" gem is out

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 2
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 1
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 2

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))



    def test_count_limited_action_middleware(self):


        ability = self.dm.instantiate_ability("dummy_ability")


        # BOTH quotas

        ability.reset_test_settings("middleware_wrapped_test_action", CountLimitedActionMiddleware, dict(max_per_character=3, max_per_game=4))

        self._set_user("guy4") # important
        ability.perform_lazy_initializations() # normally done while treating HTTP request...
        ability.reset_test_data("middleware_wrapped_test_action", CountLimitedActionMiddleware, dict()) # will be filled lazily, on call


        assert 18277 == ability.middleware_wrapped_callable1(2524) # 1 use for guy4
        assert True == ability.middleware_wrapped_callable2(2234) # 2 uses for guy4
        assert 23 == ability.non_middleware_action_callable(use_gems=[125]) # no use
        assert 18277 == ability.middleware_wrapped_callable1(132322) # 3 uses for guy4

        with raises_with_content(NormalUsageError, "exceeded your quota"):
            ability.middleware_wrapped_callable1(2524)

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


        self._set_user("guy3") # important
        ability.perform_lazy_initializations() # normally done while treating HTTP request...
        ability.reset_test_data("middleware_wrapped_test_action", CountLimitedActionMiddleware, dict()) # will be filled lazily, on call

        assert ability.middleware_wrapped_callable2(None) # 1 use for guy3
        assert ability.non_middleware_action_callable(use_gems=True) # no use
        with raises_with_content(NormalUsageError, "global quota"):
            ability.middleware_wrapped_callable2(11)


        self._set_user("guy4") # important
        with raises_with_content(NormalUsageError, "global quota"): # this msg now takes precedence over "private quota" one
            ability.middleware_wrapped_callable1(222)

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 2
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 2
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 2

        self.dm.clear_all_event_stats()

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


        # only per-character quota

        ability.reset_test_settings("middleware_wrapped_test_action", CountLimitedActionMiddleware, dict(max_per_character=3, max_per_game=None))

        self._set_user("guy3") # important
        assert ability.middleware_wrapped_callable2(None) # 2 uses for guy3
        assert ability.middleware_wrapped_callable2(None) # 3 uses for guy3
        with raises_with_content(NormalUsageError, "exceeded your quota"):
            ability.middleware_wrapped_callable2(1111122)

        self._set_user("guy4") # important
        with raises_with_content(NormalUsageError, "exceeded your quota"): # back to private quota message
            ability.middleware_wrapped_callable2(False)
        assert ability.non_middleware_action_callable(None)

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 0
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 2
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 1
        self.dm.clear_all_event_stats()

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


        # only global quota

        ability.reset_test_settings("middleware_wrapped_test_action", CountLimitedActionMiddleware, dict(max_per_character=None, max_per_game=12)) # 6 more than current total

        assert ability.middleware_wrapped_callable1(None) # guy4 still

        self._set_user("guy2") # important
        ability.perform_lazy_initializations()

        for i in range(5):
            assert ability.middleware_wrapped_callable1(None)
        with raises_with_content(NormalUsageError, "global quota"):
            ability.middleware_wrapped_callable1(False)
        assert ability.non_middleware_action_callable(None)

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 6
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 0
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 1
        self.dm.clear_all_event_stats()

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


        # no quota (or misconfiguration):

        ability.reset_test_settings("middleware_wrapped_test_action", CountLimitedActionMiddleware,
                                    dict(max_per_character=random.choice((None, 0)), max_per_game=random.choice((None, 0))))

        for username in ("guy2", "guy3", "guy4"):
            self._set_user(username) # important
            for i in range(10):
                assert ability.middleware_wrapped_callable1(None)
                assert ability.middleware_wrapped_callable2(None)
                assert ability.non_middleware_action_callable(None)

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 30
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 30
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 30

        self.dm.clear_all_event_stats()

        assert ability._get_global_usage_count("middleware_wrapped_test_action") == 72 # usage counts are yet updated
        assert ability._get_global_usage_count("middleware_wrapped_other_test_action") == 0 # important - no collision between action names

        ability.reset_test_settings("middleware_wrapped_test_action", CountLimitedActionMiddleware,
                                    dict(max_per_character=30, max_per_game=73))

        self._set_user("guy2")
        assert ability.middleware_wrapped_callable1(None)
        with raises_with_content(NormalUsageError, "global quota"):
            ability.middleware_wrapped_callable1(False) # quota of 75 reached
        assert ability.non_middleware_action_callable(None)

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 1
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 0
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 1

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


    def test_time_limited_action_middleware(self):

        WANTED_FACTOR = 2 # we only double durations below
        params = self.dm.get_global_parameters()
        assert params["game_theoretical_length_days"]
        params["game_theoretical_length_days"] = WANTED_FACTOR


        ability = self.dm.instantiate_ability("dummy_ability")
        self._set_user("guy4") # important
        ability.perform_lazy_initializations() # normally done while treating HTTP request...


        # misconfiguration case #

        waiting_period_mn = random.choice((0, None, 3))
        max_uses_per_period = random.choice((0, None, 3)) if not waiting_period_mn else None

        ability.reset_test_settings("middleware_wrapped_test_action", TimeLimitedActionMiddleware,
                                    dict(waiting_period_mn=waiting_period_mn, max_uses_per_period=max_uses_per_period))
        ability.reset_test_data("middleware_wrapped_test_action", TimeLimitedActionMiddleware, dict()) # will be filled lazily, on call

        for i in range(23):
            assert ability.middleware_wrapped_callable1(None)
            assert ability.middleware_wrapped_callable2(None)
            assert ability.non_middleware_action_callable(None)

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 23
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 23
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 23
        self.dm.clear_all_event_stats()

        private_data = ability.get_private_middleware_data(action_name="middleware_wrapped_test_action",
                                                           middleware_class=TimeLimitedActionMiddleware)
        assert len(private_data["last_use_times"]) == 2 * 23

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))


        # normal case #

        ability.reset_test_settings("middleware_wrapped_test_action", TimeLimitedActionMiddleware,
                                    dict(waiting_period_mn=0.02 / WANTED_FACTOR, max_uses_per_period=3)) # 1.2s of waiting time

        for username in ("guy2", "guy3"):
            self._set_user(username) # important
            ability.perform_lazy_initializations() # normally done while treating HTTP request...
            ability.reset_test_data("middleware_wrapped_test_action", TimeLimitedActionMiddleware, dict()) # will be filled lazily, on call

            assert ability.middleware_wrapped_callable1(None)
            assert ability.middleware_wrapped_callable1(12)
            assert ability.middleware_wrapped_callable2(32)
            self.dm.commit() # data was touched, even if not really

            old_last_use_times = ability.get_private_middleware_data("middleware_wrapped_test_action", TimeLimitedActionMiddleware)["last_use_times"]
            res = ability._compute_purged_old_use_times(middleware_settings=ability.get_middleware_settings("middleware_wrapped_test_action", TimeLimitedActionMiddleware),
                                                             last_use_times=old_last_use_times[:])
            assert res == old_last_use_times # unchanged
            del res, old_last_use_times
            self.dm.commit() # data was touched, even if not really changed in place

            with raises_with_content(NormalUsageError, "waiting period"):
                ability.middleware_wrapped_callable1(False) # quota of 3 per period reached
            assert ability.non_middleware_action_callable(None)

            assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))

            time.sleep(0.2)


        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 4
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 2
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 2
        self.dm.clear_all_event_stats()


        time.sleep(1.3)

        self._set_user("guy2") # important


        for i in range(7):
            assert ability.middleware_wrapped_callable1(None)
            time.sleep(0.41) # just enough to be under 4 accesses / 1.2s

        assert ability.middleware_wrapped_callable2(None)
        with raises_with_content(NormalUsageError, "waiting period"):
            ability.middleware_wrapped_callable1(False) # quota of 3 per period reached if we hit immediateley

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))

        time.sleep(0.5)

        old_last_use_times = ability.get_private_middleware_data("middleware_wrapped_test_action", TimeLimitedActionMiddleware)["last_use_times"]
        res = ability._compute_purged_old_use_times(middleware_settings=ability.get_middleware_settings("middleware_wrapped_test_action", TimeLimitedActionMiddleware),
                                                         last_use_times=old_last_use_times[:])
        assert set(res) < set(old_last_use_times) # purged
        del res, old_last_use_times
        # data was touched, even if not really changed in place

        assert ability.middleware_wrapped_callable1(False)
        with raises_with_content(NormalUsageError, "waiting period"):
            ability.middleware_wrapped_callable2(False)
        assert ability.non_middleware_action_callable(None)

        assert self._flatten_explanations(ability.get_middleware_data_explanations(action_name="middleware_wrapped_test_action"))

        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED1") == 8
        assert self.dm.get_event_count("INSIDE_MIDDLEWARE_WRAPPED2") == 1
        assert self.dm.get_event_count("INSIDE_NON_MIDDLEWARE_ACTION_CALLABLE") == 1
        self.dm.clear_all_event_stats()

        ability.reset_test_settings("middleware_wrapped_test_action", TimeLimitedActionMiddleware,
                                    dict(waiting_period_mn=3, max_uses_per_period=50)) # to please coherence checking, after our rough changes


    def test_action_middleware_rollback_on_error(self):

        self.dm.update_permissions("guy1", PersistentList(self.dm.PERMISSIONS_REGISTRY))

        view_url = neutral_url_reverse(views.world_scan)
        request = self.factory.post(view_url, data=dict(_action_="scan_form", item_name="statue")) # has no scanning settings
        request.datamanager._set_user("guy1")

        world_scan = request.datamanager.instantiate_ability("world_scan")

        old_account = request.datamanager.get_character_properties("guy1")["account"]

        # we break the ability
        def broken(*args, **kwargs):
            raise NormalUsageError(u"this item can't be analyzed")
        assert world_scan._compute_scanning_result_or_none
        world_scan._compute_scanning_result_or_none = broken

        res = world_scan(request)

        assert res.status_code == 200
        #print(res.content.decode("utf8"))
        assert u"this item can&#39;t be analyzed" in res.content.decode("utf8")
        assert request.datamanager.get_character_properties("guy1")["account"] == old_account


        # now success case just to be sure
        request = self.factory.post(view_url, data=dict(_action_="scan_form", item_name="sacred_chest"))
        request.datamanager._set_user("guy1")
        world_scan = request.datamanager.instantiate_ability("world_scan")

        res = world_scan(request)
        assert res.status_code == 200
        print(res.content.decode("utf8"))
        assert u"World scan submission in progress" in res.content.decode("utf8")

        assert request.datamanager.get_character_properties("guy1")["account"] < old_account



    def test_action_settings_overrides(self):

        self.dm.update_permissions("guy1", PersistentList(self.dm.PERMISSIONS_REGISTRY))

        view_url = neutral_url_reverse(views.world_scan)

        request = self.factory.post(view_url, data=dict(_action_="scan_form", item_name="sacred_chest"))
        world_scan = request.datamanager.instantiate_ability("world_scan")

        other_user = random.choice(("guy2", "guy3"))
        request.datamanager._set_user(other_user)
        settings = world_scan.get_middleware_settings("scan_form", CostlyActionMiddleware, ensure_active=True)
        assert settings == dict(money_price=115,  # GLOBAL SETTINGS
                                 gems_price=234,
                                 is_active=True)

        request.datamanager._set_user("guy1")
        settings = world_scan.get_middleware_settings("scan_form", CostlyActionMiddleware, ensure_active=True)
        assert settings == dict(money_price=888,  # PRIVATE OVERRIDES
                                 gems_price=777,
                                 is_active=True)

        private_data = world_scan.get_private_middleware_data("scan_form", CostlyActionMiddleware)
        del private_data["settings_overrides"]["money_price"]
        request.datamanager.commit()
        settings = world_scan.get_middleware_settings("scan_form", CostlyActionMiddleware, ensure_active=True)
        # we check that it's well a MERGING of different settings layers
        assert settings == dict(money_price=115,  # GLOBAL SETTINGS
                                 gems_price=777,
                                 is_active=True)  # PRIVATE OVERRIDE

        request.datamanager._set_user("master")
        settings = world_scan.get_middleware_settings("scan_form", CostlyActionMiddleware, ensure_active=False)
        assert settings == dict(money_price=115,  # ALWAYS GLOBAL SETTINGS ONLY FOR MASTER
                                 gems_price=234,
                                 is_active=True)



class TestSpecialAbilities(BaseGameTestCase):

    def test_generic_ability_features(self):
        # ability is half-view half-datamanager, so beware about zodb sessions...

        assert AbstractAbility.__call__ == AbstractGameView.__call__ # must not be overlaoded, since it's decorated to catch exceptions

        assert AbstractAbility.__call__._is_under_readonly_method # NO transaction_watcher, must be available in readonly mode too

        assert AbstractAbility.execute_game_action_callback._is_under_transaction_watcher
        assert AbstractAbility.perform_lazy_initializations._is_under_transaction_watcher # just for tests...
        assert AbstractAbility.process_admin_request._is_under_transaction_watcher


    @for_ability(runic_translation)
    def test_runic_translation(self):

        # TODO - NEED TO WEBTEST BLOCKING OF GEMS NUT NOT NON-OWNED ITEMS

        assert not self.dm.get_global_parameter("disable_automated_ability_responses")

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
        translated_tokens = runic_translation._try_translating_runes(decoded_rune_string, translator=translator,
                                                                     random_words=random_words, random_seed="hhh")

        self.assertEqual(len(translated_tokens), 4, translated_tokens)
        self.assertEqual(translated_tokens[0:2], ["welcome", "people"])
        for translated_token in translated_tokens[2:4]:
            self.assertTrue(translated_token in random_words)


        translated_tokens_bis = runic_translation._try_translating_runes(decoded_rune_string, translator=translator,
                                                                         random_words=random_words, random_seed="hhh")
        assert translated_tokens_bis == translated_tokens # random generator is initialized with same seed!

        translated_tokens_ter = runic_translation._try_translating_runes(decoded_rune_string, translator=translator,
                                                                         random_words=random_words, random_seed="dfsdfsdf")
        assert translated_tokens_ter != translated_tokens # random generator is initialized with different seed!


        rune_item = "sacred_chest"
        translation_settings = runic_translation.get_ability_parameter("references")[rune_item]

        transcription_attempt = translation_settings["decoding"] # '|' and '#'symbols are automatically cleaned
        expected_result = runic_translation._normalize_string(translation_settings["translation"].replace("#", " ").replace("|", " "))
        translation_result = runic_translation._translate_rune_message(rune_item, transcription_attempt)
        self.assertEqual(translation_result, expected_result)

        translation_result = runic_translation._translate_rune_message(item_name=None, rune_transcription=transcription_attempt)
        self.assertNotEqual(translation_result, expected_result) # NO auto detection of item as sacred chest


        assert runic_translation._get_closest_item_name_or_none("sa to | ta ka") == "statue" # not always sacred_chest, as we check

        self._set_user("guy1")
        runic_translation.process_translation(transcription_attempt)

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["recipient_emails"], ["guy1@pangea.com"])
        self.assertTrue("translation" in msg["body"].lower())
        assert "master" not in msg["has_read"]
        assert "master" not in msg["has_starred"]

        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["sender_email"], "guy1@pangea.com")
        self.assertTrue(transcription_attempt.strip() in msg["body"], (transcription_attempt, msg["body"]))
        self.assertTrue(self.dm.get_global_parameter("master_login") in msg["has_read"])
        assert "master" in msg["has_read"] # useless request
        assert "master" not in msg["has_starred"]

        self.dm.set_global_parameter("disable_automated_ability_responses", True)

        runic_translation.process_translation(transcription_attempt)
        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 2) # REQUEST is well generated
        msg = msgs[-1]
        assert "master" not in msg["has_read"] # needs answer by game master
        assert "master" in msg["has_starred"]
        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1) # unchanged, no additional RESPONSE

        runic_translation.settings["references"] = utilities.PersistentMapping()
        runic_translation.commit()
        assert runic_translation._get_closest_item_name_or_none("sa to | ta ka") == None  # no items available at all


        self.dm.set_global_parameter("disable_automated_ability_responses", False)
        runic_translation.process_translation(transcription_attempt)
        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 3) # REQUEST is well generated
        msg = msgs[-1]
        assert "master" not in msg["has_read"] # needs answer by game master
        assert "master" in msg["has_starred"]
        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1) # unchanged, no additional RESPONSE



    @for_ability(house_locking)
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


    def test_mercenaries_hiring(self):

        self._set_user("guy1")
        mercenaries_hiring = self.dm.instantiate_ability("mercenaries_hiring")
        mercenaries_hiring.perform_lazy_initializations() # normally done during request processing

        self._reset_messages()

        assert not mercenaries_hiring.has_remote_agent("Baynon")

        mercenaries_hiring.hire_remote_agent("Baynon")

        assert mercenaries_hiring.has_remote_agent("Baynon")

        with pytest.raises(UsageError):
            mercenaries_hiring.hire_remote_agent("Baynon")

        assert mercenaries_hiring.has_remote_agent("Baynon")

        assert not self.dm.get_all_queued_messages()
        assert not self.dm.get_all_dispatched_messages()


    def ___test_deprecated_agent_hiring(self):
        FIXME
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

        new_queue = self.dm.get_all_dispatched_messages()
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

        new_queue = self.dm.get_all_dispatched_messages()
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


    def ___test_akarith_attack(self):
        self._reset_messages()

        cities = self.dm.get_locations().keys()[0:5]

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        self.dm.trigger_akarith_attack("guy2", cities[3], "Please annihilate this city.")

        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        new_queue = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(new_queue), 1)

        msg = new_queue[0]
        self.assertEqual(msg["sender_email"], "guy2@akaris.com", msg) # we MUST use a dummy email to prevent forgery here
        self.assertEqual(msg["recipient_emails"], ["akaris-army@special.com"], msg)
        self.assertTrue(msg["is_certified"], msg)
        self.assertTrue("annihilate" in msg["body"].lower())
        self.assertTrue("***" in msg["body"].lower())


    @for_ability(wiretapping_management)
    def test_wiretapping_management(self):

        self._reset_messages()

        self._set_user("guy1")

        char_names = self.dm.get_character_usernames()

        wiretapping = self.dm.instantiate_ability("wiretapping")
        wiretapping.perform_lazy_initializations() # normally done during request processing

        assert wiretapping.get_wiretapping_slots_count() == 0
        for i in range(3):
            wiretapping.purchase_wiretapping_slot()
        assert wiretapping.get_wiretapping_slots_count() == 3

        wiretapping.change_current_user_wiretapping_targets(PersistentList())
        self.assertEqual(wiretapping.get_wiretapping_targets(), [])

        wiretapping.change_current_user_wiretapping_targets([char_names[0], char_names[0], char_names[1]])

        self.assertEqual(set(wiretapping.get_wiretapping_targets()), set([char_names[0], char_names[1]]))
        self.assertEqual(wiretapping.get_listeners_for(char_names[1]), ["guy1"])

        self.assertRaises(UsageError, wiretapping.change_current_user_wiretapping_targets, ["dummy_name"])
        self.assertRaises(UsageError, wiretapping.change_current_user_wiretapping_targets, [char_names[i] for i in range(wiretapping.get_wiretapping_slots_count() + 1)])

        self.assertEqual(set(wiretapping.get_wiretapping_targets()), set([char_names[0], char_names[1]])) # didn't change
        self.assertEqual(wiretapping.get_listeners_for(char_names[1]), ["guy1"])

        # SSL/TLS protection purchase
        assert not self.dm.get_confidentiality_protection_status()
        wiretapping.purchase_confidentiality_protection()
        assert self.dm.get_confidentiality_protection_status()
        with pytest.raises(UsageError):
            wiretapping.purchase_confidentiality_protection() # only possible once
        assert self.dm.get_confidentiality_protection_status()

        self._set_user("guy1")



    def test_world_scan(self):

        # TODO - NEED TO WEBTEST BLOCKING OF GEMS AND NON-OWNED ITEMS

        assert not self.dm.get_global_parameter("disable_automated_ability_responses")

        self._reset_django_db()
        self._reset_messages()

        assert self.dm.data["abilities"]["world_scan"]["settings"]["result_delay"]
        self.dm.data["abilities"]["world_scan"]["settings"]["result_delay"] = 0.03 / 45 # flexible time!
        self.dm.commit()

        scanner = self.dm.instantiate_ability("world_scan")
        scanner.perform_lazy_initializations() # normally done during request processing
        self._set_user("guy1")

        assert "statue" in self.dm.get_all_items()
        assert scanner._compute_scanning_result_or_none("statue") is None  # not analyzable

        res = scanner._compute_scanning_result_or_none("sacred_chest")
        self.assertEqual(res, ["Alifir", "Baynon"])

        with pytest.raises(AssertionError):
            scanner.process_world_scan_submission("several_misc_gems") # no gems allowed here

        # ##self.assertEqual(self.dm.get_global_parameter("scanned_locations"), [])

        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 0)
        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        # AUTOMATED SCAN #
        scanner.process_world_scan_submission("sacred_chest")
        # print datetime.utcnow(), "----", self.dm.data["scheduled_actions"]


        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        # print(">>>>>>", msg)
        self.assertEqual(msg["recipient_emails"], ["guy1@pangea.com"])
        self.assertTrue("scanning" in msg["body"].lower())
        # print(msg["body"])
        self.assertTrue("Alifir" in msg["body"])
        assert "master" not in msg["has_read"]
        assert "master" not in msg["has_starred"]

        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["sender_email"], "guy1@pangea.com")
        self.assertTrue("scan" in msg["body"])
        self.assertTrue(self.dm.get_global_parameter("master_login") in msg["has_read"])
        assert "master" in msg["has_read"]
        assert "master" not in msg["has_starred"]

        self.dm.set_global_parameter("disable_automated_ability_responses", True)
        scanner.process_world_scan_submission("sacred_chest")
        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 2) # REQUEST is well generated
        msg = msgs[-1]
        assert "master" not in msg["has_read"] # needs answer
        assert "master" in msg["has_starred"]
        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1) # unchanged, no additional RESPONSE

        self.dm.set_global_parameter("disable_automated_ability_responses", False)
        scanner.process_world_scan_submission("statue")  # has no locations specified
        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 3) # REQUEST is well generated
        msg = msgs[-1]
        pprint(msg)
        assert "master" not in msg["has_read"] # needs answer by game master
        assert "master" in msg["has_starred"]
        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1) # unchanged, no additional RESPONSE



        res = self.dm.process_periodic_tasks()

        assert res == {"messages_dispatched": 0, "actions_executed": 0}

        time.sleep(3)

        self.assertEqual(self.dm.process_periodic_tasks(), {"messages_dispatched": 1, "actions_executed": 0})

        self.assertEqual(self.dm.get_event_count("DELAYED_ACTION_ERROR"), 0)
        self.assertEqual(self.dm.get_event_count("DELAYED_MESSAGE_ERROR"), 0)

        # ##scanned_locations = self.dm.get_global_parameter("scanned_locations")
        # ##self.assertTrue("Alifir" in scanned_locations, scanned_locations)






        ''' does not work, needs authentication
        url = sssss(views.world_scan, kwargs=dict(game_instance_id=TEST_GAME_INSTANCE_ID))

        self._set_user("guy1")

        response = self.client.get(url)
        assert response.status_code == 302

        self.dm.update_permissions(permissions=self.dm.PERMISSIONS_REGISTRY)
        response = self.client.get(url)
        assert response.status_code == 200
        '''
    
    def test_telecom_investigations(self):
        
        all_characters = self.dm.get_character_usernames()
        
        characters_with_conversations = self.dm.get_character_usernames()
        characters_with_conversations.remove("my_npc")
        
        telecom = self.dm.instantiate_ability("telecom_investigation")
        telecom.perform_lazy_initializations()
        self._reset_messages()
        
        
        # message initialization
        
        email_guy1 = self.dm.get_character_email("guy1")
        email_guy2 = self.dm.get_character_email("guy2")
        email_guy3 = self.dm.get_character_email("guy3")
        email_guy4 = self.dm.get_character_email("guy4")
        email_external = sorted(self.dm.global_contacts.keys())[0]
        
        msg_id1 = self.dm.post_message(sender_email = email_guy1, recipient_emails = email_external, subject = "test", body = "test")
        msg1 = self.dm.get_dispatched_message_by_id(msg_id1)
        
        msg_id2 = self.dm.post_message(sender_email = email_guy3, recipient_emails = email_guy4, subject = "test2", body = "test2")
        msg2 = self.dm.get_dispatched_message_by_id(msg_id2)
        
        time.sleep(1)
        
        msg_id3 = self.dm.post_message(sender_email = email_guy4, recipient_emails = email_guy3, subject = msg2["subject"], body = "test3", parent_id = msg_id2)
        msg3 = self.dm.get_dispatched_message_by_id(msg_id3)
        
        msg_id4 = self.dm.post_message(sender_email = email_guy1, recipient_emails = email_guy2, subject = "sujet", body = "mon message")
        msg4 = self.dm.get_dispatched_message_by_id(msg_id4)
        
        
        # testing extract_conversation_summary utility:
        
        assert telecom.extract_conversation_summary("guy4")
        conversation_summary = telecom.extract_conversation_summary("guy4")
        
        assert type(conversation_summary) is ListType
        
        
        # guy4 has 2 conversations, we must have len = 2, therefore:
        
        conversation_summary = telecom.extract_conversation_summary("guy4")
        self.assertEqual(len(conversation_summary), 2)
        
        # NPC doesn't have any conversations, therefore:
        
        conversation_summary = telecom.extract_conversation_summary("my_npc")
        self.assertEqual(conversation_summary, [])
        
        
        for character in all_characters:
            
            conversation_summary = telecom.extract_conversation_summary(character)
            all_character_messages = self.dm.get_user_related_messages(character, None, None)
            conversations_by_character = self.dm.sort_messages_by_conversations(all_character_messages)
            self.assertEqual(len(conversation_summary),len(conversations_by_character))
        
        # time check:
        
        
        conversation_summary = telecom.extract_conversation_summary("guy4")
        for conversation in conversation_summary:
            
            first_message_date = conversation["first_message"]
            last_message_date = conversation["last_message"]
            assert not first_message_date > last_message_date
        
        
        for character in all_characters:
            
            conversation_summary = telecom.extract_conversation_summary(character)
            for conversation in conversation_summary:
                
                first_message_date = conversation["first_message"]
                last_message_date = conversation["last_message"]
                assert not first_message_date > last_message_date
        
        
        # testing conversation_formatting utility:
        
        
        context_list = telecom.extract_conversation_summary("guy4")
        assert telecom.conversation_formatting(context_list)
        conversation_formatting = telecom.conversation_formatting(context_list)
        
        assert type(conversation_formatting) is UnicodeType
        
        
        for character in characters_with_conversations :
            
            context_list = telecom.extract_conversation_summary(character)
            assert telecom.conversation_formatting(character)
            assert telecom.conversation_formatting(context_list) != "Target has no conversation!"
                
                
        context_list = telecom.extract_conversation_summary("my_npc")
        self.assertEqual(telecom.conversation_formatting(context_list), "Target has no conversation!")
                
                
        #Checking the body contents:
                
        context_list = telecom.extract_conversation_summary("guy4")
        conversation_formatting = telecom.conversation_formatting(context_list)
                
        self.assertTrue("test" in conversation_formatting)
        self.assertTrue("test2" in conversation_formatting)
        self.assertTrue("Participants" in conversation_formatting)
        self.assertTrue("guy4@pangea.com" in conversation_formatting)
        self.assertTrue("guy3@pangea.com" in conversation_formatting)
        self.assertTrue("[auction-list]@pangea.com" in conversation_formatting)
        self.assertTrue("1 messages" in conversation_formatting)
        self.assertTrue("2 messages" in conversation_formatting)
        self.assertFalse("sujet" in conversation_formatting)
        self.assertFalse("mon message" in conversation_formatting)
        self.assertFalse("4 messages" in conversation_formatting)
        self.assertFalse("guy2@pangea.com" in conversation_formatting)
                
                
        for character in characters_with_conversations:
                    
            context_list = telecom.extract_conversation_summary(character)
            conversation_formatting = telecom.conversation_formatting(context_list)
            all_character_messages = self.dm.get_user_related_messages(character, None, None)
            conversations_by_character = self.dm.sort_messages_by_conversations(all_character_messages)
                                    
            for conversation in conversations_by_character:
                
                for message in conversation:
                                            
                    self.assertTrue(message["subject"] in conversation_formatting) #watch out with response emails that have "RE" in subject; assert becomes false
                    self.assertTrue(message["sender_email"] in conversation_formatting)
                    self.assertTrue(", ".join(str(e) for e in message["recipient_emails"]) in conversation_formatting)
                    self.assertTrue("%(X)s messages" % dict(X=len(conversation)))
                                                    
                                                    
        # testing end to end ability:
                                                    
        all_other_characters = all_characters
        self._set_user("guy1")
        all_other_characters.remove(self.dm.get_username_from_official_name(self.dm.get_official_name()))

        assert type(telecom.process_telecom_investigation("guy2")) is UnicodeType
    
    
        for character in all_other_characters:
            
            assert telecom.process_telecom_investigation(character)
            self.assertEqual(telecom.process_telecom_investigation(character), "Telecom is in process, you will receive an e-mail with the intercepted messages soon!")
    
        # checking amount of e-mails during process:
        
        initial_length_sent_msgs = len(self.dm.get_all_dispatched_messages())
        
        self.assertEqual(len(self.dm.get_all_dispatched_messages()), initial_length_sent_msgs + 0)
        
        telecom.process_telecom_investigation("guy4")
        
        msgs = self.dm.get_all_dispatched_messages()
        
        self.assertEqual(len(msgs), initial_length_sent_msgs + 2)
        # we have a "+2" because there are 2 sent messages : one for requesting the investigation and one for displaying the investigation results.
        
        
        self._reset_messages()
        
        for character in all_other_characters:
            
            initial_length_sent_msgs = len(self.dm.get_all_dispatched_messages())
            telecom.process_telecom_investigation(character)
            msgs = self.dm.get_all_dispatched_messages()
            self.assertEqual(len(msgs), initial_length_sent_msgs + 2)
        
        
        # checking the e-mail subject, body and participants:
        
        self._reset_messages()
        telecom.process_telecom_investigation("guy4")
        
        
        # investigation request e-mail:
        
        msgs = self.dm.get_all_dispatched_messages()
        msg = msgs[-2]
        self.assertEqual(msg["sender_email"],"guy1@pangea.com")
        self.assertEqual(msg["recipient_emails"], ["investigator@spies.com"])
        self.assertEqual(msg["body"], "Please look for anything you can find about this person.")
        self.assertEqual(msg["subject"], "Investigation Request - Kha")
        
        
        # investigation results e-mail:
        
        context_list = telecom.extract_conversation_summary("guy4")
        body = telecom.conversation_formatting(context_list)
        
        msg = msgs[-1]
        self.assertEqual(msg["sender_email"], "investigator@spies.com")
        assert msg["recipient_emails"] == [u'guy1@pangea.com']
        self.assertEqual(msg["body"], body)
        self.assertEqual(msg["subject"], "<Investigation Results for Kha>")
        
        
        # test for all users except "ourself":
        
        for character in all_other_characters:
            self._reset_messages()
            telecom.process_telecom_investigation(character)
            target_name = self.dm.get_official_name(character)
            msgs = self.dm.get_all_dispatched_messages()
            
            
            # investigation request e-mail:
            
            msg = msgs[-2]
            assert msg["sender_email"] == "guy1@pangea.com"
            assert msg["recipient_emails"] == ["investigator@spies.com"]
            assert msg["body"] == "Please look for anything you can find about this person."
            assert msg["subject"] == (("Investigation Request - %(target_name)s") % dict(target_name=target_name))
            
            
            # investigation results e-mail:
            
            context_list = telecom.extract_conversation_summary(character)
            body = telecom.conversation_formatting(context_list)
            
            msg = msgs[-1]
            assert msg["sender_email"] == "investigator@spies.com"
            assert msg["recipient_emails"] == [u'guy1@pangea.com']
            assert msg["body"] == body
            assert msg["subject"] == (("<Investigation Results for %(target_name)s>") % dict(target_name=target_name))
    
    

    def __test_telecom_investigations(self):

        FIXME

        # no reset of initial messages

        initial_length_queued_msgs = len(self.dm.get_all_queued_messages())
        initial_length_sent_msgs = len(self.dm.get_all_dispatched_messages())

        ability = self.dm.instantiate_ability("telecom_investigation")
        ability.perform_lazy_initializations() # normally done during request processing

        """
        assert self.dm.data["abilities"] ["telecom_investigation"]["settings"]["result_delay"]
        self.dm.data["abilities"] ["world_scan"]["settings"]["result_delay"] = 0.03 / 45 # flexible time!
        self.dm.commit()
        """

        scanner = self.dm.instantiate_ability("world_scan")
        scanner.perform_lazy_initializations() # normally done during request processing
        self._set_user("guy1")


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
        parts1 = set(u"Depuis , notre Ordre Akarite fouille Ciel Terre retrouver Trois Orbes".split())
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

        msgs = self.dm.get_all_dispatched_messages()
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



    def test_matter_analysis(self):

        # TODO - NEED TO WEBTEST BLOCKING OF GEMS AND NON-OWNED ITEMS

        assert not self.dm.get_global_parameter("disable_automated_ability_responses")

        self._reset_messages()

        assert self.dm.data["abilities"] ["matter_analysis"]["settings"]["result_delay"]
        self.dm.data["abilities"] ["matter_analysis"]["settings"]["result_delay"] = 0.03 / 45 # flexible time!
        self.dm.commit()

        analyser = self.dm.instantiate_ability("matter_analysis")
        analyser.perform_lazy_initializations() # normally done during request processing
        self._set_user("guy1")
        self.dm.transfer_object_to_character("sacred_chest", "guy1")
        self.dm.transfer_object_to_character("several_misc_gems", "guy1")

        assert "statue" in self.dm.get_all_items()
        assert analyser._compute_analysis_result_or_none("statue") is None  # not analyzable

        res = analyser._compute_analysis_result_or_none("sacred_chest")
        self.assertEqual(res, "same, here stuffs about *sacred* chest")

        with pytest.raises(AssertionError):
            analyser.process_object_analysis("several_misc_gems") # no gems allowed here

        self.assertEqual(len(self.dm.get_all_dispatched_messages()), 0)
        self.assertEqual(len(self.dm.get_all_queued_messages()), 0)

        # AUTOMATED SCAN #
        analyser.process_object_analysis("sacred_chest")


        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        # print(">>>>>>", msg)
        self.assertEqual(msg["recipient_emails"], ["guy1@pangea.com"])
        self.assertTrue("*sacred* chest" in msg["body"].lower())
        assert "master" not in msg["has_read"]
        assert "master" not in msg["has_starred"]

        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertEqual(msg["sender_email"], "guy1@pangea.com")
        self.assertTrue("Please analyse" in msg["body"])
        self.assertTrue(self.dm.get_global_parameter("master_login") in msg["has_read"])
        assert "master" in msg["has_read"]
        assert "master" not in msg["has_starred"]


        self.dm.set_global_parameter("disable_automated_ability_responses", True)

        analyser.process_object_analysis("sacred_chest")
        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 2) # REQUEST is well generated
        msg = msgs[-1]
        assert "master" not in msg["has_read"]
        assert "master" in msg["has_starred"]
        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1) # unchanged, no additional RESPONSE

        self.dm.set_global_parameter("disable_automated_ability_responses", False)
        analyser.process_object_analysis("statue")
        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 3) # REQUEST is well generated
        msg = msgs[-1]
        assert "master" not in msg["has_read"]
        assert "master" in msg["has_starred"]
        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 1) # unchanged, no additional RESPONSE


        res = self.dm.process_periodic_tasks()

        assert res == {"messages_dispatched": 0, "actions_executed": 0}

        time.sleep(3)

        self.assertEqual(self.dm.process_periodic_tasks(), {"messages_dispatched": 1, "actions_executed": 0})

        self.assertEqual(self.dm.get_event_count("DELAYED_ACTION_ERROR"), 0)
        self.assertEqual(self.dm.get_event_count("DELAYED_MESSAGE_ERROR"), 0)










        ''' DISABLED FOR NOW
        # MANUAL SCAN #

        self.dm.process_scanning_submission("scanner", "", "dummydescription2")

        msgs = self.dm.get_all_queued_messages()
        self.assertEqual(len(msgs), 0) # still empty

        msgs = self.dm.get_all_dispatched_messages()
        self.assertEqual(len(msgs), 3) # 2 messages from previous operation, + new one
        msg = msgs[2]
        self.assertEqual(msg["sender_email"], "scanner@teldorium.com")
        self.assertTrue("scan" in msg["body"])
        self.assertTrue("dummydescription2" in msg["body"])
        self.assertFalse(self.dm.get_global_parameter("master_login") in msg["has_read"])

        '''


    def test_artificial_intelligence(self): # TODO PAKAL PUT BOTS BACK!!!

        if not config.ACTIVATE_AIML_BOTS:
            pytest.skip("No AIML bot is configured for testing")

        assert not artificial_intelligence_mod.DJINN_PROXY_IS_INITIALIZED
        assert not artificial_intelligence_mod.DJINN_PROXY # LAZY LOADING

        self._set_user("guy1")

        ai = self.dm.instantiate_ability("artificial_intelligence")
        ai.perform_lazy_initializations() # normally done during request processing

        bot_name = "Pay Rhuss" # self.dm.data["AI_bots"]["Pay Rhuss"].keys()[0]
        # print bot_name, " --- ",self.dm.data["AI_bots"]["bot_properties"]

        res = ai.get_bot_response(bot_name, "hello")
        self.assertTrue("hi" in res.lower())

        res = ai.get_bot_response(bot_name, "What's your name ?")
        self.assertTrue(bot_name.lower() in res.lower())

        res = ai.get_bot_response(bot_name, "What's my name ?")
        self.assertTrue("guy1" in res.lower())

        res = ai.get_bot_history(bot_name)
        self.assertEqual(len(res), 2)
        self.assertEqual(len(res[0]), 3)
        self.assertEqual(len(res[0]), len(res[1]))

        res = ai.get_bot_response(bot_name, "RESPONSEABOUTALPHAORB").lower()
        self.assertTrue("sharing the same meal" in res, res) # specific answer for that bot name

        res = ai.get_bot_response(bot_name, "SYNONYMRESPONSEABOUTALPHAORB").lower()
        self.assertTrue("sharing the same meal" in res, res) # substitutions work fine

        assert artificial_intelligence_mod.DJINN_PROXY_IS_INITIALIZED
        assert artificial_intelligence_mod.DJINN_PROXY



class TestGameViews(BaseGameTestCase):


    def test_3D_items_display(self):

        for autoreverse in (True, False):

            viewer_settings = dict(levels=2,
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
                                       "openinglogo/crystal0048.jpg"], ]
            expected_image_urls = [[game_file_url(rel_path) for rel_path in level] for level in rel_expected_image_urls]

            if autoreverse:
                for id, value in enumerate(expected_image_urls):
                    expected_image_urls[id] = value + list(reversed(value))


            # pprint.pprint(display_data["image_urls"])
            # pprint.pprint(expected_image_urls)

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


    @for_gameview(friendship_management)
    def test_friendship_management(self):

        view = self.dm.instantiate_game_view("friendship_management")

        self._set_user("guy1")

        with pytest.raises(AbnormalUsageError):
            assert "Unexisting friendship" in view.do_cancel_friendship("guy2")

        assert "friendship proposal" in view.do_propose_friendship("guy2")
        assert "friendship proposal" in view.do_cancel_friendship("guy2") # cancel proposal only
        assert "friendship proposal" in view.do_propose_friendship("guy2")
        assert "friendship proposal" in view.do_cancel_proposal("guy2")
        assert "friendship proposal" in view.do_propose_friendship("guy2")
        assert "friendship proposal" in view.do_propose_friendship("guy4")
        assert "friendship proposal" in view.do_propose_friendship("guy3")
        with pytest.raises(UsageError):
            view.do_propose_friendship("guy2") # duplicate proposal

        self._set_user("guy2")
        assert "now friend with" in view.do_propose_friendship("guy1")
        with pytest.raises(UsageError):
            view.do_propose_friendship("guy1") # already friends
        with pytest.raises(UsageError):
            view.do_accept_friendship("guy1") # already friends

        self._set_user("guy3")
        assert "now friend" in view.do_accept_friendship("guy1")
        assert "friendship proposal" in view.do_accept_friendship("guy4")
        with pytest.raises(UsageError): # too young friendship
            view.do_cancel_friendship("guy1")

        self._set_user("guy4")
        assert "now friend" in view.do_accept_friendship("guy1")

        for pair, params in self.dm.data["friendships"]["sealed"].items():
            params["acceptance_date"] -= timedelta(hours=30) # delay should be 24h in dev
            self.dm.commit()

        self._set_user("guy3")
        assert "friendship with" in view.do_cancel_friendship("guy1")

        if random.choice((True, False)):
            self._set_user("guy1") # whatever side of the friendship acts...
            assert "friendship with" in view.do_cancel_proposal("guy4")
        else:
            self._set_user("guy4")
            assert "friendship with" in view.do_cancel_proposal("guy1")

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

                        address_book=[],
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





class TestAdminActions(BaseGameTestCase):

    def test_admin_dashboard_interface(self):

        dashboard_url = neutral_url_reverse(views.admin_dashboard)
        def gen_request():
            return self.factory.post(dashboard_url, dict(target_form_id="admin_dashboard.set_game_pause_state",
                                                        is_paused="1",
                                                        _ability_form="pychronia_game.views.admin_views.admin_dashboard_mod.GamePauseForm"))


        # build complete request (without auto-checking DM)
        request = gen_request()
        dashboard = request.datamanager.instantiate_ability("admin_dashboard")

        assert request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION") == 0
        assert request.datamanager.is_game_started()

        request.datamanager._set_user(None) # anonymous
        response = dashboard(request)
        assert response.status_code == 302 # redirect
        assert request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION") == 0
        assert request.datamanager.is_game_started()

        request.datamanager._set_user(None, impersonation_target="master", impersonation_writability=False, is_superuser=True) # non-writable impersonated master
        response = dashboard(request)
        assert response.status_code == 200 # form data is just discarded
        assert u"not allowed to submit changes" in response.content.decode("utf8")
        assert request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION") == 0
        assert request.datamanager.is_game_started()
        assert request.method == "GET" # reinterpreted
        assert not request.POST


        # NOW SUCCESSFULL ATTEMPT #

        request = gen_request()
        dashboard = request.datamanager.instantiate_ability("admin_dashboard")

        assert request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION") == 0
        assert request.datamanager.is_game_started()

        choice = random.choice((True, False))
        if choice:
            request.datamanager._set_user("master")
        else:
            request.datamanager._set_user(None, impersonation_target="master", impersonation_writability=True, is_superuser=True) # writable impersonated master
        assert request.datamanager.is_master()
        request.datamanager.user.discard_notifications()
        response = dashboard(request)
        assert response.status_code == 200
        #print (response.content.decode("utf8"))

        assert request.datamanager.get_event_count("DO_PROCESS_FORM_SUBMISSION") == 1
        assert not request.datamanager.is_game_started() # well applied










