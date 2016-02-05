# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import UninstantiableFormError, AbstractAbility, register_view, readonly_method, transaction_watcher
from pychronia_game.forms import AbstractGameForm
from django import forms
from django.forms.fields import ChoiceField
from django.core.exceptions import ValidationError
from pychronia_game.utilities.select2_extensions import Select2TagsField


class WiretappingTargetsForm(AbstractGameForm):
    def __init__(self, ability, *args, **kwargs):
        super(WiretappingTargetsForm, self).__init__(ability, *args, **kwargs)
        # dynamic fields here ...

        self._usernames = ability.get_character_usernames(exclude_current=True) # for data validation
        #user_choices = ability.build_select_choices_from_character_usernames(names)

        num_slots = ability.get_wiretapping_slots_count()
        if not num_slots:
            raise UninstantiableFormError(_("No wiretapping slots available."))

        other_known_characters = ability.get_other_known_characters()
        for i in range(num_slots):
            ''' PROBLEM WITH CASE SENISITIVITY
            self.fields["target_%d" % i] = forms.ChoiceField(label=_("Target %d") % i,
                                                             required=False,
                                                             choices=[("", "")] + user_choices,
                                                             widget=forms.TextInput) # IMPORTANT - HIDE possible choices
            '''
            field_name = "target_%d" % i
            self.fields[field_name] = Select2TagsField(label=_("Target %d") % i, required=False)
            self.fields[field_name].choice_tags = other_known_characters
            self.fields[field_name].max_selection_size = 1 # IMPORTANT


    def clean(self):
        cleaned_data = super(WiretappingTargetsForm, self).clean()

        for (key, value) in cleaned_data.items():
            if key.startswith("target_"):
                assert not isinstance(value, basestring) # we expect a container
                value = value[0].strip().lower() if value else None
                if value:
                    for real_username in self._usernames:
                        if value == real_username.lower():
                            cleaned_data[key] = real_username # we restore the case of userame
                            break
                    else:
                        raise ValidationError(ChoiceField.default_error_messages['invalid_choice'] % {'value': value})
                else:
                    cleaned_data[key] = ""

        return cleaned_data


    def get_normalized_values(self):
        parameters = super(WiretappingTargetsForm, self).get_normalized_values()

        targets = set()
        for (key, value) in parameters.items():
            if key.startswith("target_") and value:
                targets.add(value) # no need to delete the "target_%d" field

        parameters["target_names"] = sorted(list(targets))

        return parameters



class WiretappingSlotsPurchaseForm(AbstractGameForm):
    pass

class WiretappingConfidentialityForm(AbstractGameForm):
    pass



@register_view
class WiretappingAbility(AbstractAbility):

    TITLE = ugettext_lazy("Wiretapping")
    NAME = "wiretapping"

    GAME_ACTIONS = dict(targets_form=dict(title=ugettext_lazy("Choose wiretapping targets"),
                                                  form_class=WiretappingTargetsForm,
                                                  callback="change_current_user_wiretapping_targets"),
                        purchase_wiretapping_slot=dict(title=ugettext_lazy("Purchase wiretapping slot"),
                                                      form_class=WiretappingSlotsPurchaseForm,
                                                      callback="purchase_wiretapping_slot"),
                        purchase_confidentiality_protection=dict(title=ugettext_lazy("Purchase confidentiality protection"),
                                                                  form_class=WiretappingConfidentialityForm,
                                                                  callback="purchase_confidentiality_protection",
                                                                  requires_permission="purchase_confidentiality_protection"))

    TEMPLATE = "abilities/wiretapping_management.html"

    ACCESS = UserAccess.character
    REQUIRES_CHARACTER_PERMISSION = True
    REQUIRES_GLOBAL_PERMISSION = True

    EXTRA_PERMISSIONS = ["purchase_confidentiality_protection"] # NOT YET ACTIVATED



    def _get_admin_summary_html(self):
        assert self.is_master()

        usernames = self.get_character_usernames()

        wiretapping_packs = []
        for username in usernames:
            current_targets = self.get_wiretapping_targets(username=username)
            has_confidentiality_activated = self.get_confidentiality_protection_status(username=username)
            if not current_targets and not has_confidentiality_activated:
                continue
            data = dict(has_confidentiality_activated=has_confidentiality_activated,
                        current_targets=current_targets,
                        broken_wiretapping_targets=list(self.determine_broken_wiretapping_data(username=username).keys()),)
            wiretapping_packs.append((username, data))

        template_vars = dict(wiretapping_packs=wiretapping_packs)
        res = render_to_string("abilities/wiretapping_management_summary.html",
                               template_vars)
        return res


    @readonly_method
    def get_template_vars(self, previous_form_data=None):

        current_targets = self.get_wiretapping_targets()
        initial_data = {}
        for i in range(self.get_wiretapping_slots_count()):
            if i < len(current_targets):
                initial_data["target_%d" % i] = [current_targets[i]]
            else:
                initial_data["target_%d" % i] = []

        #print (">>>initial_data targets", initial_data)

        targets_form = self._instantiate_game_form(new_action_name="targets_form",
                                              hide_on_success=False,
                                              initial_data=initial_data,
                                              previous_form_data=previous_form_data,)

        return {
                 'page_title': _("Wiretapping Management"),
                 'current_targets': self.build_visible_character_names(current_targets),
                 'confidentiality_form': self._instantiate_game_form(new_action_name="purchase_confidentiality_protection"), # might be None if no personal permissions
                 'wiretapping_targets_form': targets_form,
                 'slots_purchase_form': self._instantiate_game_form(new_action_name="purchase_wiretapping_slot"),
                 'has_confidentiality_activated': self.get_confidentiality_protection_status(),
                 'broken_wiretapping_targets': self.determine_broken_wiretapping_data().keys(),
                }


    @transaction_watcher
    def purchase_wiretapping_slot(self, use_gems=()):
        # supposed to be paying, of course...
        self.private_data["max_wiretapping_targets"] += 1
        return _("Wiretapping slot properly purchased.")


    def get_wiretapping_slots_count(self):
        return self.private_data["max_wiretapping_targets"]


    @transaction_watcher
    def change_current_user_wiretapping_targets(self, target_names, use_gems=()):

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

        self.datamanager.log_game_event(ugettext_noop("Wiretapping targets set to (%(targets)s)."),
                             PersistentMapping(targets=", ".join(target_names)),
                             url=None,
                             visible_by=[self.username])

        return _("Wiretapping successfully set up.")


    @transaction_watcher
    def purchase_confidentiality_protection(self, use_gems=()):
        if self.get_confidentiality_protection_status():
            raise AbnormalUsageError(_("You already have confidentiality system activated"))
        self.set_confidentiality_protection_status(has_confidentiality=True)
        self.datamanager.log_game_event(ugettext_noop("Confidentiality system activated."),
                                        visible_by=[self.username])
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

        for username, data in self.all_private_data.items():
            assert len(self.get_wiretapping_targets(username=username)) <= data["max_wiretapping_targets"]

            '''
            character_names = self.datamanager.get_character_usernames()
            for char_name in data["wiretapping_targets"]:
                assert char_name in character_names
            '''



