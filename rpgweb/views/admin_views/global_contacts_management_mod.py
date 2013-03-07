# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import register_view, AbstractGameForm, AbstractDataTableManagement, DataTableForm
from django import forms


class GlobalContactForm(DataTableForm):

    avatar = forms.CharField(label=_lazy("Avatar"), required=False)
    description = forms.CharField(label=_lazy("Description"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=False)
    
    ###test = Select2TagsField(label=_lazy("TESTING"), choice_tags=["kkk", "lll"])

    def get_normalized_values(self):
        values = super(GlobalContactForm, self).get_normalized_values()
        return values # HERE TWEAK access_tokens TODO

### TODO - DEAL WITH IMMUTABLES ???

@register_view
class GlobalContactsManagement(AbstractDataTableManagement):

    NAME = "global_contacts_management"

    GAME_FORMS = {"submit_item": (GlobalContactForm, "submit_item")}
    ACTIONS = {"delete_item": "delete_item"}
    TEMPLATE = "administration/global_contacts_management.html"


    def get_data_table_instance(self):
        return self.datamanager.global_contacts


