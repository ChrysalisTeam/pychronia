# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import register_view, AbstractGameForm, AbstractDataTableManagement, DataTableForm
from django_select2 import Select2MultipleChoiceField
from django import forms


class GlobalContactForm(DataTableForm):

    avatar = forms.CharField(label=_lazy("Avatar"), required=False)

    description = forms.CharField(label=_lazy("Description"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=False)

    is_public = forms.BooleanField(label=_lazy("Public contact"), required=False, initial=True) # public by default

    access_tokens = Select2MultipleChoiceField(label=_lazy("Or restricted to"), required=False)

    ###test = Select2TagsField(label=_lazy("TESTING"), choice_tags=["kkk", "lll"])

    def __init__(self, datamanager, **kwargs):
        initial = kwargs.get("initial")
        if initial and "access_tokens" in initial:
            initial["is_public"] = (initial["access_tokens"] is None) # else, we let it be false
        super(GlobalContactForm, self).__init__(datamanager=datamanager, **kwargs)
        assert not self.fields["access_tokens"].choices
        self.fields["access_tokens"].choices = datamanager.build_select_choices_from_usernames(datamanager.get_character_usernames())

    def get_normalized_values(self):
        values = super(GlobalContactForm, self).get_normalized_values()
        if values["is_public"]:
            values["access_tokens"] = None # special value
        del values["is_public"]
        return values




@register_view
class GlobalContactsManagement(AbstractDataTableManagement):

    TITLE = _lazy("Contacts Management")
    NAME = "global_contacts_management"

    GAME_ACTIONS = dict(submit_item=dict(title=_lazy("Submit a contact"),
                                                          form_class=GlobalContactForm,
                                                          callback="submit_item"),
                        delete_item=dict(title=_lazy("Delete a contact"),
                                                          form_class=None,
                                                          callback="delete_item"))

    TEMPLATE = "administration/global_contacts_management.html"


    def get_data_table_instance(self):
        return self.datamanager.global_contacts


