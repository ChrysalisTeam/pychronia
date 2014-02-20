# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from pychronia_game.common import *
from pychronia_game.datamanager import register_view, AbstractGameForm, AbstractDataTableManagement, DataTableForm
from pychronia_game.utilities.select2_extensions import Select2TagsField
from django import forms
from pychronia_game.datamanager.abstract_form import GAMEMASTER_HINTS_FIELD


class StaticPageForm(DataTableForm):

    categories = Select2TagsField(label=ugettext_lazy("Categories"), required=False)
    keywords = Select2TagsField(label=ugettext_lazy("Keywords"), required=False)

    content = forms.CharField(label=ugettext_lazy("Content"), widget=forms.Textarea(attrs={'rows': '8', 'cols':'40'}), required=True)

    gamemaster_hints = GAMEMASTER_HINTS_FIELD


### TODO - DEAL WITH IMMUTABLES ???


@register_view
class StaticPagesManagement(AbstractDataTableManagement):

    TITLE = ugettext_lazy("Static Pages Editing")
    NAME = "static_pages_management"

    GAME_ACTIONS = dict(submit_item=dict(title=ugettext_lazy("Submit a static page"),
                                                          form_class=StaticPageForm,
                                                          callback="submit_item"),
                        delete_item=dict(title=ugettext_lazy("Delete a static page"),
                                                          form_class=None,
                                                          callback="delete_item"))

    TEMPLATE = "administration/static_pages_management.html"


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
        #self._instantiate_game_form(new_action_name="static_page_form",
         #                                        hide_on_success=False,
         #                                         previous_form_data=None)
        return dict(form=form)
'''
