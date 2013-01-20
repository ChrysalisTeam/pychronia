# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from BTrees.OOBTree import OOBTree

from rpgweb.common import *
from . import datamanager_modules
from .datamanager_tools import zodb_transaction
from .datamanager_core import BaseDataManager



AllBases = tuple(reversed(datamanager_modules.MODULES_REGISTRY)) # latest classes must be first in hierarchy
GameDataManager = type(str('GameDataManager'), AllBases, {})
assert GameDataManager.__mro__[-3:] == (BaseDataManager, utilities.TechnicalEventsMixin, object) # IMPORTANT - all modules must be BEFORE BaseDataManager



ZODB_INSTANCE = None
GAME_INSTANCES_MOUNT_POINT = "game_instances"

def _ensure_zodb_open():
    global ZODB_INSTANCE
    if not ZODB_INSTANCE:
        local_copy = utilities.open_zodb_file(config.ZODB_FILE)
        ZODB_INSTANCE = local_copy
        @atexit.register # it should work !
        def _shutdown_db_pool():
            try:
                local_copy.close() # do NOT target global var ZODB_INSTANCE
                time.sleep(0.5) # to help daemon threads stop cleanly, just in case
            except Exception, e:
                print("Problem when closing ZODB instance: %e" % e, file=sys.stderr) # logging might already have disappeared


def _get_zodb_connection():
    _ensure_zodb_open()
    connection = ZODB_INSTANCE.open() # thread-local connection, by default
    return connection


@zodb_transaction
def check_zodb_structure():
    """
    Return True iff DB was already OK.
    """
    root = _get_zodb_connection().root()
    if not root.has_key(GAME_INSTANCES_MOUNT_POINT):
        logger.warning("Uninitialized ZODB root found - initializing...")
        root[GAME_INSTANCES_MOUNT_POINT] = OOBTree()
        return False
    return True

if __debug__ and config.DEBUG:
    @zodb_transaction
    def reset_zodb_structure():
        root = _get_zodb_connection().root()
        root.clear()
        root[GAME_INSTANCES_MOUNT_POINT] = OOBTree()




@zodb_transaction
def create_game_instance(game_instance_id, master_email, master_login, master_password):
    """
    Returns nothing. Raises ValueError if already existing game id.
    """
    connection = _get_zodb_connection()
    game_instances = connection.root()[GAME_INSTANCES_MOUNT_POINT]

    if game_instances.get(game_instance_id): # must be resent and non-empty
        raise ValueError(_("Already existing instance"))

    try:
        game_root = PersistentDict()
        dm = GameDataManager(game_instance_id=game_instance_id,
                             game_root=game_root,
                             request=None) # no user messages possible here
        assert not dm.is_initialized
        dm.reset_game_data() # TODO here provide all necessary info
        #dm.update_game_master_info(master_email=master_email,
        #                           master_login=master_login,
        #                           master_password=master_password)
        assert dm.is_initialized
        game_instances[game_instance_id] = game_root # NOW only we link data to ZODB
    except Exception, e:
        logger.critical("Impossible to initialize game instance %r..." % game_instance_id, exc_info=True)
        raise


def game_instance_exists(game_instance_id):
    connection = _get_zodb_connection()
    res = connection.root()[GAME_INSTANCES_MOUNT_POINT].has_key(game_instance_id)
    return res


@zodb_transaction
def delete_game_instance(game_instance_id):
    """
    Very sensitive method, beware...
    """
    connection = _get_zodb_connection()
    instances = connection.root()[GAME_INSTANCES_MOUNT_POINT]
    if game_instance_id not in instances:
        raise ValueError(_("Unexisting instance %r") % game_instance_id)
    del instances[game_instance_id]


def retrieve_game_instance(game_instance_id, request=None):
    connection = _get_zodb_connection()
    game_root = connection.root()[GAME_INSTANCES_MOUNT_POINT].get(game_instance_id)

    if not game_root:
        raise ValueError(_("Unexisting instance %r") % game_instance_id)

    dm = GameDataManager(game_instance_id=game_instance_id,
                         game_root=game_root,
                         request=request)
    return dm


def get_all_instances_metadata():
    """
    Returns a list of copies of metadata dicts.
    """
    connection = _get_zodb_connection()
    instances = connection.root()[GAME_INSTANCES_MOUNT_POINT].itervalues()
    res = [inst["metadata"].copy() for inst in instances] # metadata contains game instance id
    return res



