# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import UsageError, GameDataManager
from django.http import Http404, HttpResponseRedirect, HttpResponse,\
    HttpResponseForbidden

SESSION_TICKET_KEY = 'rpgweb_session_ticket'
SESSION_TIMESTAMP_KEY = 'rpgweb_session_timestamp'

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

    if session_ticket is not None:
        try:
            datamanager.authenticate_with_ticket(session_ticket)
            request.session[SESSION_TIMESTAMP_KEY] = datetime.utcnow() # forces reset of expiry time
        except UsageError:
            logging.critical("Wrong session ticket detected: %r" % session_ticket, exc_info=True)
            # we let the anonymous user be...


def logout_session(request):
    request.datamanager.logout_user()
    clear_session(request)




class AccessResult: # result of global computation
    globally_forbidden = "globally_forbidden" # eg. view disabled by the master
    authentication_required = "needs_authentication" # eg. wrong kind of user logged in
    permission_required = "permission_required" # character permissions are lacking
    available = "available" # visible and executable

class UserAccess:
    anonymous = "anonymous"
    authenticated = "authenticated" # both players and masters
    character = "character"
    master = "master"
    enum_values = (anonymous, authenticated, character, master)

_undefined = object()


class GameView(object):
    
    def __init__(self,
                  view_callable,                
                  access=_undefined, 
                  permissions=_undefined, 
                  always_available=_undefined,
                  attach_to=_undefined):
        """
        Wraps a view into a system processing all kinds of authorization operations.
        
        *access* is a UserAccess value giving which kind of user has the right to access that view.
        
        *permissions* only apply to users loged-in as characters, and asks them for specific permissions
        
        *always_available* makes the view always available to user having proper permissions, i.e the game master 
        can't globally enable/disable it.
   
        *attach_to* is exclusive of other arguments, and duplicates the permissions of the provided GameView.       
        """
        
        assert isinstance(view_callable, collections.Callable)
        
        if attach_to is not _undefined:
            assert access is _undefined and permissions is _undefined and always_available is _undefined
            # other_game_view might itself be attached to another view, but it's OK
            access = attach_to.access  
            permissions = attach_to.permissions
            always_available = attach_to.always_available 
            # all checks have already been done on these values, theoretically
    
        else:
            access = access if access is not _undefined else UserAccess.master
            if permissions is _undefined:
                permissions = []
            elif isinstance(permissions, basestring):
                permissions = [permissions]
            else:
                pass # OK
            if always_available is _undefined:
                if access == UserAccess.master:
                    always_available = True 
                else:
                    always_available = False  # by default, non-master views must be deactivable

            
            assert access in UserAccess.enum_values
            assert isinstance(permissions,  (list, tuple))
            for permission in permissions:
                assert permission in GameDataManager.PERMISSIONS_REGISTRY
            assert always_available in (True, False)
            
            if access == UserAccess.master:
                assert not permissions
                assert always_available
            elif access in (UserAccess.authenticated, UserAccess.character):
                pass # all is allowed
            elif access == UserAccess.anonymous:
                assert not permissions
            else:
                raise NotImplementedError("Missing UserAccess case in GameView init")
            
        self.access = access
        self.permissions = permissions
        self.always_available = always_available
        self._view_callable = view_callable
            
 
 
    def _redirect_to_login(self, request):
        # uses HTTP code for TEMPORARY redirection
        return HttpResponseRedirect(reverse("rpgweb.views.login", kwargs=dict(game_instance_id=request.datamanager.game_instance_id)))
    
    def _global_access_denied(self, request):
        return HttpResponseForbidden(_("Access denied")) # TODO FIXME - provide a proper template and message !!
    
    def check_access(self, request):
        
        user = request.datamanager.user
        
        if not self.always_available:
            pass # TODO HERE CHECK THAT THE VIEW IS WELL ACTIVATED BY THE GAME MASTER, if not gamemaster logged
            # TODO return AccessResult.globally_forbidden
        
        if ((self.access == UserAccess.master and not user.is_master) or
            (self.access == UserAccess.authenticated and not user.is_authenticated) or
            (self.access == UserAccess.character and not user.is_character)):
            return AccessResult.authentication_required

        if self.permissions:
            assert self.access in (UserAccess.character, UserAccess.authenticated)
            for permission in self.permissions:
                if not user.has_permission(permission):
                    return AccessResult.permission_required 
        
        return AccessResult.available
    
    
    def __call__(self, request, *args, **kwargs):
        
        user = request.datamanager.user
        access_result = self.check_access(request)
        
        if access_result == AccessResult.available:
            return self._view_callable(request, *args, **kwargs)
        elif access_result == AccessResult.permission_required:
            user.add_error(_("Access reserved to privileged members.")) # TODO - must persist to login screen
            return self._global_access_denied(request)
        elif access_result == AccessResult.authentication_required:
            user.add_error(_("Authentication required.")) # could also mean a gamemaster tries to access a character-only section
            return self._redirect_to_login(request)
        else:
            assert access_result == AccessResult.globally_forbidden
            user.add_error(_("Access forbidden."))  # TODO - must persist to login screen
            return self._global_access_denied(request)
        
        
def register_view(view_callable=None, 
                  access=_undefined, 
                  permissions=_undefined, 
                  always_available=_undefined,
                  attach_to=_undefined):
    """
    Helper allowing with or without-arguments decorator usage for GameView.
    """
    factory = lambda x: GameView(x, access=access, permissions=permissions, always_available=always_available, attach_to=attach_to)
    if view_callable: 
        return factory(view_callable)
    return factory





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

    
    
    
    
    
    
    
