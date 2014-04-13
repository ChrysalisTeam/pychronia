# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.datamanager.abstract_form import GAMEMASTER_HINTS_FIELD
from pychronia_game.datamanager.datamanager_modules import StaticPages, Encyclopedia
from pychronia_game.common import *
from pychronia_game.datamanager import register_view, AbstractGameForm, AbstractDataTableManagement, DataTableForm
from pychronia_game.utilities.select2_extensions import Select2TagsField
from django import forms
from pychronia_game.datamanager.abstract_game_view import AbstractGameView




@register_view
class EncryptedFoldersManagement(AbstractGameView):

    TITLE = ugettext_lazy("Encrypted Folders")
    NAME = "encrypted_folders_management"

    TEMPLATE = "administration/encrypted_folders_management.html"

    ACCESS = UserAccess.master
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False

    def get_template_vars(self, previous_form_data=None):

        folders_info = self.datamanager.get_all_encrypted_folders_info()

        return dict(folders_info=sorted(folders_info.items()))
