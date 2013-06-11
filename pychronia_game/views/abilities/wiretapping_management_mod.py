# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import UninstantiableFormError, AbstractAbility, register_view, readonly_method, transaction_watcher
from pychronia_game.forms import AbstractGameForm
from django import forms


class WiretappingTargetsForm(AbstractGameForm):
    def __init__(self, ability, *args, **kwargs):
        super(WiretappingTargetsForm, self).__init__(ability, *args, **kwargs)
        # dynamic fields here ...

        names = ability.get_character_usernames(exclude_current=True)
        user_choices = ability.build_select_choices_from_usernames(names)

        num_slots = ability.get_wiretapping_slots_count()

        if not num_slots:
            raise UninstantiableFormError(_("No wiretapping slots available."))
        for i in range(num_slots):
            self.fields["target_%d" % i] = forms.ChoiceField(label=_("Target %d") % i, required=False, choices=[("", "")] + user_choices)

    def get_normalized_values(self):
        parameters = super(WiretappingTargetsForm, self).get_normalized_values()

        targets = set()
        for (key, value) in parameters.items():
            if key.startswith("target_") and value:
                targets.add(value) # no need to delete the "target_%d" field
        parameters["target_names"] = sorted(list(targets))

        return parameters




@register_view
class WiretappingAbility(AbstractAbility):

    TITLE = _lazy("Wiretapping")
    NAME = "wiretapping"

    GAME_ACTIONS = dict(targets_form=dict(title=_lazy("Choose wiretapping targets"),
                                                  form_class=WiretappingTargetsForm,
                                                  callback="change_current_user_wiretapping_targets"),
                        purchase_wiretapping_slot=dict(title=_lazy("Purchase wiretapping slot"),
                                                      form_class=None,
                                                      callback="purchase_wiretapping_slot"),
                        purchase_confidentiality_protection=dict(title=_lazy("Purchase confidentiality protection"),
                                                                  form_class=None,
                                                                  callback="purchase_confidentiality_protection",
                                                                  requires_permission="purchase_confidentiality_protection"))

    TEMPLATE = "abilities/wiretapping_management.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = False
    ALWAYS_ACTIVATED = True # FIXME

    EXTRA_PERMISSIONS = ["purchase_confidentiality_protection"] # NOT YET ACTIVATED


    @readonly_method
    def get_template_vars(self, previous_form_data=None):

        current_targets = self.get_wiretapping_targets()
        initial_data = {}
        for i in range(self.get_ability_parameter("max_wiretapping_targets")):
            if i < len(current_targets):
                initial_data["target_%d" % i] = current_targets[i]
            else:
                initial_data["target_%d" % i] = ""

        targets_form = self._instantiate_game_form(new_action_name="targets_form",
                                              hide_on_success=False,
                                              initial_data=initial_data,
                                              previous_form_data=previous_form_data,)

        return {
                 'page_title': _("Wiretapping Management"),
                 'current_targets': current_targets,
                 'wiretapping_form': targets_form,
                 'has_confidentiality_activated': self.get_confidentiality_protection_status(),
                 'broken_wiretapping_targets': self.determine_broken_wiretapping_data().keys(),
                }


    @transaction_watcher
    def purchase_wiretapping_slot(self):
        # supposed to be paying, of course...
        self.private_data["max_wiretapping_targets"] += 1

    def get_wiretapping_slots_count(self):
        return self.private_data["max_wiretapping_targets"]


    @transaction_watcher
    def change_current_user_wiretapping_targets(self, target_names):

        target_names = sorted(list(set(target_names))) # renormalization, just in case

        self.set_wiretapping_targets(target_names=target_names)

        if len(target_names) > self.get_wiretapping_slots_count():
            raise AbnormalUsageError(_("Too many wiretapping targets"))


        '''
        character_names = self.datamanager.get_character_usernames()
        for name in target_names:
            if name not in character_names:
                print("tRAGTES", target_names, name)
                raise AbnormalUsageError(_("Unknown target user %(target)s") % SDICT(target=name)) # we can show it



        self.private_data["wiretapping_targets"] = PersistentList(target_names)
        '''

        self.datamanager.log_game_event(_noop("Wiretapping targets set to (%(targets)s)."),
                             PersistentDict(targets=", ".join(target_names)),
                             url=None)

        return _("Wiretapping successfully set up.")


    @transaction_watcher
    def purchase_confidentiality_protection(self):
        if self.get_confidentiality_protection_status():
            raise AbnormalUsageError(_("You already have confidentiality system activated"))
        self.set_confidentiality_protection_status(has_confidentiality=True)
        return _("Confidentiality system properly activated.")


    @classmethod
    def _setup_ability_settings(cls, settings):
        pass # all must be OK


    def _setup_private_ability_data(self, private_data):
        private_data.setdefault("max_wiretapping_targets", 0)


    def _check_data_sanity(self, strict=False):

        settings = self.settings

        _settings_reference = dict(
                                    max_wiretapping_targets=partial(utilities.check_is_positive_int, non_zero=False)
                                  )
        utilities.check_dictionary_with_template(settings, _settings_reference, strict=strict)

        for data in self.all_private_data.values():

            assert len(data["wiretapping_targets"]) <= settings["max_wiretapping_targets"]

            '''
            character_names = self.datamanager.get_character_usernames()
            for char_name in data["wiretapping_targets"]:
                assert char_name in character_names
            '''
