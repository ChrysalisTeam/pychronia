# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import json

from django import forms
from django_select2 import Select2MultipleWidget

from pychronia_game.common import *
from pychronia_game.datamanager.abstract_form import (AbstractGameForm, SimpleForm, UninstantiableFormError,
                                                      GemHandlingFormUtils, autostrip_form_charfields, GAMEMASTER_HINTS_FIELD)
from pychronia_game.utilities import add_to_ordered_dict


def _get_bank_choice(datamanager):
    return (datamanager.get_global_parameter("bank_name"), '<' + _("Bank") + '>')


class MoneyTransferForm(AbstractGameForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(MoneyTransferForm, self).__init__(datamanager, *args, **kwargs)
        user = datamanager.user

        # dynamic fields here ...
        if user.is_master:
            _money_all_character_choices = [_get_bank_choice(datamanager)] + \
                                            datamanager.build_select_choices_from_character_usernames(datamanager.get_character_usernames())
            self.fields = add_to_ordered_dict(self.fields, 0, "sender_name", forms.ChoiceField(label=_("Sender"), choices=_money_all_character_choices))
            self.fields = add_to_ordered_dict(self.fields, 1, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=_money_all_character_choices))
        else:
            # for standard characters
            if datamanager.get_character_properties()["account"] <= 0:
                raise UninstantiableFormError(_("No money available for transfer."))
            others = datamanager.get_other_known_characters()
            others_choices = datamanager.build_select_choices_from_character_usernames(others, add_empty=True)
            self.fields = add_to_ordered_dict(self.fields, 0, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=others_choices))


    amount = forms.IntegerField(label=ugettext_lazy("Amount"), widget=forms.TextInput(attrs={'size':'8', 'style':'text-align:left;', 'autocomplete':'off'}),
                                initial=0, min_value=1, max_value=1000000)

    reason = forms.CharField(label=ugettext_lazy("Reason"), required=False)


class GemsTransferForm(AbstractGameForm, GemHandlingFormUtils):


    def __init__(self, datamanager, *args, **kwargs):
        super(GemsTransferForm, self).__init__(datamanager, *args, **kwargs)
        user = datamanager.user

        if user.is_master:
            available_gems = datamanager.get_global_parameter("spent_gems")[:]  # COPY, gems taken so that we can "revive" them
            for character, properties in datamanager.get_character_sets().items():
                available_gems += properties["gems"]
        else:
            available_gems = datamanager.get_character_properties()["gems"]

        # we prepare the choice sets for gems
        gems_choices = zip(self._encode_gems(available_gems), [self._gem_display(gem) for gem in available_gems])
        gems_choices.sort(key=lambda x: x[1])
        if not gems_choices:
            raise UninstantiableFormError("no gems available")

        # dynamic fields here ...
        if user.is_master:
            _character_choices = datamanager.build_select_choices_from_character_usernames(datamanager.get_character_usernames(), add_empty=True)
            _character_choices.insert(1, _get_bank_choice(datamanager))  # we add the BANK as sender and recipient!
            self.fields = add_to_ordered_dict(self.fields, 0, "sender_name", forms.ChoiceField(label=_("Sender"), choices=_character_choices))
            self.fields = add_to_ordered_dict(self.fields, 1, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=_character_choices))
        else:
            others = datamanager.get_other_known_characters()  # character CANNOT send gems to the Bank here
            others_choices = datamanager.build_select_choices_from_character_usernames(others, add_empty=True)
            self.fields = add_to_ordered_dict(self.fields, 1, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=others_choices))

        self.fields = add_to_ordered_dict(self.fields, 2, "gems_choices", forms.MultipleChoiceField(required=False, label=_("Gems"), choices=gems_choices, widget=forms.SelectMultiple(attrs={"class": "multichecklist"})))


    def clean(self):
        """We transform back *gems_choices* to proper python objects."""
        cleaned_data = super(GemsTransferForm, self).clean()

        raw_gems_choices = cleaned_data.get("gems_choices") # might be None, if errors

        if raw_gems_choices:
            cleaned_data["gems_choices"] = self._decode_gems(raw_gems_choices)

        return cleaned_data



