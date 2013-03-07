# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import register_view, AbstractGameForm, AbstractDataTableManagement
from rpgweb.utilities.select2_extensions import Select2TagsField
from django import forms


class StaticPageForm(AbstractGameForm):

    previous_identifier = forms.SlugField(label=_lazy("Initial identifier"), widget=forms.HiddenInput(), required=False)
    identifier = forms.SlugField(label=_lazy("Identifier"), required=True)

    categories = Select2TagsField(label=_lazy("Categories"), required=False)
    keywords = Select2TagsField(label=_lazy("Keywords"), required=False)

    description = forms.CharField(label=_lazy("Hidden description"), widget=forms.Textarea(attrs={'rows': '2', 'cols':'40'}), required=False)
    content = forms.CharField(label=_lazy("Content"), widget=forms.Textarea(attrs={'rows': '8', 'cols':'40'}), required=True)

    ###test = Select2TagsField(label=_lazy("TESTING"), choice_tags=["kkk", "lll"])


    def __init__(self, datamanager, initial=None, **kwargs):

        if initial:
            assert "previous_identifier" not in initial
            initial["previous_identifier"] = initial["identifier"]

        super(StaticPageForm, self).__init__(datamanager, initial=initial, **kwargs)





@register_view
class StaticPagesManagement(AbstractDataTableManagement):

    NAME = "static_pages_management"

    GAME_FORMS = {"submit_item": (StaticPageForm, "submit_item")}
    ACTIONS = {"delete_item": "delete_item"}
    TEMPLATE = "administration/static_pages_management.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_data_table_instance(self):
        return self.datamanager.static_pages










''' USELESS

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
'''
