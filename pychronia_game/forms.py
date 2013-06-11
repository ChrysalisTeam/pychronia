# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from django import forms
from pychronia_game.datamanager.abstract_form import AbstractGameForm, UninstantiableFormError, form_field_jsonify, form_field_unjsonify





class MoneyTransferForm(AbstractGameForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(MoneyTransferForm, self).__init__(datamanager, *args, **kwargs)
        user = datamanager.user

        # dynamic fields here ...
        if user.is_master:
            _money_all_character_choices = [(datamanager.get_global_parameter("bank_name"), '<' + _("Bank") + '>')] + \
                                            datamanager.build_select_choices_from_usernames(datamanager.get_character_usernames())

            self.fields.insert(0, "sender_name", forms.ChoiceField(label=_("Sender"), choices=_money_all_character_choices))
            self.fields.insert(1, "recipient_name", forms.ChoiceField(label=_("Recipient"),
                               initial=_money_all_character_choices[min(1, len(_money_all_character_choices) - 1)][0], choices=_money_all_character_choices))
        else:
            # for standard characters
            if datamanager.get_character_properties()["account"] <= 0:
                raise UninstantiableFormError(_("No money available for transfer."))
            others = datamanager.get_other_character_usernames()
            others_choices = datamanager.build_select_choices_from_usernames(others)
            self.fields.insert(0, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=others_choices))

    amount = forms.IntegerField(label=_("Amount"), widget=forms.TextInput(attrs={'size':'8', 'style':'text-align:center;'}),
                                initial=0, min_value=1, max_value=1000000)




class GemsTransferForm(AbstractGameForm):

    def __init__(self, datamanager, *args, **kwargs):
        super(GemsTransferForm, self).__init__(datamanager, *args, **kwargs)
        user = datamanager.user


        if user.is_master:
            available_gems = []
            for character, properties in datamanager.get_character_sets().items():
                available_gems += properties["gems"]
        else:
            available_gems = datamanager.get_character_properties()["gems"]

        # we prepare the choice sets for gems
        gems_choices = []
        for gem_value, gem_origin in available_gems:
            gem_id = form_field_jsonify((gem_value, gem_origin))
            if gem_origin:
                title = datamanager.get_item_properties(gem_origin)["title"]
            else:
                title = _("External gems")
            full_title = _("Gem of %s Kashes (%s)") % (gem_value, title)
            gems_choices.append((gem_id, full_title))
        if not gems_choices:
            raise UninstantiableFormError("no gems available")

        # dynamic fields here ...
        if user.is_master:
            _character_choices = datamanager.build_select_choices_from_usernames(datamanager.get_character_usernames())
            self.fields.insert(0, "sender_name", forms.ChoiceField(label=_("Sender"), choices=_character_choices))
            self.fields.insert(1, "recipient_name", forms.ChoiceField(label=_("Recipient"), initial=_character_choices[min(1, len(_character_choices) - 1)][0], choices=_character_choices))
        else:
            others = datamanager.get_other_character_usernames()
            others_choices = datamanager.build_select_choices_from_usernames(others)
            self.fields.insert(1, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=others_choices))

        self.fields.insert(2, "gems_choices", forms.MultipleChoiceField(required=False, label=_("Gems (use Ctrl key)"), choices=gems_choices))


    def clean(self):
        """We transform back *gems_choices* to proper python objects."""
        cleaned_data = super(GemsTransferForm, self).clean()

        raw_gems_choices = cleaned_data.get("gems_choices") # might be None, if errors

        if raw_gems_choices:
            gems_choices = [tuple(form_field_unjsonify(value)) for value in raw_gems_choices] # strings -> tuples (price, origin)
            cleaned_data["gems_choices"] = gems_choices

        return cleaned_data



class ArtefactTransferForm(AbstractGameForm):

    artefact_name = forms.ChoiceField(label=_lazy("Artefact"), required=True)
    recipient_name = forms.ChoiceField(label=_lazy("Recipient"), required=True)

    def __init__(self, datamanager, *args, **kwargs):
        super(ArtefactTransferForm, self).__init__(datamanager, *args, **kwargs)

        artefacts = datamanager.get_user_artefacts() # dicts
        artefacts_choices = [(name, value["title"]) for (name, value) in artefacts.items()]
        self.fields["artefact_name"].choices = artefacts_choices

        others = datamanager.get_other_character_usernames()
        others_choices = datamanager.build_select_choices_from_usernames(others)
        self.fields["recipient_name"].choices = others_choices

        if not artefacts_choices or not others_choices:
            raise UninstantiableFormError("No artefact or recipient available")

        #others = datamanager.get_other_character_usernames()




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

