# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from rpgweb.common import *
from django.http import Http404
import django.core.mail as mail
from django.utils.cache import patch_vary_headers
from django.core.exceptions import MiddlewareNotUsed

from . import authentication
from rpgweb.datamanager.datamanager_administrator import retrieve_game_instance

settings = None
del settings # use config instead

assert logging




class ReverseProxyFixer(object):
    """
    Sets 'REMOTE_ADDR' based on 'HTTP_X_FORWARDED_FOR', if the latter is set.

    Based on http://djangosnippets.org/snippets/1706/
    """
    def process_request(self, request):
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            ip = request.META['HTTP_X_FORWARDED_FOR'].split(",")[0].strip()
            request.META['REMOTE_ADDR'] = ip



class MobileHostMiddleware:

    def __init__(self):
        if not config.MOBILE_HOST_NAMES:
            raise MiddlewareNotUsed

    def process_request(self, request):
        host = request.META.get("HTTP_HOST", "") # not present in django test client
        if host[-3:] == ":80":
            host = host[:-3] # ignore default port number, if present
        if host in config.MOBILE_HOST_NAMES:
            request.urlconf = config.ROOT_URLCONF_MOBILE
            request.is_mobile = True
        else:
            assert not hasattr(request, "urlconf")
            request.is_mobile = False

    def process_response(self, request, response):
        if getattr(request, "urlconf", None):
            patch_vary_headers(response, ('Host',))
        return response



class ZodbTransactionMiddleware(object):

    def process_request(self, request):
        # on exception : normal 500 handling takes place
        pass

    def process_view(self, request, view_func, view_args, view_kwargs):
        # on exception : normal 500 handling takes place

        assert hasattr(request, 'session'), "The game authentication middleware requires session middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.sessions.middleware.SessionMiddleware'."

        request.process_view = None # GameView instance will attache itself here on execution

        if view_kwargs.has_key("game_instance_id"):
            # TOFIX select the proper subtree of ZODB
            # Manage possible errors of wrong game_id !
            ##request.game_instance_id = view_kwargs["game_instance_id"]
            game_instance_id = view_kwargs["game_instance_id"]
            del view_kwargs["game_instance_id"]

            try:
                request.datamanager = retrieve_game_instance(game_instance_id=game_instance_id, request=request)
            except ValueError:
                raise Http404

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
            logger.critical("Exception occurred in view - %r" % exception, exc_info=True)

        # we let the exception propagate anyway
        pass


    def process_response(self, request, response):
        # on exception : no response handling occurs, a simple traceback is output !

        try:
            logger = request.datamanager.logger
        except Exception:
            logger = logging

        try:
            if hasattr(request, "datamanager"):
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

        authentication.try_authenticating_with_session(request)

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


