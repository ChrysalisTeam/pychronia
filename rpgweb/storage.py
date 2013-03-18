# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import os
from django.core.files.storage import FileSystemStorage
from .utilities import config
from rpgweb.common import game_file_url


class ProtectedGameFileSystemStorage(FileSystemStorage):
    """
    Replacement for ThumbnailFileSystemStorage, which builds "obfuscated urls" for thumbnails.
    """

    def __init__(self):
        location = config.GAME_FILES_ROOT
        assert location.endswith(os.sep), location
        super(ProtectedGameFileSystemStorage, self).__init__(location=location,
                                                             base_url=None) # useless here

    def url(self, name):
        return game_file_url(name)

protected_game_file_system_storage = ProtectedGameFileSystemStorage()
