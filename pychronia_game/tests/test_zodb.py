# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import unittest, copy, time, random
import traceback
from unittest import TestCase
import multiprocessing.pool


import ZODB
from ZODB import DB, FileStorage
from ZODB.PersistentList import PersistentList
from ZODB.PersistentMapping import PersistentMapping
from ZODB.POSException import ConflictError

import transaction
from transaction.interfaces import TransactionFailedError


pool = multiprocessing.pool.ThreadPool(3)


def transfer_list_value(db, origin, target):
    conn = db.open()
    root = conn.root

    value = getattr(root, origin)[0]
    getattr(root, target)[0] = value

    transaction.commit()

    assert getattr(root, target)[0] == value
    conn.close()


def delete_container(db, name):
    conn = db.open()
    root = conn.root

    delattr(root, name)

    transaction.commit()
    assert not hasattr(root, name)
    conn.close()



HUGE_DATABASE_NAME = 'huge_database.fs'

def _get_huge_db_root():
    storage = FileStorage.FileStorage(HUGE_DATABASE_NAME)
    db = DB(storage)
    connection = db.open()
    root = connection.root()
    return db, connection, root


def ___test_huge_db_ghosting_system():
    """
    Interactive testcase, to demonstrate the behaviour of ZODB regarding memory management and ghost objects.
    Launch it with a "top"-like window opened next to it.

    MIGHT TRIGGER THIS WARNING:

        p:\development\.virtualenvs\pychronia\lib\site-packages\ZODB\Connection.py:550: UserWarning: The <class 'persistent.list.PersistentList'>
        object you're saving is large. (20001339 bytes.)

        Perhaps you're storing media which should be stored in blobs.

        Perhaps you're using a non-scalable data structure, such as a
        PersistentMapping or PersistentList.

        Perhaps you're storing data in objects that aren't persistent at
        all. In cases like that, the data is stored in the record of the
        containing persistent object.

        In any case, storing records this big is probably a bad idea.

        If you insist and want to get rid of this warning, use the
        large_record_size option of the ZODB.DB constructor (or the
        large-record-size option in a configuration file) to specify a larger
        size.

    Playing with this test shows that:
    
    - contants of persistent lists and mappings are really only loaded when accessed (eg. when lookup is done on them..)
    - non persistent types (list(), dict()) are badly treated, and remain in memory even when committed to file
    """

    use_non_persistent_types = False

    PersistentList = globals()["PersistentList"]
    PersistentMapping = globals()["PersistentMapping"]
    if use_non_persistent_types:
        PersistentList = list
        PersistentMapping = dict

    db, connection, root = _get_huge_db_root()

    root["data"] = PersistentList(PersistentMapping({"toto": "tata"*random.randint(500, 600)}) for i in range(200000))

    print("We have a HUGE database filled with transient data now!")
    time.sleep(5)

    transaction.commit()

    print("We have committed the transaction!")
    time.sleep(5)

    connection.close()
    db.close()

    # ---------

    db, connection, root = _get_huge_db_root()

    print("We have reopened the huge database now!")
    time.sleep(5)

    data = root["data"]

    print("We have accessed data list!", type(data))
    time.sleep(5)

    var1 = data[0]

    print("We have accessed data list first element!", type(var1))
    time.sleep(5)

    for i in data:
        i["toto"]  # THIS removes the ghosting effect on element

    print("We have accessed data list all elements!", type(i))
    time.sleep(15)



