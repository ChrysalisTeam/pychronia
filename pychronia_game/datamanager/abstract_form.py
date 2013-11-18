# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django import forms
import json


from pychronia_game.common import *
from django.core.exceptions import ValidationError



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



class BaseAbstractGameForm(forms.Form):
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

    def clean(self):
        """
        We never need fields with leading/trailing spaces in that game, so we strip everything...
        """
        cleaned_data = super(BaseAbstractGameForm, self).clean()

        for field in cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                cleaned_data[field] = cleaned_data[field].strip()
        return cleaned_data

    def get_normalized_values(self):
        assert self.is_valid()
        values = self.cleaned_data.copy()
        del values[self._ability_field_name]
        return values





class GemPayementFormMixin(object):

    @staticmethod
    def _encode_gems(gems): # gems are TUPLES
        return [json.dumps([idx] + list(gem)) for idx, gem in enumerate(gems)] # add index to make all values different

    @staticmethod
    def _decode_gems(gems):
        return [tuple(json.loads(gem)[1:]) for gem in gems] # back to hashable TUPLES

    def _gem_display(self, gem):
        if gem[1]:
            return _("Gem of %(cost)d Kashes (%(origin)s)") % SDICT(cost=gem[0], origin=gem[1].replace("_", " "))
        else:
            return _("Gem of %d Kashes (unknown origin)") % gem[0]

    def __init__(self, datamanager, *args, **kwargs):

        # remove and analyze specific payment parameters (which could be missing)
        payment_by_gems = kwargs.pop("payment_by_gems", False)
        payment_by_money = kwargs.pop("payment_by_money", False)


        super(GemPayementFormMixin, self).__init__(datamanager, *args, **kwargs)


        if datamanager.is_character():

            _gems = datamanager.get_character_properties()["gems"]
            _gems_choices = zip(self._encode_gems(_gems), [self._gem_display(gem) for gem in _gems]) # gem is (value, origin) here

            if payment_by_money:
                if payment_by_gems and _gems_choices:
                    self.fields["pay_with_money"] = forms.BooleanField(label=_("Pay with money"), initial=False, required=False)
                else:
                    self.fields["pay_with_money"] = forms.BooleanField(initial=True, widget=forms.HiddenInput, required=True)

                assert "pay_with_money" in self.fields


            if payment_by_gems:

                if _gems_choices:
                    self.fields["gems_list"] = forms.MultipleChoiceField(required=False, label=_("Or pay with gems"), choices=_gems_choices) #, widget=forms.SelectMultiple(attrs={"class": "multichecklist"}))
                else:
                    self.fields["gems_list"] = forms.MultipleChoiceField(required=False, widget=forms.HiddenInput) # we could just

                assert "gems_list" in self.fields

        #print(">>>>>>>>> GemPayementFormMixin", self.__class__.__name__, self.fields.keys())


    def get_normalized_values(self):

        parameters = super(GemPayementFormMixin, self).get_normalized_values()

        #print(">>>>>>>>> get_normalized_values", self.__class__.__name__, parameters)

        if "gems_list" in parameters:
            try:
                parameters["use_gems"] = self._decode_gems(parameters["gems_list"])
                del parameters["gems_list"]
            except (TypeError, ValueError), e:
                self.logger.critical("Wrong data submitted - %r", parameters["gems_list"], exc_info=True) # FIXME LOGGER MISSING
                raise AbnormalUsageError("Wrong data submitted")

        if "pay_with_money" in parameters:
            if "use_gems" in parameters:
                # only if we have a choice between several means of payment
                if ((parameters["pay_with_money"] and parameters["use_gems"]) or
                   not (parameters["pay_with_money"] or parameters["use_gems"])):
                    raise NormalUsageError("You must choose between money and gems, for payment.")
            del parameters["pay_with_money"]

        return parameters




# REAL abstract base class for the game forms
# Adds both auto-recognition of form class, and additional fields like payment controls
AbstractGameForm = type("AbstractGameForm".encode("ascii"), # can't be unicode
                        (GemPayementFormMixin, BaseAbstractGameForm), {})
assert issubclass(AbstractGameForm, forms.Form)


class DataTableForm(AbstractGameForm):

    previous_identifier = forms.CharField(label=_lazy("Initial identifier"), widget=forms.HiddenInput(), required=False)
    identifier = forms.CharField(label=_lazy("Identifier"), required=True)

    BAD_ID_MSG = _lazy("Identifier must contain no space")

    def __init__(self, datamanager, initial=None, **kwargs):

        if initial:
            assert "previous_identifier" not in initial
            initial["previous_identifier"] = initial["identifier"]

        super(DataTableForm, self).__init__(datamanager, initial=initial, **kwargs)


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



