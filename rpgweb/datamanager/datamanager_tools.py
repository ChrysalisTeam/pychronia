# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *



def readonly_method(obj):
    @decorator
    def _readonly_method(func, self, *args, **kwargs):
        """
        This method can only ensure that no uncommitted changes are made by the function and its callees,
        committed changes might not be seen.
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
                datamanager = self._inner_datamanager # for methods of ability or other kind of proxy
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






class DataTableManager(dict):
    """
    Put an instance of this class in a datamanager class, 
    to automatically extend it to handle (get/set/delete...)
    on a (ZODB) dict of data items.
    """

    TRANSLATABLE_ITEM_NAME = None # must be a lazy-translatable string

    def _load_initial_data(self, **kwargs):
        # NO NEED TO CALL UPPER CLASS !
        raise NotImplementedError("_load_initial_data")

    def _check_database_coherency(self, strict=False, **kwargs):
        # NO NEED TO CALL UPPER CLASS !
        for key, value in self._table.items():
            self._check_item_validity(key, value)


    def _preprocess_new_item(self, key, value):
        """
        Method that completes and normalizes a new item (for example with enforced default values).
        Must return the (possibly modified) (key, value) pair.
        """
        raise NotImplementedError("_preprocess_new_item")

    def _check_item_validity(self, key, value, strict=False):
        """
        Method that checks a given item, and raises proper UsageError if it's not OK.
        """
        raise NotImplementedError("_check_item_validity")

    def _sorting_key(self, item_pair):
        """
        Method that returns the key used to sort items, when a sorted list is asked for.
        *item_pair* is a (key, value) pair as returned by dict.items()
        """
        raise NotImplementedError("_sorting_key")

    def _get_table_container(self, root):
        """
        Method that browses the root container to return the concerned data "table" as a dict.
        """
        raise NotImplementedError("_get_table_container")

    def _item_can_be_edited(self, key, value):
        """
        Returns True iff item can be safely modified and removed from list.
        """
        raise NotImplementedError("_item_can_be_edited")


    def __init__(self, datamanager):
        self._inner_datamanager = datamanager # do not change name -> used by decorators!
        assert self.TRANSLATABLE_ITEM_NAME

    @property
    def _table(self):
        return self._get_table_container(self._inner_datamanager.data)

    @classmethod
    def _check_item_is_in_table(cls, table, key):
        if key not in table:
            raise AbnormalUsageError(_("Couldn't find %s item with key %s") % (cls.TRANSLATABLE_ITEM_NAME, key))

    @classmethod
    def _check_item_is_not_in_table(cls, table, key):
        if key in table:
            raise AbnormalUsageError(_("Items of type %s with key %s already exists") % (cls.TRANSLATABLE_ITEM_NAME, key))

    @readonly_method
    def list_keys(self):
        return sorted(self._table.keys())

    @readonly_method
    def get_all_data(self, as_sorted_list=False):
        if not as_sorted_list:
            return copy.copy(self._table) # shallow copy of dict
        else:
            mylist = self._table.items()
            mylist.sort(key=self._sorting_key)
            return mylist

    @readonly_method
    def contains_item(self, key):
        return (key in self._table)

    @readonly_method
    def get_item(self, key):
        table = self._table
        self._check_item_is_in_table(table, key)
        return table[key]

    # Beware - ensure_game_started=False because we assume these are game master items mostly
    @transaction_watcher(ensure_game_started=False)
    def insert_item(self, key, value):
        table = self._table
        self._check_item_is_not_in_table(table, key)
        key, value = self._preprocess_new_item(key, value)
        self._check_item_validity(key, value)
        table[key] = value

    @transaction_watcher(ensure_game_started=False)
    def update_item(self, key, value):
        table = self._table
        self._check_item_is_in_table(table, key)
        if not self._item_can_be_edited(key, table[key]):
            raise AbnormalUsageError(_("Can't modify %s item with key %s") % (self.TRANSLATABLE_ITEM_NAME, key))
        key, value = self._preprocess_new_item(key, value)
        self._check_item_validity(key, value)
        table[key] = value

    @transaction_watcher(ensure_game_started=False)
    def delete_item(self, key):
        table = self._table
        self._check_item_is_in_table(table, key)
        if not self._item_can_be_edited(key, table[key]):
            raise AbnormalUsageError(_("Can't delete %s item with key %s") % (self.TRANSLATABLE_ITEM_NAME, key))
        del table[key]




class LazyInstantiationDescriptor(object):
    """
    Used to place a special attribute in datamanager modules, 
    proxying to a new instance of DataTableManager on attribute access.
    """
    def __init__(self, target_klass):
        self.target_klass = target_klass

    def __get__(self, obj, objtype):
        return self.target_klass(datamanager=obj)





