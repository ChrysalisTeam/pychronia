# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import register_view, AbstractGameForm, AbstractDataTableManagement, DataTableForm
from django_select2 import Select2MultipleChoiceField
from django import forms
from pychronia_game.datamanager.abstract_form import GAMEMASTER_HINTS_FIELD


class GlobalContactForm(DataTableForm):

    avatar = forms.CharField(label=ugettext_lazy("Avatar (url or local file)"), required=False)

    description = forms.CharField(label=ugettext_lazy("Description"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=False)

    # NOT YET SETUP is_public = forms.BooleanField(label=ugettext_lazy("Public contact"), required=False, initial=True) # public by default

    # NOT YET SETUP access_tokens = Select2MultipleChoiceField(label=ugettext_lazy("Or restricted to (then ensure the field above is unchecked)"), required=False)

    gamemaster_hints = GAMEMASTER_HINTS_FIELD()

    ###test = Select2TagsField(label=ugettext_lazy("TESTING"), choice_tags=["kkk", "lll"])

    def __init__(self, datamanager, **kwargs):
        initial = kwargs.get("initial")
        # NOT YET SETUP if initial and "access_tokens" in initial:
        # NOT YET SETUP     initial["is_public"] = (initial["access_tokens"] is None) # else, we let it be false
        super(GlobalContactForm, self).__init__(datamanager=datamanager, **kwargs)
        # NOT YET SETUP assert not self.fields["access_tokens"].choices
        # NOT YET SETUP self.fields["access_tokens"].choices = datamanager.build_select_choices_from_character_usernames(datamanager.get_character_usernames(), add_empty=False)

    def get_normalized_values(self):
        values = super(GlobalContactForm, self).get_normalized_values()
        return values

        """
        # NOT YET SETUP
        if values["is_public"]:
            values["access_tokens"] = None # special value
        del values["is_public"]
        return values
        """



@register_view
class GlobalContactsManagement(AbstractDataTableManagement):

    TITLE = ugettext_lazy("Contacts Management")
    NAME = "global_contacts_management"

    GAME_ACTIONS = dict(submit_item=dict(title=ugettext_lazy("Submit a contact"),
                                                          form_class=GlobalContactForm,
                                                          callback="submit_item"),
                        delete_item=dict(title=ugettext_lazy("Delete a contact"),
                                                          form_class=None,
                                                          callback="delete_item"))

    TEMPLATE = "administration/global_contacts_management.html"


    def get_data_table_instance(self):
        return self.datamanager.global_contacts


