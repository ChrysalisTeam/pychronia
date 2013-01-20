# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from django import forms


class AbstractGameForm(forms.Form):
    """
    Base class for forms, able to recognize their data, by adding some hidden fields.
    """

    _ability_field_name = "_ability_form"

    def __init__(self, datamanager, *args, **kwargs):
        """
        *datamanager* may also be an ability, since it proxies datamanager methods too.
        """
        super(AbstractGameForm, self).__init__(*args, **kwargs)

        self.fields.insert(0, self.__class__._ability_field_name, forms.CharField(initial=self._get_dotted_class_name(),
                                                                                  widget=forms.HiddenInput))
        self.target_url = ""  # by default we stay on the same page when submitting


    @classmethod
    def _get_dotted_class_name(cls):
        return "%s.%s" % (cls.__module__, cls.__name__)

    @classmethod
    def matches(cls, post_data):
        if post_data.get(cls._ability_field_name, None) == cls._get_dotted_class_name():
            return True
        return False

    def get_normalized_values(self):
        values = self.cleaned_data.copy()
        del values[self._ability_field_name]
        return values


