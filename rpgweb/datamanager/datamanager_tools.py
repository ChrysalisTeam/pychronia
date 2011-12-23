# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from django.shortcuts import render_to_response
from django.template import RequestContext



class UsageError(Exception):
    pass


class NormalUsageError(UsageError):
    pass

class AbnormalUsageError(UsageError):
    pass

class PermissionError(UsageError):
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
        msg = _("Unexpected exception caught in action_failure_handler")
        logging.critical(msg, exc_info=True)
        if config.DEBUG:
            user.add_error(msg)
        else:
            user.add_error(_("An internal error occurred"))
    else:
        if success_message: # might be left empty sometimes, if another message is ready elsewhere
            user.add_message(success_message)


class SDICT(dict):
    def __getitem__(self, name):
        try:
            dict.__getitem__(self, name)
        except KeyError:
            logging.critical("Wrong key %s looked up in dict %r", name, self)
            return "<UNKNOWN>"
        
    ''' obsolete
    def SDICT(**kwargs):
        import collections
        # TODO - log errors when wrong lookup happens!!!
        mydict = collections.defaultdict(lambda: "<UNKNOWN>") # for safe string substitutions
        for (name, value) in kwargs.items():
            mydict[name] = value # we mimic the normal dict constructor
        return mydict
    '''

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

        if hasattr(self, "_datamanager"):
            datamanager = self._datamanager # for ability methods
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

