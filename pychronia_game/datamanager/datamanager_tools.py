# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *



def readonly_method(obj):
    @decorator
    def _readonly_method(func, self, *args, **kwargs):
        """
        This method can only ensure that no uncommitted changes 
        are made by the function and its callees,
        committed changes might not be detected.
        """

        if hasattr(self, "_inner_datamanager"):
            connection = self._inner_datamanager.connection # for methods of ability or other kind of proxy
        else:
            connection = self.connection # for datamanager methods


        if not connection:
            return func(self, *args, **kwargs)

        original = connection._registered_objects[:]

        try:
            return func(self, *args, **kwargs)
        finally:
            final = connection._registered_objects[:]
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


def transaction_watcher(object=None, always_writable=False):
    """
    Decorator for use on datamanager and ability methods.
    
    It that can be directly applied to a method, or customized with 
    keyword arguments and then only applied to a method.
    
    *always_writable* ensure that game state or user permissions have no effect
    on the ability to use the wrapped method.
    """


    def _decorate_and_sign(obj):
        @decorator
        def _transaction_watcher(func, self, *args, **kwargs): #@NoSelf

            if hasattr(self, "_inner_datamanager"):
                datamanager = self._inner_datamanager # for methods of ability or other kind of proxy
            else:
                datamanager = self # for datamanager methods


            if not datamanager.connection: # special bypass
                return func(self, *args, **kwargs)

            if not always_writable:
                # then, we assume that - NECESSARILY - data is in a coherent state
                writability_data = datamanager.determine_actual_game_writability()
                if not writability_data["writable"]: # abnormal, views should have blocked that feature
                    datamanager.logger.critical("Forbidden access to %s while having writability_data = %r", func.__name__, writability_data)
                    raise AbnormalUsageError(_("This feature is unavailable at the moment"))

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
        new_func._is_always_writable = always_writable
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








