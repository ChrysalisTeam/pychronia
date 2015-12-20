# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from pychronia_game.common import *
from django.http import Http404, HttpResponse
import django.core.mail as mail
from django.utils.cache import patch_vary_headers
from django.core.exceptions import MiddlewareNotUsed

from . import authentication
from pychronia_game.datamanager.datamanager_administrator import retrieve_game_instance
from django.http.response import HttpResponseRedirect

settings = None
del settings # use config instead

assert logging


class ZodbTransactionMiddleware(object):

    def process_request(self, request):
        # on exception : normal 500 handling takes place
        pass

    def process_view(self, request, view_func, view_args, view_kwargs):
        # on exception : normal 500 handling takes place

        assert hasattr(request, 'session'), "The game authentication middleware requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."

        request.process_view = None # GameView instance will attach itself here on execution

        if __debug__: request.start_time = time.time()

        if view_kwargs.has_key("game_instance_id"):
            # TOFIX select the proper subtree of ZODB
            # Manage possible errors of wrong game_id !
            ##request.game_instance_id = view_kwargs["game_instance_id"]
            game_instance_id = view_kwargs["game_instance_id"]
            del view_kwargs["game_instance_id"]

            try:
                update_timestamp = (request.method == "POST")  # we consider that other accesses are not meaningful
                # by default, this checks that game is not in maintenance
                request.datamanager = retrieve_game_instance(game_instance_id=game_instance_id,
                                                             request=request,
                                                             update_timestamp=update_timestamp)
            except GameMaintenanceError, e:
                # TODO - better handling of 503 code, with dedicated template #
                return HttpResponse(content=unicode(e) + "<br/>" + _("Please come back later."),
                                    status=503)
            except UsageError:
                raise Http404 # unexisting instance

            if not request.datamanager.is_initialized:
                raise RuntimeError("ZodbTransactionMiddleware - Game data isn't in initialized state")

            return None


    def process_exception(self, request, exception):
        # on exception : normal 500 handling takes place
        try:
            logger = request.datamanager.logger
        except Exception:
            logger = logging

        if not isinstance(exception, Http404):
            logger.critical("Exception occurred in view - %r" % exception)

        # we let the exception propagate anyway
        pass


    def process_response(self, request, response):
        # on exception : no response handling occurs, a simple traceback is output !

        try:
            logger = request.datamanager.logger
        except Exception:
            logger = logging

        if __debug__ and hasattr(request, "start_time"):
            url = request.get_full_path()
            if not url.startswith(config.GAME_FILES_URL): # we don't care about media files here
                delay = time.time() - request.start_time
                logger.info("Pychronia request took %.3f seconds for url %r" % (delay, url))

        try:
            if hasattr(request, "datamanager"):
                if config.DEBUG:
                    pass
                    #request.datamanager.check_database_coherence() # checking after each request, then
                    #logger.info("Pychronia debug mode: post-processing check_database_coherence() is over (might take a long time)")
                request.datamanager.close()
        except Exception, e:
            # exception should NEVER flow out of response processing middlewares
            logger.critical("Exception occurred in ZODB middleware process_response - %r" % e, exc_info=True)

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

        if not hasattr(request, 'session'):
            raise RuntimeError("The game authentication middleware requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'.")


        raw_url_game_username = None
        if view_kwargs.has_key("game_username"):
            raw_url_game_username = view_kwargs["game_username"]
            del view_kwargs["game_username"]  # don't interfere with final view

        url_game_username = None
        if raw_url_game_username and raw_url_game_username not in (authentication.UNIVERSAL_URL_USERNAME, authentication.TEMP_URL_USERNAME):
            url_game_username = raw_url_game_username  # WILL be transmitted for potential impersonation

        authentication.try_authenticating_with_session(request, url_game_username=url_game_username)
        del url_game_username

        if raw_url_game_username and raw_url_game_username not in (request.datamanager.username, authentication.UNIVERSAL_URL_USERNAME):
            # we redirect to the proper url prefix, so that current "effective username" is well kept during navigation (but not for UNIVERSAL_URL_USERNAME)
            new_kwargs = view_kwargs.copy()  # additional URL parts like "msg_id"
            new_kwargs["game_instance_id"] = request.datamanager.game_instance_id
            new_kwargs["game_username"] = request.datamanager.username  # important
            corrected_url = reverse(view_func, args=view_args, kwargs=new_kwargs)
            return HttpResponseRedirect(corrected_url)

        return None




class PeriodicProcessingMiddleware(object):

    def process_view(self, request, view_func, view_args, view_kwargs):

        if not hasattr(request, "datamanager"):
            return None # not a valid game instance

        datamanager = request.datamanager

        # tasks that must be done BEFORE the user request is processed
        try:
            if datamanager.is_game_writable(): # important
                datamanager.process_periodic_tasks() # eg. to send pending emails
        except Exception, e:
            try:
                msg = "PeriodicProcessingMiddleware error : %r" % e
                datamanager.logger.error(msg, exc_info=True)
                mail.mail_admins("Error", msg, config.SERVER_EMAIL)
            except:
                pass
        return None


