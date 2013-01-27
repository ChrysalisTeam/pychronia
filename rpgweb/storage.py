# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django.core.files.storage import FileSystemStorage
from .utilities import config
from rpgweb.common import game_file_url


class ProtectedGameFileSystemStorage(FileSystemStorage):
    """
    Replacement for ThumbnailFileSystemStorage, which builds "obfuscated urls" for thumbnails.
    """

    def __init__(self):
        super(ProtectedGameFileSystemStorage, self).__init__(location=config.GAME_FILES_ROOT,
                                                             base_url=None) # useless here

    def url(self, name):
        return game_file_url(name)
