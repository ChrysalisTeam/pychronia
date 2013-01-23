# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from rpgweb.datamanager.abstract_form import AbstractGameForm




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
    secret_username = forms.CharField(label=_lazy("Username"), required=True, max_length=30, widget=forms.TextInput(attrs={'autocomplete':'off'}))
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


class MoneyTransferForm(forms.Form):

    def __init__(self, datamanager, user, *args, **kwargs):
        super(MoneyTransferForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...
        if user.is_master:
            _money_all_character_choices = [(datamanager.get_global_parameter("bank_name"), '<' + _("Bank") + '>')] + \
                                            datamanager.build_select_choices_from_usernames(datamanager.get_character_usernames())

            self.fields.insert(0, "sender_name", forms.ChoiceField(label=_("Sender"), choices=_money_all_character_choices))
            self.fields.insert(1, "recipient_name", forms.ChoiceField(label=_("Recipient"),
                               initial=_money_all_character_choices[min(1, len(_money_all_character_choices) - 1)][0], choices=_money_all_character_choices))
        else:
            others = datamanager.get_other_usernames(user.username)
            others_choices = datamanager.build_select_choices_from_usernames(others)
            self.fields.insert(0, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=others_choices))

    amount = forms.IntegerField(label=_("Amount"), widget=forms.TextInput(attrs={'size':'8', 'style':'text-align:center;'}),
                                initial=0, min_value=0, max_value=1000000)




class GemsTransferForm(forms.Form):

    def __init__(self, datamanager, user, gems_choices, *args, **kwargs):
        super(GemsTransferForm, self).__init__(*args, **kwargs)
        # dynamic fields here ...
        if user.is_master:
            _character_choices = datamanager.build_select_choices_from_usernames(datamanager.get_character_usernames())
            self.fields.insert(0, "sender_name", forms.ChoiceField(label=_("Sender"), choices=_character_choices))
            self.fields.insert(1, "recipient_name", forms.ChoiceField(label=_("Recipient"), initial=_character_choices[min(1, len(_character_choices) - 1)][0], choices=_character_choices))
        else:
            others = datamanager.get_other_usernames(user.username)
            others_choices = datamanager.build_select_choices_from_usernames(others)
            self.fields.insert(1, "recipient_name", forms.ChoiceField(label=_("Recipient"), choices=others_choices))

        self.fields.insert(2, "gems_choices", forms.MultipleChoiceField(required=False, label=_("Gems (use Ctrl key)"), choices=gems_choices))






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

        others = datamanager.get_other_usernames(user.username)
        others_choices = datamanager.build_select_choices_from_usernames(others)
        self.fields["official_name"] = forms.ChoiceField(label=_("Name"), choices=others_choices)


class DjinnContactForm(forms.Form):

    def __init__(self, available_djinns, *args, **kwargs):
        super(DjinnContactForm, self).__init__(*args, **kwargs)
        available_djinns_choices = zip(available_djinns, available_djinns)
        self.fields["djinn"] = forms.ChoiceField(label=_("Djinn"), choices=available_djinns_choices)


