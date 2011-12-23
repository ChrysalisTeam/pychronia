# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from ._abstract_ability import *
from ..datamanager import *




class WiretappingTargetsForm(AbstractAbilityForm):
    def __init__(self, datamanager, *args, **kwargs):
        super(WiretappingTargetsForm, self).__init__(datamanager, *args, **kwargs)
        # dynamic fields here ...

        names = datamanager.get_character_usernames()
        user_choices = datamanager.build_select_choices_from_usernames(names)

        for i in range(datamanager.abilities.wiretapping.get_ability_parameter("max_wiretapping_targets")):
            self.fields["target_%d"%i] = forms.ChoiceField(label=_("Target %d")%i, required=False, choices=[("", "")]+user_choices)

    def get_normalized_values(self):
        parameters = super(WiretappingTargetsForm, self).get_normalized_values()

        targets = set()
        for (key, value) in parameters.items():
            if key.startswith("target_") and value:
                targets.add(value) # no need to delete the "target_%d" field
        parameters["target_names"] = sorted(list(targets))

        return parameters





class WiretappingAbility(AbstractAbilityHandler):

    TITLE = _lazy("Wiretapping")
    
    NAME = "wiretapping"

    FORMS = {"targets_form": (WiretappingTargetsForm, "change_wiretapping_targets")}

    TEMPLATE = "abilities/wiretapping_management.html"

    ACCESS = "player"
    
    REQUIREMENTS = ["messaging"]


    @readonly_method
    def get_template_vars(self, **previous_form_data):

        current_targets = self.get_current_targets()
        initial_data = {}
        for i in range(self.get_ability_parameter("max_wiretapping_targets")):
            if i < len(current_targets):
                initial_data["target_%d"%i] = current_targets[i]
            else:
                initial_data["target_%d"%i] = ""

        targets_form = self._instantiate_form(new_form_name="targets_form", hide_on_success=False,
                                                  initial_data=initial_data,
                                                  **previous_form_data)

        return {
                 'page_title': _("Wiretapping Management"),
                 'current_targets': current_targets,
                 'wiretapping_form': targets_form,
                }


    @transaction_watcher
    def change_wiretapping_targets(self, target_names):
        
        ####### DUPLICATED OF MODULE'S
        target_names = sorted(list(set(target_names))) # renormalization, just in case

        character_names = self._datamanager.get_character_usernames()
        for name in target_names:
            if name not in character_names:
                print("tRAGTES", target_names, name)
                raise AbnormalUsageError(_("Unknown target user %(target)s") % SDICT(target=name)) # we can show it

        if len(target_names) > self.get_ability_parameter("max_wiretapping_targets"):
            raise AbnormalUsageError(_("Too many wiretapping targets"))

        self.private_data["wiretapping_targets"] = PersistentList(target_names)

        self._datamanager.log_game_event(_noop("Wiretapping targets set to (%(targets)s) by %(username)s."),
                             PersistentDict(targets=", ".join(target_names), username=self._datamanager.user.username),
                             url=None)

        return _("Wiretapping successfully set up.")


    @readonly_method
    def get_current_targets(self):
        return self.private_data["wiretapping_targets"]

    @readonly_method
    def get_listeners_for(self, target):
        listeners = []
        for player, private_data in self.all_private_data.items():
            if target in private_data["wiretapping_targets"]:
                listeners.append(player)
        return sorted(listeners)

    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # all must be OK


    def _setup_private_ability_data(self, private_data):
        private_data.setdefault("wiretapping_targets", PersistentList())


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        _settings_reference = dict(
                                    max_wiretapping_targets=utilities.check_positive_int
                                  )
        utilities.check_dictionary_with_template(settings, _settings_reference, strict=strict)

        for data in self.all_private_data.values():

            assert len(data["wiretapping_targets"]) <= settings["max_wiretapping_targets"]

            character_names = self._datamanager.get_character_usernames()
            for char_name in data["wiretapping_targets"]:
                assert char_name in character_names
