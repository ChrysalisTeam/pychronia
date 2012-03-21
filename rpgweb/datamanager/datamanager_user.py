# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


from rpgweb.common import *
import weakref, functools


class GameUser(object):

    def __init__(self, datamanager, username=None, previous_user=None, 
                 has_write_access=None, impersonation=None):
        """
        Builds a user object, storing notifications for the current HTTP request,
        and exposing shortcuts to useful data.
        
        *previous_user* is used when logging in/out a user, to ensure no
        notifications and other persistent data gets lost in the change.
        
        Existence of provided logins is checked, not the permission to use them 
        (which must be done at upper levels).
        """
        assert has_write_access in (True, False)
        
        assert has_write_access == (impersonation is None) # at the moment only...
        
        if username is None:
            username = datamanager.get_global_parameter("anonymous_login") # better than None, to display in templates
        
        available_logins = datamanager.get_available_logins()
        
        if username not in available_logins:
            raise AbnormalUsageError(_("Username %s is unknown") % username)
        if impersonation and impersonation not in datamanager.get_available_logins():
            raise AbnormalUsageError(_("Impersonation %s is unknown") % username)
        
        if impersonation:
            assert datamanager.can_impersonate(username, impersonation)

        self._real_username = username
        self.is_impersonation = bool(impersonation)
        
        self.has_write_access = has_write_access # allows or not POST requests
        
        _effective_username = impersonation if impersonation else username
        self._effective_username = _effective_username
        del username, impersonation # security
        
        self.is_master = datamanager.is_master(_effective_username)
        self.is_character = datamanager.is_character(_effective_username)
        self.is_anonymous = datamanager.is_anonymous(_effective_username)
        assert len([item for item in (self.is_master, self.is_character, self.is_anonymous) if item]) == 1

        self._datamanager = weakref.ref(datamanager)

        # notifications only used for the current request/response, 
        # but persistent through user authentications
        self.messages = previous_user.messages if previous_user else []
        self.errors = previous_user.errors if previous_user else []

    @property
    def real_username(self):
        return self._real_username
    
    @property
    def username(self):
        """
        Returns *effective* user name.
        """
        return self._effective_username

    @property
    def is_authenticated(self):
        return not self.is_anonymous

    def character_properties(self):
        """
        Only for normal players.
        """
        assert self.is_character, self._effective_username
        return self._datamanager().get_character_properties(self._effective_username)

    def has_permission(self, permission):
        return self._datamanager().has_permission(permission)


    def add_message(self, message):
        #print(">>>>>>>>> registering message", message)
        self.messages.append(message)

    def add_error(self, error):
        #print(">>>>>>>>> registering error", error)
        self.errors.append(error)
    
    def has_notifications(self):
        #print(">>>>>>>>> notifications", self.messages, self.errors)
        return bool(self.messages or self.errors)
    
    def discard_notifications(self):
        self.errors = []
        self.messages = []
        
        
    def _dm_call_forwarder(self, func_name, *args, **kwargs):
        """
        Forwards call to the select function of the attached datamanager, 
        transferring given arguments.
        """
        target = getattr(self._datamanager(), func_name)
        return target(*args, **kwargs)

    def __getattr__(self, func_name):
        """
        Helper to call methods of the datamanager, 
        forcing *username* to the currently selected username.
        
        Will fail if target method doesn't expect a username argument, 
        or if current user isn't of a proper type.
        """
        if not hasattr(self._datamanager(), func_name):
            raise AttributeError(func_name)
        return functools.partial(self._dm_call_forwarder,
                                 func_name=func_name,
                                 username=self._effective_username)