class MessageComposeForm(forms.Form):
    """
    A simple default form for private messages.
    """

    # origin = forms.CharField(required=False, widget=forms.HiddenInput) # the id of the message to which we replay, if any
    subject = forms.CharField(label=_lazy("Subject"), widget=forms.TextInput(attrs={'size':'35'}))
    body = forms.CharField(label=_lazy("Body"),
        widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}))
    attachment = forms.CharField(label=_lazy("Attachment"), required=False, widget=forms.TextInput(attrs={'size':'40', 'autocomplete':'off'}))


    def __init__(self, request, *args, **kwargs):
        super(MessageComposeForm, self).__init__(*args, **kwargs)

        sender = None
        recipient = None
        subject = None
        body = None
        attachment = None

        datamanager = request.datamanager
        _all_email_contacts = datamanager.get_user_contacts(datamanager.get_global_parameter("master_login"))
        # _all_email_choices = zip(_all_email_contacts, _all_email_contacts)
        _delay_values_minutes = [unicode(value) for value in [0, 2, 5, 10, 15, 30, 45, 60]]
        _delay_values_minutes_labels = [value + " minutes" for value in _delay_values_minutes]
        _delay_values_minutes_choices = zip(_delay_values_minutes, _delay_values_minutes_labels)

        user = request.datamanager.user
        parent_id = None
        recontact = None
        message_id = request.GET.get("message_id", "")
        if message_id:
            msg = request.datamanager.get_sent_message_by_id(message_id)
            recipient = msg["recipient_emails"]
            if hasattr(recipient, "__iter__"):
                recipient = recipient[0]  # FIXME, WELL BUGGY
            sender = msg["sender_email"]

            if request.datamanager.get_username_from_email(recipient) == user.username:
                # reply message
                parent_id = message_id
                if not user.is_master and recipient != datamanager.get_character_email(user.username):  # TODO FIXME WEIRD
                    user.add_error(_("Access to initial message forbidden"))
                else:

                    if user.is_master:  # else, the sender is imposed anyway...
                        sender = msg["recipient_emails"][0]

                    recipient = msg["sender_email"]
                    subject = _("Re: ") + msg["subject"]
                    attachment = msg["attachment"]

            if request.datamanager.get_username_from_email(sender) == user.username:
                # recontact message
                parent_id = message_id
                if not user.is_master and sender != datamanager.get_character_email(user.username):  # TODO FIXME WEIRD
                    user.add_error(_("Access to original message forbidden"))
                else:
                    sender = msg["sender_email"]
                    recipient = "; ".join(msg["recipient_emails"])
                    subject = _("Bis: ") + msg["subject"]
                    attachment = msg["attachment"]


        use_template = request.GET.get("use_template", "")
        if use_template:
            try:
                tpl = datamanager.get_message_template(use_template)
            except UsageError:
                user.add_error(_("Message template not found"))
            else:
                if not user.is_master:
                    user.add_error(_("Access to message template forbidden"))
                else:
                    sender = tpl["sender_email"]
                    recipient = "; ".join(tpl["recipient_emails"])
                    subject = tpl["subject"]
                    body = tpl["body"]
                    attachment = tpl["attachment"]


        self.fields.insert(0, "parent_id", forms.CharField(required=False, initial=parent_id, widget=forms.HiddenInput()))
        self.fields.insert(0, "use_template", forms.CharField(required=False, initial=use_template, widget=forms.HiddenInput()))

        if user.is_master:
            self.fields.insert(0, "sender", forms.EmailField(label=_("Sender"), initial=sender))
            self.fields["sender"].widget.attrs["selectBoxOptions"] = "|".join(_all_email_contacts)
            self.fields["sender"].widget.attrs["autocomplete"] = "off"

            self.fields.insert(1, "recipients", forms.CharField(label=_("Recipient"), initial=recipient))
            available_recipients = _all_email_contacts

            self.fields.insert(2, "delay_mn", forms.ChoiceField(label=_("Sending delay"), choices=_delay_values_minutes_choices, initial="0"))
            files_username = None
        else:
            self.fields.insert(0, "recipients", forms.CharField(label=_(u"Recipient"), initial=recipient))

            available_recipients = datamanager.get_user_contacts(user.username)  # should not be "anonymous", as it's used only in member areas !

            files_username = user.username

        recipients_str = "|".join(available_recipients)
        self.fields["recipients"].widget.attrs["selectBoxOptions"] = recipients_str
        self.fields["recipients"].widget.attrs["autocomplete"] = "off"

        self.fields["subject"].initial = subject
        self.fields["body"].initial = body
        self.fields["attachment"].initial = attachment

        try:
            files = datamanager.get_personal_files(files_username, absolute_urls=False)
            files_str = "|".join(files)
            self.fields["attachment"].widget.attrs["selectBoxOptions"] = files_str
            self.fields["attachment"].widget.attrs["autocomplete"] = "off"
        except:
            # we skip this selectBoxOptions attribute, so the input field won't turn into a combobox
            logging.error("Error while gathering %s's personal files" % files_username , exc_info=True)





class ArtefactForm(AbstractGameForm):
    def __init__(self, ability, *args, **kwargs):
        super(ArtefactForm, self).__init__(ability, *args, **kwargs)

        _user_items = ability.get_available_items_for_user(ability.user.username)
        _user_artefacts = {key: value for (key, value) in _user_items.items() if not value["is_gem"]}
        _user_artefacts_choices = [(key, value["title"]) for (key, value) in _user_artefacts.items()]
        _user_artefacts_choices.sort(key=lambda pair: pair[1])

        _user_artefacts_choices = [("", _("Select your artefact..."))] + _user_artefacts_choices  # ALWAYS non-empty choice field
        self.fields["item_name"] = forms.ChoiceField(label=_("Object"), choices=_user_artefacts_choices, required=True)

