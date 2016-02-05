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

GAME_STATUSES = Enum(("active", "terminated", "aborted"))


GAME_INSTANCES_BACKUPS_ABSPATH = (os.path.join(config.GAME_FILES_ROOT, config.GAME_BACKUPS_PATH)
                                  if not os.path.isabs(config.GAME_BACKUPS_PATH)
                                  else config.GAME_BACKUPS_PATH)



_undefined = object()



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

def _get_game_instances_mapping():
    # this connection will get attached to all ZODB objects, and thus auto-closed by the Datamanager after request processing
    connection = _get_zodb_connection()
    game_instances = connection.root()[GAME_INSTANCES_MOUNT_POINT]
    return game_instances




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



def _create_metadata_record(game_instance_id, creator_login, creator_email):
    utilities.check_is_slug(game_instance_id)
    utilities.check_is_string(creator_login) # NOT necessarily a slug
    if creator_email is not None:
        utilities.check_is_email(creator_email)
    utcnow = datetime.utcnow()
    game_metadata = PersistentMapping(instance_id=game_instance_id,
                                   creator_login=creator_login,
                                   creator_email=creator_email,
                                   creation_time=utcnow,
                                   accesses_count=0,
                                   last_access_time=utcnow,
                                   last_status_change_time=utcnow,
                                   status=GAME_STATUSES.active,
                                   maintenance_until=None) # None or datetime here
    return game_metadata


@zodb_transaction
def create_game_instance(game_instance_id,
                         creator_login,
                         creator_email=None,
                         skip_initializations=False,
                         skip_randomizations=False,
                         skip_coherence_check=False,
                         yaml_fixture=None,
                         strict=False): # TODO here try strict=True once
    """
    Returns nothing. Raises UsageError if already existing game id.
    """
    game_instances = _get_game_instances_mapping()

    if game_instances.get(game_instance_id): # must be present and non-empty
        raise AbnormalUsageError(_("Already existing instance"))

    try:

        game_metadata = _create_metadata_record(game_instance_id=game_instance_id,
                                                creator_login=creator_login,
                                                creator_email=creator_email)
        game_data = PersistentMapping()
        game_root = PersistentMapping(metadata=game_metadata,
                                   data=game_data)

        dm = GameDataManager(game_instance_id=game_instance_id,
                             game_root=game_data,
                             request=None) # no user messages possible here

        assert not dm.is_initialized
        dm.reset_game_data(strict=strict, 
                           skip_randomizations=skip_randomizations, 
                           skip_initializations=skip_initializations,
                           skip_coherence_check=skip_coherence_check,
                           yaml_fixture=yaml_fixture)
        assert dm.is_initialized

        game_instances[game_instance_id] = game_root # NOW only we link data to ZODB

    except Exception, e:
        logging.critical("Impossible to initialize game instance %r..." % game_instance_id, exc_info=True)
        raise

    else:
        logging.info("Successfully initialized game instance %r!" % game_instance_id)


@zodb_transaction # TODO UNTESTED
def replace_existing_game_instance_data(game_instance_id, new_data):
    """
    Replaces only inner data, not metadata.
    """
    assert isinstance(new_data, PersistentMapping)
    game_instances = _get_game_instances_mapping()

    if game_instance_id not in game_instances:
        raise AbnormalUsageError(_("Unexisting instance %r") % game_instance_id)

    if "data" in new_data:
        raise RuntimeError("Trying to replace instance 'data' with 'full_data' for %s" % game_instance_id)

    assert game_instances[game_instance_id]["data"]
    game_instances[game_instance_id]["data"] = new_data


# no need for transaction management
def game_instance_exists(game_instance_id):
    res = _get_game_instances_mapping().has_key(game_instance_id)
    return res

# no need for transaction management
def get_game_instance_metadata_copy(game_instance_id):

    game_root = _get_game_instances_mapping().get(game_instance_id)

    if not game_root:
        raise AbnormalUsageError(_("Unexisting instance %r") % game_instance_id)

    return game_root["metadata"].copy()



@zodb_transaction
def delete_game_instance(game_instance_id):
    """
    Very sensitive method, beware...
    """
    game_instances = _get_game_instances_mapping()
    if game_instance_id not in game_instances:
        raise AbnormalUsageError(_("Unexisting instance %r") % game_instance_id)
    if game_instances[game_instance_id]["metadata"]["status"] == GAME_STATUSES.active:
        raise AbnormalUsageError(_("Can't delete active instance %r") % game_instance_id)
    del game_instances[game_instance_id]



