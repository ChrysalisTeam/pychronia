# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals


import unittest, copy
import ZODB
import transaction
from ZODB import DB
from ZODB.PersistentList import PersistentList
from ZODB.PersistentMapping import PersistentMapping
from unittest import TestCase
import multiprocessing.pool
import traceback
from ZODB.POSException import ConflictError
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

        assert a == b
        assert a == c
        assert a is not b
        assert a is not c
        assert b is not c

        del a["a"]
        assert b["a"]  # NOT impacted
        assert c["a"]  # NOT impacted



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

        s2.rollback() # again

        self.assertEqual(root.ex, 3)

        s1.rollback()

        # invalidated by s1, so corrupts connection, but raises no errors here !!!!!
        # s2.rollback()

        transaction.commit()

        self.assertFalse(hasattr(root, "ex"))

        root.ex = 6

        transaction.commit()

        self.assertEqual(root.ex, 6)

        self.assertRaises(Exception, s1.rollback) # invalidated by commit

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

        self.assertRaises(ConflictError, transaction.commit) # conflict !!
        self.assertRaises(TransactionFailedError, transaction.commit) # transaction broken

        transaction.abort()

        self.assertFalse(hasattr(root, "dummy2")) # rolled back



        # no conflict when a branch gets detached while leaf is updated

        container = root.stuff

        pool.apply(delete_container, args=(self.db, "stuff"))

        container[0] = 88

        transaction.commit()

        self.assertFalse(hasattr(root, "stuff")) # update lost



        # without readCurrent() - lost update #

        root.origin = PersistentList([13])
        value = root.origin

        pool.apply(transfer_list_value, args=(self.db, "origin", "target"))

        root.target = value

        transaction.commit()

        self.assertEqual(root.target, PersistentList([13])) # we lost [3]



        # with readCurrent() and container update - ReadConflictError raised! #


        root.origin = PersistentList([17])
        transaction.commit()

        res = conn.readCurrent(root.target) # container object selected !!
        assert res is None # no return value expected

        value = root.target

        pool.apply(transfer_list_value, args=(self.db, "origin", "target"))

        root.othertarget = value

        self.assertRaises(Exception, transaction.commit)

        self.assertEqual(root.target, PersistentList([17])) # auto refreshing occurred
        self.assertFalse(hasattr(root, "othertarget")) # auto refreshing occurred

        self.assertRaises(Exception, transaction.commit) # but transaction still broken

        transaction.abort()
        transaction.commit() # now all is ok once again



        # with readCurrent() and container deletion - somehow lost update! #

        value = root.origin[0]

        res = conn.readCurrent(root.origin) # container object selected !!
        assert res is None # no return value expected

        pool.apply(delete_container, args=(self.db, "origin"))

        root.target[0] = value # we use a value whose origin has now been deleted in other thread

        transaction.commit() # here it's OK, the deleted object still remains in the DB history even if unreachable


if __name__ == '__main__':
    try:
        unittest.main()
    except SystemExit:
        pass