class CharacterProfileForm(forms.Form):
    target_username = forms.CharField(widget=forms.HiddenInput())

    real_life_identity = forms.CharField(label=_lazy("Real identity"), required=False, max_length=100)
    real_life_email = forms.EmailField(label=_lazy("Real email"), required=False)

    allegiances = forms.MultipleChoiceField(label=_lazy("Allegiances"), required=False, widget=forms.SelectMultiple(attrs={"class": "multichecklist"}))
    permissions = forms.MultipleChoiceField(label=_lazy("Permissions"), required=False, widget=forms.SelectMultiple(attrs={"class": "multichecklist"}))


    def __init__(self, allegiances_choices, permissions_choices, *args, **kwargs):
        super(CharacterProfileForm, self).__init__(*args, **kwargs)
        self.fields['allegiances'].choices = allegiances_choices
        self.fields['permissions'].choices = permissions_choices


class SimplePasswordForm(forms.Form):
    simple_password = forms.CharField(label=_lazy("Password"), required=True, widget=forms.PasswordInput)


class AuthenticationForm(forms.Form):
    secret_username = forms.CharField(label=_lazy("Username"), required=True, max_length=30, widget=forms.TextInput(attrs={'autocomplete':'on'}))
    secret_password = forms.CharField(label=_lazy("Password"), required=False, max_length=30, widget=forms.PasswordInput(attrs={'autocomplete':'off'}))  # not required for "password forgotten" action



class PasswordChangeForm(AbstractGameForm):

    old_password = forms.CharField(label=_lazy("Current password"), required=True, widget=forms.PasswordInput)
    new_password1 = forms.CharField(label=_lazy("New password"), required=True, widget=forms.PasswordInput)
    new_password2 = forms.CharField(label=_lazy("New password (again)"), required=True, widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super(PasswordChangeForm, self).clean()

        new_password1 = cleaned_data.get("new_password1") # might be None
        new_password2 = cleaned_data.get("new_password2") # might be None

        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError(_("New passwords not matching"))

        # Always return the full collection of cleaned data.
        return cleaned_data



class SecretQuestionForm(forms.Form):
    secret_username = forms.CharField(widget=forms.HiddenInput())
    secret_answer = forms.CharField(label=_lazy("Answer"), max_length=50, widget=forms.TextInput(attrs={'autocomplete':'off'}))
    target_email = forms.EmailField(label=_lazy("Email"), max_length=50)

    def __init__(self, username, *args, **kwargs):
        super(SecretQuestionForm, self).__init__(*args, **kwargs)
        self.fields["secret_username"].initial = username


class RadioFrequencyForm(forms.Form):
    frequency = forms.CharField(label=_lazy(u"Radio Frequency"), widget=forms.TextInput(attrs={'autocomplete':'off'}))





class TranslationForm(forms.Form):
    def __init__(self, datamanager, *args, **kwargs):
        super(TranslationForm, self).__init__(*args, **kwargs)

        _translatable_items_ids = datamanager.get_translatable_items().keys()
        _translatable_items_pretty_names = [datamanager.get_all_items()[item_name]["title"] for item_name in _translatable_items_ids]
        _translatable_items_choices = zip(_translatable_items_ids, _translatable_items_pretty_names)
        _translatable_items_choices.sort(key=lambda double: double[1])

        # WARNING - we always put ALL runic items, even before they have been sold at auction - it's OK !
        self.fields["target_item"] = forms.ChoiceField(label=_("Object"), choices=_translatable_items_choices)
        self.fields["transcription"] = forms.CharField(label=_("Transcription"), widget=forms.Textarea(attrs={'rows': '5', 'cols':'30'}))



class ScanningForm(forms.Form):
    def __init__(self, available_items, *args, **kwargs):
        super(ScanningForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...
        reference_items_choices = [("", _("< Use Description Instead >"))]
        reference_items_choices += [(name, value["title"]) for (name, value) in available_items.items()]

        self.fields["item_name"] = forms.ChoiceField(label=_("Reference Object"), choices=reference_items_choices, required=False)

        self.fields["description"] = forms.CharField(label=_("Or Description"), required=False,
                                                     widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}))





class ArmedInterventionForm(forms.Form):

    message = forms.CharField(label=_lazy("Message"),
                              widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}))

    def __init__(self, available_locations, *args, **kwargs):
        super(ArmedInterventionForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...
        available_locations_choices = [(name, name.capitalize()) for name in available_locations]
        self.fields["city_name"] = forms.ChoiceField(label=_("Location"), choices=available_locations_choices)



class TelecomInvestigationForm(forms.Form):

    def __init__(self, datamanager, user, *args, **kwargs):
        super(TelecomInvestigationForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...

        others = datamanager.get_other_character_usernames()
        others_choices = datamanager.build_select_choices_from_usernames(others)
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
        usernames_choices = datamanager.build_select_choices_from_usernames(usernames)
        self.fields['target_username'] = forms.ChoiceField(label=_("User"), choices=usernames_choices)


'''
class CharacterForm(forms.Form):

    def __init__(self, datamanager, *args, **kwargs):
        super(CharacterForm, self).__init__(*args, **kwargs)

        _usernames = datamanager.get_character_usernames()
        _usernames_choices = zip(_usernames, _usernames)
        _usernames_choices.sort()

        self.fields['target_username'] = forms.ChoiceField(label=_("User"), choices=_usernames_choices)
'''
