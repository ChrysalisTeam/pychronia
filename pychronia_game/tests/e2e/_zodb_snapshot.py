# -*- coding: utf-8 -*-

import glob
import os
import shutil

from pychronia_game.datamanager import datamanager_administrator as dm_admin


def close_active_zodb():
    """Closes and forgets the process-wide ZODB_INSTANCE, so the next request reopens
    it lazily from whatever file currently sits at config.ZODB_FILE."""
    with dm_admin.PROCESS_LOCK:
        if dm_admin.ZODB_INSTANCE is not None:
            dm_admin.ZODB_INSTANCE.close()
            dm_admin.ZODB_INSTANCE = None


def _zodb_file_variants(fs_path):
    return [fs_path, fs_path + ".index"]


def _remove_stale_lock_files(directory):
    for pattern in ("*.lock", "*.tmp"):
        for path in glob.glob(os.path.join(directory, pattern)):
            os.remove(path)


def snapshot_zodb(active_fs_path, pristine_dir):
    os.makedirs(pristine_dir, exist_ok=True)
    for path in _zodb_file_variants(active_fs_path):
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(pristine_dir, os.path.basename(path)))


def restore_zodb(active_fs_path, pristine_dir):
    """Closes the active ZODB (if open) and overwrites it with the pristine snapshot.
    The caller is responsible for making sure no request is currently in flight."""
    close_active_zodb()
    active_dir = os.path.dirname(active_fs_path)
    os.makedirs(active_dir, exist_ok=True)
    _remove_stale_lock_files(active_dir)
    for path in _zodb_file_variants(active_fs_path):
        pristine_path = os.path.join(pristine_dir, os.path.basename(path))
        if os.path.exists(pristine_path):
            shutil.copy2(pristine_path, path)
        elif os.path.exists(path):
            os.remove(path)