class ArtefactTransferForm(AbstractGameForm):

    artefact_name = forms.ChoiceField(label=ugettext_lazy("Artefact"), required=True)
    recipient_name = forms.ChoiceField(label=ugettext_lazy("Recipient"), required=True)

    def __init__(self, datamanager, *args, **kwargs):
        super(ArtefactTransferForm, self).__init__(datamanager, *args, **kwargs)

        artefacts = datamanager.get_user_artefacts() # dicts
        artefacts_choices = [(name, value["title"]) for (name, value) in artefacts.items()]
        artefacts_choices.sort(key=lambda x: x[1])  # sorted by title
        self.fields["artefact_name"].choices = [("", _("None"))] + artefacts_choices

        others = datamanager.get_other_known_characters()
        others_choices = datamanager.build_select_choices_from_character_usernames(others, add_empty=True)
        self.fields["recipient_name"].choices = others_choices

        if not artefacts_choices or not others_choices:
            raise UninstantiableFormError("No artefact or recipient available")





""" ???
class DropdownMultiSelect(forms.SelectMultiple):
    
    def render(self, name, value, attrs=None, choices=()):
        if value is None: value = []
        final_attrs = self.build_attrs(attrs, name=name)
        output = [u'<select multiple="multiple"%s>' % flatatt(final_attrs)]
        options = self.render_options(choices, value)
        if options:
            output.append(options)
        output.append('</select>')
        return mark_safe(u'\n'.join(output))

    def value_from_datadict(self, data, files, name):
        if isinstance(data, (MultiValueDict, MergeDict)):
            return data.getlist(name)
        return data.get(name, None)

    def _has_changed(self, initial, data):
        if initial is None:
            initial = []
        if data is None:
            data = []
        if len(initial) != len(data):
            return True
        initial_set = set([force_unicode(value) for value in initial])
        data_set = set([force_unicode(value) for value in data])
        return data_set != initial_set
    """


