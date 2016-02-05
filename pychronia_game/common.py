# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import sys, os, math, random, traceback, hashlib, logging, types, base64, re
import types, contextlib, collections, time, glob, copy, weakref, atexit, inspect
from datetime import datetime, timedelta

from contextlib import contextmanager, closing, nested
from decorator import decorator
from functools import partial
from textwrap import dedent
from urlparse import urlparse

from odict import odict as OrderedDict
from pafo import printObject
from collections import Counter

import yaml, pyparsing

import ZODB # must be first !
from ZODB.POSException import ConflictError

import transaction
from persistent import Persistent
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList

from django.conf import settings
from django.utils.html import escape
from django.utils.translation import ungettext, ugettext as _, ugettext_lazy, ugettext_noop
from django.template.response import SimpleTemplateResponse, TemplateResponse
from django.template.loader import render_to_string
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import user_passes_test
## from django.utils.text import slugify - FIXME - for 1.5 only
from django.template.defaultfilters import slugify
from django.template import Template, Context

from . import utilities
from .utilities import config, SDICT, Enum
from .utilities.encryption import unicode_decrypt, unicode_encrypt, hash


_undefined = object()


# decorator to be applied on views
superuser_required = user_passes_test(lambda u: u.is_superuser)


NBSP = "\u00a0"  # unicode equivalent of &nbsp;


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


# FIXME USE THAT
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


class GameMaintenanceError(AccessDeniedError):
    """
    Raised when the game instance has been locked for maintenance, eg. to manually edit the data tree.
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
def action_failure_handler(request, success_message=ugettext_lazy("Operation successful.")):
    user = request.datamanager.user
    logger = request.datamanager.logger

    try:
        # nothing in __enter__()
        yield None
    except UsageError, e:
        #print (">YYYY", repr(e))
        user.add_error(unicode(e))
        if isinstance(e, AbnormalUsageError):
            logger.critical(unicode(e), exc_info=True)
    except Exception, e:
        #print (">OOOOOOO", repr(e))
        #import traceback
        #traceback.print_exc()
        # we must locate this serious error, as often (eg. assertion errors) there is no specific message attached...

        if isinstance(e, ConflictError) and request.datamanager.is_under_top_level_wrapping():
            raise  # we let upper level handle the retry!

        msg = _("Unexpected exception caught in action_failure_handler - %r") % e
        logger.critical(msg, exc_info=True)
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



def hash_url_path(url_path):
    """
    Only accepts relative url paths.
    """
    assert not url_path.startswith("/")
    url_hash = hash(url_path.lstrip("/"), length=8) # in prod, we remove the possible "/" anyway
    assert url_hash == url_hash.lower()
    return url_hash
    '''
    hash = hashlib.sha1(config.SECRET_KEY + url_path.lstrip("/")).digest() 
    url_hash = base64.b32encode(hash)[:8].lower()
    return url_hash
    '''

def game_view_url(view, datamanager, **kwargs):
    return reverse(view, kwargs=dict(game_instance_id=datamanager.game_instance_id,
                                     game_username=datamanager.username,
                                     **kwargs))


def game_file_url(url):
    """
    If URL is relative, complete it with the secret hash and make it absolute. 
    """
    url = url.strip()
    assert url

    if utilities.is_absolute_url(url):
        return url

    rel_path = url.replace("\\", "/") # some external libs use os.path methods to create urls.......
    rel_path = rel_path.lstrip("/")  # IMPORTANT
    url_hash = hash_url_path(rel_path)
    full_url = config.GAME_FILES_URL + url_hash + "/" + rel_path

    return full_url  # url starting with / and containing security token


_game_files_url_prefix = urlparse(config.GAME_FILES_URL).path
def checked_game_file_path(url):
    """
    Returns a relative (without leading /) file path, or None if the given 
    url doesn't have a proper security hash inside.
    
    Url can be complete, or only an absolute path component starting with /.
    """
    match_obj = None
    try:
        path = urlparse(url).path
        match_obj = re.match("%s(?P<hash>[^/]*)/(?P<path>.*)$" % _game_files_url_prefix, path)
    except Exception, e:
        # FIXME, log error
        pass

    if not match_obj:
        return None
    else:
        hash, url_path = (match_obj.group("hash"), match_obj.group("path"))
        if hash == hash_url_path(url_path):
            return url_path # path has NO leading /
        # FIXME, log error
        return None
        hash_url_path


def determine_asset_url(properties, absolute=True):
    if properties is None:
        file_base = properties  # let it be handled below
    elif isinstance(properties, basestring):
        file_base = properties
    elif properties.get("file"):
        file_base = properties["file"]
    elif properties.get("url"):
        file_base = properties["url"]  # mostly LEGACY attribute
    else:
        file_base = None  # now this case is possible

    if not file_base:
        return ""  # fallback value, which will often cause NO mediaplayer to be displayer

    file_url = game_file_url(file_base)  # works for both absolute and relative file urls
        
    if absolute and not utilities.is_absolute_url(file_url):
        file_url = config.SITE_DOMAIN + file_url  # important for most mediaplayers

    return file_url


def utctolocal(value):
    """
    Convert naive UTC datetime to wanted gameserver timezone.
    """
    import pytz
    if not value:
        pass ## return "@@%r@@" % value  # if we need to debug troubles
    now_utc = pytz.utc.localize(value)
    local_time = now_utc.astimezone(config.GAME_LOCAL_TZ)
    return local_time



def __obsolete_render_rst_template(rst_tpl, datamanager):
    template = Template(rst_tpl)

    context = Context(dict(a="bbbbbbbb"))

    rst_text = template.render(context)

    print("RST TEXT", rst_text)

    return rst_text



__all__ = [key for key in globals().copy() if not key.startswith("_")]
__all__ += ["_", "ugettext_lazy", "ugettext_noop", "_undefined"] # we add translation shortcuts and _undefined placeholder for default function args



