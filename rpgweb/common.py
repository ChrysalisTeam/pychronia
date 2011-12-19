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
from django.core.urlresolvers import reverse
from django.utils.html import escape
from django.utils.translation import ungettext, ugettext as _, ugettext_lazy as _lazy, ugettext_noop as _noop

from . import utilities
from .utilities import config
from .utilities.counter import Counter


class Enum(set):
    """
    Takes a string of values, or a list, and exposes the corresponding enumeration.
    """
    def __init__(self, names=[]):
        if isinstance(names, basestring):
            names = names.split()
        set.__init__(self, names)

    def update(self, iterable):
        if isinstance(iterable, basestring):
            iterable = iterable.split()
        set.update(iterable)

    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError(name)

 
__all__ = [key for key in globals().copy() if not key.startswith("_")]
__all__ += ["_", "_lazy", "_noop"] # we add translation shortcuts


print("SETTING UP LOGGING")
logging.basicConfig() ## FIXME
logging.disable(0)