@autostrip_form_charfields
class CharacterProfileForm(AbstractGameForm):
    """
    CHAR fields are auto-stripped thanks to that base class.
    """
    target_username = forms.CharField(widget=forms.HiddenInput())

    is_npc = forms.BooleanField(label=ugettext_lazy("Is NPC"), required=False)

    official_name = forms.CharField(label=ugettext_lazy("Official name"), required=True, max_length=100)
    official_role = forms.CharField(label=ugettext_lazy("Official role"), required=True, max_length=500)

    real_life_identity = forms.CharField(label=ugettext_lazy("Real life identity"), required=False, max_length=100)
    real_life_email = forms.EmailField(label=ugettext_lazy("Real life email"), required=False)

    gamemaster_hints = GAMEMASTER_HINTS_FIELD() # optional

    allegiances = forms.MultipleChoiceField(label=ugettext_lazy("Allegiances"), required=False, widget=forms.SelectMultiple(attrs={"class": "multichecklist"}))
    permissions = forms.MultipleChoiceField(label=ugettext_lazy("Permissions"), required=False, widget=forms.SelectMultiple(attrs={"class": "multichecklist"}))

    extra_goods = forms.CharField(label=ugettext_lazy("Extra Goods"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=False)


    def __init__(self, datamanager, *args, **kwargs):
        super(CharacterProfileForm, self).__init__(datamanager, *args, **kwargs)

        allegiances_choices = datamanager.build_domain_select_choices()
        permissions_choices = datamanager.build_permission_select_choices()

        self.fields['allegiances'].choices = allegiances_choices
        self.fields['permissions'].choices = permissions_choices



class SimplePasswordForm(SimpleForm):
    simple_password = forms.CharField(label=ugettext_lazy("Password"), required=True, widget=forms.PasswordInput)

class CleartextPasswordForm(SimpleForm):
    simple_password = forms.CharField(label=ugettext_lazy("Password"), required=True, widget=forms.TextInput(attrs={"autocomplete": "off"}))


class AuthenticationForm(SimpleForm):
    secret_username = forms.CharField(label=ugettext_lazy("Username"), required=True, max_length=30, widget=forms.TextInput(attrs={'autocomplete':'on'}))
    secret_password = forms.CharField(label=ugettext_lazy("Password"), required=False, max_length=30, widget=forms.PasswordInput(attrs={'autocomplete':'off'}))  # not required for "password forgotten" action



class PasswordChangeForm(AbstractGameForm):

    old_password = forms.CharField(label=ugettext_lazy("Current password"), required=True, widget=forms.PasswordInput)
    new_password1 = forms.CharField(label=ugettext_lazy("New password"), required=True, widget=forms.PasswordInput)
    new_password2 = forms.CharField(label=ugettext_lazy("New password (again)"), required=True, widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super(PasswordChangeForm, self).clean()

        new_password1 = cleaned_data.get("new_password1") # might be None
        new_password2 = cleaned_data.get("new_password2") # might be None

        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError(_("New passwords not matching"))

        # Always return the full collection of cleaned data.
        return cleaned_data



class SecretQuestionForm(SimpleForm):
    secret_username = forms.CharField(widget=forms.HiddenInput())
    secret_answer = forms.CharField(label=ugettext_lazy("Answer"), max_length=50, widget=forms.TextInput(attrs={'autocomplete':'off'}))
    target_email = forms.EmailField(label=ugettext_lazy("Email"), max_length=50)

    def __init__(self, username, *args, **kwargs):
        super(SecretQuestionForm, self).__init__(*args, **kwargs)
        self.fields["secret_username"].initial = username


class RadioFrequencyForm(SimpleForm):
    frequency = forms.CharField(label=ugettext_lazy(u"Radio Frequency"), widget=forms.TextInput(attrs={'autocomplete':'off'}))





class TranslationForm(SimpleForm):
    def __init__(self, datamanager, *args, **kwargs):
        super(TranslationForm, self).__init__(*args, **kwargs)

        _translatable_items_ids = datamanager.get_translatable_items().keys()
        _translatable_items_pretty_names = [datamanager.get_all_items()[item_name]["title"] for item_name in _translatable_items_ids]
        _translatable_items_choices = zip(_translatable_items_ids, _translatable_items_pretty_names)
        _translatable_items_choices.sort(key=lambda double: double[1])

        # WARNING - we always put ALL runic items, even before they have been sold at auction - it's OK !
        self.fields["target_item"] = forms.ChoiceField(label=_("Object"), choices=_translatable_items_choices)
        self.fields["transcription"] = forms.CharField(label=_("Transcription"), widget=forms.Textarea(attrs={'rows': '5', 'cols':'30'}))



class ScanningForm(SimpleForm):
    def __init__(self, available_items, *args, **kwargs):
        super(ScanningForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...
        reference_items_choices = [("", _("< Use Description Instead >"))]
        reference_items_choices += [(name, value["title"]) for (name, value) in available_items.items()]

        self.fields["item_name"] = forms.ChoiceField(label=_("Reference Object"), choices=reference_items_choices, required=False)

        self.fields["description"] = forms.CharField(label=_("Or Description"), required=False,
                                                     widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}))





class ArmedInterventionForm(SimpleForm):

    message = forms.CharField(label=ugettext_lazy("Message"),
                              widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}))

    def __init__(self, available_locations, *args, **kwargs):
        super(ArmedInterventionForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...
        available_locations_choices = [(name, name.capitalize()) for name in available_locations]
        self.fields["city_name"] = forms.ChoiceField(label=_("Location"), choices=available_locations_choices)



class ___TelecomInvestigationForm(SimpleForm):

    def __init__(self, datamanager, user, *args, **kwargs):
        super(TelecomInvestigationForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...

        others = datamanager.get_other_known_characters()
        others_choices = datamanager.build_select_choices_from_character_usernames(others)
        self.fields["official_name"] = forms.ChoiceField(label=_("Name"), choices=others_choices)




class ArtefactForm(AbstractGameForm):
    def __init__(self, ability, *args, **kwargs):
        super(ArtefactForm, self).__init__(ability, *args, **kwargs)

        _user_artefacts = ability.get_user_artefacts()

        if not _user_artefacts:
            raise UninstantiableFormError(_("No artefacts currently owned."))

        _user_artefacts_choices = [(key, value["title"]) for (key, value) in _user_artefacts.items()]
        _user_artefacts_choices.sort(key=lambda pair: pair[1])

        _user_artefacts_choices = [("", _("Select your artefact..."))] + _user_artefacts_choices
        self.fields["item_name"] = forms.ChoiceField(label=_("Object"), choices=_user_artefacts_choices, required=True)



class OtherCharactersForm(AbstractGameForm):


    def __init__(self, datamanager, *args, **kwargs):
        super(OtherCharactersForm, self).__init__(datamanager=datamanager, *args, **kwargs)

        usernames = datamanager.get_character_usernames(exclude_current=True)
        usernames_choices = datamanager.build_select_choices_from_character_usernames(usernames)
        self.fields['target_username'] = forms.ChoiceField(label=_("User"), choices=usernames_choices)


'''
class CharacterForm(SimpleForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(CharacterForm, self).__init__(*args, **kwargs)

        _usernames = datamanager.get_character_usernames()
        _usernames_choices = zip(_usernames, _usernames)
        _usernames_choices.sort()

        self.fields['target_username'] = forms.ChoiceField(label=_("User"), choices=_usernames_choices)
'''