class TestZODB(TestCase):
    def setUp(self):
        self.db = DB(None)
        self.conn = self.db.open()

    def tearDown(self):
        self.conn.close()
        self.db.close()

    def test_mapping_copy(self):
        a = PersistentMapping(dict(a=3, b=5))
        b = a.copy()
        c = copy.copy(a)
        d = copy.deepcopy(a)

        assert a == b
        assert a == c
        assert a == d
        assert a is not b
        assert a is not c
        assert b is not c
        assert a is not d

        del a["a"]
        assert b["a"]  # NOT impacted
        assert "a" not in c, c  # BUG, is impacted!
        assert d["a"]  # NOT impacted

    def test_savepoints(self):
        """
        Here we ensure that ZODB transactions
        and qavepoint behave well like nested transactions,
        except that savepoints must not be committed.
        """

        conn = self.conn
        root = conn.root

        #pprint(dir(conn))

        s1 = conn.savepoint()

        root.ex = 3

        s2 = conn.savepoint()

        root.ex = 4

        self.assertEqual(root.ex, 4)

        s2.rollback()

        root.ex = 5

        s2.rollback()  # again

        self.assertEqual(root.ex, 3)

        s1.rollback()

        # invalidated by s1, so corrupts connection, but raises no errors here !!!!!
        # s2.rollback()

        transaction.commit()

        self.assertFalse(hasattr(root, "ex"))

        root.ex = 6

        transaction.commit()

        self.assertEqual(root.ex, 6)

        self.assertRaises(Exception, s1.rollback)  # invalidated by commit

        root.ex = 7

        transaction.abort()

        self.assertEqual(root.ex, 6)

        root.ex = 8

        s3 = conn.savepoint()

        root.ex = 9

        transaction.commit()
        transaction.abort()

        # commit was well for the whole transaction, not just s3
        self.assertEqual(root.ex, 9)

    def test_conflict_errors(self):
        """
        Here we realize that conflict errors occur only occur when concurrent modifications
        on a particular container (with specific oid) occur concurrently. Updates can still
        be lost if a branch of the object tree is disconnected from the root while one of 
        its leaves gets updated.
        
        Similarly, readCurrent() only protects a specific container of the object tree,
        which can still be disconnected from the root by a transaction, while its content
        is updated by another transaction.
        """

        conn = self.conn

        root = conn.root

        root.stuff = PersistentList([9])
        root.origin = PersistentList([3])
        root.target = PersistentList([8])
        root.dummy1 = PersistentList([9])
        transaction.commit()

        # basic conflict on root #

        pool.apply(delete_container, args=(self.db, "dummy1"))

        root.dummy2 = 5

        self.assertRaises(ConflictError, transaction.commit)  # conflict !!
        self.assertRaises(TransactionFailedError, transaction.commit)  # transaction broken

        transaction.abort()

        self.assertFalse(hasattr(root, "dummy2"))  # rolled back

        # no conflict when a branch gets detached while leaf is updated

        container = root.stuff

        pool.apply(delete_container, args=(self.db, "stuff"))

        container[0] = 88

        transaction.commit()

        self.assertFalse(hasattr(root, "stuff"))  # update lost

        # without readCurrent() - lost update #

        root.origin = PersistentList([13])
        value = root.origin

        pool.apply(transfer_list_value, args=(self.db, "origin", "target"))

        root.target = value

        transaction.commit()

        self.assertEqual(root.target, PersistentList([13]))  # we lost [3]

        # with readCurrent() and container update - ReadConflictError raised! #


        root.origin = PersistentList([17])
        transaction.commit()

        res = conn.readCurrent(root.target)  # container object selected !!
        assert res is None  # no return value expected

        value = root.target

        pool.apply(transfer_list_value, args=(self.db, "origin", "target"))

        root.othertarget = value

        self.assertRaises(Exception, transaction.commit)

        self.assertEqual(root.target, PersistentList([17]))  # auto refreshing occurred
        self.assertFalse(hasattr(root, "othertarget"))  # auto refreshing occurred

        self.assertRaises(Exception, transaction.commit)  # but transaction still broken

        transaction.abort()
        transaction.commit()  # now all is ok once again

        # with readCurrent() and container deletion - somehow lost update! #

        value = root.origin[0]

        res = conn.readCurrent(root.origin)  # container object selected !!
        assert res is None  # no return value expected

        pool.apply(delete_container, args=(self.db, "origin"))

        root.target[0] = value  # we use a value whose origin has now been deleted in other thread

        transaction.commit()  # here it's OK, the deleted object still remains in the DB history even if unreachable


if __name__ == '__main__':
    try:
        unittest.main()
    except SystemExit:
        pass
