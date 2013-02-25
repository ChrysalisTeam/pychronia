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

    GAME_FORMS = {"submit_item": (StaticPageForm, "submit_item")}
    ACTIONS = {"delete_item": "delete_item"}
    TEMPLATE = "administration/static_pages_management.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True

    DATA_TABLE_FORM = StaticPageForm

    def get_data_table_instance(self):
        return self.datamanager.static_pages

    def instantiate_table_form(self, table_item=None, previous_form_data=None, idx=None):
             
        assert table_item or previous_form_data or (idx == 0)
 
        initial_data = None
        if table_item:
            table_key, table_value = table_item
            initial_data = dict(previous_identifier=table_key,
                                identifier=table_key)
            initial_data.update(table_value)
        
        form_options = dict(prefix=None, # NO prefix, all forms must submit the same data names
                            auto_id="id_%s_%%s" % slugify(idx), # needed by select2 to wrap fields
                            label_suffix=":<br/>") # no id, since there will be numerous such forms

        res = self._instantiate_form("submit_item", 
                                     previous_form_data=previous_form_data,
                                     initial_data=initial_data,
                                     **form_options)
        
        return res

    def submit_item(self, previous_identifier, identifier, categories, keywords, description, content):
        table = self.get_data_table_instance()
        
        # insertion and update are the same
        table["identifier"] = dict(categories=categories,
                                   keywords=keywords,
                                   description=description,
                                   content=content)
        
        # cleanup in case of renaming
        if previous_identifier and previous_identifier != identifier:
            if previous_identifier in table:
                del table["previous_identifier"]
            else:
                self.logger.critical("Wrong previous_identifier submitted in StaticPagesManagement: %r", previous_identifier)

        return _("Entry %r properly submitted") % identifier


    def delete_item(self, deleted_id):
        table = self.get_data_table_instance()
        
        if not deleted_id or deleted_id not in table:
            raise AbnormalUsageError(_("Entry %r not found") % deleted_id)
        del table[deleted_id]
        return _("Entry %r properly deleted") % deleted_id

        
    def get_template_vars(self, previous_form_data=None):

        table = self.get_data_table_instance()
        table_items = table.get_all_data(as_sorted_list=True)

        submitted_identifier = None
        if previous_form_data and not previous_form_data.form_successful:
            submitted_identifier = self.request.POST.get("identifier")


        forms = [(None, self.instantiate_table_form(idx=0))] # form for new table entry
        
        for (idx, (table_key, table_value)) in enumerate(table_items, start=1):
            
            transfered_previous_form_data = previous_form_data if (submitted_identifier and submitted_identifier == table_key) else None
            transfered_table_item = (table_key, table_value) if not transfered_previous_form_data else None # slight optimization
            
            new_form = self.instantiate_table_form(table_item=transfered_table_item, previous_form_data=transfered_previous_form_data, idx=idx)
            forms.append((table_key, new_form))

        return dict(page_title=_("TO DEFINE FIXME"),
                    forms=forms)













    def _________process_html_post_data(self):
        assert not self.request.is_ajax()
        assert self.request.method == "POST"
        res = dict(result=False, # default
                   form_data=None)
        
        POST = self.request.POST
        
        table = self.get_data_table_instance()
        
        if "delete" in POST:
            with action_failure_handler(self.request, success_message): # only for unhandled exceptions
                deleted_id = POST.get("deleted_id", None)

                
        else:
            
            with action_failure_handler(self.request, success_message=_("Entry %r properly submitted") % deleted_id):
            
                form = self.instantiate_table_form(post_data=self.request.POST)
                if form.is_valid():
                    data = form.clean_data
                
                # don't forget to remove old entry, if renaming occurred
            
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

