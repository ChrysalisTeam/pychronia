# -*- coding: utf-8 -*-



import os
from django.core.files.storage import FileSystemStorage
from .utilities import config
from pychronia_game.common import game_file_url
from easy_thumbnails.files import Thumbnailer


class ProtectedGameFileSystemStorage(FileSystemStorage):
    """
    Replacement for ThumbnailFileSystemStorage, which builds "obfuscated urls" for thumbnails.
    """

    def __init__(self):
        location = config.GAME_FILES_ROOT
        assert location.endswith(os.sep), location
        super(ProtectedGameFileSystemStorage, self).__init__(location=location,
                                                             base_url=None)  # useless here

    def url(self, name):
        return game_file_url(name)


protected_game_file_system_storage = ProtectedGameFileSystemStorage()


def get_game_thumbnailer(rel_path):
    assert not rel_path.startswith("/")
    return Thumbnailer(
        file=None, name=rel_path,
        source_storage=protected_game_file_system_storage,
        thumbnail_storage=protected_game_file_system_storage)
