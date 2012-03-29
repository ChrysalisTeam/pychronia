# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from django.shortcuts import render_to_response
from django.template import RequestContext




def _ensure_data_ok(datamanager):

    # TO BE REMOVED !!!!!!!!!!!!!!
    #self._check_database_coherency() # WARNING - quite CPU intensive, to be removed later on ? TODO TODO REMOVE PAKAL !!!
    if datamanager.db_state not in (datamanager.DB_STATES.LOADED, datamanager.DB_STATES.INITIALIZED):
        raise AbnormalUsageError(_("Game databases haven't yet been initialized !"))


@decorator
def readonly_method(func, self, *args, **kwargs):
    """
    This method can only ensure that no uncommitted changes are made by the function,
    committed changes might not be seen.
    """

    _ensure_data_ok(self)

    original = self.connection._registered_objects[:]

    try:
        return func(self, *args, **kwargs)
    finally:
        final = self.connection._registered_objects[:]
        if original != final:
            original_str = repr(original)
            final_str = repr(final)
            """ # NOPE - only works for hashable elements!
            s = SequenceMatcher(a=original, b=final)
            msg = ""
            for tag, i1, i2, j1, j2 in s.get_opcodes():
              msg += ("%7s a[%d:%d] (%s) b[%d:%d] (%s)\n" % (tag, i1, i2, before[i1:i2], j1, j2, after[j1:j2]))
            """
            raise RuntimeError("ZODB was changed by readonly method %s" % func.__name__)


def transaction_watcher(object=None, ensure_data_ok=True, ensure_game_started=True):
    """
    Context manager that can be directly used on a function, or customized with 
    keyword arguments and then only applied to a function.
    
    *ensure_data_ok* false implies *ensure_game_started* false too.
    """

    if not ensure_data_ok:
        ensure_game_started = False

    @decorator
    def _transaction_watcher(func, self, *args, **kwargs): #@NoSelf

        if hasattr(self, "datamanager"):
            datamanager = self.datamanager # for ability methods
        else:
            datamanager = self # for datamanager methods


        if ensure_data_ok:
            _ensure_data_ok(datamanager)

            if ensure_game_started:
                if not datamanager.get_global_parameter("game_is_started"):
                    # some state-changing methods are allowed even before the game starts !
                    #if func.__name__ not in ["set_message_read_state", "set_new_message_notification", "force_message_sending",
                    #                         "set_online_status"]:
                    if not getattr(func, "always_available", None):
                        raise UsageError(_("This feature is unavailable at the moment"))

        was_in_transaction = datamanager._in_transaction
        savepoint = datamanager.begin()
        assert not was_in_transaction or savepoint, repr(savepoint)

        try:

            res = func(self, *args, **kwargs)
            #datamanager._check_database_coherency() # WARNING - quite CPU intensive, 
            #to be removed later on ? TODO TODO REMOVE PAKAL !!!
            #print("COMMITTING", func.__name__, savepoint)
            datamanager.commit(savepoint)
            if not savepoint:
                assert not datamanager.connection._registered_objects, datamanager.connection._registered_objects # on real commit
            return res
        except Exception:
            #print("ROLLING BACK", func.__name__, savepoint)
            datamanager.rollback(savepoint)
            if not savepoint:
                assert not datamanager.connection._registered_objects, datamanager.connection._registered_objects # on real rollback
            raise

    return _transaction_watcher(object) if object is not None else _transaction_watcher





"""
# HACK TO ALLOW THE PICKLING OF INSTANCE METHODS #
# WOULD REQUIRE PICKLABILITY OF DATAMANAGER #
import copy_reg
import new
def make_instancemethod(inst, methodname):
    return getattr(inst, methodname)
def pickle_instancemethod(method):
    return make_instancemethod, (method.im_self, method.im_func.__name__)
copy_reg.pickle(new.instancemethod, pickle_instancemethod,
make_instancemethod)

def mark_always_available(func):
    func.always_available = True
    return func

"""
