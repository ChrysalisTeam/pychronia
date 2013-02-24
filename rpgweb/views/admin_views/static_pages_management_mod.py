# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import register_view, AbstractGameView, AbstractGameForm
from django import forms

from django_select2.util import JSVar
from django_select2 import HeavySelect2MultipleChoiceField, Select2MultipleWidget
from django_select2.widgets import MultipleSelect2HiddenInput, Select2Mixin
from django.forms.widgets import Input


"""
SEPARATOR = "||"

class SpecialHiddenInput(Input):
    input_type = 'hidden'
    is_hidden = False
"""

class Select2TagsWidget(Select2Mixin, MultipleSelect2HiddenInput): ##SpecialHiddenInput): ###forms.HiddenInput): ###MultipleSelect2HiddenInput):

    def init_options(self):
        self.options.update({"separator": JSVar('django_select2.MULTISEPARATOR'),
                            "tokenSeparators": [",", ";", " "],
                            "tags": []}) # no tags proposed by default

    def set_choice_tags(self, tags):
        self.options["tags"] = tags

    '''
    def render(self, name, value, attrs=None):
        print(">>>>>>>>>", name, repr(value))
        if isinstance(value, (list, tuple)):
            value = SEPARATOR.join(value)
        return super(Select2SpecialWidget, self).render(name=name, value=value, attrs=attrs)

    def value_from_datadict(self, data, files, name):
        value = data.get(name, None)
        if value and isinstance(value, basestring):
            value = value.split(SEPARATOR)
        return value
    '''

class Select2TagsField(HeavySelect2MultipleChoiceField):
    widget = Select2TagsWidget

    def __init__(self, **kwargs):

        choice_tags = kwargs.pop("choice_tags", None) # done first

        if kwargs.get('widget', None) is None:
            # we override the nasty behaviour of HeavySelect2MultipleChoiceField mixins
            #who expect data_view to be sent to widget
            kwargs['widget'] = self.widget()

        super(Select2TagsField, self).__init__(**kwargs)

        if choice_tags:
            self.choice_tags = choice_tags # triggers property

    def coerce_value(self, value):
        """
        Coerces ``value`` to a Python data type.
        Sub-classes should override this if they do not want unicode values.
        """
        return super(Select2TagsField, self).coerce_value(value=value)

    def _get_choice_tags(self):
        return self._choice_tags

    def _set_choice_tags(self, value):
        # tags can be any iterable, but we call list() on it because
        # it will be consumed more than once.
        self._choice_tags = list(value)
        self.widget.set_choice_tags(value)

    choice_tags = property(_get_choice_tags, _set_choice_tags)



class StaticPageForm(AbstractGameForm):

    previous_identifier = forms.SlugField(label=_lazy("Initial identifier"), widget=forms.HiddenInput())
    identifier = forms.SlugField(label=_lazy("Identifier"))
    description = forms.CharField(label=_lazy("Hidden description"), widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}))
    content = forms.CharField(label=_lazy("Content"), widget=forms.Textarea(attrs={'rows': '8', 'cols':'35'}))

    categories = forms.CharField(label=_lazy("Categories"))
    keywords = forms.CharField(label=_lazy("Keywords"))


    test = Select2TagsField(label=_lazy("TESTING"), choice_tags=["kkk", "lll"])

    def __init__(self, datamanager, initial=None, **kwargs):
        
        if initial:
            initial["previous_identifier"] = initial["identifier"]
        
        super(StaticPageForm, self).__init__(datamanager, initial=initial, **kwargs)


    def ___clean(self):
        cleaned_data = super(StaticPageForm, self).clean()

        cleaned_data["categories"] = cleaned_data["categories"].split(SEPARATOR)
        cleaned_data["keywords"] = cleaned_data["keywords"].split(SEPARATOR)

        # Always return the full collection of cleaned data.
        return cleaned_data


'''
class MultipleTagField(forms.Field):

    def prepare_value(self, value):
        return value

    def to_python(self, value):
        return value
'''


@register_view
class StaticPagesManagement(AbstractGameView):

    NAME = "static_pages_management"

    GAME_FORMS = {"static_page_form": (StaticPageForm, "static_page_form")}
    ACTIONS = {}
    TEMPLATE = "administration/static_pages_management.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_data_table_instance(self):
        return self._datamanager.static_pages

    def get_template_vars(self, previous_form_data=None):

        form = StaticPageForm(self.datamanager, initial=None, data=dict(_ability_form="HHH", test=("aaa", "hhhh")))
        if form.is_valid():
            print ("@@@@@@@@@#", form.cleaned_data)
        #self._instantiate_form(new_form_name="static_page_form",
         #                                        hide_on_success=False,
         #                                         previous_form_data=None)
        return dict(form=form)
        '''
        if self.request.GET.get("new"):
            pass
        elif self.request.REQUEST.get("edited_item"): # can be given by GET or hidden POST field
            pass
        else:
            pass
        
            '''

    def static_page_form(self):
        return

