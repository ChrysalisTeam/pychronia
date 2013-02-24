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

    previous_identifier = forms.SlugField(label=_lazy("Initial identifier"), widget=forms.HiddenInput(), required=False)
    identifier = forms.SlugField(label=_lazy("Identifier"))

    categories = Select2TagsField(label=_lazy("Categories"))
    keywords = Select2TagsField(label=_lazy("Keywords"))

    description = forms.CharField(label=_lazy("Hidden description"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}))
    content = forms.CharField(label=_lazy("Content"), widget=forms.Textarea(attrs={'rows': '8', 'cols':'40'}))

    ###test = Select2TagsField(label=_lazy("TESTING"), choice_tags=["kkk", "lll"])


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

    GAME_FORMS = {}
    ACTIONS = {}
    TEMPLATE = "administration/static_pages_management.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True

    DATA_TABLE_FORM = StaticPageForm

    def get_data_table_instance(self):
        return self.datamanager.static_pages

    def instantiate_table_form(self, table_item=None, post_data=None, idx=None):
        assert table_item or post_data or (idx == 0)

        initial_data = None
        if table_item:
            table_key, table_value = table_item
            initial_data = dict(previous_identifier=table_key,
                           identifier=table_key)
            initial_data.update(table_value)

        res = self.DATA_TABLE_FORM(self.datamanager,
                                    data=post_data,
                                    initial=initial_data,
                                    prefix=None, # NO prefix, all forms must submit the same data names
                                    auto_id="id_%s_%%s" % idx, # needed by select2 to wrap fields
                                    label_suffix=":<br/>") # no id, since there will be numerous such forms
        return res



    def get_template_vars(self, previous_form_data=None):

        table = self.get_data_table_instance()
        table_items = table.get_all_data(as_sorted_list=True)

        #print("@@@kkk", table_items)
        forms = [(None, self.instantiate_table_form(idx=0))] # form for new table entry
        forms += [(table_item[0], self.instantiate_table_form(table_item=table_item, idx=idx)) for (idx, table_item) in enumerate(table_items, start=1)]

        return dict(page_title=_("TO DEFINE FIXME"),
                    forms=forms)


    def _process_html_post_data(self):
        assert not self.request.is_ajax()
        assert self.request.method == "POST"
        res = dict(result=None,
                   form_data=None)
        
        form = self.instantiate_table_form(post_data=self.request.POST)
        if form.is_valid():
            pass # TODO  
        
            res["result"] = True

        return res


    def _____________process_html_request(self):


        template_vars = self.get_template_vars()
        assert isinstance(template_vars, collections.Mapping), template_vars

        response = render(self.request,
                          self.TEMPLATE,
                          template_vars)
        return response



    def ____________get_template_vars(self, previous_form_data=None):

        form = StaticPageForm(self.datamanager, initial=None, data=dict(_ability_form="HHH", test=("aaa", "hhhh")))
        if form.is_valid():
            print ("@@@@@@@@@#", form.cleaned_data)
        #self._instantiate_form(new_form_name="static_page_form",
         #                                        hide_on_success=False,
         #                                         previous_form_data=None)
        return dict(form=form)

