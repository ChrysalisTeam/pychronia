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
class AdminInformation(AbstractGameView):

    TITLE = ugettext_lazy("Admin Information")
    NAME = "admin_information"

    TEMPLATE = "administration/admin_information.html"

    ACCESS = UserAccess.master
    REQUIRES_CHARACTER_PERMISSION = False
    REQUIRES_GLOBAL_PERMISSION = False


    def get_template_vars(self, previous_form_data=None):

        global_parameters = self.datamanager.get_global_parameters()

        folders_info = self.datamanager.get_all_encrypted_folders_info()

        # we sort these by view identifier, for now
        admin_summaries = self.datamanager.get_game_view_admin_summaries()
        admin_summaries = sorted(admin_summaries.items(), key=lambda x: x[0])

        return dict(global_parameters=global_parameters,
                    folders_info=sorted(folders_info.items()),
                    admin_summaries=admin_summaries)
