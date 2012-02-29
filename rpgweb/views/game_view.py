# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

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

