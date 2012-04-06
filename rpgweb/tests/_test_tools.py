# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals



import os, sys, pytest, unittest


## TEST CONFIGURATION ##

os.environ["DJANGO_SETTINGS_MODULE"] = "rpgweb.tests._test_settings"


from rpgweb.common import *

import rpgweb.datamanager as dm_module
from rpgweb.datamanager import *
from rpgweb.datamanager.datamanager_modules import *

import rpgweb.middlewares
import rpgweb.views
from rpgweb.views._abstract_game_view import AbstractGameView
# we want django-specific checker methods
# do NOT use the django.test.TestCase version, with SQL session management
#from django.utils.unittest.case import TestCase 
#from django.test.testcases import TransactionTestCase as TestCase
from django.test import TestCase
from django.test.client import Client, RequestFactory
from django.core.handlers.base import BaseHandler  
import django.utils.translation
from rpgweb.views._abstract_game_view import register_view
from rpgweb.abilities import *

if not config.DB_RESET_ALLOWED:
    raise RuntimeError("Can't launch tests - we must be in a production environment !!")


TEST_ZODB_FILE = config.ZODB_FILE+".test" # let's not conflict with the handle already open in middlewares, on config.ZODB_FILE




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

def for_ability(view):
    # TODO - track proper testing of ability module
    if hasattr(view, "_klass"):
        view = view._klass
    assert view in SpecialAbilities.ABILITIES_REGISTRY.values(), view
    return lambda func: func



TEST_GAME_INSTANCE_ID = "TeStiNg"
ROOT_GAME_URL = "/%s" % TEST_GAME_INSTANCE_ID
HOME_URL = reverse(rpgweb.views.homepage, kwargs={"game_instance_id": TEST_GAME_INSTANCE_ID})

sys.setrecursionlimit(200) # to help detect recursion problems

logging.basicConfig() ## FIXME
logging.disable(0)
logging.getLogger(0).setLevel(logging.DEBUG)





  
class RequestMock(RequestFactory):  
    def request(self, **request):  
        """Constructs a generic request object, INCLUDING middleware modifications.""" 
        
        from django.core import urlresolvers
        
        
        request = RequestFactory.request(self, **request)  
        handler = BaseHandler()  
        
        handler.load_middleware()  
        
        for middleware_method in handler._request_middleware:  
            print("APPLYING REQUEST MIDDLEWARE ", middleware_method, file=sys.stderr)
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
            print("APPLYING VIEW MIDDLEWARE ", middleware_method, file=sys.stderr)
            response = middleware_method(request, callback, callback_args, callback_kwargs)
            if response:
                raise Exception("Couldn't create request mock object - "  
                                "view middleware returned a response")                  
            
        return request  
    
    


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

        logging.basicConfig() # in case ZODB or others have things to say...
    
        self.db = utilities.open_zodb_file(TEST_ZODB_FILE)

        rpgweb.middlewares.ZODB_TEST_DB = self.db # to allow testing views via normal request dispatching

        self.connection = self.db.open()
 
        try: 
            
            self.client = Client()
            self.factory = RequestMock()
            
            self.request = self.factory.get(HOME_URL)
            assert self.request.user
            assert self.request.datamanager.user.request # double linking
            assert self.request.session 
            assert self.request._messages is not None
            assert self.request.datamanager
            
            # we mimic messages middleware
            from django.contrib.messages.storage import default_storage
            self.request._messages = default_storage(self.request)
            
            self.dm = self.request.datamanager
            """dm_module.GameDataManager(game_instance_id=TEST_GAME_INSTANCE_ID,
                                                game_root=self.connection.root(),
                                                request=self.request) # request is used"""

            self.dm.reset_game_data()

            self.dm.check_database_coherency() # important
            assert self.dm.get_event_count("BASE_CHECK_DB_COHERENCY_PUBLIC_CALLED") == 1 # no bypassing because of wrong override
            
            self.dm.set_game_state(True)
            self.dm.set_activated_game_views(self.dm.get_activable_views().keys()) # QUICK ACCESS FIXTURE
            self.dm.clear_all_event_stats()
            
            #self.default_player = self.dm.get_character_usernames()[0]
            #self._set_user(self.TEST_LOGIN)

            self.initial_msg_sent_length = len(self.dm.get_all_sent_messages())
            self.initial_msg_queue_length = len(self.dm.get_all_queued_messages())


            # comment this to have eclipse's autocompletion to work for datamanager anyway
            self.dm = AutoCheckingDM(self.dm) # protection against uncommitted, pending changes

            logging.disable(logging.CRITICAL) # to be commented if more output is wanted !!!

            
        except:
            self.tearDown(check=False) # cleanup of db and connection in any case
            raise


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


    def _set_user(self, username, has_write_access=True):
        """
        Here *username* might be "master" or None, too. 
        """
        self.dm._set_user(username, has_write_access=has_write_access)


    def _reset_messages(self):
        self.dm.data["messages_sent"] = PersistentList()
        self.dm.data["messages_queued"] = PersistentList()
        self.dm.commit()


    def _reset_django_db(self):
        from django.test.utils import setup_test_environment ## ,???
        from django.core import management
        management.call_command('syncdb', verbosity=0, interactive=False)
        management.call_command('flush', verbosity=0, interactive=False)



