# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

from rpgweb.common import *

from .abstract_form import AbstractGameForm
from .abstract_game_view import AbstractGameView


class AbstractDataTableManagement(AbstractGameView):

    ACCESS = UserAccess.master
    PERMISSIONS = []
    ALWAYS_AVAILABLE = True


    def get_data_table_instance(self):
        raise NotImplementedError("get_data_table_instance")


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


    def submit_item(self, previous_identifier, identifier, **data): ####, previous_identifier, identifier, categories, keywords, description, content):

        del data[AbstractGameForm._ability_field_name] # all other form fields should be OK for data table
        table = self.get_data_table_instance()

        # insertion and update are the same
        table[identifier] = data
        '''dict(categories=categories,
                                   keywords=keywords,
                                   description=description,
                                   content=content)'''

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

