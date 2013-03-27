# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


import os, sys, pytest, unittest, traceback, pprint


## TEST CONFIGURATION ##

os.environ["DJANGO_SETTINGS_MODULE"] = "rpgweb.tests._test_settings"


from rpgweb.common import *
from rpgweb.datamanager.datamanager_administrator import create_game_instance, \
    retrieve_game_instance, game_instance_exists, reset_zodb_structure
import rpgweb.datamanager as dm_module
from rpgweb.datamanager import *
from rpgweb.datamanager.datamanager_modules import *

import rpgweb.middlewares
import rpgweb.views
from rpgweb.datamanager.abstract_game_view import AbstractGameView, register_view
# we want django-specific checker methods
# do NOT use the django.test.TestCase version, with SQL session management
#from django.utils.unittest.case import TestCase
#from django.test.testcases import TransactionTestCase as TestCase
from django.test import TestCase
from django.test.client import Client, RequestFactory
from django.core.handlers.base import BaseHandler
import django.utils.translation

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


# trackers to eventually ensure every module is well tested

def for_datamanager_base(func):
    return func

def for_core_module(klass):
    # TODO - track proper testing of core module
    assert klass in MODULES_REGISTRY, klass
    return lambda func: func

def for_gameview(view):
    # TODO - track proper testing of ability module
    view = getattr(view, "klass", view)
    assert view in GameViews.GAME_VIEWS_REGISTRY.values(), view
    return lambda func: func

def for_ability(view):
    # TODO - track proper testing of gameview module
    view = getattr(view, "klass", view)
    assert view in SpecialAbilities.ABILITIES_REGISTRY.values(), view
    return lambda func: func



TEST_GAME_INSTANCE_ID = "TeStiNg"
ROOT_GAME_URL = "/%s" % TEST_GAME_INSTANCE_ID
HOME_URL = reverse(rpgweb.views.homepage, kwargs={"game_instance_id": TEST_GAME_INSTANCE_ID})

sys.setrecursionlimit(800) # to help detect recursion problems


logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logging.disable(logging.DEBUG) # to be commented if more output is wanted !!!



class RequestMock(RequestFactory):
    def request(self, **request):
        """Constructs a generic request object, INCLUDING middleware modifications."""

        from django.core import urlresolvers


        request = RequestFactory.request(self, **request)
        ###pprint.pprint(request)

        handler = BaseHandler()

        handler.load_middleware()

        for middleware_method in handler._request_middleware:
            #print("APPLYING REQUEST MIDDLEWARE ", middleware_method, file=sys.stderr)
            if middleware_method(request):
                raise Exception("Couldn't create request mock object - "
                                "request middleware returned a response")

        urlconf = settings.ROOT_URLCONF
        urlresolvers.set_urlconf(urlconf)
        resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)

        callback, callback_args, callback_kwargs = resolver.resolve(
                            request.path_info)

        # Apply view middleware
        for middleware_method in handler._view_middleware:
            #print("APPLYING VIEW MIDDLEWARE ", middleware_method, file=sys.stderr)
            response = middleware_method(request, callback, callback_args, callback_kwargs)
            if response:
                raise Exception("Couldn't create request mock object - "
                                "view middleware returned a response")

        return request



@contextlib.contextmanager
def raises_with_content(klass, string):
    with pytest.raises(klass) as exc:
        yield exc
    assert string.lower() in str(exc.value).lower()




class AutoCheckingDM(object):
    """
    Dirty hack to automatically abort the ZODB transaction after each primary call to a datamanager method.

    This helps us ensure that we haven't forgotten the transaction watcher for any modifying operation.
    """

    def __init__(self, dm):
        assert dm.connection # really initialized DM
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
                except GameError:
                    raise
                except Exception, e:
                    print("Abnormal exception seen in AutoCheckingDM:", repr(e), file=sys.stderr)
                    traceback.print_exc()
                    raise
                finally:
                    if real_dm.connection: # i.e not for close() method
                        assert not real_dm.connection._registered_objects, real_dm.connection._registered_objects # AFTER
                return res

            return _checked_method

    def __setattr__(self, name, value):
        return object.__getattribute__(self, "_real_dm").__setattr__(name, value)


@contextlib.contextmanager
def temp_datamanager(game_instance_id, request=None):
    assert game_instance_exists(game_instance_id)
    dm = retrieve_game_instance(game_instance_id, request=request)
    yield dm
    dm.close()




class BaseGameTestCase(TestCase):

    """
    WARNING - when directly modifying "self.dm.data" content, 
    don't forget to commit() after that !!
    """

    def __call__(self, *args, **kwds):
        return unittest.TestCase.run(self, *args, **kwds) # we bypass test setups from django's TestCase, to use py.test instead



    def setUp(self):

        assert settings.DEBUG == True

        django.utils.translation.activate("en") # to test for error messages, just in case...

        reset_zodb_structure()
        create_game_instance(game_instance_id=TEST_GAME_INSTANCE_ID, master_email="dummy@dummy.fr", master_login="master", master_password="ultimate")

        try:

            # need for custom urlconf setup
            if "mobile" in self.__class__.__name__.lower():
                test_http_host = config.MOBILE_HOST_NAMES[0]
            else:
                test_http_host = "localhost:80"

            self.client = Client()
            self.factory = RequestMock(HTTP_HOST=test_http_host)

            self.request = self.factory.get(HOME_URL)
            assert self.request.user
            assert self.request.datamanager.user.datamanager.request # double linking
            assert self.request.session
            assert self.request._messages is not None
            assert self.request.datamanager

            # we mimic messages middleware
            from django.contrib.messages.storage import default_storage
            self.request._messages = default_storage(self.request)

            self.dm = self.request.datamanager
            assert self.dm.is_initialized
            assert self.dm.connection

            self.dm.clear_all_event_stats()
            self.dm.check_database_coherency() # important
            assert self.dm.get_event_count("BASE_CHECK_DB_COHERENCY_PUBLIC_CALLED") == 1 # no bypassing because of wrong override

            self.dm.set_game_state(True)
            self.dm.set_activated_game_views(self.dm.get_activable_views().keys()) # QUICK ACCESS FIXTURE
            self.dm.clear_all_event_stats()

            #self.default_player = self.dm.get_character_usernames()[0]
            #self._set_user(self.TEST_LOGIN)

            self.initial_msg_sent_length = len(self.dm.get_all_dispatched_messages())
            self.initial_msg_queue_length = len(self.dm.get_all_queued_messages())

            # comment this to have eclipse's autocompletion to work for datamanager anyway
            self.dm = AutoCheckingDM(self.dm) # protection against uncommitted, pending changes

        except Exception, e:
            print(">>>>>>>>>", repr(e))
            self.tearDown(check=False) # cleanup of connection
            raise


    def tearDown(self, check=True):
        if hasattr(self, "dm"):
            if check:
                pass### self.dm.check_database_coherency()
            self.dm.close()
            self.dm = None



    def _set_user(self, username, has_write_access=True):
        """
        Here *username* might be "master" or None, too. 
        """
        self.dm._set_user(username, has_write_access=has_write_access)


    def _reset_messages(self):
        self.dm.messaging_data["messages_dispatched"] = PersistentList()
        self.dm.messaging_data["messages_queued"] = PersistentList()
        self.dm.commit()


    def _reset_django_db(self):
        from django.test.utils import setup_test_environment ## ,???
        from django.core import management
        management.call_command('syncdb', verbosity=0, interactive=False)
        management.call_command('flush', verbosity=0, interactive=False)



