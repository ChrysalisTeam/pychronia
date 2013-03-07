# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *
from rpgweb.datamanager import register_view, AbstractGameView, AbstractGameForm
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
class StaticPagesManagement(AbstractGameView):

    NAME = "static_pages_management"

    GAME_FORMS = {"submit_item": (StaticPageForm, "submit_item")}
    ACTIONS = {"delete_item": "delete_item"}
    TEMPLATE = "administration/static_pages_management.html"

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_data_table_instance(self):
        return self.datamanager.static_pages


    def instantiate_table_form(self, table_item=None, previous_form_data=None, idx=None):

        assert table_item or previous_form_data or (idx == 0)

        initial_data = None
        if table_item:
            table_key, table_value = table_item
            initial_data = dict(identifier=table_key)
            initial_data.update(table_value)

        res = self._instantiate_form(new_form_name="submit_item",
                                     previous_form_data=previous_form_data,
                                     initial_data=initial_data,
                                     auto_id="id_%s_%%s" % slugify(idx)) # needed by select2 to wrap fields

        return res


    def submit_item(self, previous_identifier, identifier, categories, keywords, description, content):
        table = self.get_data_table_instance()

        # insertion and update are the same
        table[identifier] = dict(categories=categories,
                                   keywords=keywords,
                                   description=description,
                                   content=content)

        # cleanup in case of renaming
        if previous_identifier and previous_identifier != identifier:
            if previous_identifier in table:
                del table[previous_identifier]
            else:
                self.logger.critical("Wrong previous_identifier submitted in StaticPagesManagement: %r", previous_identifier)

        return _("Entry %r properly submitted") % identifier


    def delete_item(self, deleted_item):
        table = self.get_data_table_instance()

        if not deleted_item or deleted_item not in table:
            raise AbnormalUsageError(_("Entry %r not found") % deleted_item)
        del table[deleted_item]
        return _("Entry %r properly deleted") % deleted_item


    def get_template_vars(self, previous_form_data=None):

        table = self.get_data_table_instance()
        table_items = table.get_all_data(as_sorted_list=True)

        concerned_identifier = None
        if previous_form_data and not previous_form_data.form_successful:
            concerned_identifier = self.request.POST.get("previous_identifier", "") # empty string if it was a new item


        forms = [(None, self.instantiate_table_form(idx=0, previous_form_data=(previous_form_data if concerned_identifier == "" else None)))] # form for new table entry

        for (idx, (table_key, table_value)) in enumerate(table_items, start=1):

            transfered_previous_form_data = previous_form_data if (concerned_identifier and concerned_identifier == table_key) else None
            transfered_table_item = (table_key, table_value) if not transfered_previous_form_data else None # slight optimization

            new_form = self.instantiate_table_form(table_item=transfered_table_item, previous_form_data=transfered_previous_form_data, idx=idx)
            forms.append((table_key, new_form))

        return dict(page_title=_("TO DEFINE FIXME"),
                    forms=forms)











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