@zodb_transaction
def _fetch_available_game_data(game_instance_id, metadata_checker, update_timestamp):
    """
    The callable metadata_checker, if provided, is called with a copy of instance metadata, 
    and may raise errors or return false to forbid creation of datamanager instance.
    
    Parameter "update_timestamp" is a boolean.
    """

    game_root = _get_game_instances_mapping().get(game_instance_id)

    if not game_root:
        raise AbnormalUsageError(_("Unexisting instance %r") % game_instance_id)

    game_metadata = game_root["metadata"]

    if metadata_checker:
        res = metadata_checker(game_instance_id=game_instance_id, game_metadata=game_metadata.copy())
        assert res is not None # programming error
        if not res:
            raise GameMaintenanceError(_("Metadata check didn't allow access to instance."))

    game_metadata["accesses_count"] += 1
    if update_timestamp:
        game_metadata["last_access_time"] = datetime.utcnow()

    game_data = game_root["data"] # we don't care about game STATUS, we fetch it anyway
    return game_data



def _game_is_maintenance(game_metadata):
    return (game_metadata["maintenance_until"] and game_metadata["maintenance_until"] > datetime.utcnow())

def check_game_not_in_maintenance(game_instance_id, game_metadata):
    if _game_is_maintenance(game_metadata):
        raise GameMaintenanceError(_("Instance %s is in maintenance.") % game_instance_id)
    return True

def check_game_is_in_maintenance(game_instance_id, game_metadata):
    if not _game_is_maintenance(game_metadata):
        raise GameMaintenanceError(_("Instance %s is NOT in maintenance.") % game_instance_id)
    return True


# NO transaction management here!
def retrieve_game_instance(game_instance_id, request=None, metadata_checker=check_game_not_in_maintenance, update_timestamp=False):
    """
    If metadata_checker is None, checks on instance availability are skipped.
    """
    game_data = _fetch_available_game_data(game_instance_id=game_instance_id,
                                           metadata_checker=metadata_checker,
                                           update_timestamp=update_timestamp)
    dm = GameDataManager(game_instance_id=game_instance_id,
                         game_root=game_data,
                         request=request)
    return dm

@zodb_transaction
def change_game_instance_status(game_instance_id, new_status=None, maintenance_until=_undefined):
    assert new_status or (maintenance_until is not _undefined)

    game_root = _get_game_instances_mapping().get(game_instance_id)

    if not game_root:
        raise AbnormalUsageError(_("Unexisting instance %r") % game_instance_id)

    game_metadata = game_root["metadata"]

    if new_status:
        if new_status not in GAME_STATUSES:
            raise AbnormalUsageError(_("Wrong new game status %(status)s for %(instance_id)r") % dict(status=new_status, instance_id=game_instance_id))
        game_metadata["status"] = new_status

    if maintenance_until is not _undefined:
        assert maintenance_until is None or maintenance_until >= datetime.utcnow()
        game_metadata["maintenance_until"] = maintenance_until

    game_metadata["last_status_change_time"] = datetime.utcnow()


# NO transaction management here!
def get_all_instances_metadata():
    """
    Returns a list of copies of metadata dicts.
    """
    instances = _get_game_instances_mapping().itervalues()
    res = sorted((inst["metadata"].copy() for inst in instances), key=lambda x: x["creation_time"], reverse=True) # metadata contains instance id too
    return res






# BACKUP/RESTORE API #


def _get_backup_folder(game_instance_id):
    return os.path.join(GAME_INSTANCES_BACKUPS_ABSPATH, game_instance_id)

def _ensure_instance_backup_folder(game_instance_id):
    assert game_instance_id
    wanted_folder = _get_backup_folder(game_instance_id)
    if not os.path.exists(wanted_folder):
        os.makedirs(wanted_folder)
    return wanted_folder

def list_backups_for_game_instance(game_instance_id):
    """
    Returns basenames of backup files.
    """
    wanted_folder = _get_backup_folder(game_instance_id)
    if not os.path.exists(wanted_folder):
        return []
    return os.listdir(wanted_folder)  # might be empty though

def backup_game_instance_data(game_instance_id, comment=None):
    """
    We only backup game "data", not metadata.
    """
    assert not comment or utilities.check_is_slug(comment)
    comment = comment or "standard"

    # no need to "lock" instance, ACID properties do it for us #
    game_root = _get_game_instances_mapping().get(game_instance_id)
    if not game_root:
        raise AbnormalUsageError(_("Unexisting instance %r") % game_instance_id)

    json_bytes_str = utilities.dump_data_tree_to_yaml(game_root["data"],
                                                      convert=True, # should be output in UTF8
                                                      default_style="|") # will output very long lines

    basename = "backup_" + game_instance_id + "_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + comment + ".yaml"
    wanted_folder = _ensure_instance_backup_folder(game_instance_id)
    final_file_path = os.path.join(wanted_folder, basename)

    with open(final_file_path, "wb") as f:
        f.write(json_bytes_str)

