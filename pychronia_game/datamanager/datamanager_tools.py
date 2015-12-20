# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import time
from ZODB.POSException import ConflictError

from pychronia_game.common import *
import functools


def begin_transaction_with_autoreconnect():
    from _mysql_exceptions import OperationalError, InterfaceError
    disconnected_exceptions = (
        OperationalError,
        InterfaceError,
    )
    for i in range(10):
        try:
            return transaction.begin()
            break ## OK done
        except disconnected_exceptions:
            pass # maybe SQL connection timed out in relstorage...
    else:
        raise # reraise latest "OperationalError: (2006, 'MySQL server has gone away')" or thing like that


def _execute_under_toplevel_zodb_conflict_solver(datamanager, completed_func):

    datamanager.begin_top_level_wrapping()
    try:
        for i in range(3):
            try:
                return completed_func()
            except ConflictError:
                time.sleep(1)
        raise AbnormalUsageError(_("Concurrent access conflict on the resource, please retry"))
    finally:
        datamanager.end_top_level_wrapping()




def _call_checked_readonly_method(datamanager, func, args, kwargs):
    """
    This method can only ensure that no uncommitted changes 
    are made by the function and its callees,
    committed changes might not be detected.
    """

    connection = datamanager.connection
    if not connection:
        return func(*args, **kwargs)

    original = connection._registered_objects[:]

    try:
        return func(*args, **kwargs)
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


def _call_with_transaction_watcher(datamanager, always_writable, func, args, kwargs):

    if not datamanager.connection: # special bypass
        return func(*args, **kwargs)

    if not always_writable:
        # then, we assume that - NECESSARILY - data is in a coherent state
        writability_data = datamanager.determine_actual_game_writability()
        if not writability_data["writable"]: # abnormal, views should have blocked that feature
            datamanager.logger.critical("Forbidden access to %s while having writability_data = %r", func.__name__, writability_data)
            raise AbnormalUsageError(_("This feature is unavailable at the moment"))

    was_in_transaction = datamanager._in_writing_transaction
    savepoint = datamanager.begin() # savepoint is None if it's top-level transaction
    assert datamanager._in_writing_transaction
    assert not was_in_transaction or savepoint, repr(savepoint)

    try:

        res = func(*args, **kwargs)
        #datamanager._check_database_coherence() # WARNING - quite CPU intensive,
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



def _build_wrapped_method(obj, secondary_wrapper, **extra_args):
    @decorator
    def _conditional_method_wrapper(func, *args, **kwargs):
        self = args[0] # should always exist, we're in methods here
        if hasattr(self, "_inner_datamanager"):
            datamanager = self._inner_datamanager # for methods of ability or other kind of proxy
        else:
            datamanager = self

        completed_func = functools.partial(secondary_wrapper,
                                           datamanager=datamanager, func=func, args=args, kwargs=kwargs,
                                           **extra_args)

        already_wrapped = datamanager.is_under_top_level_wrapping()

        if already_wrapped:
            return completed_func()
        else:
            return _execute_under_toplevel_zodb_conflict_solver(datamanager=datamanager, completed_func=completed_func)
    return _conditional_method_wrapper(obj)


def readonly_method(obj):
    '''
    @decorator
    def _build_readonly_method(func, *args, **kwargs):
        self = args[0] # should always exist, we're in methods here
        if hasattr(self, "_inner_datamanager"):
            datamanager = self._inner_datamanager # for methods of ability or other kind of proxy
        else:
            datamanager = self

        completed_func = functools.partial(_call_checked_readonly_method, datamanager=datamanager, func=func, args=args, kwargs=kwargs)
        already_in_transaction = datamanager._in_transaction

        if already_in_transaction:
            return completed_func()
        else:
            return _execute_under_toplevel_zodb_conflict_solver(completed_func)
        '''
    new_func = _build_wrapped_method(obj, secondary_wrapper=_call_checked_readonly_method)
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
        new_func = _build_wrapped_method(obj, secondary_wrapper=_call_with_transaction_watcher, always_writable=always_writable)
        new_func._is_under_transaction_watcher = True
        new_func._is_always_writable = always_writable
        return new_func

    return _decorate_and_sign(object) if object is not None else _decorate_and_sign



@decorator
def zodb_transaction(func, *args, **kwargs):
    """
    Wraps a callable with a transaction rollback/commit logic, 
    with retries on conflict.
    
    Subtransactions are not supported with this decorator.
    """
    for i in range(5):
        try:
            begin_transaction_with_autoreconnect()
            try:
                res = func(*args, **kwargs)
            except BaseException: # even sys.exit() !
                transaction.abort()
                raise
            else:
                transaction.commit()
                return res
        except ConflictError, e:
            time.sleep(0.5)
    raise AbnormalUsageError(_("Couldn't solve 'concurrent access' conflict on the resource"))










