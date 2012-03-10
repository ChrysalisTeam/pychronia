# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import sys, os, math, random, traceback, hashlib, logging, types
import types, contextlib, collections, time, glob, copy, weakref, atexit
from datetime import datetime, timedelta

from contextlib import contextmanager, closing, nested
from textwrap import dedent
from decorator import decorator

from odict import odict as OrderedDict

import yaml, pyparsing

import ZODB # must be first !
import transaction
from persistent import Persistent
from persistent.dict import PersistentDict
from persistent.list import PersistentList

from django import forms
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.html import escape
from django.utils.translation import ungettext, ugettext as _, ugettext_lazy as _lazy, ugettext_noop as _noop

from . import utilities
from .utilities import config, SDICT, Enum
from .utilities.counter import Counter

_undefined = object()


class UserAccess:
    """
    Enumeration attached to game views, to define the kind of users that can access them.
    """
    anonymous = "anonymous"
    authenticated = "authenticated" # both players and masters
    character = "character"
    master = "master"
    enum_values = (anonymous, authenticated, character, master)

       
class AccessResult: # result of global computation
    """
    Result of a computation between a view's access permissions and a current user.
    """
    globally_forbidden = "globally_forbidden" # eg. view disabled by the master
    authentication_required = "authentication_required" # eg. wrong kind of user logged in
    permission_required = "permission_required" # character permissions are lacking
    available = "available" # visible and executable


class AvailablePermissions:
    """
    Centralized enum of permissions, to ensure no typo is made...
    """
    pass
    



class GameError(Exception):
    def __init__(self, *args, **kwargs):
        if self.__class__ == GameError:
            raise NotImplementedError("This is an abstract error class")
        super(GameError, self).__init__(*args, **kwargs)


class AccessDeniedError(GameError):
    """
    Raised if a view can't be accessed for whatever reason (if not subclass is used, 
    it's probably a global deactivation of the concerned view by the game master).
    """
    pass

class AuthenticationRequiredError(AccessDeniedError):
    """
    Raised if access if denied, but could be granted provided the user logs in.
    """
    pass

class PermissionRequiredError(AccessDeniedError):
    """
    Raised if additional character privileges are required.
    """
    pass




class UsageError(GameError):
    """
    Base class for command workflow errors.
    """
    pass # FIXME - make this class pure abstract !!!

class NormalUsageError(UsageError):
    pass

class AbnormalUsageError(UsageError):
    pass




@contextmanager
def action_failure_handler(request, success_message=_lazy("Operation successful.")):
    user = request.datamanager.user

    try:
        # nothing in __enter__()
        yield None
    except UsageError, e:
        print (">YYYY", repr(e))
        user.add_error(unicode(e))
        if isinstance(e, AbnormalUsageError):
            logging.critical(unicode(e), exc_info=True)
    except Exception, e:
        print (">OOOOOOO", repr(e))
        import traceback
        traceback.print_exc()
        # we must locate this serious error, as often (eg. assertion errors) there is no specific message attached...
        msg = _("Unexpected exception caught in action_failure_handler - %r") % e
        logging.critical(msg, exc_info=True)
        if config.DEBUG:
            user.add_error(msg)
        else:
            user.add_error(_("An internal error occurred"))
    else:
        if success_message: # might be left empty sometimes, if another message is ready elsewhere
            user.add_message(success_message)



@contextlib.contextmanager
def exception_swallower():
    """
    When called, this function returns a context manager which
    catches and logs all exceptions raised inside its
    block of code (useful for rarely crossed try...except clauses,
    to swallow unexpected name or string formatting errors).
    """

    try:
        yield
    except Exception, e:
        try:
            logging.critical(_("Unexpected exception occurred in exception swallower context : %r !"), e, exc_info=True)
        except Exception:
            print >> sys.stderr, _("Exception Swallower logging is broken !!!")

        if __debug__:
            raise RuntimeError(_("Unexpected exception occurred in exception swallower context : %r !") % e)


 
__all__ = [key for key in globals().copy() if not key.startswith("_")]
__all__ += ["_", "_lazy", "_noop", "_undefined"] # we add translation shortcuts and _undefined placeholder for default function args


print("SETTING UP LOGGING")
logging.basicConfig() ## FIXME
logging.disable(0)


