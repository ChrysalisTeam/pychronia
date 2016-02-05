# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django import forms
import json


from pychronia_game.common import *
from django import forms
from django.core.exceptions import ValidationError



GAMEMASTER_HINTS_FIELD = lambda: forms.CharField(label=ugettext_lazy("Hints for Game Master"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=False)



class UninstantiableFormError(Exception):
    """
    Exception to be raised by a form constructor when 
    the instance would be meaningless (eg. no data to choose from).
    """
    pass


def form_field_jsonify(value):
    """Value must be ASCII."""
    res = json.dumps(value, indent=None)
    assert "\n" not in res # must be compact form
    return res
def form_field_unjsonify(value):
    res = json.loads(value)
    return res



def autostrip_form_charfields(cls):
    """
    Marks all CharField entries of that form class as "auto-stripping", BEFORE validation.
    
    Does NOT work with dynamically created fields though.
    """
    fields = [(key, value) for key, value in cls.base_fields.iteritems() if isinstance(value, forms.CharField)]
    for field_name, field_object in fields:
        def get_clean_func(original_clean):
            return lambda value: original_clean(value and value.strip())
        clean_func = get_clean_func(getattr(field_object, 'clean'))
        setattr(field_object, 'clean', clean_func)  # we set it on FIELD, not FORM
    return cls


class SimpleForm(forms.Form):
    """
    Simple form class with cosmetic tweaks and string stripping.
    """
    required_css_class = "required"

    def clean(self):
        """
        We never need fields with leading/trailing spaces in that game, so we strip everything...
        """
        cleaned_data = super(forms.Form, self).clean()

        for field in cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                # note that Field "required=True" constraints might be already passed here, use autostrip() instead to prevent "space-only" inputs
                cleaned_data[field] = cleaned_data[field].strip()

        return cleaned_data



class BaseAbstractGameForm(SimpleForm):
    """
    Base class for forms, able to recognize their data, by adding some hidden fields.
    """

    _ability_field_name = "_ability_form"

    def __init__(self, datamanager, **kwargs):
        """
        *datamanager* may also be an ability, since it proxies datamanager methods too.
        """

        kwargs.setdefault("prefix", None) # NO prefix, all forms must submit the same data names
        kwargs.setdefault("auto_id", "id_default_%s") # in multi-form case, this one will be used for unique "bound" form
        kwargs.setdefault("label_suffix", ":") # no <br/>, not always a better presentation

        super(BaseAbstractGameForm, self).__init__(**kwargs)

        self.fields[self.__class__._ability_field_name] = forms.CharField(initial=self._get_dotted_class_name(), widget=forms.HiddenInput) # appended at the end
        self.target_url = ""  # by default we stay on the same page when submitting

        self._datamanager = datamanager
        self.logger = datamanager.logger # handy

    @classmethod
    def _get_dotted_class_name(cls):
        return "%s.%s" % (cls.__module__, cls.__name__)

    @classmethod
    def matches(cls, post_data):
        if post_data.get(cls._ability_field_name, None) == cls._get_dotted_class_name():
            return True
        return False

    def get_normalized_values(self):
        assert self.is_valid()
        values = self.cleaned_data.copy()
        del values[self._ability_field_name]
        return values




class GemHandlingFormUtils(object):

    @staticmethod
    def _encode_gems(gems): # gems are TUPLES
        return [json.dumps([idx] + list(gem)) for idx, gem in enumerate(gems)] # add index to make all values different

    @staticmethod
    def _decode_gems(gems):
        return [tuple(json.loads(gem)[1:]) for gem in gems] # back to hashable TUPLES

    def _gem_display(self, gem):
        if gem[1]:
            return _("Gem of %(cost)d¤ (%(origin)s)") % SDICT(cost=gem[0], origin=gem[1].replace("_", " "))
        else:
            return _("Gem of %d¤ (unknown origin)") % gem[0]



class GemPayementFormMixin(GemHandlingFormUtils):

    def __init__(self, datamanager, *args, **kwargs):

        # remove and analyze specific payment parameters (which could be missing)
        payment_by_gems = kwargs.pop("payment_by_gems", False)
        payment_by_money = kwargs.pop("payment_by_money", False)


        super(GemPayementFormMixin, self).__init__(datamanager, *args, **kwargs)


        if datamanager.is_character():

            _gems = datamanager.get_character_properties()["gems"]
            _gems_choices = zip(self._encode_gems(_gems), [self._gem_display(gem) for gem in _gems]) # gem is (value, origin) here
            _gems_choices.sort(key=lambda x: x[1]) # sort by labels

            if payment_by_money:
                if payment_by_gems and _gems_choices:
                    self.fields["pay_with_money"] = forms.BooleanField(label=_("Pay with money"), initial=False, required=False)
                else:
                    self.fields["pay_with_money"] = forms.BooleanField(initial=True, widget=forms.HiddenInput, required=True)

                assert "pay_with_money" in self.fields


            if payment_by_gems:

                if _gems_choices:
                    self.fields["gems_list"] = forms.MultipleChoiceField(required=False, 
                                                                         label=_("Or pay with gems"), 
                                                                         choices=_gems_choices,
                                                                         widget=forms.SelectMultiple(attrs={"class": "multichecklist"}))
                else:
                    self.fields["gems_list"] = forms.MultipleChoiceField(required=False, widget=forms.HiddenInput) # we could just

                assert "gems_list" in self.fields


    def get_normalized_values(self):

        parameters = super(GemPayementFormMixin, self).get_normalized_values()

        #print(">>>>>>>>> get_normalized_values", self.__class__.__name__, parameters)

        if "gems_list" in parameters:
            try:
                parameters["use_gems"] = self._decode_gems(parameters["gems_list"])
                del parameters["gems_list"]
            except (TypeError, ValueError), e:
                self.logger.critical("Wrong data submitted - %r", parameters["gems_list"], exc_info=True)
                raise AbnormalUsageError(_("Wrong data submitted"))

        if "pay_with_money" in parameters:
            if "use_gems" in parameters:
                # only if we have a choice between several means of payment
                if ((parameters["pay_with_money"] and parameters["use_gems"]) or
                   not (parameters["pay_with_money"] or parameters["use_gems"])):
                    raise NormalUsageError(_("You must choose between money and gems, for payment."))
            del parameters["pay_with_money"]

        return parameters




# REAL abstract base class for the game forms
# Adds both auto-recognition of form class, and additional fields like payment controls
AbstractGameForm = type("AbstractGameForm".encode("ascii"), # can't be unicode
                        (GemPayementFormMixin, BaseAbstractGameForm), {})
assert issubclass(AbstractGameForm, SimpleForm)
assert issubclass(AbstractGameForm, forms.Form)


class DataTableForm(AbstractGameForm):

    previous_identifier = forms.CharField(label=ugettext_lazy("Initial identifier"), widget=forms.HiddenInput(), required=False)
    identifier = forms.CharField(label=ugettext_lazy("Identifier"), required=True)

    BAD_ID_MSG = ugettext_lazy("Identifier must contain no space")

    def __init__(self, datamanager, initial=None, undeletable_identifiers=None, **kwargs):

        if initial:
            assert "previous_identifier" not in initial
            initial["previous_identifier"] = initial["identifier"]
        
        super(DataTableForm, self).__init__(datamanager, initial=initial, **kwargs)
        
        if initial and undeletable_identifiers:
            assert isinstance(undeletable_identifiers, set), undeletable_identifiers
            if initial["identifier"] in undeletable_identifiers:
                # not very secure, but DataTable protections will take care of hacking attempts
                self.fields['identifier'].widget.attrs['readonly'] = True

        


    def clean_previous_identifier(self):
        data = self.cleaned_data['previous_identifier']
        if " " in data:
            raise ValidationError(self.BAD_ID_MSG)
        return data

    def clean_identifier(self):
        data = self.cleaned_data['identifier']
        if " " in data:
            raise ValidationError(self.BAD_ID_MSG)
        return data



