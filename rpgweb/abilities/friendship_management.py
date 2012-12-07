# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from ._abstract_ability import *


"""
class TranslationForm(AbstractGameForm):
    def __init__(self, ability, *args, **kwargs):
        super(TranslationForm, self).__init__(ability, *args, **kwargs)

        _translatable_items_ids = ability.get_translatable_items().keys()
        _translatable_items_pretty_names = [ability.get_all_items()[item_name]["title"] for item_name in _translatable_items_ids]
        _translatable_items_choices = zip(_translatable_items_ids, _translatable_items_pretty_names)
        _translatable_items_choices.sort(key=lambda double: double[1])

        # WARNING - we always put ALL runic items, even before they have been sold at auction - it's OK !
        self.fields["target_item"] = forms.ChoiceField(label=_("Object"), choices=_translatable_items_choices)
        self.fields["transcription"] = forms.CharField(label=_("Transcription"), widget=forms.Textarea(attrs={'rows': '5', 'cols':'30'}))
"""



@register_view
class FriendshipManagementAbility(AbstractAbility):


    NAME = "friendship_management"

    GAME_FORMS = {}
    ADMIN_FORMS = {}

    TEMPLATE = "abilities/friendship_management.html"

    ACCESS = UserAccess.authenticated
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_template_vars(self, previous_form_data=None):

        username = self.datamanager.user.username
        friendship_statuses = self.datamanager.get_other_characters_friendship_statuses(username)
        friendship_statuses = sorted(friendship_statuses.items()) # list of pairs (other_username, relation_type) 

        return {
                 'page_title': _("Friendship Management"),
                 "friendship_statuses": friendship_statuses,
               }




    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # Nothing to do, all translation data must be fully present in initial fixture

    def _setup_private_ability_data(self, private_data):
        pass # nothing stored here at the moment


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        if strict:
            assert not any(self.all_private_data)

