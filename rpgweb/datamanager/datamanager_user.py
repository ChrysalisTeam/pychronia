# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from .datamanager_tools import UsageError
from ..common import *
import weakref, functools


class GameUser(object):

    def __init__(self, datamanager, username=None, previous_user=None):
        """
        Builds a user object, storing notifications for the current HTTP request,
        and exposing shortcuts to useful data.
        
        *previous_user* is used when logging in/out a user, to ensure no
        notifications and other persistent data gets lost in the change.
        """
        
        if username  not in datamanager.get_available_logins():
            raise UsageError(_("Username %s is unknown") % username)

        self.is_master = datamanager.is_master(username)
        self.is_character = datamanager.is_character(username)
        self.is_anonymous = datamanager.is_anonymous(username)

        assert len([item for item in (self.is_master, self.is_character, self.is_anonymous) if item]) == 1

        self._datamanager = weakref.ref(datamanager)
        self._username = username

        # notifications only used for the current request/response, 
        # but persistent through user authentications
        self.messages = previous_user.messages if previous_user else []
        self.errors = previous_user.errors if previous_user else []


    @property
    def username(self):
        return self._username

    @property
    def is_authenticated(self):
        return not self.is_anonymous

    def character_properties(self):
        """
        Only for normal players.
        """
        assert self.is_character, self._username
        return self._datamanager().get_character_properties(self._username)

    def has_permission(self, permission):
        return self._datamanager().has_permission(permission)

    def add_message(self, message):
        self.messages.append(message)

    def add_error(self, error):
        self.errors.append(error)

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
        return functools.partial(self._user_call_forwarder,
                                 func_name=func_name,
                                 username=self._username)


