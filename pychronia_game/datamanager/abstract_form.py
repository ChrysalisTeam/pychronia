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



class AbstractGameForm(forms.Form):
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

        super(AbstractGameForm, self).__init__(**kwargs)

        self.fields[self.__class__._ability_field_name] = forms.CharField(initial=self._get_dotted_class_name(), widget=forms.HiddenInput) # appended at the end
        self.target_url = ""  # by default we stay on the same page when submitting

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
        cleaned_data = super(AbstractGameForm, self).clean()

        for field in cleaned_data:
            if isinstance(self.cleaned_data[field], basestring):
                cleaned_data[field] = cleaned_data[field].strip()
        return cleaned_data

    def get_normalized_values(self):
        values = self.cleaned_data.copy()
        del values[self._ability_field_name]
        return values





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





