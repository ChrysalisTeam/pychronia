# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import register_view, AbstractGameForm, AbstractDataTableManagement, DataTableForm
from django_select2 import Select2MultipleChoiceField
from django import forms
from pychronia_game.datamanager.abstract_form import GAMEMASTER_HINTS_FIELD


class GameItemForm(DataTableForm):

    auction = forms.CharField(label=ugettext_lazy("Auction"), required=False)  # can be empty string

    title = forms.CharField(label=ugettext_lazy("Title"), required=True)

    comments = forms.CharField(label=ugettext_lazy("Description"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=True)

    image = forms.CharField(label=ugettext_lazy("Image (url or local file)"), required=True)

    is_gem = forms.BooleanField(label=_("Made of gems"), initial=False, required=False)

    total_price = forms.IntegerField(label=ugettext_lazy("Total cost"), min_value=0, required=True)

    num_items = forms.IntegerField(label=ugettext_lazy("Count of items"), min_value=1, required=True)

    unit_cost = forms.IntegerField(label=ugettext_lazy("Unit cost"), min_value=0, required=True)

    gamemaster_hints = GAMEMASTER_HINTS_FIELD()



@register_view
class GameItemsManagement(AbstractDataTableManagement):

    TITLE = ugettext_lazy("Game Items Management")
    NAME = "game_items_management"

    GAME_ACTIONS = dict(submit_item=dict(title=ugettext_lazy("Submit an item"),
                                                          form_class=GameItemForm,
                                                          callback="submit_item"),
                        delete_item=dict(title=ugettext_lazy("Delete an item"),
                                                          form_class=None,
                                                          callback="delete_item"))

    TEMPLATE = "administration/game_items_management.html"


    def get_data_table_instance(self):
        return self.datamanager.game_items


