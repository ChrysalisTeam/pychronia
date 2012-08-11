# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from django.shortcuts import render
from django.template import RequestContext



"""
def _ensure_data_ok(datamanager):
    if not datamanager.is_initialized:
        raise AbnormalUsageError(_("Game databases haven't yet been initialized !"))
"""

def readonly_method(obj):
    @decorator
    def _readonly_method(func, self, *args, **kwargs):
        """
        This method can only ensure that no uncommitted changes are made by the function and its callees,
        committed changes might not be seen.
        """
        if not self.connection:
            return func(self, *args, **kwargs)
        
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
                raise RuntimeError("ZODB was changed by readonly method %s: %s != %s" % (func.__name__, original_str, final_str))
    new_func = _readonly_method(obj)
    new_func._is_under_readonly_method = True
    return new_func


def transaction_watcher(object=None, ensure_data_ok=True, ensure_game_started=True):
    """
    Decorator for use on datamanager and ability methods.
    
    It that can be directly applied to a method, or customized with 
    keyword arguments and then only applied to a method.
    
    *ensure_data_ok* false implies *ensure_game_started* false too.
    """
    
    if not ensure_data_ok:
        ensure_game_started = False
    
    def _decorate_and_sign(obj):
        @decorator
        def _transaction_watcher(func, self, *args, **kwargs): #@NoSelf
    
            if hasattr(self, "_inner_datamanager"):
                datamanager = self._inner_datamanager # for ability methods
            else:
                datamanager = self # for datamanager methods
    

            if not datamanager.connection: # special bypass
                return func(self, *args, **kwargs)
        
            if ensure_data_ok:
    
                if ensure_game_started:
                    if not datamanager.is_game_started():
                        # some state-changing methods are allowed even before the game starts !
                        #if func.__name__ not in ["set_message_read_state", "set_new_message_notification", "force_message_sending",
                        #                         "set_online_status"]:
                        if not getattr(func, "always_available", None):
                            raise UsageError(_("This feature is unavailable at the moment"))
    
            was_in_transaction = datamanager._in_transaction
            savepoint = datamanager.begin()
            assert datamanager._in_transaction
            assert not was_in_transaction or savepoint, repr(savepoint)
    
            try:
    
                res = func(self, *args, **kwargs)
                #datamanager._check_database_coherency() # WARNING - quite CPU intensive, 
                #to be removed later on ? TODO TODO REMOVE PAKAL !!!
                #print("COMMITTING", func.__name__, savepoint)
                datamanager.commit(savepoint)
                if not savepoint:
                    datamanager.check_no_pending_transaction() # on real commit
                return res
            
            except Exception, e:
                #logger.warning("ROLLING BACK", exc_info=True)
                datamanager.rollback(savepoint)
                if not savepoint:
                    datamanager.check_no_pending_transaction() # on real rollback
                raise
        new_func = _transaction_watcher(obj)
        new_func._is_under_transaction_watcher = True
        return new_func
    
    return _decorate_and_sign(object) if object is not None else _decorate_and_sign



@decorator
def zodb_transaction(func, *args, **kwargs):
    """
    Simply wraps a callable with a transaction rollback/commit logic.
    
    Subtransactions are not supported with this decorator.
    """
    transaction.begin() # not really needed
    try:
        res = func(*args, **kwargs)   
        return res
    except:
        transaction.abort()
        raise
    finally: 
        transaction.commit()   
        


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
