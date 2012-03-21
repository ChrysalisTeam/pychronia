# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import UsageError, GameDataManager
from django.http import Http404, HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden

SESSION_TICKET_KEY = 'rpgweb_session_ticket'
IMPERSONATION_POST_VARIABLE = "_impersonate_rpgweb_user_"


"""
Django Notes

Reading a session is not considered activity for expiration purposes. Session expiration is computed from the last time the session was modified.
Use normal Python strings as dictionary keys on request.session. This is more of a convention than a hard-and-fast rule.
Session dictionary keys that begin with an underscore are reserved for internal use by Django.
Don’t override request.session with a new object, and don’t access or set its attributes. Use it like a Python dictionary.
The session dictionary should accept any pickleable Python object. See the pickle module for more information.
Session data is stored in a database table named django_session .
Django only sends a cookie if it needs to. If you don't set any session data, it won't send a session cookie.
"""





def clear_session(request):
    request.session.flush()
    request.session.cycle_key()


def authenticate_with_credentials(request, username, password):
    """
    This function lets exceptions flow...
    """
    datamanager = request.datamanager
    session_ticket = datamanager.authenticate_with_credentials(username, password)
    clear_session(request)
    
    request.session[SESSION_TICKET_KEY] = session_ticket 


def try_authenticating_with_ticket(request):
    """
    This function lets exceptions flow...
    """
    datamanager = request.datamanager
    session_ticket = request.session.get(SESSION_TICKET_KEY)
    
    if session_ticket:

        # beware, here we distinguish between empty string (stop impersonation) and None (do nothing)
        requested_impersonation = request.POST.pop(IMPERSONATION_POST_VARIABLE, [None])[0] # Beware, pop() on QueryDict returns a LIST always
        
        try:
            res = datamanager.authenticate_with_ticket(session_ticket, 
                                                       requested_impersonation=requested_impersonation)
            request.session[SESSION_TICKET_KEY] = res # this refreshes expiry time, and ensures we properly modify session
        except NormalUsageError, e:
            pass # wrong game instance, surely... let it be.
        except UsageError, e:
            # a disappeared character ? wrong impersonation username ?
            logging.critical("Wrong session ticket detected: %r" % (session_ticket,), exc_info=True)
            request.session[SESSION_TICKET_KEY] = None # important cleanup!
            
        # anyway, we let the anonymous user be...
 

def logout_session(request):
    request.datamanager.logout_user()
    clear_session(request)





'''
def _redirection_to_login(request):
    return HttpResponseRedirect(reverse("rpgweb.views.login", kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))


@decorator
def basic_access_required(func, request, *args, **kwargs):
    """
    Decorator to apply basic filtering to views, depending on the global availability of these views and their menus.
    """
    if not request.datamanager.user.is_master:
        view_is_allowed = request.datamanager.view_is_allowed


def game_player_required(object=None, permission=None):
    """
    Decorator to only allow normal players, possibly with 
    special access permissions.
    """
    if object and not isinstance(object, collections.Callable):
        raise RuntimeError("game_player_required decorator badly used")

    def decorate(func):
        @decorator
        def player_auth_wrapper(func, request, *args, **kwargs):
            user = request.datamanager.user
            if not user.is_character or (permission and not user.has_permission(permission)):
                user.add_error(_("Access reserved to privileged members."))
                return _redirection_to_login(request)
            return func(request, *args, **kwargs)
        wrapped = player_auth_wrapper(func)
        wrapped.game_permission_required = permission
        return wrapped
    return decorate(object) if object else decorate


def game_master_required(func):
    """
    Decorator to only allow the game master.
    """
    @decorator
    def wrapper(func, request, *args, **kwargs):
        user = request.datamanager.user
        if not user.is_master:
            user.add_error(_("Access reserved to administrators."))
            return _redirection_to_login(request)
        return func(request, *args, **kwargs)
    wrapped = wrapper(func)
    wrapped.game_master_required = True
    return wrapped



def game_authenticated_required(func):
    """
    Decorators to allow game master and players, not visitors.
    """
    @decorator
    def wrapper(func, request, *args, **kwargs):
        user = request.datamanager.user
        if not user.is_authenticated:
            user.add_error(_("Access forbidden to anonymous users."))
            return _redirection_to_login(request)
        return func(request, *args, **kwargs)
    wrapped = wrapper(func)
    wrapped.game_authenticated_required = True
    return wrapped
'''

    
    
    
    
    
    
    
