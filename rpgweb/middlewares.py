# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from rpgweb.common import *

from django.contrib import auth
from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from django.http import HttpResponseRedirect, HttpResponseServerError, HttpResponse, Http404
import django.core.mail as mail

from .datamanager.datamanager_tools import UsageError
from . import authentication
import rpgweb.datamanager as dm_module







# TOFIX - use real database pool, later on
_database_pool = utilities.open_zodb_file(config.ZODB_FILE)

def _shutdown():
    global _database_pool
    try:
        _database_pool.close()
        time.sleep(0.5) # to help daemon threads stop cleanly, just in case
    except:
        pass # maybe database was already automatically closed
atexit.register(_shutdown) # it should work !


ZODB_TEST_DB = None # may be overwritten during tests, to override normal database

class ZodbTransactionMiddleware(object):

    def process_request(self, request):
        # on exception : normal 500 handling takes place
        pass

    def process_view(self, request, view_func, view_args, view_kwargs):
        # on exception : normal 500 handling takes place

        global _database_pool, ZODB_TEST_DB
        
        assert hasattr(request, 'session'), "The game authentication middleware requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."

        request.processed_view = view_func # useful for computation of game menus 

        if view_kwargs.has_key("game_instance_id"):
            # TOFIX select the proper subtree of ZODB
            # Manage possible errors of wrong game_id !
            ##request.game_instance_id = view_kwargs["game_instance_id"]
            game_instance_id = view_kwargs["game_instance_id"]
            del view_kwargs["game_instance_id"]

            if ZODB_TEST_DB: # we're well in test environment
                DB = ZODB_TEST_DB
            else:
                DB = _database_pool

            connection = DB.open()

            request.datamanager = dm_module.GameDataManager(game_instance_id=game_instance_id, 
                                                            game_root=connection.root()) # TOFIX - discriminate with game_instance_id

            if not request.datamanager.is_initialized():
                raise RuntimeError("ZodbTransactionMiddleware - Game data isn't in initialized state")

            return None



    def process_exception(self, request, exception):
        # on exception : normal 500 handling takes place

        if not isinstance(exception, Http404):
            logging.critical("Exception occurred in view - %r" % exception, exc_info=True)
    
        # we let the exception propagate anyway
        pass


    def process_response(self, request, response):
        # on exception : no response handling occurs, a simple traceback is output !

        try:
            if hasattr(request, "datamanager"):
                request.datamanager.shutdown()
        except Exception, e:
            # exception should NEVER flow out of response processing middlewares
            logging.critical("Exception occurred in ZODB middelware process_response - %r" % e, exc_info=True)

        return response




class AuthenticationMiddleware(object):

    def process_view(self, request, view_func, view_args, view_kwargs):

        if not hasattr(request, "datamanager"):
            return None # not a valid game instance
            
        ## Screw the immutability of these QueryDicts, we need FREEDOM ##
        request._post = request.POST.copy()
        request._get = request.GET.copy()
        if hasattr(request, "_request"):
            del request._request # force regeneration of MergeDict
        assert request._post._mutable and request._get._mutable
        
        datamanager = request.datamanager

        if not hasattr(request, 'session'):
            raise RuntimeError("The game authentication middleware requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'.")
        
        authentication.try_authenticating_with_ticket(request)
        
        return None




class PeriodicProcessingMiddleware(object):

    def process_view(self, request, view_func, view_args, view_kwargs):

        if not hasattr(request, "datamanager"):
            return None # not a valid game instance

        datamanager = request.datamanager

        # tasks that must be done BEFORE the user request is processed
        try:
            if datamanager.get_global_parameter("game_is_started"): # prevents crash when game not launched
                datamanager.process_periodic_tasks() # eg. to send pending emails
        except Exception, e:
            try:
                msg = "PeriodicProcessingMiddleware error : %r"%e
                logging.error(msg, exc_info=True)
                mail.mail_admins("Error", msg, config.SERVER_EMAIL)
            except:
                pass
        return None


