# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from BTrees.OOBTree import OOBTree

from pychronia_game.common import *
from . import datamanager_modules
from .datamanager_tools import zodb_transaction
from .datamanager_core import BaseDataManager
import threading

assert logging

AllBases = tuple(reversed(datamanager_modules.MODULES_REGISTRY)) # latest classes must be first in hierarchy
GameDataManager = type(str('GameDataManager'), AllBases, {})
assert GameDataManager.__mro__[-3:] == (BaseDataManager, utilities.TechnicalEventsMixin, object) # IMPORTANT - all modules must be BEFORE BaseDataManager


PROCESS_LOCK = threading.Lock()
ZODB_INSTANCE = None
GAME_INSTANCES_MOUNT_POINT = "game_instances"


GAME_STATUSES = Enum(("active", "terminated", "aborted", "obsolete"))


def _ensure_zodb_is_open():
    global ZODB_INSTANCE, PROCESS_LOCK
    with PROCESS_LOCK:
        if not ZODB_INSTANCE:
            if config.ZODB_URL:
                local_copy = utilities.open_zodb_url(config.ZODB_URL)
            else:
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
    _ensure_zodb_is_open()
    connection = ZODB_INSTANCE.open() # thread-local connection, by default
    return connection


@zodb_transaction
def check_zodb_structure():
    """
    Return True iff DB was already OK.
    """
    root = _get_zodb_connection().root()
    if not root.has_key(GAME_INSTANCES_MOUNT_POINT):
        logging.warning("Uninitialized ZODB root found - initializing...")
        root[GAME_INSTANCES_MOUNT_POINT] = OOBTree()
        return False
    return True


if __debug__ and config.DEBUG and config.ZODB_RESET_ALLOWED:
    @zodb_transaction
    def reset_zodb_structure():
        root = _get_zodb_connection().root()
        root.clear()
        root[GAME_INSTANCES_MOUNT_POINT] = OOBTree()



def _create_metadata_record(game_instance_id):
    utcnow = datetime.utcnow()
    game_metadata = PersistentDict(instance_id=game_instance_id,
                                   creation_time=utcnow,
                                   accesses_count=0,
                                   last_acccess_time=utcnow,
                                   last_status_change_time=utcnow,
                                   status=GAME_STATUSES.active)
    return game_metadata


@zodb_transaction
def create_game_instance(game_instance_id, master_real_email, master_login, master_password):
    """
    Returns nothing. Raises ValueError if already existing game id.
    """
    connection = _get_zodb_connection()
    game_instances = connection.root()[GAME_INSTANCES_MOUNT_POINT]

    if game_instances.get(game_instance_id): # must be present and non-empty
        raise ValueError(_("Already existing instance"))

    try:

        game_metadata = _create_metadata_record(game_instance_id=game_instance_id)
        game_data = PersistentDict()
        game_root = PersistentDict(metadata=game_metadata,
                                   data=game_data)

        dm = GameDataManager(game_instance_id=game_instance_id,
                             game_root=game_data,
                             request=None) # no user messages possible here
        assert not dm.is_initialized
        dm.reset_game_data() # TODO here provide all necessary info
        #dm.update_game_master_info(master_real_email=master_real_email,
        #                           master_login=master_login,
        #                           master_password=master_password)
        assert dm.is_initialized
        game_instances[game_instance_id] = game_root # NOW only we link data to ZODB
    except Exception, e:
        logging.critical("Impossible to initialize game instance %r..." % game_instance_id, exc_info=True)
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
    if instances[game_instance_id]["metadata"]["status"] != GAME_STATUSES.obsolete:
        raise ValueError(_("Can't delete non-obsolete instance %r") % game_instance_id)
    del instances[game_instance_id]



@zodb_transaction
def _fetch_game_data(game_instance_id):
    connection = _get_zodb_connection()
    game_root = connection.root()[GAME_INSTANCES_MOUNT_POINT].get(game_instance_id)

    if not game_root:
        raise ValueError(_("Unexisting instance %r") % game_instance_id)

    game_metadata = game_root["metadata"]
    game_metadata["accesses_count"] += 1
    game_metadata["last_acccess_time"] = datetime.utcnow()

    game_data = game_root["data"] # we don't care about game STATUS, we fetch it anyway
    return game_data


# NO transaction management here!
def retrieve_game_instance(game_instance_id, request=None):
    game_data = _fetch_game_data(game_instance_id=game_instance_id)
    dm = GameDataManager(game_instance_id=game_instance_id,
                         game_root=game_data,
                         request=request)
    return dm


@zodb_transaction
def change_game_instance_status(game_instance_id, new_status):
    if new_status not in GAME_STATUSES:
        raise ValueError(_("Wrong new game status %s for %r") % (new_status, game_instance_id))

    connection = _get_zodb_connection()
    game_root = connection.root()[GAME_INSTANCES_MOUNT_POINT].get(game_instance_id)

    if not game_root:
        raise ValueError(_("Unexisting instance %r") % game_instance_id)

    game_metadata = game_root["metadata"]
    game_metadata["status"] = new_status
    game_metadata["last_status_change_time"] = datetime.utcnow()


# NO transaction management here!
def get_all_instances_metadata():
    """
    Returns a list of copies of metadata dicts.
    """
    connection = _get_zodb_connection()
    instances = connection.root()[GAME_INSTANCES_MOUNT_POINT].itervalues()
    res = sorted((inst["metadata"].copy() for inst in instances), key=lambda x: x["creation_time"], reverse=True) # metadata contains instance id too
    return res



